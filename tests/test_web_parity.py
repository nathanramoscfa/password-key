"""Parity tests for the browser build in ``web/``.

``web/app.js`` is a hand-written port of :mod:`password_key.generator` and
:mod:`password_key.passphrase`. Two implementations of the same generator
drift silently: nothing crashes when a charset loses a character or a
strength threshold moves — the page keeps producing plausible-looking
passwords that no longer match the package, and the entropy figure it
prints stops being true.

So the constants are compared here, against the real Python objects rather
than against a second copy of the expected values. The behavioural parity
suite (uniformity, rejection sampling, the inclusion-exclusion correction)
needs a JS engine and lives outside pytest; these are the assertions that
can be made from Python alone, and they are the ones that catch a careless
edit.
"""

import json
import re
from pathlib import Path

import pytest

from password_key import generator, passphrase

WEB = Path(__file__).resolve().parent.parent / "web"
APP_JS = WEB / "app.js"
INDEX_HTML = WEB / "index.html"
WORDLIST_JS = WEB / "wordlist.js"


def _strip_js_comments(src):
    """Return ``src`` with comments removed, strings preserved.

    The files under ``web/`` document the very things these tests forbid
    ("Math.random must never appear here"), so a plain substring search
    would match the documentation instead of a violation.

    Quote-aware but not regex-literal-aware, which is safe only while no
    regex in the file contains ``//`` or ``/*`` — true today, as they are
    all simple character classes.
    """
    out = []
    state = "code"
    i = 0
    while i < len(src):
        ch = src[i]
        nxt = src[i + 1] if i + 1 < len(src) else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line"
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block"
                i += 2
                continue
            if ch in "'\"`":
                state = ch
            out.append(ch)
        elif state == "line":
            if ch == "\n":
                state = "code"
                out.append(ch)
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
        else:  # inside a string literal
            if ch == "\\":
                out.append(ch + nxt)
                i += 2
                continue
            if ch == state:
                state = "code"
            out.append(ch)
        i += 1
    return "".join(out)


# A term is a double-quoted literal or an identifier; matching terms rather
# than splitting on "+" is what keeps the "+" inside FULL's punctuation from
# being read as concatenation.
_TERM = re.compile(r'"((?:[^"\\]|\\.)*)"|([A-Za-z_][A-Za-z0-9_]*)')
# Greedy to the LAST semicolon on the line, not the first: FULL's punctuation
# set contains a ";" of its own, and stopping at it silently truncates the
# charset to letters and digits — which is exactly the drift this file exists
# to catch, so the parser must not reproduce it.
_STR_CONST = re.compile(r"^const ([A-Z_][A-Z0-9_]*) = (.+);\s*$", re.M)
_NUM_CONST = re.compile(r"^const ([A-Z_][A-Z0-9_]*) = (\d+);", re.M)


