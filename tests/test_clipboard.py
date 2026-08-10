"""Tests for password_key.clipboard.

The real system clipboard is exercised only when one is actually
available (skipped on headless CI runners); the guard logic is tested
with monkeypatching everywhere.
"""

import ctypes

import pytest

from password_key import clipboard


def _clipboard_works() -> bool:
    return clipboard.copy("password-key-probe")


requires_clipboard = pytest.mark.skipif(
    not _clipboard_works(), reason="no system clipboard available"
)


@requires_clipboard
class TestRealClipboard:
    def test_round_trip(self):
        assert clipboard.copy("secret-abc123") is True
        assert clipboard.read() == "secret-abc123"

    def test_round_trip_preserves_exact_value(self):
        # No trailing newline may ever be appended (the clip.exe bug).
        value = "x7~Kd-2.fQ_9"
        clipboard.copy(value)
        assert clipboard.read() == value

    def test_clear_when_value_matches(self):
        clipboard.copy("to-be-cleared")
        assert clipboard.clear(expected="to-be-cleared") is True
        assert clipboard.read() in ("", None)

    def test_clear_skipped_when_value_changed(self):
        clipboard.copy("user-copied-this-later")
        assert clipboard.clear(expected="the-old-password") is False
        assert clipboard.read() == "user-copied-this-later"

    def test_unconditional_clear(self):
        clipboard.copy("anything")
        assert clipboard.clear() is True


class TestGracefulDegradation:
    def test_copy_failure_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            clipboard, "_win_copy", lambda text: (_ for _ in ()).throw(OSError)
        )
        monkeypatch.setattr(clipboard, "_copy_commands", list)
        monkeypatch.setattr(clipboard.sys, "platform", "linux")
        assert clipboard.copy("x") is False

    def test_read_failure_returns_none(self, monkeypatch):
        monkeypatch.setattr(clipboard, "_read_commands", list)
        monkeypatch.setattr(clipboard.sys, "platform", "linux")
        assert clipboard.read() is None

    def test_clear_clears_unconditionally_when_unreadable(self, monkeypatch):
        # If the clipboard cannot be read, wiping the secret wins.
        calls = []
        monkeypatch.setattr(clipboard, "read", lambda: None)
        monkeypatch.setattr(clipboard, "copy", lambda text: calls.append(text) or True)
        assert clipboard.clear(expected="secret") is True
        assert calls == [""]

    def test_missing_helper_binary(self, monkeypatch):
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
        assert clipboard._run_helper(["definitely-not-a-real-binary"]) is None


class _FakeWinFunc:
    """A Win32 function stub that mimics ctypes return-value semantics.

    ctypes converts every foreign function's return value through its
    ``restype``, which defaults to a 32-bit ``c_int``. Reproducing that
    conversion here means these tests fail for exactly the bug class the
    production code must guard against: a 64-bit HANDLE truncated to 32
    bits because no restype was declared.
    """

    def __init__(self, impl):
        self._impl = impl
        self.restype = ctypes.c_int  # the ctypes default
        self.argtypes = None
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        raw = self._impl(*args) or 0
        return self.restype(raw).value


class _Namespace:
    pass


# A handle value whose low 32 bits are all zero: valid and non-NULL as a
# 64-bit HANDLE, but exactly 0 after truncation to a 32-bit int.
_HIGH_HANDLE = 0x1_0000_0000


@pytest.fixture
def fake_windll(monkeypatch):
    """Replace ctypes.windll with an instrumented Win32 clipboard fake."""
    buf = ctypes.create_string_buffer(4096)

    kernel32 = _Namespace()
    kernel32.GlobalAlloc = _FakeWinFunc(lambda flags, size: _HIGH_HANDLE)
    kernel32.GlobalLock = _FakeWinFunc(lambda h: ctypes.addressof(buf))
    kernel32.GlobalUnlock = _FakeWinFunc(lambda h: 1)
    kernel32.GlobalFree = _FakeWinFunc(lambda h: 0)

    user32 = _Namespace()
    user32.OpenClipboard = _FakeWinFunc(lambda hwnd: 1)
    user32.EmptyClipboard = _FakeWinFunc(lambda: 1)
    user32.SetClipboardData = _FakeWinFunc(lambda fmt, h: h)
    user32.CloseClipboard = _FakeWinFunc(lambda: 1)

    windll = _Namespace()
    windll.kernel32 = kernel32
    windll.user32 = user32
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)

    windll.buffer = buf
    return windll


class TestWin32Copy:
    """Protocol-level tests for _win_copy against an instrumented fake.

    These run on every platform: the Win32 surface is faked, but the
    fake reproduces ctypes' restype conversion, so declaring the wrong
    (or no) restype fails here the same way it would on real Windows.
    """

    def test_success_with_64bit_handle(self, fake_windll):
        # SetClipboardData hands back a valid handle whose low 32 bits
        # are zero. Without an explicit HANDLE restype this reads as
        # failure, and the recovery path frees memory the clipboard now
        # owns - a use-after-free planted in every subsequent paste.
        assert clipboard._win_copy("secret") is True
        assert fake_windll.kernel32.GlobalFree.calls == []
        assert len(fake_windll.user32.CloseClipboard.calls) == 1

    def test_written_data_is_utf16le_with_terminator(self, fake_windll):
        clipboard._win_copy("x7~Kd-2.fQ_9")
        expected = "x7~Kd-2.fQ_9".encode("utf-16-le") + b"\x00\x00"
        assert fake_windll.buffer.raw[: len(expected)] == expected

    def test_handle_freed_when_set_clipboard_data_fails(self, fake_windll):
        fake_windll.user32.SetClipboardData._impl = lambda fmt, h: 0
        assert clipboard._win_copy("secret") is False
        assert fake_windll.kernel32.GlobalFree.calls == [(_HIGH_HANDLE,)]
        assert len(fake_windll.user32.CloseClipboard.calls) == 1

    def test_handle_freed_when_lock_fails(self, fake_windll):
        fake_windll.kernel32.GlobalLock._impl = lambda h: 0
        assert clipboard._win_copy("secret") is False
        assert fake_windll.kernel32.GlobalFree.calls == [(_HIGH_HANDLE,)]
        assert len(fake_windll.user32.CloseClipboard.calls) == 1

    def test_clipboard_closed_even_when_alloc_fails(self, fake_windll):
        fake_windll.kernel32.GlobalAlloc._impl = lambda flags, size: 0
        assert clipboard._win_copy("secret") is False
        assert len(fake_windll.user32.CloseClipboard.calls) == 1
