"""Cryptographically secure random password generation.

Every random draw in this module goes through :mod:`secrets`, which is
backed by the operating system's CSPRNG. ``random.Random`` is seeded
pseudo-randomness and must never be used for a credential.

``secrets.choice`` performs unbiased selection internally (rejection
sampling), so no character in a charset is ever more likely than
another.
"""

from __future__ import annotations

import math
import secrets
import string

__all__ = [
    "AMBIGUOUS",
    "FULL",
    "URL_SAFE",
    "entropy_bits",
    "entropy_bits_all_classes",
    "generate",
    "strength_label",
]

#: The default charset: letters, digits, and ``- _ . ~`` — the four
#: punctuation characters classed as "unreserved" by RFC 3986. These
#: carry no special meaning in a URL, a single-quoted SQL literal, or a
#: shell, so a password built from this set can be pasted anywhere
#: without escaping or percent-encoding.
URL_SAFE = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_.~"

#: The full punctuation set, for systems that mandate a symbol class.
#: Deliberately excludes quotes, backslash, backtick, and space: they
#: cost nothing in entropy at any reasonable length, and they are the
#: characters that turn a working password into an escaping bug.
FULL = (
    string.ascii_uppercase
    + string.ascii_lowercase
    + string.digits
    + "!#$%&()*+,-.:;<=>?@[]^{|}_~"
)

#: Characters easily confused with one another when a password must be
#: read aloud or typed from paper: 0/O, 1/l/I, and |.
AMBIGUOUS = "0O1lI|"

#: Character classes used by ``require_all_classes``.
_CLASSES = (
    string.ascii_uppercase,
    string.ascii_lowercase,
    string.digits,
)

MIN_LENGTH = 4
MAX_LENGTH = 1024


def entropy_bits(charset_size: int, length: int) -> float:
    """Bits of entropy for ``length`` independent uniform draws."""
    if charset_size < 2 or length < 1:
        return 0.0
    return math.log2(charset_size) * length


def entropy_bits_all_classes(charset: str, length: int) -> float:
    """Bits of entropy for ``generate(..., require_all_classes=True)``.

    Rejection keeps the output uniform, but uniform over a *smaller*
    set: every string missing a class is discarded. The honest figure
    is therefore ``log2`` of the accepted-string count, computed
    exactly by inclusion-exclusion over the classes present in the
    charset. At 32 characters the correction is ~0.03 bits; at the
    short lengths where composition rules actually bite it is real
    (~3.8 bits at length 4 with the FULL set).
    """
    chars = set(charset)
    n = len(chars)
    if n < 2 or length < 1:
        return 0.0
    sizes = [len(chars & set(cls)) for cls in _CLASSES]
    sizes = [s for s in sizes if s]
    symbols = sum(1 for ch in chars if not ch.isalnum())
    if symbols:
        sizes.append(symbols)
    accepted = 0
    for subset in range(2 ** len(sizes)):
        excluded = sum(s for i, s in enumerate(sizes) if subset >> i & 1)
        sign = -1 if bin(subset).count("1") % 2 else 1
        accepted += sign * (n - excluded) ** length
    if accepted < 2:
        return 0.0
    return math.log2(accepted)


def strength_label(bits: float) -> str:
    """A human word for an entropy figure.

    Thresholds follow common guidance: 128 bits is beyond any
    brute-force attack; ~75+ bits resists offline cracking on serious
    hardware (a 6-word diceware passphrase, ~77.5 bits, sits here by
    design); below ~60 is only fit for throwaway accounts.
    """
    if bits >= 128:
        return "excellent"
    if bits >= 75:
        return "strong"
    if bits >= 60:
        return "fair"
    return "weak"


def _has_all_classes(password: str, charset: str) -> bool:
    """True if the password contains every class present in the charset."""
    classes = [c for c in _CLASSES if any(ch in charset for ch in c)]
    symbols = "".join(ch for ch in charset if not ch.isalnum())
    if symbols:
        classes.append(symbols)
    return all(any(ch in cls for ch in password) for cls in classes)


def generate(
    length: int = 32,
    *,
    charset: str = URL_SAFE,
    exclude_ambiguous: bool = False,
    require_all_classes: bool = False,
) -> str:
    """Generate a random password.

    Args:
        length: Number of characters, ``MIN_LENGTH``-``MAX_LENGTH``.
        charset: Characters to draw from. Defaults to :data:`URL_SAFE`.
        exclude_ambiguous: Drop ``0 O 1 l I |`` from the charset, for
            passwords that must survive being read aloud or typed from
            paper.
        require_all_classes: Regenerate until the password contains at
            least one character from every class present in the charset
            (upper, lower, digit, and symbol if any). Uses rejection
            sampling, so the result is still uniform over the accepted
            set. Only meaningful at short lengths or for systems that
            enforce composition rules; at 32 characters a miss is
            already rare.

    Returns:
        The generated password.

    Raises:
        ValueError: If ``length`` is out of range or the charset is
            too small.
    """
    if not MIN_LENGTH <= length <= MAX_LENGTH:
        raise ValueError(
            f"length must be between {MIN_LENGTH} and {MAX_LENGTH}, got {length}"
        )
    if exclude_ambiguous:
        charset = "".join(ch for ch in charset if ch not in AMBIGUOUS)
    if len(set(charset)) < 2:
        raise ValueError("charset must contain at least 2 distinct characters")
    charset = "".join(sorted(set(charset)))

    while True:
        password = "".join(secrets.choice(charset) for _ in range(length))
        if not require_all_classes or _has_all_classes(password, charset):
            return password
