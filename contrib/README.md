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