@pytest.fixture(scope="module")
def app_js():
    return _strip_js_comments(APP_JS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def js_strings(app_js):
    """Resolve the module-level string constants in app.js."""
    resolved = {}
    for name, expr in _STR_CONST.findall(app_js):
        parts = []
        for literal, ident in _TERM.findall(expr):
            if ident:
                if ident not in resolved:
                    parts = None
                    break
                parts.append(resolved[ident])
            else:
                parts.append(literal.encode().decode("unicode_escape"))
        if parts:
            resolved[name] = "".join(parts)
    return resolved


@pytest.fixture(scope="module")
def js_numbers(app_js):
    return {name: int(value) for name, value in _NUM_CONST.findall(app_js)}


class TestCharsets:
    """The charsets are the generator's whole security surface."""

    def test_url_safe_matches(self, js_strings):
        assert js_strings["URL_SAFE"] == generator.URL_SAFE

    def test_full_matches(self, js_strings):
        assert js_strings["FULL"] == generator.FULL

    def test_ambiguous_matches(self, js_strings):
        assert js_strings["AMBIGUOUS"] == generator.AMBIGUOUS

    def test_no_quotes_or_backslash_in_full(self, js_strings):
        # The Python FULL set deliberately excludes the characters that turn
        # a working password into an escaping bug; the port must too.
        for char in "'\"\\` ":
            assert char not in js_strings["FULL"]


class TestBounds:
    def test_length_bounds_match(self, js_numbers):
        assert js_numbers["MIN_LENGTH"] == generator.MIN_LENGTH
        assert js_numbers["MAX_LENGTH"] == generator.MAX_LENGTH

    def test_wordlist_size_matches(self, js_numbers):
        assert js_numbers["WORDLIST_SIZE"] == passphrase.WORDLIST_SIZE

    def test_strength_thresholds_match(self, app_js):
        # strength_label's boundaries, read back out of the port. Each is
        # the point where the page starts telling a visitor something
        # different about their password.
        for bits in (128, 75, 60):
            assert f"bits >= {bits}" in app_js
        labels = re.findall(r'return "(\w+)";', app_js)
        for word in ("excellent", "strong", "fair", "weak"):
            assert word in labels
            assert (
                generator.strength_label(
                    {"excellent": 128, "strong": 75, "fair": 60, "weak": 0}[word]
                )
                == word
            )


class TestWordlist:
    def test_bundled_wordlist_is_identical(self):
        source = WORDLIST_JS.read_text(encoding="utf-8")
        match = re.search(r"Object\.freeze\((\[.*\])\)", source, re.S)
        assert match, "no frozen word array found in web/wordlist.js"
        assert tuple(json.loads(match.group(1))) == passphrase.load_wordlist()

    def test_is_generated_not_hand_edited(self):
        # The only writer is tools/build_web_wordlist.py, which verifies the
        # canonical EFF digest before it emits anything.
        head = WORDLIST_JS.read_text(encoding="utf-8")[:400]
        assert "tools/build_web_wordlist.py" in head


class TestRandomness:
    def test_draws_from_the_browser_csprng(self, app_js):
        assert "crypto.getRandomValues" in app_js

    def test_never_uses_math_random(self, app_js):
        # Seeded, predictable, and indistinguishable from real randomness
        # to anyone reading the output.
        assert not re.search(r"Math\s*\.\s*random", app_js)

    def test_rejection_sampling_is_present(self, app_js):
        # Plain "% n" on a 32-bit draw is biased toward the low values;
        # randomBelow must reject the ragged tail before taking a modulus.
        assert "randomBelow" in app_js
        assert "limit" in app_js


class TestNoNetwork:
    """The page's claim is that nothing leaves the browser."""

    @pytest.mark.parametrize(
        "api",
        ["fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "EventSource"],
    )
    def test_no_network_api(self, app_js, api):
        assert api not in app_js

    def test_no_off_origin_resources(self):
        html = re.sub(
            r"<!--.*?-->", "", INDEX_HTML.read_text(encoding="utf-8"), flags=re.S
        )
        sources = re.findall(r'<script\b[^>]*\bsrc="([^"]+)"', html)
        sources += re.findall(
            r'<link\b[^>]*\brel="stylesheet"[^>]*\bhref="([^"]+)"', html
        )
        assert sources, "found no resources at all - the pattern is wrong"
        for url in sources:
            assert not re.match(r"(?:[a-z][a-z0-9+.-]*:)?//", url, re.I), url

    def test_no_inline_script(self):
        # index.html ships a CSP without 'unsafe-inline'; an inline script
        # would be dead code that fails only in a real browser.
        html = re.sub(
            r"<!--.*?-->", "", INDEX_HTML.read_text(encoding="utf-8"), flags=re.S
        )
        assert not re.search(r"<script\b(?![^>]*\bsrc=)[^>]*>", html, re.I)


class TestMarkup:
    def test_every_element_app_js_needs_exists(self):
        # app.js resolves its elements once, at load, and a missing id
        # surfaces as a TypeError in the console - not as a broken page.
        app_source = APP_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        wanted = set(re.findall(r'\$\("([^"]+)"\)', app_source))
        assert wanted, "no element lookups found in app.js"
        for element_id in sorted(wanted):
            assert f'id="{element_id}"' in html, f"web/index.html has no #{element_id}"
