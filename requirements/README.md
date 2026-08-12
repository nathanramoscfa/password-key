# Locked CI requirements

CI installs its tooling with `pip install --require-hashes`, which
refuses any artifact whose hash is not listed here — transitive
dependencies included. That closes the gap left by pinning only the
GitHub Actions: a compromised or substituted wheel from PyPI would
otherwise still land in a job.

| File | Used by | Scope | Compiled from |
| --- | --- | --- | --- |
| `dev.txt` | `lint`, `types` | linux, 3.12 | `pyproject.toml` (`dev` extra) |
| `test.txt` | `test` | universal, 3.9–3.13 | `test.in` |
| `build.txt` | `build`, `Publish to PyPI` | universal | `build.in` |
| `fuzz.txt` | `fuzz` | linux, 3.12 | `fuzz.in` |

`dev.txt` is compiled straight from `pyproject.toml` rather than a
separate `.in` file, so the dev extra stays the single source of truth
and the lock cannot drift from it.

The split between `dev.txt` and `test.txt` is deliberate. The test
matrix spans Python 3.9–3.13 but needs only pytest; the linters run on
3.12 alone. Installing one combined lock everywhere would impose the
whole toolchain's Python floor on every matrix leg — and it did: mypy
dropped 3.9 support in 1.20.0, which broke the 3.9 legs on a routine
Dependabot bump for a tool those legs never invoke.

## Regenerating

The exact command that produced each file is in its header comment.
`dev.txt` is resolved `--universal`, so one file covers Linux, macOS,
and Windows across Python 3.9–3.13; `fuzz.txt` is Linux/3.12 only,
because that is the only place the fuzz job runs.

```bash
uv pip compile pyproject.toml --extra dev --python-platform linux \
  --python-version 3.12 --generate-hashes --output-file requirements/dev.txt

uv pip compile requirements/test.in --universal \
  --generate-hashes --python-version 3.9 --output-file requirements/test.txt

uv pip compile requirements/build.in --universal \
  --generate-hashes --python-version 3.9 --output-file requirements/build.txt

uv pip compile requirements/fuzz.in --python-platform linux \
  --python-version 3.12 --generate-hashes --output-file requirements/fuzz.txt
```

Each lock is scoped to where its job actually runs. `dev.txt`,
`build.txt`, and `fuzz.txt` are linux/3.12 because the `lint`, `types`,
`build`, `Publish` and `fuzz` jobs run only there. Resolving those
`--universal` would pull in an old-interpreter marker branch nothing
executes — and did: `build.txt` briefly carried vulnerable
`cryptography` and `urllib3` pins that existed solely to satisfy a
Python 3.9 branch of a job that only ever runs on 3.12.

## Known, accepted

`test.txt` pins `pytest==8.4.2` on its Python 3.9 branch. That release
is affected by GHSA "pytest has vulnerable tmpdir handling", fixed in
9.0.3 — which requires Python ≥ 3.10, so no patched pytest exists for
3.9. It is a test runner on a throwaway CI container, it is never a
dependency of the published package (which has none), and the fix is
unavailable rather than unapplied. It resolves when `requires-python`
moves past 3.9.

Note that Dependabot edits these files textually — it does not re-run
`uv`, so it cannot recompute the environment markers a universal
resolution produces. A bump that changes a package's `Requires-Python`
will therefore look fine in the diff and fail on the affected matrix
legs. That is what CI is for; do not merge a lock bump on a red matrix.

Dependabot watches this directory and opens a PR when a pin moves, so
the locks do not silently rot — a stale hash pin is still a stale
dependency.
