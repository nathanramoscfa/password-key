// password-key — client-side generator.
//
// Parity contract: the generation core below mirrors
// src/password_key/generator.py and src/password_key/passphrase.py.
// Every random draw goes through crypto.getRandomValues — the
// browser's CSPRNG, the same OS entropy source the Python package
// reaches through `secrets` — with rejection sampling, so no
// character or word is ever more likely than another. Math.random()
// must never appear in this file.
"use strict";

/* ===================== generation core ===================== */

const UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const LOWER = "abcdefghijklmnopqrstuvwxyz";
const DIGITS = "0123456789";

// RFC 3986 "unreserved" punctuation only — paste anywhere, escape nothing.
const URL_SAFE = UPPER + LOWER + DIGITS + "-_.~";
// Full punctuation minus quotes, backslash, backtick, and space.
const FULL = UPPER + LOWER + DIGITS + "!#$%&()*+,-.:;<=>?@[]^{|}_~";
const AMBIGUOUS = "0O1lI|";
const CLASSES = [UPPER, LOWER, DIGITS];
const MIN_LENGTH = 4;
const MAX_LENGTH = 1024;
const WORDLIST_SIZE = 7776; // 6^5, the classic diceware size
const BITS_PER_WORD = Math.log2(WORDLIST_SIZE);

const randBuf = new Uint32Array(1);

/** Unbiased integer in [0, n): rejection sampling over a 32-bit draw,
 *  mirroring what secrets.choice does internally. */
function randomBelow(n) {
  const limit = Math.floor(0x100000000 / n) * n;
  do {
    crypto.getRandomValues(randBuf);
  } while (randBuf[0] >= limit);
  return randBuf[0] % n;
}

function choice(seq) {
  return seq[randomBelow(seq.length)];
}

function normalizeCharset(charset, excludeAmbiguous) {
  let chars = [...charset];
  if (excludeAmbiguous) {
    chars = chars.filter((ch) => !AMBIGUOUS.includes(ch));
  }
  const unique = [...new Set(chars)].sort(); // ASCII sort == Python sorted()
  if (unique.length < 2) {
    throw new Error("charset must contain at least 2 distinct characters");
  }
  return unique.join("");
}

/** Character classes present in the charset: upper, lower, digit, and
 *  the charset's symbols if any (port of generator._has_all_classes). */
function classesIn(charset) {
  const classes = CLASSES.filter((cls) =>
    [...cls].some((ch) => charset.includes(ch))
  );
  const symbols = [...charset].filter((ch) => !/[0-9A-Za-z]/.test(ch)).join("");
  if (symbols) classes.push(symbols);
  return classes;
}

function hasAllClasses(password, charset) {
  return classesIn(charset).every((cls) =>
    [...password].some((ch) => cls.includes(ch))
  );
}

function generatePassword(length, opts) {
  const { charset = URL_SAFE, excludeAmbiguous = false, requireAllClasses = false } =
    opts || {};
  if (!(length >= MIN_LENGTH && length <= MAX_LENGTH)) {
    throw new Error(`length must be between ${MIN_LENGTH} and ${MAX_LENGTH}`);
  }
  const cs = normalizeCharset(charset, excludeAmbiguous);
  for (;;) {
    let out = "";
    for (let i = 0; i < length; i++) out += choice(cs);
    if (!requireAllClasses || hasAllClasses(out, cs)) return out;
  }
}

function entropyBits(charsetSize, length) {
  if (charsetSize < 2 || length < 1) return 0;
  return Math.log2(charsetSize) * length;
}

/** log2 of the accepted-string count under require-all-classes
 *  rejection, by inclusion-exclusion — port of
 *  generator.entropy_bits_all_classes. Python computes the sum in
 *  exact integers; floats are fine here because the correction beyond
 *  ~40 characters is smaller than double precision anyway, and we
 *  fall back to the naive figure if the terms overflow. */
