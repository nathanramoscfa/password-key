"""Tests for password_key.generator."""

import math
import string
from collections import Counter

import pytest

from password_key.generator import (
    AMBIGUOUS,
    FULL,
    URL_SAFE,
    entropy_bits,
    entropy_bits_all_classes,
    generate,
    strength_label,
)


class TestCharsets:
    def test_url_safe_is_rfc3986_unreserved(self):
        # Exactly the RFC 3986 "unreserved" set: ALPHA / DIGIT / - . _ ~
        assert set(URL_SAFE) == set(string.ascii_letters + string.digits + "-._~")

    def test_url_safe_size(self):
        assert len(URL_SAFE) == 66

    def test_full_contains_url_safe(self):
        assert set(URL_SAFE) <= set(FULL)

    def test_full_excludes_escaping_hazards(self):
        for ch in "'\"\\` ":
            assert ch not in FULL, f"{ch!r} must never appear in a password"

    def test_no_duplicates(self):
        assert len(set(URL_SAFE)) == len(URL_SAFE)
        assert len(set(FULL)) == len(FULL)


class TestGenerate:
    def test_default_length(self):
        assert len(generate()) == 32

    @pytest.mark.parametrize("length", [4, 8, 32, 64, 256, 1024])
    def test_lengths(self, length):
        assert len(generate(length)) == length

    @pytest.mark.parametrize("length", [0, 1, 3, 1025, -5])
    def test_out_of_range_length_raises(self, length):
        with pytest.raises(ValueError, match="length"):
            generate(length)

    def test_only_charset_characters(self):
        for _ in range(50):
            assert set(generate()) <= set(URL_SAFE)
            assert set(generate(charset=FULL)) <= set(FULL)

    def test_uniqueness(self):
        # 300 32-char passwords colliding would mean the RNG is broken.
        samples = {generate() for _ in range(300)}
        assert len(samples) == 300

    def test_exclude_ambiguous(self):
        for _ in range(50):
            password = generate(exclude_ambiguous=True)
            assert not set(password) & set(AMBIGUOUS)

    def test_exclude_ambiguous_full_set(self):
        for _ in range(50):
            password = generate(charset=FULL, exclude_ambiguous=True)
            assert not set(password) & set(AMBIGUOUS)

    def test_require_all_classes(self):
        for _ in range(50):
            password = generate(8, charset=FULL, require_all_classes=True)
            assert any(c in string.ascii_uppercase for c in password)
            assert any(c in string.ascii_lowercase for c in password)
            assert any(c in string.digits for c in password)
            assert any(not c.isalnum() for c in password)

    def test_tiny_charset_raises(self):
        with pytest.raises(ValueError, match="charset"):
            generate(charset="a")

    def test_charset_deduplicated(self):
        # A repeated character must not be twice as likely.
        password = generate(200, charset="ab" + "b" * 100)
        counts = Counter(password)
        # With a fair coin, 200 flips landing < 55 heads is ~a 5-sigma
        # event; with the biased set it would be the norm.
        assert counts["a"] > 55

    def test_all_characters_reachable(self):
        # Every charset character should appear across a large sample.
        seen = set()
        for _ in range(200):
            seen |= set(generate(64))
        assert seen == set(URL_SAFE)


class TestDistribution:
    def test_flat_frequency(self):
        """Chi-squared uniformity check over ~64k draws.

        With 66 categories (65 degrees of freedom) the 99.9th percentile
        of chi-squared is ~108. A biased modulo implementation (the bug
        rejection sampling exists to prevent) blows far past that.
        """
        n_draws = 64_000
        counts = Counter()
        for _ in range(n_draws // 64):
            counts.update(generate(64))
        expected = n_draws / len(URL_SAFE)
        chi2 = sum((counts[c] - expected) ** 2 / expected for c in URL_SAFE)
        assert chi2 < 120, f"chi-squared {chi2:.1f} suggests biased sampling"


class TestEntropy:
    def test_known_value(self):
        # 66-char set, 32 chars: log2(66) * 32 ≈ 193.42
        assert entropy_bits(66, 32) == pytest.approx(193.42, abs=0.01)

    def test_degenerate_inputs(self):
        assert entropy_bits(0, 32) == 0.0
        assert entropy_bits(66, 0) == 0.0
        assert entropy_bits(1, 10) == 0.0

    def test_matches_math(self):
        assert entropy_bits(94, 20) == pytest.approx(math.log2(94) * 20)


class TestEntropyAllClasses:
    def test_matches_brute_force_enumeration(self):
        # Two chars per class over four classes, length 4: count the
        # accepted strings directly and compare.
        from itertools import product

        charset = "ABab12-."
        classes = ["AB", "ab", "12", "-."]

        def has_all(s):
            return all(any(c in cls for c in s) for cls in classes)

        accepted = sum(1 for p in product(charset, repeat=4) if has_all("".join(p)))
        assert accepted == 384  # 4! * 2**4
        assert entropy_bits_all_classes(charset, 4) == pytest.approx(
            math.log2(accepted)
        )

    def test_always_below_unconstrained_entropy(self):
        for length in (4, 8, 12, 32):
            assert entropy_bits_all_classes(FULL, length) < entropy_bits(
                len(FULL), length
            )

    def test_correction_negligible_at_default_length(self):
        # At 32 chars the rejection correction must be well under a bit.
        gap = entropy_bits(len(FULL), 32) - entropy_bits_all_classes(FULL, 32)
        assert 0 < gap < 0.05

    def test_correction_real_at_short_lengths(self):
        # At length 4 the naive figure overstates by ~3.8 bits.
        gap = entropy_bits(len(FULL), 4) - entropy_bits_all_classes(FULL, 4)
        assert gap > 3

    def test_zero_when_length_below_class_count(self):
        # 4 classes cannot all appear in 3 draws: no accepted strings.
        assert entropy_bits_all_classes(FULL, 3) == 0.0

    def test_degenerate_inputs(self):
        assert entropy_bits_all_classes("a", 10) == 0.0
        assert entropy_bits_all_classes(FULL, 0) == 0.0

    def test_duplicates_in_charset_ignored(self):
        assert entropy_bits_all_classes("Aa1." * 10, 8) == pytest.approx(
            entropy_bits_all_classes("Aa1.", 8)
        )


class TestStrengthLabel:
    @pytest.mark.parametrize(
        ("bits", "label"),
        [
            (200, "excellent"),
            (128, "excellent"),
            (100, "strong"),
            (77.5, "strong"),  # 6-word diceware must not read as "fair"
            (75, "strong"),
            (70, "fair"),
            (60, "fair"),
            (59, "weak"),
            (20, "weak"),
        ],
    )
    def test_thresholds(self, bits, label):
        assert strength_label(bits) == label
