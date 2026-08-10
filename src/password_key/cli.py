"""Command-line interface for password-key.

Design rules, in priority order:

1. **The password goes to the clipboard, not the terminal.** Terminal
   scrollback is a file on disk. ``--show`` and ``--print`` exist for
   the cases where display is genuinely required.
2. **URL-safe output is the default.** ``--full`` is the escape hatch
   for systems that mandate a punctuation class, and it warns.
3. **No surprises in scripts.** ``--print`` writes the bare password to
   stdout and everything else to stderr, so it composes with pipes.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import __version__, clipboard, generator, passphrase

# ---------------------------------------------------------------------------
# Terminal color handling
# ---------------------------------------------------------------------------


def _colors_enabled(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if sys.platform == "win32":
        _enable_windows_vt()
    return True


def _enable_windows_vt() -> None:
    """Enable ANSI escape processing on the Windows console.

    Purely cosmetic — on failure the CLI simply runs without color.
    """
    import contextlib
    import ctypes

    with contextlib.suppress(Exception):
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)


class _Style:
    def __init__(self, enabled: bool):
        self.green = "\x1b[32m" if enabled else ""
        self.yellow = "\x1b[33m" if enabled else ""
        self.cyan = "\x1b[36m" if enabled else ""
        self.bold = "\x1b[1m" if enabled else ""
        self.dim = "\x1b[2m" if enabled else ""
        self.reset = "\x1b[0m" if enabled else ""


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="password-key",
        description=(
            "Generate a cryptographically random password onto the clipboard. "
            "Output is URL-safe by default (letters, digits, - _ . ~), so it "
            "can be pasted into a connection string, SQL literal, or shell "
            "without escaping."
        ),
        epilog=(
            "examples:\n"
            "  password-key                 32 chars, URL-safe, onto the clipboard\n"
            "  password-key -l 48           longer\n"
            "  password-key --words 6       diceware passphrase (EFF wordlist)\n"
            "  password-key --clear 30      auto-clear the clipboard after 30s\n"
            "  password-key --print         bare password on stdout, for scripts\n"
            "  password-key -i              interactive menu"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-l",
        "--length",
        type=int,
        default=32,
        metavar="N",
        help=f"password length in characters "
        f"({generator.MIN_LENGTH}-{generator.MAX_LENGTH}, default: 32)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="use the full punctuation set instead of the URL-safe default. "
        "WARNING: the result must be percent-encoded before it goes "
        "into a connection string. Guarantees at least one upper, "
        "lower, digit, and symbol, for systems with composition rules",
    )
    parser.add_argument(
        "--no-ambiguous",
        action="store_true",
        help="exclude characters that are easily misread (0 O 1 l I |), for "
        "passwords that must be read aloud or typed from paper",
    )
    parser.add_argument(
        "-w",
        "--words",
        type=int,
        metavar="N",
        help="generate a diceware passphrase of N words from the EFF Large "
        "Wordlist instead of a character password (6 words is ~77 bits)",
    )
    parser.add_argument(
        "--separator",
        default="-",
        metavar="SEP",
        help="separator between passphrase words (default: '-', which keeps "
        "the passphrase URL-safe)",
    )
    parser.add_argument(
        "--capitalize",
        action="store_true",
        help="capitalize each passphrase word, for systems that demand an "
        "uppercase character",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=1,
        metavar="N",
        help="generate N candidates. With N > 1 the passwords are printed "
        "(nothing touches the clipboard)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="also display the password (it still goes to the clipboard)",
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="write the bare password to stdout and skip the clipboard "
        "entirely - for piping into other tools",
    )
    parser.add_argument(
        "--clear",
        type=int,
        metavar="SECONDS",
        help="wait SECONDS, then clear the clipboard (skipped if you copied "
        "something else in the meantime; Ctrl+C cancels the wait and "
        "leaves the clipboard alone)",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="interactive menu mode",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


# ---------------------------------------------------------------------------
# Generation dispatch
# ---------------------------------------------------------------------------


def _generate_one(args) -> tuple[str, float, str]:
    """Returns (secret, entropy_bits, charset_description)."""
    if args.words is not None:
        secret = passphrase.generate_passphrase(
            args.words, separator=args.separator, capitalize=args.capitalize
        )
        bits = passphrase.entropy_bits(args.words)
        desc = f"{args.words} words, EFF Large Wordlist"
        if args.separator == "-" and not args.capitalize:
            desc += " (URL-safe)"
        return secret, bits, desc

    charset = generator.FULL if args.full else generator.URL_SAFE
    secret = generator.generate(
        args.length,
        charset=charset,
        exclude_ambiguous=args.no_ambiguous,
        require_all_classes=args.full,
    )
    size = len(charset) - (
        sum(c in charset for c in generator.AMBIGUOUS) if args.no_ambiguous else 0
    )
    bits = generator.entropy_bits(size, args.length)
    if args.full:
        desc = "full punctuation: NOT safe in a DSN without percent-encoding"
    else:
        desc = "URL-safe (letters, digits, - _ . ~): safe anywhere"
    return secret, bits, desc


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_panel(secret: str, bits: float, desc: str, args, style: _Style) -> None:
    err = sys.stderr
    label = generator.strength_label(bits)
    warn = style.yellow if args.full else ""
    print("", file=err)
    if args.words is not None:
        print(f"  Words     : {args.words}", file=err)
    else:
        print(f"  Length    : {args.length} characters", file=err)
    print(f"  Charset   : {warn}{desc}{style.reset}", file=err)
    print(f"  Strength  : ~{int(bits)} bits of entropy ({label})", file=err)
    if args.full:
        print(
            f"  {style.yellow}WARNING   : percent-encode this before putting "
            f"it in a connection string{style.reset}",
            file=err,
        )

    copied = clipboard.copy(secret)
    if copied:
        print(f"  Clipboard : {style.green}COPIED{style.reset}", file=err)
        print("", file=err)
        if args.clear is None:
            print(
                "  Paste it into your password manager now, then copy",
                file=err,
            )
            print("  something harmless to clear the clipboard.", file=err)
    else:
        print(
            f"  Clipboard : {style.yellow}unavailable - showing it instead"
            f"{style.reset}",
            file=err,
        )
        print("", file=err)
        print(f"  {secret}", file=err)
    if args.show and copied:
        print("", file=err)
        print(f"  {secret}", file=err)
    print("", file=err)

    if copied and args.clear is not None:
        _countdown_clear(secret, args.clear, style)


def _countdown_clear(secret: str, seconds: int, style: _Style) -> None:
    err = sys.stderr
    try:
        for remaining in range(seconds, 0, -1):
            print(
                f"\r  Clearing clipboard in {remaining:3d}s  "
                f"{style.dim}(Ctrl+C to keep it){style.reset} ",
                end="",
                file=err,
                flush=True,
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\r{' ' * 60}\r  Clipboard kept.{' ' * 20}", file=err)
        return
    cleared = clipboard.clear(expected=secret)
    if cleared:
        print(f"\r{' ' * 60}\r  Clipboard cleared.", file=err)
    else:
        print(
            f"\r{' ' * 60}\r  Clipboard left alone - it no longer held the password.",
            file=err,
        )


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

_MENU = """
  ============================================
             password-key {version}
  ============================================

  The password is copied to your clipboard.
  It is never displayed and never written to disk.

    1  Standard 32 chars  [USE THIS]
       Letters, digits, - _ . ~
       Safe in a database URL, in SQL, and in a shell.

    2  Custom length

    3  Passphrase (6 words, easy to type and remember)

    4  Full punctuation  [ADVANCED]
       Adds @ : / ? # % and friends. These BREAK a
       database URL unless you percent-encode them.

    Q  Quit
