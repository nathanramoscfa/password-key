# contrib

## `new-password.ps1`

The original, standalone PowerShell implementation of `password-key` —
useful on locked-down Windows machines where Python is unavailable. It
implements the same design: OS cryptographic RNG with rejection sampling,
URL-safe charset by default, clipboard-first output.

```powershell
.\new-password.ps1               # 32 chars, URL-safe, onto the clipboard
.\new-password.ps1 -Length 48    # longer
.\new-password.ps1 -Full         # full punctuation (warns; needs encoding)
.\new-password.ps1 -Show         # also print it
```

It is kept in sync philosophically, not feature-for-feature: passphrases,
auto-clear, and script mode exist only in the Python CLI.

## Tests

This script generates credentials, so it is tested rather than trusted on
inspection. [`tests/new-password.Tests.ps1`](tests/new-password.Tests.ps1)
covers charset containment, absence of modulo bias (a chi-squared check
over 33,000 draws, the same guarantee the Python suite asserts), the
exclusion of shell- and SQL-hostile characters, and parity of both
alphabets with `password_key.generator` so the two implementations cannot
silently drift apart. It runs on every push.

```powershell
Install-Module Pester -MinimumVersion 5.5.0 -Scope CurrentUser
Invoke-Pester tests
```

Dot-sourcing the script (`. .\new-password.ps1`) loads the charsets and
the generator function without generating anything or touching the
clipboard — that is how the suite reaches them.
