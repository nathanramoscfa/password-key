"""Diceware-style passphrase generation.

Uses the EFF Large Wordlist (7,776 words, ~12.9 bits of entropy per
word), the modern standard for diceware passphrases. Words are drawn
with :mod:`secrets` — the OS CSPRNG — never seeded pseudo-randomness.

A passphrase trades length for memorability: ``mumbling-doorknob-
strife-unpaved-abridge-cementer`` is far easier to type on a phone or
read over a call than 20 random characters of the same strength.
"""

from __future__ import annotations

import math
import secrets
from importlib import resources

__all__ = ["WORDLIST_SIZE", "entropy_bits", "generate_passphrase", "load_wordlist"]

WORDLIST_SIZE = 7776  # 6^5, the classic diceware size

_wordlist_cache: tuple[str, ...] | None = None


def load_wordlist() -> tuple[str, ...]:
    """Load the bundled EFF Large Wordlist (cached after first read)."""
    global _wordlist_cache
    if _wordlist_cache is None:
        text = (
            resources.files("password_key")
            .joinpath("data/eff_large_wordlist.txt")
            .read_text(encoding="utf-8")
        )
        # Each line is "<dice roll>\t<word>"; only the word matters here.
        words = tuple(
            line.split("\t")[-1].strip() for line in text.splitlines() if line.strip()
        )
        if len(words) != WORDLIST_SIZE:
            raise RuntimeError(
                f"bundled wordlist is corrupt: expected {WORDLIST_SIZE} words, "
                f"got {len(words)}"
            )
        _wordlist_cache = words
    return _wordlist_cache


def entropy_bits(words: int) -> float:
    """Bits of entropy for ``words`` independent draws from the list."""
    if words < 1:
        return 0.0
    return math.log2(WORDLIST_SIZE) * words


def generate_passphrase(
    words: int = 6,
    *,
    separator: str = "-",
    capitalize: bool = False,
) -> str:
    """Generate a random diceware passphrase.

    Args:
        words: Number of words. The EFF recommends six (~77 bits);
            seven (~90 bits) comfortably clears offline-cracking
            territory.
        separator: String placed between words. The default ``-`` keeps
            the passphrase URL-safe end to end.
        capitalize: Capitalize each word, for systems that demand an
            uppercase character.

    Raises:
        ValueError: If ``words`` is out of range.
    """
    if not 1 <= words <= 40:
        raise ValueError(f"words must be between 1 and 40, got {words}")
    wordlist = load_wordlist()
    chosen = [secrets.choice(wordlist) for _ in range(words)]
    if capitalize:
        chosen = [w.capitalize() for w in chosen]
    return separator.join(chosen)
