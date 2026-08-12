"""Exercise the fuzz harness's properties without Atheris.

The fuzz job runs on Linux only and for a bounded time. Without this,
a refactor could silently break the harness and nobody would notice
until the next fuzz run — an assertion that never executes is worth
nothing. These cases pin the boundaries the fuzzer explores around.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

from password_key.generator import AMBIGUOUS, FULL, MAX_LENGTH, MIN_LENGTH, URL_SAFE

_HARNESS = Path(__file__).parent / "fuzz" / "fuzz_generator.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("fuzz_generator", _HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


def test_harness_imports_without_atheris():
    """The module must import on a machine with no Atheris installed."""
    assert harness.atheris is None or hasattr(harness.atheris, "Setup")
    assert callable(harness.check_all)


@pytest.mark.parametrize(
    "length",
    [
        MIN_LENGTH - 3,
        MIN_LENGTH - 1,
        MIN_LENGTH,
        MIN_LENGTH + 1,
        32,
        MAX_LENGTH - 1,
        MAX_LENGTH,
        MAX_LENGTH + 1,
    ],
)
@pytest.mark.parametrize(
    "charset",
    [
        "",
        "a",
        "ab",
        "aaab",  # duplicates must not bias or break length accounting
        AMBIGUOUS,  # becomes empty under exclude_ambiguous
        URL_SAFE,
        FULL,
        "ünïcödé",
        "\x00\x01",
    ],
)
@pytest.mark.parametrize("exclude_ambiguous", [False, True])
def test_generate_contract(length, charset, exclude_ambiguous):
    harness.check_generate(length, charset, exclude_ambiguous)


@pytest.mark.parametrize("charset", ["", "a", "ab", URL_SAFE, FULL, "ünïcödé"])
@pytest.mark.parametrize("length", [0, 1, 4, 32, MAX_LENGTH, MAX_LENGTH + 3])
def test_entropy_never_overstated(charset, length):
    harness.check_entropy(charset, length)


@pytest.mark.parametrize(
    "bits",
    [
        -1e9,
        -1.0,
        0.0,
        59.999,
        60.0,
        74.999,
        75.0,
        127.999,
        128.0,
        1e9,
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_strength_label_is_total(bits):
    harness.check_strength_label(bits)


@pytest.mark.parametrize("words", [0, 1, 2, 6, 24])
@pytest.mark.parametrize("separator", ["", "-", "::", "a", "\x00"])
@pytest.mark.parametrize("capitalize", [False, True])
def test_passphrase_contract(words, separator, capitalize):
    harness.check_passphrase(words, separator, capitalize)


def test_check_all_smoke():
    harness.check_all(
        length=32,
        charset=URL_SAFE,
        exclude_ambiguous=False,
        words=6,
        separator="-",
        capitalize=False,
        bits=193.0,
    )