function entropyBitsAllClasses(charset, length) {
  const chars = new Set(charset);
  const n = chars.size;
  if (n < 2 || length < 1) return 0;
  const sizes = CLASSES.map(
    (cls) => [...cls].filter((ch) => chars.has(ch)).length
  ).filter((s) => s > 0);
  const symbols = [...chars].filter((ch) => !/[0-9A-Za-z]/.test(ch)).length;
  if (symbols) sizes.push(symbols);
  let accepted = 0;
  for (let subset = 0; subset < 1 << sizes.length; subset++) {
    let excluded = 0;
    let bitsSet = 0;
    for (let i = 0; i < sizes.length; i++) {
      if ((subset >> i) & 1) {
        excluded += sizes[i];
        bitsSet++;
      }
    }
    accepted += (bitsSet % 2 ? -1 : 1) * Math.pow(n - excluded, length);
  }
  if (!Number.isFinite(accepted)) return entropyBits(n, length);
  if (accepted < 2) return 0;
  return Math.log2(accepted);
}

/** Thresholds mirror generator.strength_label. */
function strengthLabel(bits) {
  if (bits >= 128) return "excellent";
  if (bits >= 75) return "strong";
  if (bits >= 60) return "fair";
  return "weak";
}

function generatePassphraseWords(count) {
  if (!(count >= 1 && count <= 40)) {
    throw new Error("words must be between 1 and 40");
  }
  const out = [];
  for (let i = 0; i < count; i++) out.push(choice(EFF_WORDLIST));
  return out;
}

/* ===================== UI ===================== */

const $ = (id) => document.getElementById(id);
const els = {
  tabPassword: $("tab-password"),
  tabPassphrase: $("tab-passphrase"),
  tablist: $("tablist"),
  panelPassword: $("panel-password"),
  panelPassphrase: $("panel-passphrase"),
  secret: $("secret"),
  copy: $("copy"),
  regen: $("regen"),
  dieGlyph: $("die-glyph"),
  bits: $("bits"),
  strength: $("strength"),
  detail: $("detail"),
  gaugeFill: $("gauge-fill"),
  lenRange: $("len-range"),
  lenNum: $("len-num"),
  charset: $("charset"),
  noAmbiguous: $("no-ambiguous"),
  allClasses: $("all-classes"),
  wordsRange: $("words-range"),
  wordsNum: $("words-num"),
  separator: $("separator"),
  capitalize: $("capitalize"),
};

const GAUGE_MAX_BITS = 160; // gauge scale; ticks sit at 60 / 75 / 128
const STRENGTHS = ["weak", "fair", "strong", "excellent"];

const state = {
  mode: "password",
  password: "", // last drawn password
  words: [], // last drawn passphrase words, lowercase
};

