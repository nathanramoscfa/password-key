# Third-party notices

`password-key` itself is MIT licensed — see [LICENSE](LICENSE). It has no
runtime dependencies. It does bundle one third-party data file, whose
license is reproduced below.

This file is distributed inside the wheel and the sdist alongside
`LICENSE`, so the attribution travels with the data it applies to.

## EFF Large Wordlist

`src/password_key/data/eff_large_wordlist.txt`

The bundled EFF Large Wordlist is by the Electronic Frontier Foundation
and is licensed under the Creative Commons Attribution 3.0 License
(CC BY 3.0):

- Source: <https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases>
- License: <https://creativecommons.org/licenses/by/3.0/>

The list is bundled byte-for-byte as published, and its SHA-256 is
verified against the canonical EFF list by a test on every CI run, so
this attribution stays attached to the data it actually describes.
