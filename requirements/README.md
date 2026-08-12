# Locked CI requirements

CI installs its tooling with `pip install --require-hashes`, which
refuses any artifact whose hash is not listed here — transitive
dependencies included. That closes the gap left by pinning only the
GitHub Actions: a compromised or substituted wheel from PyPI would
otherwise still land in a job.

| File | Used by | Compiled from |
| --- | --- | --- |
| `dev.txt` | `lint`, `types`, `test` | `pyproject.toml` (`dev` extra) |
| `build.txt` | `build`, `Publish to PyPI` | `build.in` |
| `fuzz.txt` | `fuzz` | `fuzz.in` |

`dev.txt` is compiled straight from `pyproject.toml` rather than a
separate `.in` file, so the dev extra stays the single source of truth
and the lock cannot drift from it.

## Regenerating

The exact command that produced each file is in its header comment.
`dev.txt` is resolved `--universal`, so one file covers Linux, macOS,
and Windows across Python 3.9–3.13; `fuzz.txt` is Linux/3.12 only,
because that is the only place the fuzz job runs.

```bash
uv pip compile pyproject.toml --extra dev --universal \
  --generate-hashes --python-version 3.9 --output-file requirements/dev.txt

uv pip compile requirements/build.in --universal \
  --generate-hashes --python-version 3.9 --output-file requirements/build.txt

uv pip compile requirements/fuzz.in --python-platform linux \
  --python-version 3.12 --generate-hashes --output-file requirements/fuzz.txt
```

Dependabot watches this directory and opens a PR when a pin moves, so
the locks do not silently rot — a stale hash pin is still a stale
dependency.
