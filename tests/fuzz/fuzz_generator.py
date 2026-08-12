"""Atheris fuzz harness for the generator and passphrase APIs.

This is a real fuzz target, not a marker file. It drives the public API
with adversarial inputs and asserts the properties that actually matter
for a credential generator:

- ``generate`` either returns a password of exactly the requested length
  drawn only from the requested charset, or raises ``ValueError``. Any
  other exception, or a password of the wrong length or alphabet, is a
  bug.
- Entropy figures are finite, non-negative, and never *over*-report. An
  overstated entropy number is the dangerous direction: it tells someone
  a weak secret is strong.
- ``strength_label`` is total over the reals.

Inputs are bounded to the API's documented domain (plus a margin either
side of every limit, so the boundaries themselves get exercised). The
point is to find contract violations, not to rediscover that asking for
a 10-million-character password is slow.

Run under Atheris:

    python tests/fuzz/fuzz_generator.py -max_total_time=60

The property assertions are also exercised by tests/test_fuzz_harness.py
on every CI run, so this file cannot rot unnoticed between fuzz runs.
"""

from __future__ import annotations

import math
import sys

from password_key import generator, passphrase

# A margin past MIN_LENGTH/MAX_LENGTH so the boundary conditions
# themselves are fuzzed, not just the interior.
_LENGTH_LO = generator.MIN_LENGTH - 3
_LENGTH_HI = generator.MAX_LENGTH + 3
_MAX_WORDS = 24


def check_generate(length: int, charset: str, exclude_ambiguous: bool) -> None:
    """``generate`` returns a conforming password or raises ValueError."""
    try:
        password = generator.generate(
            length, charset=charset, exclude_ambiguous=exclude_ambiguous
        )
    except ValueError:
        return  # documented failure mode

    effective = set(charset)
    if exclude_ambiguous:
        effective -= set(generator.AMBIGUOUS)

    assert len(password) == length, f"asked for {length}, got {len(password)}"
    assert set(password) <= effective, (
        f"password contains characters outside the charset: "
        f"{sorted(set(password) - effective)!r}"
    )


def check_entropy(charset: str, length: int) -> None:
    """Entropy is finite, non-negative, and never overstated."""
    distinct = len(set(charset))

    bits = generator.entropy_bits(distinct, length)
    assert math.isfinite(bits), f"entropy_bits not finite: {bits}"
    assert bits >= 0.0, f"entropy_bits negative: {bits}"

    exact = generator.entropy_bits_all_classes(charset, length)
    assert math.isfinite(exact), f"entropy_bits_all_classes not finite: {exact}"
    assert exact >= 0.0, f"entropy_bits_all_classes negative: {exact}"

    # Requiring every class can only shrink the accepted set, so the
    # exact figure must never exceed the unrestricted one. Overstating
    # entropy is the failure that actually endangers someone.
    if bits > 0.0:
        assert exact <= bits + 1e-9, f"{exact} > {bits} for {distinct}^{length}"


def check_strength_label(bits: float) -> None:
    assert generator.strength_label(bits) in {"excellent", "strong", "fair", "weak"}


def check_passphrase(words: int, separator: str, capitalize: bool) -> None:
    """``generate_passphrase`` returns the requested number of words."""
    try:
        phrase = passphrase.generate_passphrase(
            words, separator=separator, capitalize=capitalize
        )
    except ValueError:
        return

    # With an empty separator the words are not recoverable by splitting,
    # so only the non-empty case can assert a count.
    if separator:
        assert phrase.count(separator) >= words - 1, (
            f"expected {words} words joined by {separator!r}, got {phrase!r}"
        )
    assert phrase, "empty passphrase"


def check_all(
    length: int,
    charset: str,
    exclude_ambiguous: bool,
    words: int,
    separator: str,
    capitalize: bool,
    bits: float,
) -> None:
    """Every property, in one call. Shared with the pytest suite."""
    check_generate(length, charset, exclude_ambiguous)
    check_entropy(charset, length)
    check_strength_label(bits)
    check_passphrase(words, separator, capitalize)


try:
    import atheris
except ImportError:  # pragma: no cover - only present in the fuzz job
    atheris = None


def _test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    check_all(
        length=fdp.ConsumeIntInRange(_LENGTH_LO, _LENGTH_HI),
        charset=fdp.ConsumeUnicodeNoSurrogates(64),
        exclude_ambiguous=fdp.ConsumeBool(),
        words=fdp.ConsumeIntInRange(0, _MAX_WORDS),
        separator=fdp.ConsumeUnicodeNoSurrogates(4),
        capitalize=fdp.ConsumeBool(),
        bits=fdp.ConsumeFloat(),
    )


def main() -> None:  # pragma: no cover - entry point for the fuzz job
    if atheris is None:
        raise SystemExit("atheris is not installed; see requirements/fuzz.txt")
    atheris.instrument_all()
    atheris.Setup(sys.argv, _test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":  # pragma: no cover
    main()
