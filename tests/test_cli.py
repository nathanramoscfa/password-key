"""Tests for the password-key CLI."""

import os
import string
import subprocess
import sys
from pathlib import Path

import pytest

from password_key import __version__, clipboard, generator
from password_key.cli import build_parser, main


@pytest.fixture
def fake_clipboard(monkeypatch):
    """Replace the system clipboard with an in-memory one."""
    state = {"value": None}

    monkeypatch.setattr(
        clipboard, "copy", lambda text: state.update(value=text) or True
    )
    monkeypatch.setattr(clipboard, "read", lambda: state["value"])
    return state


@pytest.fixture
def broken_clipboard(monkeypatch):
    monkeypatch.setattr(clipboard, "copy", lambda text: False)


class TestDefaults:
    def test_copies_32_url_safe_chars(self, fake_clipboard, capsys):
        assert main([]) == 0
        secret = fake_clipboard["value"]
        assert len(secret) == 32
        assert set(secret) <= set(generator.URL_SAFE)

    def test_password_not_printed(self, fake_clipboard, capsys):
        main([])
        captured = capsys.readouterr()
        assert fake_clipboard["value"] not in captured.out
        assert fake_clipboard["value"] not in captured.err

    def test_panel_reports_strength(self, fake_clipboard, capsys):
        main([])
        err = capsys.readouterr().err
        assert "193 bits" in err
        assert "COPIED" in err


