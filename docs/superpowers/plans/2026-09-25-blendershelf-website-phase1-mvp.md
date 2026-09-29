# BlenderShelf Website Phase 1 (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public, bilingual (RU/EN) one-page website that lets any BlenderShelf user download the addon version matching their Blender install, and watch/read the guide — with zero backend and zero hosting cost.

**Architecture:** A single static HTML page (`site/index.html`) with vanilla JS, hosted on GitHub Pages from a new public repo. A manually-maintained `versions.json` manifest maps addon releases to Blender-version compatibility ranges; a small pure-function module (`site/assets/logic.js`) picks the right entry for whatever Blender version the visitor selects. No build step, no framework, no server.

**Tech Stack:** Plain HTML/CSS/vanilla JS, GitHub Pages, GitHub Releases. Node.js (`node --test`, built-in, no dependency) used only at dev time to test the pure logic in `logic.js` — nothing Node-related ships to the site.

**Spec:** `docs/superpowers/specs/2026-09-25-blendershelf-website-design.md`

## Global Constraints

- New repo is **public**, on the owner's **personal** GitHub account (not an org).
- Hosting is **GitHub Pages**, free subdomain only — no purchased domain.
- **No build tooling** — plain HTML/CSS/JS, no bundler, no npm dependencies shipped to the site.
- **No LLM-based feedback triage** anywhere in this phase (feedback form itself is Phase 2, out of scope here).
- **No self-hosted video** — guide videos are YouTube embeds only.
- Current addon version at time of writing: `0.1.0` (from `bl_info` in the live 4.4 addon copy), minimum supported Blender: `4.1.0`. Treat `bl_info` as the source of truth if it has changed by the time this plan is executed — re-check before Task 8.
- Bilingual (RU/EN) content is mandatory throughout; RU is the default/first language.

## Review Focus

- `versions.json` fails to load (network error, 404, malformed JSON) → the Download section must show a fallback message and a direct link to the latest release, not a blank/broken UI. (Task 5)
- Visitor's Blender version is older than every entry in `versions.json` → must fall back to the closest (oldest) compatible version with an "unofficial/at your own risk" note, not show nothing. (Task 3)
- `localStorage` is unavailable (private browsing, blocked storage) → the language toggle must still work for the current page view without throwing an uncaught error. (Task 4)
- `versions.json` is an empty array (e.g. mid-setup) → the Download section must show the "unavailable" message instead of crashing on `undefined`. (Task 3, Task 5)
- GitHub Pages can serve a cached, stale `versions.json` for a few minutes right after a new release is published — this is a known operational quirk, not a bug to fix in code; documented so the owner doesn't mistake it for a broken site. (Task 8)

---

## Task 1: Repo scaffold — clean addon source + gitignore

**Files:**
- Create: `addon/` (directory, populated from the existing build output)
- Create: `.gitignore`
- Modify: none

**Interfaces:**
- Consumes: the existing `build_release.py` (unchanged in this task) and the live addon at `%APPDATA%\Blender Foundation\Blender\4.4\scripts\addons\BlenderShelf`.
- Produces: `addon/` — a clean, shareable copy of the addon source (no `shelf_config.json`, no `backups/`, no `__pycache__`) for other tasks and for future releases to zip from.

- [ ] **Step 1: Run the existing build script to produce a clean staged copy**

Run (from `C:\Users\denis\BlenderShelf-releases`):
```bash
python build_release.py
```
Expected output: `Clean release built: .../dist/BlenderShelf.zip` and the staged folder `dist/BlenderShelf/` now exists (this reuses the existing exclude logic — `shelf_config.json`, `backups/`, `__pycache__` are already stripped).

- [ ] **Step 2: Copy the staged copy into `addon/`**

```bash
rm -rf addon
cp -r dist/BlenderShelf addon
```

- [ ] **Step 3: Verify the copy is clean**

Run:
```bash
find addon -iname "shelf_config.json" -o -iname "backups" -o -iname "__pycache__"
```
Expected: no output (nothing matches).

- [ ] **Step 4: Add `.gitignore`**

```gitignore
dist/
backups/
blender-icons.7z
blender-icons/
__pycache__/
*.pyc
```

- [ ] **Step 5: Commit**

