# Changelog

All notable changes to this project are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

No behavior changes. This release is about making the project's existing
security claims checkable by someone who has no reason to trust the
author.

### Added

- **README section on verifying a release** rather than trusting it.
  Every artifact already carried a PEP 740 attestation binding it to the
  commit it was built from; nothing said so or explained how to check it.
- **CodeQL** analysis (`security-extended`) on every push and weekly.
- **OpenSSF Scorecard**, publishing an independent supply-chain score.
- **A Pester suite for `contrib/new-password.ps1`** — until now a second
  credential generator with no tests at all. Covers charset containment,
  modulo bias (chi-squared over 33,000 draws), exclusion of shell- and
  SQL-hostile characters, and parity of both alphabets with
  `password_key.generator`, so the two implementations cannot drift apart
  unnoticed.
- **`mypy --strict` in CI**, run for `linux`, `darwin`, and `win32`. The
  package shipped `py.typed` — a promise to every importer — that nothing
  had been enforcing.
- **OpenSSF Best Practices badge** (passing), and branch protection on `main`
  now applies to administrators too. The badge audit is not decoration: it
  found that nothing here measured branch coverage, which is why the
  coverage gate above exists.
- **Dependabot**, so the SHA-pinned GitHub Actions actually get
  refreshed. Pinning by commit SHA is the right default, but an
  unrefreshed pin quietly keeps a known-vulnerable action forever; the
  pin is only as good as the process that updates it.

- **A real Atheris fuzz target** for the generator and passphrase APIs
  (`tests/fuzz/`), run for a bounded time on every push. It asserts that
  `generate` either honors its contract exactly or raises `ValueError`,
  and that entropy figures are never *over*-stated — the direction that
  would tell someone a weak secret is strong. The properties are also
  exercised by the normal test suite, so an assertion that stops running
  cannot go unnoticed.
- **Branch coverage measurement** on every test run, with a floor. The
  figure that matters is on the modules that generate secrets —
  `generator.py` at 99% and `passphrase.py` at 95%; the remainder is
  concentrated in the interactive menu and in clipboard backends that
  cannot all execute on one operating system.
- **Hash-pinned CI tooling.** Every `pip install` in CI now runs with
  `--require-hashes` against lock files compiled from `pyproject.toml`,
  so a substituted wheel cannot enter a job. Pinning the GitHub Actions
  by SHA had left this half of the supply chain open.

### Changed

- **`LICENSE` is now unmodified MIT text.** The bundled EFF wordlist's
  CC BY 3.0 attribution moved to `THIRD-PARTY-NOTICES.md`, which ships
  in the wheel and sdist alongside it. The appended section had made
  every license scanner — GitHub included — resolve this project to
  "Other" / `NOASSERTION` rather than MIT.
- **`mypy` capped below 2.0.** mypy 2.x rejects `python_version = "3.9"`
  and falls back silently, which would have quietly stopped type-checking
  the oldest Python this package supports. Lift the cap when
  `requires-python` moves past 3.9.
- `contrib/new-password.ps1` returns early when dot-sourced, so the
  generator can be tested without copying a password to the clipboard as
  an import side effect.
- Internal type annotations added to four functions. `ctypes.windll` is
  now reached through a documented cast, since typeshed declares it only
  on Windows and the non-Windows type-check runs are worth keeping.
- **Trove classifier lowered from `Development Status :: 5 -
  Production/Stable` to `4 - Beta`.** Nothing got less reliable; the
  original claim was simply not one this project had earned yet, and an
  unearned stability claim is exactly what makes a careful reader
  discount everything else in the metadata.

## [1.1.0] - 2026-08-10

First release published to PyPI. Incorporates the results of a full
security audit of 1.0.0 (which was tagged on GitHub but never reached
PyPI).

### Added

- `entropy_bits_all_classes(charset, length)`: exact entropy of the
  accepted set under `require_all_classes` rejection sampling, via
  inclusion-exclusion. Exported from the package root.

### Security

- **`--print` appended an invisible `\r` on Windows.** Text-mode stdout
  translates `\n` to `\r\n` when piped, so
  `DB_PASSWORD=$(password-key --print)` captured the password plus a
  trailing carriage return — the same invisible-character bug class as
  `clip.exe` appending a newline. Script mode now writes `\n` only, on
  every platform, verified by a raw-bytes subprocess test.
- **The bundled EFF wordlist is now integrity-checked in CI** against the
  SHA-256 of the canonical list published by the EFF (verified
  byte-identical during this audit), and a test asserts the list is
  prefix-free, so passphrases stay uniquely decodable — and the entropy
  figure honest — under any separator, including an empty one.
- **`--full` overstated entropy at short lengths.** The class guarantee
  works by rejection sampling, so the output is uniform over a smaller
  set than charset^length, but the panel reported the unconstrained
  figure (e.g. ~25 bits at `--full --length 4`; the honest number is
  ~22). The CLI now reports `log2` of the accepted-string count,
  computed exactly by inclusion-exclusion; the difference at the default
  32 characters is ~0.03 bits. New public helper:
  `entropy_bits_all_classes(charset, length)`.
- **Win32 clipboard: `SetClipboardData` return value was truncated to 32
  bits.** No `restype` was declared, so ctypes converted the returned
  64-bit `HANDLE` through the default 32-bit `int`. A valid handle whose
  low 32 bits happened to be zero would read as failure, and the error
  path would then `GlobalFree` memory the clipboard already owned — a
  use-after-free surfacing in later pastes. Correct prototypes are now
  declared for `SetClipboardData`, `GlobalAlloc`, and `GlobalFree`, with
  protocol-level regression tests that reproduce ctypes' conversion
  semantics.
- **GitHub Actions are now pinned to full commit SHAs** instead of mutable
  tags, and checkout steps no longer persist git credentials. A moved or
  compromised tag on a third-party action could previously change the code
  running inside the workflow that holds the PyPI trusted-publishing
  identity.

### Fixed

- **CLI could crash with `UnicodeEncodeError` on Windows.** Output
  contained a few non-ASCII characters (em dash, `≈`). When stdout is
  redirected, Python encodes with the locale code page, and cp437/cp850 —
  still the default on many Windows systems — cannot represent them, so
  the tool crashed at the moment it printed the result. All terminal
  output is now pure ASCII, enforced by a regression test.
- **Double-click launcher closed its window too fast.** `New Password.bat`
  now detects launch-by-double-click and pauses before exiting, so the
  result stays on screen. It also verifies the package is actually present
  before using the repo checkout, and explains how to install the full
  version when it falls back to the PowerShell generator.

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

[1.1.0]: https://github.com/nathanramoscfa/password-key/releases/tag/v1.1.0
[1.0.0]: https://github.com/nathanramoscfa/password-key/releases/tag/v1.0.0
