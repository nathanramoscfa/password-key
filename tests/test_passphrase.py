"""Tests for password_key.passphrase."""

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


class TestGeneratePassphrase:
    def test_default_six_words(self):
        phrase = generate_passphrase()
        assert len(phrase.split("-")) == 6

    def test_words_come_from_the_list(self):
        wordlist = set(load_wordlist())
        for word in generate_passphrase(8).split("-"):
            assert word in wordlist

    def test_separator(self):
        phrase = generate_passphrase(4, separator=" ")
        assert len(phrase.split(" ")) == 4

    def test_capitalize(self):
        for word in generate_passphrase(6, capitalize=True).split("-"):
            assert word[0].isupper()

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
