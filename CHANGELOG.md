# Changelog

All notable changes to this project are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-08-10

First public release. `password-key` began as an internal PowerShell script
used in credential-rotation runbooks; this release is a ground-up Python
rewrite of the same design.

### Added

- **Core generator**: cryptographically secure passwords via the OS CSPRNG
  (`secrets`), URL-safe charset by default (letters, digits, `- _ . ~`),
  32 characters (~193 bits) by default.
- **`--full`**: full-punctuation charset for systems that mandate a symbol
  class, with a guarantee of at least one upper, lower, digit, and symbol —
  and a warning that the result needs percent-encoding before entering a
  connection string.
- **`--words N`**: diceware passphrases from the bundled EFF Large Wordlist
  (7,776 words, ~12.9 bits/word), URL-safe by default via the `-` separator.
- **Clipboard-first UX**: the secret is copied, never printed, using
  zero-dependency clipboard access (Win32 API via `ctypes`, `pbcopy`,
  `wl-copy`, `xclip`, or `xsel`), with a graceful display fallback when no
  clipboard exists.
- **`--clear SECONDS`**: countdown, then wipe the clipboard — only if it
  still holds the generated password.
- **`--no-ambiguous`**: exclude `0 O 1 l I |` for passwords that must be
  read aloud or typed from paper.
- **`--print` / `--count N`**: script-friendly bare output on stdout.
- **`-i` / `--interactive`**: menu mode, plus a Windows double-click
  launcher (`New Password.bat`).
- **Python API**: `generate()`, `generate_passphrase()`, `entropy_bits()`,
  `strength_label()`; fully typed (`py.typed`).
- **`pwk`**: short console alias.
- Test suite including a chi-squared uniformity test; CI across
  Linux/macOS/Windows and Python 3.9–3.13.
- Standalone PowerShell implementation preserved in
  `contrib/new-password.ps1` for machines without Python.

[1.0.0]: https://github.com/nathanramoscfa/password-key/releases/tag/v1.0.0