"""


def _interactive(style: _Style) -> int:
    parser = build_parser()
    while True:
        print(_MENU.format(version=__version__))
        try:
            choice = input("  Choose [1/2/3/4/Q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice == "q":
            return 0
        if choice == "1":
            args = parser.parse_args([])
        elif choice == "2":
            try:
                raw = input(
                    f"  Length ({generator.MIN_LENGTH}-{generator.MAX_LENGTH}): "
                ).strip()
                length = int(raw)
            except (ValueError, EOFError, KeyboardInterrupt):
                continue
            args = parser.parse_args(["--length", str(length)])
        elif choice == "3":
            args = parser.parse_args(["--words", "6"])
        elif choice == "4":
            try:
                sure = (
                    input(
                        "\n  Full punctuation CANNOT go straight into a database "
                        "URL.\n  Continue anyway? [y/N]: "
                    )
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                continue
            if sure != "y":
                continue
            args = parser.parse_args(["--full"])
        else:
            continue

        try:
            secret, bits, desc = _generate_one(args)
        except ValueError as exc:
            print(f"\n  error: {exc}", file=sys.stderr)
            continue
        _print_panel(secret, bits, desc, args, style)

        try:
            again = input("  Generate another? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if again != "y":
            return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    style = _Style(_colors_enabled(sys.stderr))

    if args.interactive:
        return _interactive(style)

    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.words is not None and args.words < 1:
        parser.error("--words must be at least 1")
    if args.clear is not None and args.clear < 1:
        parser.error("--clear must be at least 1 second")

    try:
        results = [_generate_one(args) for _ in range(args.count)]
    except ValueError as exc:
        parser.error(str(exc))

    if args.print_only or args.count > 1:
        # Script mode: bare secrets on stdout, one per line, nothing else.
        for secret, _, _ in results:
            print(secret)
        if args.count > 1 and not args.print_only:
            print(
                "\nnote: with --count > 1 nothing is copied to the clipboard",
                file=sys.stderr,
            )
        return 0

    secret, bits, desc = results[0]
    _print_panel(secret, bits, desc, args, style)
    return 0


if __name__ == "__main__":
    sys.exit(main())
