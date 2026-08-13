# password-key — web version

A static, client-side port of the `password_key` generator. No build
step, no npm, no framework: four hand-written files plus one generated
one. Open `index.html` in a browser and it works, including from
`file://` and fully offline.

## Files

| File          | Role                                                        |
| ------------- | ----------------------------------------------------------- |
| `index.html`  | Markup. No inline scripts or styles (the CSP forbids them). |
| `style.css`   | All styling. Dark-first, with a full light theme.           |
| `app.js`      | Generation core (parity with the Python package) + UI.      |
| `wordlist.js` | **Generated** — see below. The EFF Large Wordlist as a JS constant. |
| `_headers`    | Security headers for Cloudflare Pages / Netlify.            |

## Regenerating the wordlist

`wordlist.js` is written only by:

```
python tools/build_web_wordlist.py
```

The script re-reads `src/password_key/data/eff_large_wordlist.txt`,
verifies the pinned SHA-256 (the same digest asserted in
`tests/test_passphrase.py`), and rewrites the JS file. Never edit
`wordlist.js` by hand.

## Local preview

```
python -m http.server 8000 -d web
```

…then open <http://localhost:8000>. (Opening `index.html` directly
also works; the wordlist is embedded, so nothing needs to be fetched.)

## Deploying

Any static host. Point it at the `web/` directory with **no build
command**.

- **Cloudflare Pages / Netlify** — recommended: both honor `_headers`,
  so the full CSP (including `frame-ancestors`) is enforced at the
  HTTP layer.
- **GitHub Pages** — works, but ignores `_headers`. The
  `<meta http-equiv="Content-Security-Policy">` tag in `index.html`
  still forbids all external requests, which is the part that matters.

## Invariants (mirror of the package's ground rules)

- **No third-party scripts, ever.** No analytics, no fonts, no CDNs,
  no ad networks. The page's whole claim is "nothing leaves your
  browser"; one remote `<script>` tag makes that claim false. If the
  page ever carries revenue, it is a single disclosed affiliate *text
  link* (see the comment in the footer), never executable content.
- **All randomness via `crypto.getRandomValues`** with rejection
  sampling — the browser mirror of "all randomness via `secrets`".
  `Math.random()` must never appear.
- **Parity with the package.** Charsets, entropy math (including the
  inclusion–exclusion correction for `require every class`), strength
  thresholds, and wordlist handling in `app.js` mirror
  `src/password_key/generator.py` and `passphrase.py`. Change them
  together or not at all.
- **Zero build tooling.** No `package.json`. The moment this needs a
  bundler it has failed at its job.
