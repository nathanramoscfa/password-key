"""Static checks on the double-click browser launchers.

Each launcher opens ``web/index.html`` from the folder it sits in and does
nothing else, so nothing listens on a port and nothing touches the network.
They are run by double-click, which makes a broken one the failure its user
is least equipped to diagnose, and no CI job double-clicks anything. These
are the assertions that can be made without doing so.

The file mode and the line endings are read from the git index, never from
the working tree. Windows has no executable bit, ``core.autocrlf`` can
rewrite a checkout, and an unpacked sdist has neither guarantee, so the
index is the only place the committed value can be seen on every platform.
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BAT = "New Password in Browser.bat"
COMMAND = "New Password in Browser.command"

# The exact command, not just the path. An empty title is what stops `start`
# from reading the quoted path as a window title, and both paths are relative
# to the launcher because a double-click does not promise a working directory.
OPENERS = {
    BAT: 'start "" "%~dp0web\\index.html"',
    COMMAND: 'exec open "$(dirname "$0")/web/index.html"',
}

# Compared against lowercased text. The comment in each launcher says
# "No server and no network", so these are commands and addresses rather
# than those bare words.
FORBIDDEN = (
    "http.server",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "http://",
    "https://",
    "curl",
    "wget",
    "invoke-webrequest",
    "invoke-restmethod",
    "bitsadmin",
    "certutil",
)

requires_git_checkout = pytest.mark.skipif(
    not (ROOT / ".git").exists(), reason="not a git checkout, e.g. an unpacked sdist"
)


def _git_ls_files(*args, path):
    """Return the index entry for ``path``, failing if it is not tracked."""
    out = subprocess.run(
        ["git", "ls-files", *args, "--", path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert out, f"{path} is not tracked by git"
    return out


@pytest.mark.parametrize("launcher", OPENERS)
class TestLauncher:
    def test_exists(self, launcher):
        assert (ROOT / launcher).is_file()

    def test_opens_the_page_beside_itself(self, launcher):
        assert OPENERS[launcher] in (ROOT / launcher).read_text(encoding="utf-8")

    def test_starts_no_server_and_makes_no_network_call(self, launcher):
        text = (ROOT / launcher).read_text(encoding="utf-8").lower()
        assert [word for word in FORBIDDEN if word in text] == []


def test_the_page_they_open_exists():
    assert (ROOT / "web" / "index.html").is_file()


def test_command_starts_with_a_shebang():
    text = (ROOT / COMMAND).read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh")


@requires_git_checkout
def test_command_is_tracked_as_executable():
    """Without the bit, Terminal refuses to run it after a clone or a ZIP."""
    assert _git_ls_files("-s", path=COMMAND).split()[0] == "100755"


@requires_git_checkout
def test_command_is_committed_with_lf_endings():
    """``#!/bin/sh`` followed by a CR names an interpreter that does not exist."""
    assert _git_ls_files("--eol", path=COMMAND).split()[0] == "i/lf"
