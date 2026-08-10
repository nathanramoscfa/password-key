"""Tests for password_key.passphrase."""

import hashlib
from importlib import resources

import pytest

from password_key.passphrase import (
    WORDLIST_SIZE,
    entropy_bits,
    generate_passphrase,
    load_wordlist,
)


class TestWordlist:
    def test_exact_size(self):
        assert len(load_wordlist()) == WORDLIST_SIZE == 7776

    def test_no_duplicates(self):
        words = load_wordlist()
        assert len(set(words)) == len(words)

    def test_words_are_lowercase_ascii(self):
        for word in load_wordlist():
            assert word
            assert word.isascii()
            assert word == word.lower()
            assert "\t" not in word and " " not in word

    def test_cached(self):
        assert load_wordlist() is load_wordlist()

    def test_matches_canonical_eff_wordlist(self):
        # SHA-256 of https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt
        # A silently modified wordlist would skew every passphrase drawn
        # from it; entropy claims are only valid for the canonical list.
        # CRLF is normalized so checkout line-ending translation cannot
        # produce a false alarm.
        data = (
            resources.files("password_key")
            .joinpath("data/eff_large_wordlist.txt")
            .read_bytes()
        )
        digest = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        assert (
            digest
            == "addd35536511597a02fa0a9ff1e5284677b8883b83e986e43f15a3db996b903e"
        )

    def test_prefix_free(self):
        # No word is a prefix of another, so even separator="" keeps a
        # passphrase uniquely decodable and the entropy figure honest.
        words = sorted(load_wordlist())
        for shorter, longer in zip(words, words[1:]):
            assert not longer.startswith(shorter), (
                f"{shorter!r} is a prefix of {longer!r}"
            )


def _rejoins_into_n_words(phrase: str, sep: str, n: int) -> bool:
    """True if ``phrase`` decomposes into exactly ``n`` wordlist words.

    Four EFF words contain a hyphen themselves (drop-down, felt-tip,
    t-shirt, yo-yo), so with the default ``-`` separator a naive split
    can cut a word in half; try every way of re-joining the pieces.
    """
    wordset = set(load_wordlist())
    parts = phrase.split(sep)

    def walk(i: int, remaining: int) -> bool:
        if i == len(parts):
            return remaining == 0
        if remaining == 0:
            return False
        candidate = ""
        for j in range(i, len(parts)):
            candidate = parts[i] if j == i else candidate + sep + parts[j]
            if candidate in wordset and walk(j + 1, remaining - 1):
                return True
        return False

    return walk(0, n)


class TestGeneratePassphrase:
    def test_default_six_words(self):
        phrase = generate_passphrase()
        assert _rejoins_into_n_words(phrase, "-", 6)

    def test_words_come_from_the_list(self):
        # Space never appears in a word, so splitting on it is exact.
        wordlist = set(load_wordlist())
        for word in generate_passphrase(8, separator=" ").split(" "):
            assert word in wordlist

    def test_separator(self):
        phrase = generate_passphrase(4, separator=" ")
        assert len(phrase.split(" ")) == 4

    def test_capitalize(self):
        for word in generate_passphrase(6, separator=" ", capitalize=True).split(" "):
            assert word[0].isupper()

    def test_hyphenated_words_survive_default_separator(self):
        # Regression: these tests once split naively on "-" and failed
        # ~1% of runs, whenever a hyphenated word was drawn.
        assert _rejoins_into_n_words("t-shirt-abacus-yo-yo", "-", 3)
        assert not _rejoins_into_n_words("t-shirt-abacus-yo-yo", "-", 4)

    def test_uniqueness(self):
        # 100 six-word phrases colliding would mean a broken RNG.
        phrases = {generate_passphrase() for _ in range(100)}
        assert len(phrases) == 100

    @pytest.mark.parametrize("words", [0, -1, 41])
    def test_out_of_range_raises(self, words):
        with pytest.raises(ValueError, match="words"):
            generate_passphrase(words)

    def test_default_is_url_safe(self):
        from password_key.generator import URL_SAFE

        assert set(generate_passphrase()) <= set(URL_SAFE)


class TestEntropy:
    def test_six_words(self):
        # log2(7776) * 6 ≈ 77.5 bits — the EFF's recommended default
        assert entropy_bits(6) == pytest.approx(77.55, abs=0.01)

    def test_degenerate(self):
        assert entropy_bits(0) == 0.0