function clampNumber(input, fallback) {
  const value = parseInt(input.value, 10);
  const min = parseInt(input.min, 10);
  const max = parseInt(input.max, 10);
  if (Number.isNaN(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

function passwordCharset() {
  return normalizeCharset(
    els.charset.value === "full" ? FULL : URL_SAFE,
    els.noAmbiguous.checked
  );
}

function capitalized(word) {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

function currentSecret() {
  if (state.mode === "password") return state.password;
  const words = els.capitalize.checked
    ? state.words.map(capitalized)
    : state.words;
  return words.join(els.separator.value);
}

function reroll() {
  if (state.mode === "password") {
    state.password = generatePassword(clampNumber(els.lenNum, 32), {
      charset: els.charset.value === "full" ? FULL : URL_SAFE,
      excludeAmbiguous: els.noAmbiguous.checked,
      requireAllClasses: els.allClasses.checked,
    });
  } else {
    state.words = generatePassphraseWords(clampNumber(els.wordsNum, 6));
  }
  render();
}

function renderSecret() {
  els.secret.textContent = "";
  if (state.mode === "password") {
    for (const ch of state.password) {
      const span = document.createElement("span");
      span.textContent = ch;
      if (/[0-9]/.test(ch)) span.className = "ch-d";
      else if (!/[A-Za-z]/.test(ch)) span.className = "ch-s";
      els.secret.appendChild(span);
    }
  } else {
    // Words are appended as units — 4 EFF words contain hyphens, so
    // the joined string must never be re-split on the separator.
    const sep = els.separator.value;
    state.words.forEach((word, i) => {
      if (i > 0 && sep) {
        const span = document.createElement("span");
        span.className = "ch-s";
        span.textContent = sep;
        els.secret.appendChild(span);
      }
      els.secret.appendChild(
        document.createTextNode(els.capitalize.checked ? capitalized(word) : word)
      );
    });
  }
}

function renderMeter() {
  let bits;
  let detail;
  if (state.mode === "password") {
    const cs = passwordCharset();
    const length = state.password.length;
    bits = els.allClasses.checked
      ? entropyBitsAllClasses(cs, length)
      : entropyBits(cs.length, length);
    detail = `${length} chars · ${cs.length}-char set`;
  } else {
    bits = BITS_PER_WORD * state.words.length;
    detail = `${state.words.length} words · EFF list (7,776)`;
  }
  const label = strengthLabel(bits);
  els.bits.textContent = bits.toFixed(1);
  els.strength.textContent = label;
  els.detail.textContent = detail;
  for (const name of STRENGTHS) {
    els.strength.classList.toggle(name, name === label);
    els.gaugeFill.classList.toggle(name, name === label);
  }
  const pct = Math.min(100, (bits / GAUGE_MAX_BITS) * 100);
  els.gaugeFill.style.width = pct.toFixed(2) + "%";
}

function render() {
  renderSecret();
  renderMeter();
}

function setMode(mode, focusTab) {
  state.mode = mode;
  const isPassword = mode === "password";
  els.tabPassword.classList.toggle("is-active", isPassword);
  els.tabPassphrase.classList.toggle("is-active", !isPassword);
  els.tabPassword.setAttribute("aria-selected", String(isPassword));
  els.tabPassphrase.setAttribute("aria-selected", String(!isPassword));
  els.panelPassword.hidden = !isPassword;
  els.panelPassphrase.hidden = isPassword;
  if (focusTab) (isPassword ? els.tabPassword : els.tabPassphrase).focus();
  reroll();
}

function legacyCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
  } finally {
    ta.remove();
  }
}

let copyTimer = 0;
async function copySecret() {
  const text = currentSecret();
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    legacyCopy(text);
  }
  els.copy.textContent = "Copied ✓";
  els.copy.classList.add("is-done");
  clearTimeout(copyTimer);
  copyTimer = setTimeout(() => {
    els.copy.textContent = "Copy";
    els.copy.classList.remove("is-done");
  }, 1400);
}

function spinDie() {
  els.dieGlyph.classList.remove("spin");
  // Force a reflow so re-adding the class restarts the animation.
  void els.dieGlyph.getBoundingClientRect();
  els.dieGlyph.classList.add("spin");
}

/* ---- wiring ---- */

els.tabPassword.addEventListener("click", () => setMode("password"));
els.tabPassphrase.addEventListener("click", () => setMode("passphrase"));
els.tablist.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    setMode(state.mode === "password" ? "passphrase" : "password", true);
  }
});

els.copy.addEventListener("click", copySecret);
els.regen.addEventListener("click", () => {
  spinDie();
  reroll();
});

// Sliders and their paired number inputs stay in sync; the slider pegs
// at its own max when the typed value exceeds it.
els.lenRange.addEventListener("input", () => {
  els.lenNum.value = els.lenRange.value;
  reroll();
});
els.lenNum.addEventListener("change", () => {
  els.lenNum.value = clampNumber(els.lenNum, 32);
  els.lenRange.value = Math.min(parseInt(els.lenRange.max, 10), els.lenNum.value);
  reroll();
});
els.wordsRange.addEventListener("input", () => {
  els.wordsNum.value = els.wordsRange.value;
  reroll();
});
els.wordsNum.addEventListener("change", () => {
  els.wordsNum.value = clampNumber(els.wordsNum, 6);
  els.wordsRange.value = Math.min(
    parseInt(els.wordsRange.max, 10),
    els.wordsNum.value
  );
  reroll();
});

// Redraw-on-change controls.
for (const el of [els.charset, els.noAmbiguous, els.allClasses]) {
  el.addEventListener("change", reroll);
}
// Presentation-only controls: re-render the words already drawn.
els.separator.addEventListener("input", render);
els.capitalize.addEventListener("change", render);

reroll();
