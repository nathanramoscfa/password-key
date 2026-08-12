"""password-key: cryptographically secure passwords that are safe to paste anywhere.

The library surface is three functions:

    >>> from password_key import generate, generate_passphrase, entropy_bits
    >>> generate()                      # 32 chars, URL-safe
    >>> generate(48, charset=FULL)      # full punctuation
    >>> generate_passphrase(6)          # diceware passphrase

Everything is drawn from the OS CSPRNG via the :mod:`secrets` module.
"""

from .generator import (
    AMBIGUOUS,
    FULL,
    URL_SAFE,
    entropy_bits,
    entropy_bits_all_classes,
    generate,
    strength_label,
)
from .passphrase import generate_passphrase, load_wordlist

__version__ = "1.1.1"

__all__ = [
    "AMBIGUOUS",
    "FULL",
    "URL_SAFE",
    "__version__",
    "entropy_bits",
    "entropy_bits_all_classes",
    "generate",
    "generate_passphrase",
    "load_wordlist",
    "strength_label",
]
