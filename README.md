# password-key

[![PyPI](https://img.shields.io/pypi/v/password-key)](https://pypi.org/project/password-key/)
[![Python](https://img.shields.io/pypi/pyversions/password-key)](https://pypi.org/project/password-key/)
[![CI](https://github.com/nathanramoscfa/password-key/actions/workflows/ci.yml/badge.svg)](https://github.com/nathanramoscfa/password-key/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Cryptographically secure passwords that are safe to paste anywhere.**

Most password generators hand you `k9$P@x/2'` and let you discover — an hour
later, three layers deep in a stack trace — that `@` split your database URL,
`$` was expanded by your shell, and `'` broke your SQL. `password-key` is
built around one idea:

> **URL-safe output is the default.** Letters, digits, and `- _ . ~` — the
> only punctuation [RFC 3986](https://datatracker.ietf.org/doc/html/rfc3986#section-2.3)
> guarantees is safe in a URL — and characters that also carry no special
> meaning in a SQL literal or a shell. At 32 characters that is still
> **~193 bits of entropy**, far beyond any brute-force attack. The
> restriction buys safety and costs nothing.

The password is copied to your **clipboard, never printed** (terminal
scrollback is a file on disk), drawn from the **OS cryptographic RNG** via
Python's [`secrets`](https://docs.python.org/3/library/secrets.html) module,
and the whole package has **zero runtime dependencies** — the smallest
possible supply-chain surface for a tool that generates credentials.

## Install

```bash
pipx install password-key    # recommended for CLI use
# or
pip install password-key
```

## Usage

```console
$ password-key

  Length    : 32 characters
  Charset   : URL-safe (letters, digits, - _ . ~) — safe anywhere
  Strength  : ~193 bits of entropy (excellent)
  Clipboard : COPIED

  Paste it into your password manager now, then copy
  something harmless to clear the clipboard.
```

The essentials:

```bash
password-key                  # 32 chars, URL-safe → clipboard
password-key -l 48            # longer
password-key --words 6        # diceware passphrase (see below)
password-key --clear 30       # auto-clear the clipboard after 30 s
password-key --no-ambiguous   # drop 0 O 1 l I | (for reading aloud)
password-key --full           # full punctuation (see warning below)
password-key --show           # display it too (still copied)
password-key --print          # bare password on stdout, for scripts
password-key -i               # interactive menu
pwk                           # short alias for all of the above
```

### Passphrases

```console
$ password-key --words 6

  Words     : 6
  Charset   : 6 words, EFF Large Wordlist (URL-safe)
  Strength  : ~77 bits of entropy (strong)
  Clipboard : COPIED
```

Diceware passphrases from the [EFF Large Wordlist](https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases)
(7,776 words, ~12.9 bits each) — for the secrets a human has to type or
remember. The default `-` separator keeps even passphrases URL-safe.
Six words is the EFF's recommendation; use `--words 7` (~90 bits) for
anything facing offline attack.

### Auto-clear

```console
$ password-key --clear 30
  ...
  Clearing clipboard in  30s  (Ctrl+C to keep it)
```

After the countdown, the clipboard is wiped **only if it still holds the
password** — if you copied something else in the meantime, it is left alone.

### Scripting

`--print` writes the bare secret to stdout and everything else to stderr,
so it composes:

```bash
DB_PASSWORD=$(password-key --print)
password-key --print --count 5        # five candidates, one per line
```

### Python API

```python
from password_key import generate, generate_passphrase, entropy_bits, FULL

generate()                        # 32-char URL-safe password
generate(48)                      # longer
generate(20, charset=FULL)        # full punctuation
generate(exclude_ambiguous=True)  # no 0 O 1 l I |
generate_passphrase(6)            # 'correct-horse-battery-staple-...'
entropy_bits(66, 32)              # 193.38...
```

Everything is drawn from `secrets` — never `random`.

## When you *do* need punctuation

Some systems mandate a symbol class. `--full` adds
``! # $ % & ( ) * + , - . : ; < = > ? @ [ ] ^ { | } _ ~`` and guarantees at
least one upper, lower, digit, and symbol:

```console
$ password-key --full

  Charset   : full punctuation — NOT safe in a DSN without percent-encoding
  WARNING   : percent-encode this before putting it in a connection string
```

An unencoded `@` or `%` inside
`postgresql://user:PASSWORD@host/db` splits the string and surfaces much
later as a confusing *"could not translate host name"*. If you must embed a
`--full` password in a URL, percent-encode it first:

```python
from urllib.parse import quote
quote(password, safe="")
```

Even `--full` deliberately excludes quotes, backslash, backtick, and space —
they add ~0.1 bits per character and are the characters that turn a working
password into an escaping bug.

## Security design

| Decision | Why |
| --- | --- |
| `secrets` (OS CSPRNG), never `random` | `random` is seeded, deterministic pseudo-randomness — unfit for credentials. |
| Unbiased selection | `secrets.choice` uses rejection sampling internally; no character is ever more likely than another (verified by a chi-squared test in CI). |
| Clipboard, not terminal | Terminal scrollback is written to disk. The secret is displayed only on explicit request or when no clipboard exists. |
| Zero dependencies | Nothing to typosquat, nothing to compromise. Clipboard access uses the Win32 API directly (`ctypes`) and `pbcopy` / `wl-copy` / `xclip` elsewhere. |
| Guarded auto-clear | `--clear` wipes the clipboard only while it still holds the generated password. |
| No state, no telemetry, no network | Passwords are never logged, cached, or written anywhere. |

Found a vulnerability? See [SECURITY.md](SECURITY.md).

## Windows double-click launcher

Prefer not to open a terminal? [`New Password.bat`](New%20Password.bat)
launches the interactive menu with a double-click. A standalone
PowerShell implementation (no Python required) lives in
[`contrib/new-password.ps1`](contrib/new-password.ps1).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The bundled EFF Large Wordlist is © the
[Electronic Frontier Foundation](https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases),
CC BY 3.0.
