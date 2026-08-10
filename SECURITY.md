# Security Policy

## Supported versions

Only the latest release published on [PyPI](https://pypi.org/project/password-key/)
is supported with security fixes.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Instead, use
GitHub's private reporting:
[Report a vulnerability](https://github.com/nathanramoscfa/password-key/security/advisories/new),
or email **nathan.ramos.github@gmail.com** with `[password-key security]` in
the subject line.

You can expect an acknowledgement within a few days. Fixes for confirmed
issues are released as soon as they are ready, with credit to the reporter
unless you prefer otherwise.

## Scope notes

Things that are *by design* and not vulnerabilities:

- The password is placed on the system clipboard, which other local
  processes can read. That is the point of the tool; if your threat model
  includes hostile local processes, use `--print` piped directly to the
  consumer, and note that a compromised local machine can defeat any
  clipboard hygiene.
- `--show` / `--print` write the secret to the terminal or stdout when
  explicitly requested.
- Python cannot guarantee secrets are wiped from process memory; the
  process is short-lived by design.

Things that absolutely are vulnerabilities and we want to know about:

- Any bias in generated output (character frequency, positional, or
  otherwise).
- Any code path that draws randomness from something other than `secrets`.
- Any code path that writes a generated secret to disk, logs, or the
  network.
