"""Tests for password_key.clipboard.

The real system clipboard is exercised only when one is actually
available (skipped on headless CI runners); the guard logic is tested
with monkeypatching everywhere.
"""

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