```bash
git add addon .gitignore
git commit -m "chore: scaffold clean addon/ source and gitignore build artifacts"
```

---

## Task 2: Create the public GitHub repository and push

**Files:** none (repository/remote operation only)

**Interfaces:**
- Consumes: the local git repo at `C:\Users\denis\BlenderShelf-releases` (already initialized, currently holds the spec commit + Task 1's commit).
- Produces: a live public GitHub repository URL, referenced by name `<GITHUB_OWNER>/BlenderShelf` in later tasks (Task 4, Task 5, Task 7, Task 8 need the real owner name — get it from the human partner in this task).

- [ ] **Step 1: Human creates the repository**

This step needs the human partner (no scripted repo creation — avoids requiring a GitHub token just to create one repo): go to https://github.com/new, repository name `BlenderShelf`, visibility **Public**, do NOT initialize with a README/license/gitignore (this repo already has content). Click Create.

- [ ] **Step 2: Record the exact owner/repo path**

Ask the human partner for the resulting URL (e.g. `https://github.com/denisghome/BlenderShelf`) and note the `<GITHUB_OWNER>` value — every later task that hardcodes a GitHub URL uses this exact value.

- [ ] **Step 3: Add the remote and push**

```bash
git remote add origin https://github.com/<GITHUB_OWNER>/BlenderShelf.git
git branch -M main
git push -u origin main
```

- [ ] **Step 4: Verify**

Run:
```bash
git ls-remote origin
```
Expected: lists `refs/heads/main` pointing at the current commit — confirms the push landed.

---

## Task 3: Version-matching logic (pure functions + tests)

**Files:**
- Create: `site/assets/logic.js`
- Create: `tests/logic.test.js`

**Interfaces:**
- Consumes: nothing (pure functions, no DOM, no fetch).
- Produces: `compareVersions(a: string, b: string) -> number` and `pickVersionForBlender(versions: Array<{addon_version, blender_min, blender_max, url}>, blenderVersion: string) -> {version, exact: boolean} | null`. Task 5 imports and calls `pickVersionForBlender` from the browser via a plain `<script>` tag (not a module import — see the dual CommonJS/global export pattern below).

- [ ] **Step 1: Write the failing tests**

Create `tests/logic.test.js`:
```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { compareVersions, pickVersionForBlender } = require('../site/assets/logic.js');

test('compareVersions orders correctly', () => {
  assert.equal(compareVersions('4.1.0', '4.1.0'), 0);
  assert.ok(compareVersions('4.4.3', '4.1.0') > 0);
  assert.ok(compareVersions('3.6.0', '4.1.0') < 0);
});

test('pickVersionForBlender matches an open-ended range (blender_max: null)', () => {
  const versions = [
    { addon_version: '0.1.0', blender_min: '4.1.0', blender_max: null, url: 'a' },
  ];
  const result = pickVersionForBlender(versions, '4.4.3');
  assert.equal(result.exact, true);
  assert.equal(result.version.addon_version, '0.1.0');
});

test('pickVersionForBlender matches a closed range and prefers the newest matching entry', () => {
  const versions = [
    { addon_version: '0.2.0', blender_min: '4.2.0', blender_max: null, url: 'a' },
    { addon_version: '0.1.0', blender_min: '3.6.0', blender_max: '4.1.9', url: 'b' },
  ];
  const result = pickVersionForBlender(versions, '4.0.0');
  assert.equal(result.exact, true);
  assert.equal(result.version.addon_version, '0.1.0');
});

test('pickVersionForBlender falls back to the closest entry when nothing matches, flagged not-exact', () => {
  const versions = [
    { addon_version: '0.1.0', blender_min: '4.1.0', blender_max: null, url: 'a' },
  ];
  const result = pickVersionForBlender(versions, '3.0.0');
  assert.equal(result.exact, false);
  assert.equal(result.version.addon_version, '0.1.0');
});

test('pickVersionForBlender returns null for an empty version list', () => {
  assert.equal(pickVersionForBlender([], '4.1.0'), null);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test tests/`
Expected: FAIL — `Cannot find module '../site/assets/logic.js'` (file doesn't exist yet).

- [ ] **Step 3: Implement `logic.js`**

Create `site/assets/logic.js`:
```javascript
function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na !== nb) return na - nb;
  }
  return 0;
}

function pickVersionForBlender(versions, blenderVersion) {
  if (!versions || versions.length === 0) return null;

  const inRange = versions.filter((v) => {
    const aboveMin = compareVersions(blenderVersion, v.blender_min) >= 0;
    const belowMax = v.blender_max === null || v.blender_max === undefined
      || compareVersions(blenderVersion, v.blender_max) <= 0;
    return aboveMin && belowMax;
  });

  if (inRange.length > 0) {
    inRange.sort((a, b) => compareVersions(b.blender_min, a.blender_min));
    return { version: inRange[0], exact: true };
  }

  const byDistance = [...versions].sort((a, b) => {
    const da = Math.abs(compareVersions(blenderVersion, a.blender_min));
    const db = Math.abs(compareVersions(blenderVersion, b.blender_min));
    return da - db;
  });
  return { version: byDistance[0], exact: false };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { compareVersions, pickVersionForBlender };
}
```
The trailing `if (typeof module...)` block is what lets the same file work both as a plain `<script src="logic.js">` in the browser (where `module` is undefined, so the block is skipped and the functions are just global) and as a `require()`-able CommonJS module in the Node test above — no bundler needed either way.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test tests/`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add site/assets/logic.js tests/logic.test.js
git commit -m "feat: add version-matching logic with tests"
```

---

## Task 4: Landing page skeleton — Hero, Footer, language toggle

**Files:**
- Create: `site/index.html`
- Create: `site/assets/main.js`
- Create: `site/assets/style.css`

**Interfaces:**
- Consumes: nothing from earlier tasks yet (Task 5 wires `logic.js` in).
- Produces: a working `applyLanguage(lang)` / `setLanguage(lang)` / `currentLanguage()` mechanism in `main.js` that Task 5 and Task 6 extend (Task 5 adds Download-section rendering to the same file; Task 6 adds the `data-src-ru`/`data-src-en`/`data-href-ru`/`data-href-en` handling to `applyLanguage`).

- [ ] **Step 1: Create `site/index.html`**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BlenderShelf</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <header>
    <nav>
      <span class="brand">BlenderShelf</span>
      <button id="lang-toggle" type="button">EN</button>
    </nav>
  </header>

  <main>
    <section id="hero">
      <h1 data-ru="Панель инструментов в стиле Maya-shelf для Blender" data-en="A Maya-shelf-style toolbar for Blender">Панель инструментов в стиле Maya-shelf для Blender</h1>
      <p data-ru="Быстрый доступ к любимым инструментам прямо во вьюпорте." data-en="Quick access to your favorite tools right in the viewport.">Быстрый доступ к любимым инструментам прямо во вьюпорте.</p>
      <a href="#download" class="cta" data-ru="Скачать" data-en="Download">Скачать</a>
    </section>

    <section id="download">
      <!-- Populated by Task 5 -->
    </section>

    <section id="guide">
      <!-- Populated by Task 6 -->
    </section>
  </main>

  <footer>
    <a href="https://github.com/&lt;GITHUB_OWNER&gt;/BlenderShelf" data-ru="Исходный код на GitHub" data-en="Source code on GitHub">Исходный код на GitHub</a>
  </footer>

  <script src="assets/logic.js"></script>
  <script src="assets/main.js"></script>
</body>
</html>
```
Replace `&lt;GITHUB_OWNER&gt;` with the real owner name recorded in Task 2, Step 2, before committing (write it as a literal `href="https://github.com/<real-name>/BlenderShelf"`).

- [ ] **Step 2: Create `site/assets/main.js`**

```javascript
(function () {
  const STORAGE_KEY = 'blendershelf-lang';

  function currentLanguage() {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'ru';
    } catch (e) {
      return 'ru';
    }
  }

  function applyLanguage(lang) {
    document.querySelectorAll('[data-ru]').forEach((el) => {
      const text = lang === 'ru' ? el.dataset.ru : el.dataset.en;
      if (text !== undefined) el.textContent = text;
    });
    document.documentElement.lang = lang;
    const toggle = document.getElementById('lang-toggle');
    if (toggle) toggle.textContent = lang === 'ru' ? 'EN' : 'RU';
  }

  function setLanguage(lang) {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch (e) {
      // private browsing / blocked storage — language still applies for this view
    }
    applyLanguage(lang);
  }

  document.addEventListener('DOMContentLoaded', () => {
    applyLanguage(currentLanguage());

    const toggle = document.getElementById('lang-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        setLanguage(currentLanguage() === 'ru' ? 'en' : 'ru');
      });
    }
  });
})();
```

- [ ] **Step 3: Create `site/assets/style.css`**

```css
body { font-family: system-ui, sans-serif; margin: 0; color: #222; }
header { display: flex; justify-content: flex-end; padding: 1rem; }
#lang-toggle { cursor: pointer; padding: 0.3rem 0.8rem; }
main { max-width: 800px; margin: 0 auto; padding: 0 1rem; }
section { padding: 3rem 0; border-bottom: 1px solid #eee; }
.cta { display: inline-block; padding: 0.6rem 1.2rem; background: #333; color: #fff; text-decoration: none; border-radius: 4px; }
.warning { color: #a15c00; }
footer { text-align: center; padding: 2rem; }
```

- [ ] **Step 4: Manually verify the language toggle**

Open `site/index.html` directly in a browser (double-click, `file://` URL is fine for this step — no fetch involved yet). Confirm:
- Hero heading/paragraph/CTA and footer link show in Russian by default.
- Clicking the "EN" button switches all of the above to English, and the button now reads "RU".
- Reloading the page keeps the language you last picked (localStorage persistence).
- Open DevTools, disable "Cookies and site data" / use a private window with storage blocked, reload — the page must not throw an uncaught error and must still render in some language (Review Focus item: localStorage unavailable).

- [ ] **Step 5: Commit**

```bash
git add site/index.html site/assets/main.js site/assets/style.css
git commit -m "feat: add landing page skeleton with hero, footer, and language toggle"
```

---

## Task 5: Download section — version picker wired to `versions.json`

**Files:**
- Modify: `site/index.html:16-18` (the `<section id="download">` placeholder from Task 4)
- Modify: `site/assets/main.js` (append the download-section logic)
- Create: `site/versions.json`
- Test: `tests/download-section.test.js`

**Interfaces:**
- Consumes: `pickVersionForBlender` from `site/assets/logic.js` (Task 3), `currentLanguage()` from `main.js` (Task 4).
- Produces: `renderDownloadResult(container, lang, match)` — a pure-ish DOM-building function, exported the same dual CommonJS/global way as `logic.js`, so it can be unit tested without a real browser by passing in a fake `container` object.

- [ ] **Step 1: Seed `site/versions.json` with the current release data**

```json
[
  { "addon_version": "0.1.0", "blender_min": "4.1.0", "blender_max": null, "url": "PLACEHOLDER_FILLED_IN_TASK_8" }
]
```
The `url` is a real gap that Task 8 fills once the first GitHub Release exists (a release can't have a download URL before it's published) — every other task treats this file as already containing this one entry.

- [ ] **Step 2: Write the failing test for `renderDownloadResult`**

Create `tests/download-section.test.js`:
```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { renderDownloadResult } = require('../site/assets/main.js');

function fakeContainer() {
  const children = [];
  return {
    innerHTML: '',
    appendChild(el) { children.push(el); },
    get children() { return children; },
  };
}

function fakeElement() {
  return { textContent: '', className: '', href: '' };
}

test('renderDownloadResult shows an unavailable message when match is null', () => {
  const container = fakeContainer();
  renderDownloadResult(container, 'ru', null, fakeElement);
  assert.equal(container.children.length, 1);
  assert.match(container.children[0].textContent, /недоступен/);
});

test('renderDownloadResult shows a download link with the version number for an exact match', () => {
  const container = fakeContainer();
  const match = { exact: true, version: { addon_version: '0.1.0', url: 'https://example.com/x.zip' } };
  renderDownloadResult(container, 'en', match, fakeElement);
  assert.equal(container.children[0].href, 'https://example.com/x.zip');
  assert.match(container.children[0].textContent, /0\.1\.0/);
});

test('renderDownloadResult adds a warning element for a non-exact match', () => {
  const container = fakeContainer();
  const match = { exact: false, version: { addon_version: '0.1.0', url: 'https://example.com/x.zip' } };
  renderDownloadResult(container, 'ru', match, fakeElement);
  assert.equal(container.children.length, 2);
  assert.equal(container.children[1].className, 'warning');
});
```
Note the `fakeElement` factory passed as a 4th argument — `renderDownloadResult` needs to create elements, and in a browser that's `document.createElement`, but in this Node test there is no DOM. Step 3's implementation takes a `createElement` function as its 4th parameter (defaulting to `document.createElement` when available) specifically so this test can run without a DOM library — no new dependency (like jsdom) needed just to test element wiring.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `node --test tests/`
Expected: FAIL — `renderDownloadResult` is not exported / not a function yet.

- [ ] **Step 4: Implement the Download section markup**

Replace the `<section id="download">` placeholder in `site/index.html`:
```html
<section id="download">
  <h2 data-ru="Скачать" data-en="Download">Скачать</h2>
  <label for="blender-version-select" data-ru="Моя версия Blender:" data-en="My Blender version:">Моя версия Blender:</label>
  <select id="blender-version-select"></select>
  <div id="download-result"></div>
  <p><a href="https://github.com/<GITHUB_OWNER>/BlenderShelf/releases" data-ru="Показать все версии" data-en="Show all versions">Показать все версии</a></p>
</section>
```
(Same `<GITHUB_OWNER>` substitution as Task 4.)

- [ ] **Step 5: Append the download logic to `site/assets/main.js`**

Add above the closing `})();` of the existing IIFE, and change the file's export/require setup as shown:
```javascript
  const BLENDER_VERSIONS = ['5.0.0', '4.5.0', '4.4.0', '4.3.0', '4.2.0', '4.1.0', '4.0.0', '3.6.0'];

  function renderDownloadResult(container, lang, match, createElement) {
    const make = createElement || (typeof document !== 'undefined' ? document.createElement.bind(document) : null);
    container.innerHTML = '';

    if (!match) {
      const p = make('p');
      p.textContent = lang === 'ru'
        ? 'Список версий пока недоступен.'
        : 'Version list is currently unavailable.';
      container.appendChild(p);
      return;
    }

    const link = make('a');
    link.href = match.version.url;
    link.className = 'cta';
    link.textContent = (lang === 'ru' ? 'Скачать BlenderShelf ' : 'Download BlenderShelf ') + match.version.addon_version;
    container.appendChild(link);

    if (!match.exact) {
      const warn = make('p');
      warn.className = 'warning';
      warn.textContent = lang === 'ru'
        ? 'Официально не тестировалось на вашей версии Blender — используйте на свой риск.'
        : 'Not officially tested on your Blender version — use at your own risk.';
      container.appendChild(warn);
    }
  }

  async function initDownloadSection(lang) {
    const select = document.getElementById('blender-version-select');
    const result = document.getElementById('download-result');
    if (!select || !result) return;

    select.innerHTML = '';
    BLENDER_VERSIONS.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });

    let versions = [];
    try {
      const res = await fetch('versions.json');
      versions = await res.json();
    } catch (e) {
      renderDownloadResult(result, lang, null);
      return;
    }

    function update() {
      renderDownloadResult(result, lang, pickVersionForBlender(versions, select.value));
    }
    select.addEventListener('change', update);
    update();
  }
```
Then change the `DOMContentLoaded` handler to also call it, and add the CommonJS export at the very end of the file (after the closing `})();`, so it doesn't interfere with the browser's plain-script execution):
```javascript
  document.addEventListener('DOMContentLoaded', () => {
    const lang = currentLanguage();
    applyLanguage(lang);
    initDownloadSection(lang);

    const toggle = document.getElementById('lang-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        const next = currentLanguage() === 'ru' ? 'en' : 'ru';
        setLanguage(next);
        initDownloadSection(next);
      });
    }
  });
```
(this replaces the `DOMContentLoaded` block from Task 4 — same file, extended.) And at the bottom of `main.js`, outside the IIFE:
```javascript
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { renderDownloadResult };
}
```
For this line to have something to export, `renderDownloadResult` must be declared outside the IIFE's closure — move its declaration (the whole function from Step 5 above) to file scope, above the `(function () { ... })();` block, and have the IIFE reference it directly (functions declared in the same file, outside the IIFE, are still visible inside it in plain script scope). `initDownloadSection` and everything else stays inside the IIFE as before.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `node --test tests/`
Expected: all tests from Task 3 and Task 5 PASS (8 total).

- [ ] **Step 7: Manually verify in a browser (fetch needs an HTTP server, not `file://`)**

```bash
cd site
python -m http.server 8000
```
Open `http://localhost:8000/`. Confirm:
- The Blender-version dropdown is populated.
- Selecting `4.4.0` shows a "Download BlenderShelf 0.1.0" link (exact match, since `blender_max` is `null`).
- Selecting `3.6.0` shows the same link but with the "at your own risk" warning (Review Focus: version older than every range).
- Temporarily rename `site/versions.json` to `versions.json.bak` and reload — confirm the "unavailable" message appears instead of a broken page (Review Focus: fetch failure). Rename it back afterward.

- [ ] **Step 8: Commit**

```bash
git add site/index.html site/assets/main.js site/versions.json tests/download-section.test.js
git commit -m "feat: add download section with Blender-version picker"
```

---

## Task 6: Guide section — video embed + PDF link

**Files:**
- Modify: `site/index.html` (the `<section id="guide">` placeholder)
- Modify: `site/assets/main.js` (`applyLanguage`, to also swap `src`/`href` attributes)
- Copy: `guide/BlenderShelf_Guide_RU.pdf` → `site/guide/BlenderShelf_Guide_RU.pdf`

**Interfaces:**
- Consumes: `applyLanguage(lang)` from Task 4 (extended in place).
- Produces: nothing new consumed by later tasks — this is the last content section for Phase 1.

- [ ] **Step 1: Copy the existing PDF guide into the site**

```bash
mkdir -p site/guide
cp guide/BlenderShelf_Guide_RU.pdf site/guide/BlenderShelf_Guide_RU.pdf
```
No English PDF exists yet — the guide section links to the Russian PDF for both languages for now (see markup below), clearly labeled so it isn't mistaken for a finished translation.

- [ ] **Step 2: Replace the `<section id="guide">` placeholder**

```html
<section id="guide">
  <h2 data-ru="Видеогайд" data-en="Video guide">Видеогайд</h2>
  <div class="video-wrap">
    <iframe id="guide-video"
      data-src-ru="https://www.youtube.com/embed/REPLACE_WITH_RU_VIDEO_ID"
      data-src-en="https://www.youtube.com/embed/REPLACE_WITH_EN_VIDEO_ID"
      src="https://www.youtube.com/embed/REPLACE_WITH_RU_VIDEO_ID"
      width="560" height="315"
      title="BlenderShelf guide"
      allowfullscreen></iframe>
  </div>
  <p><a id="guide-pdf"
    data-href-ru="guide/BlenderShelf_Guide_RU.pdf"
    data-href-en="guide/BlenderShelf_Guide_RU.pdf"
    href="guide/BlenderShelf_Guide_RU.pdf"
    data-ru="Скачать PDF-инструкцию"
    data-en="Download PDF guide (English translation coming soon)">Скачать PDF-инструкцию</a></p>
</section>
```
`REPLACE_WITH_RU_VIDEO_ID` / `REPLACE_WITH_EN_VIDEO_ID` are literal placeholders — the videos don't exist yet (owner records them separately, outside this plan's scope). Leave them as-is; the owner swaps in real YouTube video IDs once recorded. Both PDF `data-href-*` point at the same Russian file until an English translation exists — the EN link text says so explicitly rather than silently serving RU content unlabeled.

- [ ] **Step 3: Extend `applyLanguage` in `site/assets/main.js` to swap `src`/`href` attributes**

Add these two `querySelectorAll` loops inside `applyLanguage`, alongside the existing `[data-ru]` text-swapping loop:
```javascript
    document.querySelectorAll('[data-src-ru]').forEach((el) => {
      const src = lang === 'ru' ? el.dataset.srcRu : el.dataset.srcEn;
      if (src) el.src = src;
    });
    document.querySelectorAll('[data-href-ru]').forEach((el) => {
      const href = lang === 'ru' ? el.dataset.hrefRu : el.dataset.hrefEn;
      if (href) el.href = href;
    });
```
Note: the guide link (`#guide-pdf`) has both `data-ru`/`data-en` (its visible text) and `data-href-ru`/`data-href-en` (its target) — both loops touch the same element for different attributes, which is fine since `querySelectorAll('[data-ru]')` and `querySelectorAll('[data-href-ru]')` are independent passes.

- [ ] **Step 4: Manually verify**

With the local server still running (`python -m http.server 8000` from `site/`, from Task 5 Step 7), open `http://localhost:8000/#guide`. Confirm:
- The video iframe loads (it will show YouTube's "video not found" for the placeholder ID — expected until real IDs are added; confirm the iframe element itself renders and the page doesn't error).
- The PDF link downloads/opens the Russian guide in both languages, and the EN button's label clearly reads "coming soon".
- Toggling language swaps the iframe's `src` attribute (inspect via DevTools) even though both currently point at placeholder IDs.

- [ ] **Step 5: Commit**

```bash
git add site/index.html site/assets/main.js site/guide/BlenderShelf_Guide_RU.pdf
git commit -m "feat: add guide section with video embed and PDF link"
git push
```

---

## Task 7: Enable GitHub Pages

**Files:** none (repository settings only)

**Interfaces:**
- Consumes: the `site/` folder pushed to `main` in Task 6.
- Produces: a live public URL, e.g. `https://<GITHUB_OWNER>.github.io/BlenderShelf/` — referenced in Task 8's verification step.

- [ ] **Step 1: Human enables Pages**

On GitHub: repo → Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, folder: `/site` (or `/root` if `site/` docs-mode isn't available — GitHub Pages folder options are `/root` or `/docs`; if `/site` isn't selectable, this step instead moves `site/` to `docs/` at the repo root, or the human picks `/root` and the URLs in `index.html`/`main.js` stay relative so it works either way). Save.

- [ ] **Step 2: Verify**

Wait for the "Your site is live at ..." confirmation in the Pages settings (can take a minute), then open the URL in a browser. Confirm the hero section renders. (The Download section will show "unavailable" until Task 8 publishes a real release and fills in `versions.json`'s `url` — that's expected at this point.)

---

## Task 8: Cut the first GitHub Release and complete `versions.json`

**Files:**
- Modify: `site/versions.json` (replace the placeholder `url`)

**Interfaces:**
- Consumes: `dist/BlenderShelf.zip` (built in Task 1, Step 1).
- Produces: the first real, downloadable release — the end-to-end path this whole phase exists to deliver.

- [ ] **Step 1: Re-check the current addon version**

Run:
```bash
grep -A2 "^bl_info" "addon/__init__.py" | grep version
```
Confirm it still reads `(0, 1, 0)` (per Global Constraints) — if it has changed, use the real current tuple everywhere below instead of `0.1.0`.

- [ ] **Step 2: Human publishes the GitHub Release**

On GitHub: repo → Releases → "Draft a new release" → tag `v0.1.0` (create on publish) → title `BlenderShelf 0.1.0` → attach `dist/BlenderShelf.zip` as a binary asset → Publish release.

- [ ] **Step 3: Record the asset's direct download URL**

On the published release page, right-click the `BlenderShelf.zip` asset link → copy link address. It looks like `https://github.com/<GITHUB_OWNER>/BlenderShelf/releases/download/v0.1.0/BlenderShelf.zip`.

- [ ] **Step 4: Fill in `site/versions.json`**

```json
[
  { "addon_version": "0.1.0", "blender_min": "4.1.0", "blender_max": null, "url": "https://github.com/<GITHUB_OWNER>/BlenderShelf/releases/download/v0.1.0/BlenderShelf.zip" }
]
```

- [ ] **Step 5: Commit and push**

```bash
git add site/versions.json
git commit -m "chore: point versions.json at the published v0.1.0 release asset"
git push
```

- [ ] **Step 6: End-to-end verification on the live site**

Open the live GitHub Pages URL from Task 7. Select `4.4.0` in the Blender-version dropdown, click the resulting "Download BlenderShelf 0.1.0" link, and confirm the browser actually downloads `BlenderShelf.zip`.

If the download link 404s or the dropdown still shows "unavailable" right after pushing: **wait a few minutes and hard-refresh** before assuming something is broken — GitHub Pages caches `versions.json` briefly after a push (Review Focus item; not a code bug).

Phase 1 is complete once this step succeeds: a stranger can land on the public URL, pick their Blender version, and download a working addon build, in either Russian or English.
