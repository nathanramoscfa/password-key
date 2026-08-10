"""Zero-dependency cross-platform clipboard access.

Third-party clipboard packages are an avoidable supply-chain risk for a
tool whose entire job is handling secrets, so this module talks to the
platform directly:

- **Windows** — the Win32 clipboard API via :mod:`ctypes`. (Not
  ``clip.exe``, which appends a trailing newline — invisible, and fatal
  in a pasted password.)
- **macOS** — ``pbcopy`` / ``pbpaste``.
- **Linux / BSD** — ``wl-copy`` (Wayland), ``xclip``, or ``xsel``,
  whichever exists.

Every function degrades gracefully: if no clipboard is reachable
(headless box, SSH session, missing utility), ``copy`` returns
``False`` and the caller decides what to do — it never raises.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

__all__ = ["clear", "copy", "read"]

_SUBPROCESS_TIMEOUT = 5  # seconds; a clipboard helper should be instant


# ---------------------------------------------------------------------------
# Windows (ctypes, no external process)
# ---------------------------------------------------------------------------


def _win_copy(text: str) -> bool:
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    # SetClipboardData returns a HANDLE. Without an explicit restype,
    # ctypes truncates the 64-bit return to a 32-bit int; a valid handle
    # whose low 32 bits are zero would then read as failure, and the
    # GlobalFree below would free memory the clipboard already owns.
    user32.SetClipboardData.restype = wintypes.HANDLE

    if not _win_open_clipboard(user32):
        return False
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(locked, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def _win_read() -> str | None:
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.GetClipboardData.restype = wintypes.HANDLE

    if not _win_open_clipboard(user32):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""  # clipboard is empty or holds non-text data
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return None
        try:
            return ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _win_open_clipboard(user32, attempts: int = 5) -> bool:
    """Open the clipboard, retrying briefly if another app holds it."""
    import time

    for i in range(attempts):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.01 * (i + 1))
    return False


# ---------------------------------------------------------------------------
# macOS / Linux (external helper processes)
# ---------------------------------------------------------------------------


def _copy_commands() -> list[list[str]]:
    if sys.platform == "darwin":
        return [["pbcopy"]]
    return [
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]


def _read_commands() -> list[list[str]]:
    if sys.platform == "darwin":
        return [["pbpaste"]]
    return [
        ["wl-paste", "--no-newline"],
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
    ]


def _run_helper(cmd: list[str], text: str | None = None) -> str | None:
    """Run a clipboard helper. Returns stdout, or None on any failure."""
    if shutil.which(cmd[0]) is None:
        return None
    try:
        result = subprocess.run(
            cmd,
            input=text.encode() if text is not None else None,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode(errors="replace")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def copy(text: str) -> bool:
    """Place ``text`` on the system clipboard. Returns True on success."""
    if sys.platform == "win32":
        try:
            return _win_copy(text)
        except Exception:
            return False
    for cmd in _copy_commands():
        if _run_helper(cmd, text=text) is not None:
            return True
    return False


def read() -> str | None:
    """Return the clipboard's text, or None if it cannot be read."""
    if sys.platform == "win32":
        try:
            return _win_read()
        except Exception:
            return None
    for cmd in _read_commands():
        result = _run_helper(cmd)
        if result is not None:
            return result
    return None


def clear(expected: str | None = None) -> bool:
    """Clear the clipboard.

    If ``expected`` is given and the clipboard can be read, it is only
    cleared while it still holds that value — so a password copied
    earlier is wiped, but something the user copied in the meantime is
    left alone. If the clipboard cannot be read, it is cleared
    unconditionally (wiping the secret matters more).
    """
    if expected is not None:
        current = read()
        if current is not None and current != expected:
            return False
    return copy("")