class TestOptions:
    def test_length(self, fake_clipboard):
        main(["--length", "48"])
        assert len(fake_clipboard["value"]) == 48

    def test_full_charset_and_warning(self, fake_clipboard, capsys):
        main(["--full", "--length", "12"])
        secret = fake_clipboard["value"]
        assert set(secret) <= set(generator.FULL)
        # --full guarantees every class
        assert any(c in string.ascii_uppercase for c in secret)
        assert any(c in string.ascii_lowercase for c in secret)
        assert any(c in string.digits for c in secret)
        assert any(not c.isalnum() for c in secret)
        assert "percent-encode" in capsys.readouterr().err

    def test_full_reports_honest_entropy_at_short_length(self, fake_clipboard, capsys):
        # --full rejects passwords missing a class, so the accepted set
        # at length 4 is ~22 bits, not the naive log2(89)*4 ~= 25.9.
        main(["--full", "--length", "4"])
        err = capsys.readouterr().err
        expected = int(generator.entropy_bits_all_classes(generator.FULL, 4))
        assert expected == 22
        assert f"~{expected} bits" in err
        assert "~25 bits" not in err

    def test_no_ambiguous(self, fake_clipboard):
        main(["--no-ambiguous", "--length", "256"])
        assert not set(fake_clipboard["value"]) & set(generator.AMBIGUOUS)

    def test_show_prints_secret(self, fake_clipboard, capsys):
        main(["--show"])
        assert fake_clipboard["value"] in capsys.readouterr().err

    def test_words_mode(self, fake_clipboard, capsys):
        main(["--words", "6"])
        assert len(fake_clipboard["value"].split("-")) == 6
        assert "77 bits" in capsys.readouterr().err

    def test_invalid_length_is_a_clean_error(self, fake_clipboard, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--length", "2"])
        assert excinfo.value.code == 2
        assert "length" in capsys.readouterr().err

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert __version__ in capsys.readouterr().out


class TestScriptMode:
    def test_print_writes_bare_secret_to_stdout(self, fake_clipboard, capsys):
        assert main(["--print"]) == 0
        out = capsys.readouterr().out
        assert len(out.rstrip("\n")) == 32
        assert set(out.rstrip("\n")) <= set(generator.URL_SAFE)
        # --print must not touch the clipboard
        assert fake_clipboard["value"] is None

    def test_count_prints_n_lines_and_skips_clipboard(self, fake_clipboard, capsys):
        main(["--count", "5", "--print"])
        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 5
        assert len(set(lines)) == 5
        assert fake_clipboard["value"] is None

    def test_count_without_print_warns(self, fake_clipboard, capsys):
        main(["--count", "3"])
        captured = capsys.readouterr()
        assert len(captured.out.strip().splitlines()) == 3
        assert "clipboard" in captured.err

    def test_print_emits_no_carriage_return(self):
        # Raw bytes from a real pipe: on Windows, text-mode stdout would
        # append \r, and $(password-key --print) would capture
        # "password\r" - an invisible character in the stored secret.
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "src")
        result = subprocess.run(
            [sys.executable, "-m", "password_key", "--print"],
            capture_output=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0
        assert b"\r" not in result.stdout
        assert result.stdout.endswith(b"\n")
        assert len(result.stdout) == 33  # 32 chars + exactly one \n


class TestClipboardFallback:
    def test_secret_shown_when_clipboard_unavailable(self, broken_clipboard, capsys):
        assert main([]) == 0
        err = capsys.readouterr().err
        assert "unavailable" in err
        # The secret is displayed as a fallback: find a 32-char token.
        tokens = [t for t in err.split() if len(t) == 32]
        assert any(set(t) <= set(generator.URL_SAFE) for t in tokens)


class TestAutoClear:
    def test_clear_wipes_clipboard(self, fake_clipboard, capsys, monkeypatch):
        monkeypatch.setattr("password_key.cli.time.sleep", lambda s: None)
        main(["--clear", "3"])
        assert fake_clipboard["value"] == ""
        assert "cleared" in capsys.readouterr().err

    def test_clear_respects_changed_clipboard(
        self, fake_clipboard, capsys, monkeypatch
    ):
        def sleep_and_hijack(seconds):
            fake_clipboard["value"] = "the-user-copied-this"

        monkeypatch.setattr("password_key.cli.time.sleep", sleep_and_hijack)
        # clipboard.clear reads via the fake; value differs → left alone
        main(["--clear", "1"])
        assert fake_clipboard["value"] == "the-user-copied-this"

    def test_ctrl_c_keeps_clipboard(self, fake_clipboard, capsys, monkeypatch):
        def interrupt(seconds):
            raise KeyboardInterrupt

        monkeypatch.setattr("password_key.cli.time.sleep", interrupt)
        main(["--clear", "30"])
        assert fake_clipboard["value"] not in ("", None)
        assert "kept" in capsys.readouterr().err


class TestParser:
    def test_prog_name(self):
        assert build_parser().prog == "password-key"

    @pytest.mark.parametrize(
        "argv",
        [["--count", "0"], ["--words", "0"], ["--clear", "0"]],
    )
    def test_zero_values_rejected(self, argv, fake_clipboard):
        with pytest.raises(SystemExit):
            main(argv)


def _assert_ascii(text, label):
    bad = sorted({ch for ch in text if ord(ch) > 127})
    assert not bad, f"non-ASCII character(s) in {label}: {bad}"


class TestAsciiOutput:
    """Every byte the CLI prints must be ASCII.

    On Windows, redirected output is encoded with the locale code page.
    cp437 and cp850 - still the default on plenty of machines - cannot
    represent an em dash, so a single stray one turns printing the
    result into a UnicodeEncodeError crash.
    """

    def test_help_is_ascii(self):
        _assert_ascii(build_parser().format_help(), "--help output")

    def test_menu_is_ascii(self):
        from password_key.cli import _MENU

        _assert_ascii(_MENU.format(version=__version__), "interactive menu")

    @pytest.mark.parametrize(
        "argv",
        [
            [],
            ["--full"],
            ["--words", "6"],
            ["--show"],
            ["--no-ambiguous"],
            ["--print"],
            ["--count", "3"],
        ],
    )
    def test_output_is_ascii(self, argv, fake_clipboard, capsys):
        main(argv)
        captured = capsys.readouterr()
        _assert_ascii(captured.out, f"stdout for {argv}")
        _assert_ascii(captured.err, f"stderr for {argv}")

    def test_clipboard_failure_panel_is_ascii(self, broken_clipboard, capsys):
        main([])
        _assert_ascii(capsys.readouterr().err, "clipboard-failure panel")

    def test_auto_clear_messages_are_ascii(self, fake_clipboard, capsys, monkeypatch):
        monkeypatch.setattr("password_key.cli.time.sleep", lambda s: None)
        main(["--clear", "2"])
        _assert_ascii(capsys.readouterr().err, "auto-clear countdown")


@pytest.fixture
def answers(monkeypatch):
    """Script the values ``input()`` returns, in order.

    Pass an exception class instead of a string to simulate Ctrl+C or
    Ctrl+D at that prompt. Asking for more input than was scripted fails
    the test rather than hanging, which is the failure mode that makes
    interactive code unpleasant to test.

    Returns the list that accumulates the prompts actually shown, so a
    test can assert on what the user was asked.
    """

    def _install(*responses):
        queue = list(responses)
        prompts = []

        def fake_input(prompt=""):
            prompts.append(prompt)
            if not queue:
                raise AssertionError(f"unscripted input() at prompt {prompt!r}")
            item = queue.pop(0)
            if isinstance(item, type) and issubclass(item, BaseException):
                raise item()
            return item

        monkeypatch.setattr("builtins.input", fake_input)
        return prompts

    return _install


class TestInteractiveMenu:
    """The `-i` menu, reached by double-clicking New Password.bat.

    This is the path taken by whoever is least equipped to debug it, so
    every branch gets a test - including each way of pressing Ctrl+C.
    """

    def test_menu_is_shown_and_q_quits(self, fake_clipboard, answers, capsys):
        answers("q")
        assert main(["-i"]) == 0
        out = capsys.readouterr().out
        assert "password-key" in out
        assert __version__ in out
        assert fake_clipboard["value"] is None

    def test_quit_accepts_uppercase(self, fake_clipboard, answers):
        answers("Q")
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is None

    def test_secret_never_reaches_the_terminal(self, fake_clipboard, answers, capsys):
        """The core invariant, on the path least likely to be audited."""
        answers("1", "n")
        main(["-i"])
        captured = capsys.readouterr()
        secret = fake_clipboard["value"]
        assert secret
        assert secret not in captured.out
        assert secret not in captured.err

    def test_option_1_generates_the_default(self, fake_clipboard, answers):
        answers("1", "n")
        assert main(["-i"]) == 0
        secret = fake_clipboard["value"]
        assert len(secret) == 32
        assert set(secret) <= set(generator.URL_SAFE)

    def test_option_2_uses_the_requested_length(self, fake_clipboard, answers):
        answers("2", "48", "n")
        assert main(["-i"]) == 0
        assert len(fake_clipboard["value"]) == 48

    def test_option_2_reprompts_on_non_numeric_length(self, fake_clipboard, answers):
        answers("2", "twelve", "q")
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is None

    def test_option_2_reports_an_out_of_range_length(
        self, fake_clipboard, answers, capsys
    ):
        # Parsed fine by argparse (type=int, no range), rejected by
        # generate() - so this exercises the ValueError branch rather
        # than argparse's own error path.
        answers("2", str(generator.MIN_LENGTH - 1), "q")
        assert main(["-i"]) == 0
        assert "error:" in capsys.readouterr().err
        assert fake_clipboard["value"] is None

    def test_option_3_generates_a_six_word_passphrase(self, fake_clipboard, answers):
        answers("3", "n")
        assert main(["-i"]) == 0
        phrase = fake_clipboard["value"]
        # Four EFF words contain a hyphen themselves (drop-down, felt-tip,
        # t-shirt, yo-yo), so the separator count is a lower bound, never
        # an equality.
        assert phrase.count("-") >= 5
        assert phrase == phrase.lower()

    def test_option_4_needs_confirmation_first(self, fake_clipboard, answers):
        answers("4", "y", "n")
        assert main(["-i"]) == 0
        secret = fake_clipboard["value"]
        assert set(secret) <= set(generator.FULL)

    def test_option_4_declined_generates_nothing(self, fake_clipboard, answers):
        answers("4", "n", "q")
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is None

    def test_option_4_warns_about_connection_strings(
        self, fake_clipboard, answers, capsys
    ):
        prompts = answers("4", "y", "n")
        main(["-i"])
        assert any("database" in p.lower() for p in prompts)
        assert "WARNING" in capsys.readouterr().err

    def test_unrecognized_choice_reprompts(self, fake_clipboard, answers):
        prompts = answers("9", "", "q")
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is None
        assert sum(1 for p in prompts if "Choose" in p) == 3

    def test_generate_another_loops_back_to_the_menu(self, fake_clipboard, answers):
        prompts = answers("1", "y", "1", "n")
        assert main(["-i"]) == 0
        assert sum(1 for p in prompts if "Choose" in p) == 2

    @pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
    def test_interrupt_at_the_menu_exits_cleanly(
        self, fake_clipboard, answers, interrupt
    ):
        answers(interrupt)
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is None

    @pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
    def test_interrupt_at_length_prompt_reprompts(
        self, fake_clipboard, answers, interrupt
    ):
        answers("2", interrupt, "q")
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is None

    @pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
    def test_interrupt_at_full_confirmation_reprompts(
        self, fake_clipboard, answers, interrupt
    ):
        answers("4", interrupt, "q")
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is None

    @pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
    def test_interrupt_after_generating_still_exits_zero(
        self, fake_clipboard, answers, interrupt
    ):
        answers("1", interrupt)
        assert main(["-i"]) == 0
        assert fake_clipboard["value"] is not None


class TestModuleEntryPoint:
    """``python -m password_key``.

    The subprocess test in TestScripting already runs this for real; it
    cannot be seen by coverage because it happens in a child process.
    Running it in-process here covers the ``__main__`` guard and asserts
    the exit status the shell would observe.
    """

    def test_run_as_module(self, fake_clipboard, monkeypatch):
        import runpy

        monkeypatch.setattr(sys, "argv", ["password-key"])
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("password_key", run_name="__main__")
        assert excinfo.value.code == 0
        assert len(fake_clipboard["value"]) == 32
