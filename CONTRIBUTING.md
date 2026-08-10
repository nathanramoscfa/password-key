# Contributing to password-key

Thanks for your interest! This is a small, focused tool, and contributions
that keep it small and focused are the most welcome kind.

## Ground rules

1. **Zero runtime dependencies is a feature.** PRs that add a runtime
   dependency will be declined — the supply-chain surface of a
   secret-generating tool must stay minimal.
2. **All randomness comes from `secrets`.** Never `random`, never a seed,
   never a homemade PRNG.
3. **Secrets never touch disk, logs, or the network.** Output goes to the
   clipboard, or to stdout/stderr only on explicit request.
4. **URL-safe stays the default.** New charsets or modes must be opt-in.

## Development setup

```bash
git clone https://github.com/nathanramoscfa/password-key.git
cd password-key
python -m venv .venv && . .venv/bin/activate   # or .venv\Scripts\activate
pip install -e .[dev]
```

## Before you open a PR

```bash
ruff check .          # lint (includes bandit security rules)
ruff format --check . # formatting
pytest                # full test suite
```

- Add tests for any behavior change. The distribution test
  (`tests/test_generator.py::TestDistribution`) must keep passing — it is
  the canary for sampling bias.
- Keep the docs honest: if behavior changes, update `README.md` and the
  `--help` text in the same PR.
- One logical change per PR.

## Reporting bugs

Open an issue with your OS, Python version, the exact command, and what
happened. For anything security-sensitive, see [SECURITY.md](SECURITY.md)
instead.
