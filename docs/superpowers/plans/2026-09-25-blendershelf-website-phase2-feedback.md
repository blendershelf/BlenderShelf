# BlenderShelf Website Phase 2 (Feedback Form) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bilingual feedback form to the BlenderShelf site that lets anyone submit a bug/feature/question with no GitHub account and no email, and have it land as a correctly-labeled GitHub Issue in the (public) BlenderShelf repo via a Cloudflare Worker.

**Architecture:** A static HTML form (new `#feedback` section, reusing the Phase 1 design tokens) posts JSON to a Cloudflare Worker (`worker/`, deployed on the free tier). The Worker holds a fine-grained GitHub PAT as a secret, builds a labeled issue from the submitted fields via a pure function, and calls the GitHub REST API to create it. No LLM, no database, no email.

**Tech Stack:** Plain HTML/CSS/vanilla JS on the client (matches Phase 1 — no framework). Cloudflare Workers (native ES modules) for the backend piece. Node's built-in test runner for the pure issue-building logic.

**Spec:** `docs/superpowers/specs/2026-09-25-blendershelf-website-design.md` (Feedback system section)

## Scope decisions made this session (not in the original spec)

- Feedback issues are created in the **same public `denisghome-wq/BlenderShelf` repo** the addon and site already live in (owner's choice — simplest, matches existing `FEEDBACK.md` triage habit; means submitted bug text and any optional contact info the submitter provides are publicly visible, same as any open-source issue tracker).
- Owner has **no Cloudflare account yet** — Task 1 creates one.
- The GitHub PAT used by the Worker is a **fine-grained token scoped to only this one repo**, permission "Issues: Read and write" only — not a reuse of the broad `gh` CLI login token from Phase 1, which has `repo` scope across every repo the owner can access. Least-privilege: if the Worker secret ever leaked, the blast radius is "someone can open/label issues on this one repo," not "someone can touch every repo you own."
- The raw PAT value is **never typed into this session's chat or shell history** — the owner runs the one command that stores it (`wrangler secret put`) themselves, in their own terminal, so it only ever exists in Cloudflare's encrypted secret store and the owner's own clipboard.

## Global Constraints

- No LLM-based classification anywhere — categorization is 100% derived from the submitter's explicit form choices (spec).
- Submitter needs **no GitHub account and no email address** (spec).
- Spam mitigation is a **honeypot field only** — no CAPTCHA (spec).
- On any submit failure, show a plain "couldn't submit, try again later" message — **no retry queue, no offline storage** (spec).
- Cloudflare Worker on the **free tier** — no paid plan, no KV/D1/other bound resources needed (the Worker is stateless).
- Reuse the Phase 1 design tokens (`--bg`, `--accent`, `--text`, etc. in `site/assets/style.css`) — no new color system for this section.
- GitHub owner/repo for both the addon and the issue tracker: `denisghome-wq/BlenderShelf`.

## Review Focus

- A bot fills the honeypot field → the Worker must return success (200) **without** creating a GitHub issue, so the bot's feedback loop tells it the submission "worked" and it doesn't adapt. (Task 3)
- The GitHub API call fails (bad/expired token, rate limit, network error) → the Worker must return a non-200 the client turns into "couldn't submit, try again later," not hang or 500 with no client-visible message. (Task 3, Task 7)
- CORS preflight (`OPTIONS`) isn't handled → the browser silently blocks the real `POST` before it ever reaches the Worker, and the visitor sees a generic, undiagnosable failure. (Task 3)
- Type = Bug but Severity, Blender version, or BlenderShelf version is left blank → the client must block submission and say what's missing, not send an unlabeled/unusable bug report. (Task 7)
- Submitted free text contains `@someone` or `#123` → naively dropped into an issue body, GitHub would notify a real, uninvolved user or cross-link an unrelated issue/PR. The description and contact fields must be fenced so GitHub's Markdown doesn't parse mentions/references inside them. (Task 2)

---

## Task 1: Cloudflare account + wrangler CLI

**Files:** none (account + CLI auth only)

**Interfaces:**
- Consumes: nothing.
- Produces: an authenticated `wrangler` CLI session, used by every later task that touches the Worker (Task 2 onward).

- [ ] **Step 1: Human creates a free Cloudflare account**

Go to https://dash.cloudflare.com/sign-up, sign up (email/password or GitHub SSO), verify email if asked. No payment method needed for the Workers free tier.

- [ ] **Step 2: Install wrangler**

```bash
npm install -g wrangler
wrangler --version
```
Expected: prints a version number (wrangler 3.x or later).

- [ ] **Step 3: Authenticate wrangler**

```bash
wrangler login
```
This opens a browser OAuth flow (same shape as `gh auth login --web` from Phase 1) — the human approves it in their browser against the account created in Step 1.

- [ ] **Step 4: Verify**

```bash
wrangler whoami
```
Expected: prints the authenticated Cloudflare account's email — confirms the CLI can deploy to it.

---

## Task 2: Issue-building logic (pure function + tests)

**Files:**
- Create: `worker/src/issueBuilder.js`
- Create: `tests/issue-builder.test.mjs`

**Interfaces:**
- Consumes: nothing (pure function, no network, no Worker runtime APIs).
- Produces: `buildIssuePayload(fields: {type, severity, blenderVersion, addonVersion, description, contact}) -> {title: string, labels: string[], body: string}`. Task 3's Worker handler imports this directly (`import { buildIssuePayload } from './issueBuilder.js'`) — real ES module, not the dual CommonJS/global pattern used by the site's own `logic.js` (Workers run native ES modules; there is no `<script>` tag to also satisfy here).

- [ ] **Step 1: Write the failing tests**

Create `tests/issue-builder.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildIssuePayload } from '../worker/src/issueBuilder.js';

test('bug report builds a title with type and severity, and the right labels', () => {
  const result = buildIssuePayload({
    type: 'bug',
    severity: 'critical',
    blenderVersion: '4.4.0',
    addonVersion: '0.1.0',
    description: 'The shelf disappears after switching workspace tabs and never comes back, has to restart Blender every time this happens which is extremely disruptive to my workflow',
    contact: '',
  });
  assert.equal(result.title, '[Bug][critical] The shelf disappears after switching workspace tabs and never');
  assert.deepEqual(result.labels, ['type:bug', 'severity:critical']);
});

test('feature request builds a title with only the type, no severity label', () => {
  const result = buildIssuePayload({
    type: 'feature',
    severity: '',
    blenderVersion: '',
    addonVersion: '',
    description: 'Add a way to reorder pie menu items by drag and drop',
    contact: '',
  });
  assert.equal(result.title, '[Feature] Add a way to reorder pie menu items by drag and drop');
  assert.deepEqual(result.labels, ['type:feature']);
});

test('question and other types map to their own label with no severity', () => {
  assert.deepEqual(buildIssuePayload({ type: 'question', description: 'x' }).labels, ['type:question']);
  assert.deepEqual(buildIssuePayload({ type: 'other', description: 'x' }).labels, ['type:other']);
});

test('title truncates description to 60 characters', () => {
  const result = buildIssuePayload({ type: 'other', description: 'x'.repeat(200) });
  assert.equal(result.title, '[Other] ' + 'x'.repeat(60));
});

test('body fences the description so @mentions and #references do not go live', () => {
  const result = buildIssuePayload({
    type: 'bug',
    severity: 'minor',
    blenderVersion: '4.4.0',
    addonVersion: '0.1.0',
    description: 'Reported by @someone-unrelated, see also #123 for context',
    contact: '',
  });
  const fenced = '```\nReported by @someone-unrelated, see also #123 for context\n```';
  assert.ok(result.body.includes(fenced), 'description must be inside a fenced code block');
});

test('body fences the optional contact field too, and omits the line entirely when blank', () => {
  const withContact = buildIssuePayload({ type: 'question', description: 'x', contact: '@bob email@example.com' });
  assert.ok(withContact.body.includes('```\n@bob email@example.com\n```'));

  const withoutContact = buildIssuePayload({ type: 'question', description: 'x', contact: '' });
  assert.ok(!withoutContact.body.toLowerCase().includes('contact'));
});

test('body includes Blender and addon version when provided, omits the fields when blank', () => {
  const withVersions = buildIssuePayload({ type: 'bug', severity: 'major', blenderVersion: '4.4.0', addonVersion: '0.1.0', description: 'x' });
  assert.ok(withVersions.body.includes('4.4.0'));
  assert.ok(withVersions.body.includes('0.1.0'));

  const withoutVersions = buildIssuePayload({ type: 'question', description: 'x' });
  assert.ok(!withoutVersions.body.includes('Blender version'));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test tests/issue-builder.test.mjs`
Expected: FAIL — `Cannot find module '../worker/src/issueBuilder.js'`.

- [ ] **Step 3: Implement `issueBuilder.js`**

Create `worker/src/issueBuilder.js`:
```javascript
const TYPE_LABELS = {
  bug: 'type:bug',
  feature: 'type:feature',
  question: 'type:question',
  other: 'type:other',
};

const TYPE_TITLES = {
  bug: 'Bug',
  feature: 'Feature',
  question: 'Question',
  other: 'Other',
};

const SEVERITY_LABELS = {
  critical: 'severity:critical',
  major: 'severity:major',
  minor: 'severity:minor',
};

function fence(text) {
  return '```\n' + text + '\n```';
}

export function buildIssuePayload(fields) {
  const type = fields.type || 'other';
  const severity = fields.type === 'bug' ? fields.severity : '';
  const description = (fields.description || '').trim();
  const truncated = description.slice(0, 60);

  const titlePrefix = severity
    ? `[${TYPE_TITLES[type]}][${severity}]`
    : `[${TYPE_TITLES[type]}]`;
  const title = `${titlePrefix} ${truncated}`;

  const labels = [TYPE_LABELS[type]];
  if (severity && SEVERITY_LABELS[severity]) {
    labels.push(SEVERITY_LABELS[severity]);
  }

  const lines = [`**Type:** ${TYPE_TITLES[type]}`];
  if (severity) {
    lines.push(`**Severity:** ${severity}`);
  }
  if (fields.blenderVersion) {
    lines.push(`**Blender version:** ${fields.blenderVersion}`);
  }
  if (fields.addonVersion) {
    lines.push(`**BlenderShelf version:** ${fields.addonVersion}`);
  }
  lines.push('', '**Description:**', fence(description));
  if (fields.contact) {
    lines.push('', '**Contact:**', fence(fields.contact));
  }
  lines.push('', '_Submitted via the website feedback form._');

  return { title, labels, body: lines.join('\n') };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test tests/issue-builder.test.mjs`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add worker/src/issueBuilder.js tests/issue-builder.test.mjs
git commit -m "feat: add pure issue-building logic for the feedback Worker, with tests"
```

---

## Task 3: Worker fetch handler (CORS, honeypot, GitHub API call)

**Files:**
- Create: `worker/src/index.js`
- Create: `worker/wrangler.toml`

**Interfaces:**
- Consumes: `buildIssuePayload` from `worker/src/issueBuilder.js` (Task 2).
- Produces: an HTTP endpoint (URL known only after Task 5 deploys it) that Task 7's client code POSTs to. Request contract: `POST` with JSON body `{ type, severity, blenderVersion, addonVersion, description, contact, website }` (`website` is the honeypot field — real visitors never fill it). Response: `200 {"ok": true}` on success (including the silent-honeypot case), non-200 JSON `{"ok": false}` on failure.

- [ ] **Step 1: Create `worker/wrangler.toml`**

```toml
name = "blendershelf-feedback"
main = "src/index.js"
compatibility_date = "2026-09-25"

[vars]
GITHUB_OWNER = "denisghome-wq"
GITHUB_REPO = "BlenderShelf"
```

- [ ] **Step 2: Create `worker/src/index.js`**

```javascript
import { buildIssuePayload } from './issueBuilder.js';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://denisghome-wq.github.io',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== 'POST') {
      return json(405, { ok: false, error: 'method not allowed' });
    }

    let fields;
    try {
      fields = await request.json();
    } catch (e) {
      return json(400, { ok: false, error: 'invalid JSON' });
    }

    // Honeypot: a real visitor never fills this hidden field. Report success
    // without ever touching the GitHub API, so a bot's own success signal
    // tells it nothing changed and it has no reason to try a different field.
    if (fields.website) {
      return json(200, { ok: true });
    }

    const { title, labels, body } = buildIssuePayload(fields);

    const ghResponse = await fetch(
      `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/issues`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${env.GITHUB_ISSUE_TOKEN}`,
          Accept: 'application/vnd.github+json',
          'User-Agent': 'blendershelf-feedback-worker',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title, body, labels }),
      }
    );

    if (!ghResponse.ok) {
      return json(502, { ok: false, error: 'GitHub API error' });
    }

    return json(200, { ok: true });
  },
};
```

- [ ] **Step 3: Commit**

```bash
git add worker/wrangler.toml worker/src/index.js
git commit -m "feat: add Worker fetch handler with CORS, honeypot, and GitHub issue creation"
```

(No automated test here — this file's only untested logic, the honeypot branch and the GitHub-call branch, gets exercised for real in Task 5's deploy verification and Task 8's end-to-end check. The pure decision logic it depends on is already covered by Task 2's tests.)

---

## Task 4: GitHub PAT, Worker secret, and repo labels

**Files:** none (credential + repo-settings step)

**Interfaces:**
- Consumes: nothing.
- Produces: the `GITHUB_ISSUE_TOKEN` secret Task 3's Worker reads from `env`, and the seven labels (`type:bug`, `type:feature`, `type:question`, `type:other`, `severity:critical`, `severity:major`, `severity:minor`) Task 2's payloads reference.

- [ ] **Step 1: Human creates a fine-grained GitHub PAT**

On GitHub: Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
- Repository access: **Only select repositories** → `denisghome-wq/BlenderShelf`.
- Permissions: **Issues: Read and write**. Leave everything else at its default (No access).
- Expiration: the human's choice (a long expiry is fine — this is a low-privilege, single-repo token).
- Generate, copy the token value. **Do not paste it into this chat** — the next step uses it directly in a terminal only the human runs.

- [ ] **Step 2: Human stores it as the Worker secret**

In `worker/`, the human runs (in their own terminal, not dispatched by the assistant):
```bash
cd worker
wrangler secret put GITHUB_ISSUE_TOKEN
```
`wrangler` prompts for the value; pasting it there sends it straight to Cloudflare's encrypted secret store — it is never written to a file, this repo, or the chat transcript.

- [ ] **Step 3: Create the labels**

```bash
gh label create "type:bug" --repo denisghome-wq/BlenderShelf --color d73a4a --description "Bug report from the feedback form" --force
gh label create "type:feature" --repo denisghome-wq/BlenderShelf --color a2eeef --description "Feature request from the feedback form" --force
gh label create "type:question" --repo denisghome-wq/BlenderShelf --color d876e3 --description "Question from the feedback form" --force
gh label create "type:other" --repo denisghome-wq/BlenderShelf --color cfd3d7 --description "Uncategorized feedback" --force
gh label create "severity:critical" --repo denisghome-wq/BlenderShelf --color b60205 --description "Blocks or crashes Blender" --force
gh label create "severity:major" --repo denisghome-wq/BlenderShelf --color d93f0b --description "A feature doesn't work" --force
gh label create "severity:minor" --repo denisghome-wq/BlenderShelf --color fbca04 --description "Cosmetic/minor" --force
```

- [ ] **Step 4: Verify**

```bash
gh label list --repo denisghome-wq/BlenderShelf
```
Expected: all seven labels listed above appear, alongside GitHub's own defaults.

---

## Task 5: Deploy the Worker and verify it end-to-end (backend only)

**Files:** none (deploy + verification only)

**Interfaces:**
- Consumes: `worker/wrangler.toml` and `worker/src/*.js` (Tasks 2-3), the secret and labels from Task 4.
- Produces: a live Worker URL, e.g. `https://blendershelf-feedback.<account>.workers.dev`, that Task 7's client code targets.

- [ ] **Step 1: Deploy**

```bash
cd worker
wrangler deploy
```
Expected: prints the deployed URL, e.g. `https://blendershelf-feedback.<account>.workers.dev`. Record it — Task 7 needs it as a literal constant in the client JS.

- [ ] **Step 2: Verify the honeypot path creates no issue**

```bash
curl -s -X POST https://blendershelf-feedback.<account>.workers.dev \
  -H "Content-Type: application/json" \
  -d '{"type":"bug","description":"honeypot test — should NOT create an issue","website":"http://spam.example"}'
```
Expected: `{"ok":true}`, and no new issue appears at `https://github.com/denisghome-wq/BlenderShelf/issues` (check the issues list — this is the Review Focus item about bots).

- [ ] **Step 3: Verify the real path creates a labeled issue**

```bash
curl -s -X POST https://blendershelf-feedback.<account>.workers.dev \
  -H "Content-Type: application/json" \
  -d '{"type":"question","description":"Deploy verification test from Task 5 — safe to close.","contact":""}'
```
Expected: `{"ok":true}`. Confirm via `gh issue list --repo denisghome-wq/BlenderShelf --label "type:question"` that a new issue titled `[Question] Deploy verification test from Task 5 — safe to close.` exists with the `type:question` label.

- [ ] **Step 4: Close the verification issue**

```bash
gh issue close --repo denisghome-wq/BlenderShelf --comment "Deploy verification for the feedback Worker — confirmed working." <issue-number-from-step-3>
```
Keeps the tracker clean — this issue was a connectivity check, not real feedback.

---

## Task 6: Feedback section markup and styling

**Files:**
- Modify: `site/index.html` (add `<section id="feedback">` between `#guide` and the footer)
- Modify: `site/assets/style.css` (form-control styling, reusing Phase 1's design tokens)

**Interfaces:**
- Consumes: the `--bg`, `--bg-elevated`, `--border`, `--text`, `--text-muted`, `--accent`, `--accent-hover`, `--accent-text`, `--warning`, `--radius` custom properties already defined in `site/assets/style.css` (Phase 1's design pass).
- Produces: the DOM structure Task 7's `feedback.js` queries by ID/class (`#feedback-form`, `#feedback-type`, `.severity-field`, `#feedback-result`, and the honeypot input named `website`).

- [ ] **Step 1: Insert the feedback section into `site/index.html`**

Insert this new `<section>` right after the closing `</section>` of `#guide` and before `</main>`:
```html
<section id="feedback" class="wrap">
  <h2 data-ru="Обратная связь" data-en="Feedback">Обратная связь</h2>
  <p data-ru="Баг, идея или вопрос — без аккаунта GitHub и без почты." data-en="A bug, an idea, or a question — no GitHub account or email needed.">Баг, идея или вопрос — без аккаунта GitHub и без почты.</p>

  <form id="feedback-form" class="panel" novalidate>
    <input type="text" name="website" class="hp-field" tabindex="-1" autocomplete="off" aria-hidden="true">

    <fieldset id="feedback-type">
      <legend data-ru="Тип обращения" data-en="Type">Тип обращения</legend>
      <label><input type="radio" name="type" value="bug" required> <span data-ru="Баг" data-en="Bug">Баг</span></label>
      <label><input type="radio" name="type" value="feature"> <span data-ru="Идея / хотелка" data-en="Feature request">Идея / хотелка</span></label>
      <label><input type="radio" name="type" value="question"> <span data-ru="Вопрос" data-en="Question">Вопрос</span></label>
      <label><input type="radio" name="type" value="other"> <span data-ru="Другое" data-en="Other">Другое</span></label>
    </fieldset>

    <div class="field-group severity-field" hidden>
      <label for="feedback-severity" data-ru="Насколько критично" data-en="How critical">Насколько критично</label>
      <select id="feedback-severity" name="severity">
        <option value="critical" data-ru="Блокирует работу / крашит Blender" data-en="Blocks work / crashes Blender">Блокирует работу / крашит Blender</option>
        <option value="major" data-ru="Функция не работает" data-en="A feature doesn't work">Функция не работает</option>
        <option value="minor" data-ru="Мелочь, косметика" data-en="Cosmetic, minor">Мелочь, косметика</option>
      </select>
    </div>

    <div class="field-group versions-field" hidden>
      <div class="field-group">
        <label for="feedback-blender-version" data-ru="Версия Blender" data-en="Blender version">Версия Blender</label>
        <input type="text" id="feedback-blender-version" name="blenderVersion" placeholder="4.4.0">
      </div>
      <div class="field-group">
        <label for="feedback-addon-version" data-ru="Версия BlenderShelf" data-en="BlenderShelf version">Версия BlenderShelf</label>
        <input type="text" id="feedback-addon-version" name="addonVersion" placeholder="0.1.0">
      </div>
    </div>

    <div class="field-group">
      <label for="feedback-description" data-ru="Описание" data-en="Description">Описание</label>
      <textarea id="feedback-description" name="description" rows="5" required></textarea>
    </div>

    <div class="field-group">
      <label for="feedback-contact" data-ru="Контакт для ответа (необязательно)" data-en="Contact info (optional)">Контакт для ответа (необязательно)</label>
      <input type="text" id="feedback-contact" name="contact">
    </div>

    <button type="submit" class="cta" data-ru="Отправить" data-en="Submit">Отправить</button>
    <div id="feedback-result"></div>
  </form>
</section>
```

- [ ] **Step 2: Add form styling to `site/assets/style.css`**

Append:
```css
.hp-field {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
}

#feedback fieldset {
  border: 0;
  padding: 0;
  margin: 0 0 1.25rem;
}

#feedback legend {
  color: var(--text);
  font-weight: 600;
  font-size: 0.95rem;
  margin-bottom: 0.5rem;
  padding: 0;
}

#feedback fieldset label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0 1.25rem 0.5rem 0;
  color: var(--text-muted);
  cursor: pointer;
}

.field-group {
  margin-bottom: 1.25rem;
}

.field-group label {
  display: block;
  color: var(--text);
  font-weight: 600;
  font-size: 0.95rem;
  margin-bottom: 0.4rem;
}

.versions-field {
  display: flex;
  gap: 1rem;
}

.versions-field .field-group {
  flex: 1;
  margin-bottom: 0;
}

#feedback input[type="text"],
#feedback textarea,
#feedback select {
  width: 100%;
  font: inherit;
  color: var(--text);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.6rem 0.8rem;
  transition: border-color 0.15s ease-out;
}

#feedback input[type="text"]:hover,
#feedback textarea:hover,
#feedback select:hover {
  border-color: var(--accent);
}

#feedback textarea {
  resize: vertical;
}

#feedback-result {
  margin-top: 1rem;
}

#feedback-result .success {
  color: var(--accent);
}

#feedback-result .error {
  color: var(--warning);
}
```

- [ ] **Step 3: Manually verify markup renders (no submit logic yet — that's Task 7)**

Open the local server and confirm: the Type radios, severity/version fields (hidden by default via the `hidden` attribute), description textarea, contact field, and submit button all render inside a `.panel`, styled consistently with the Download section from Phase 1.

- [ ] **Step 4: Commit**

```bash
git add site/index.html site/assets/style.css
git commit -m "feat: add feedback form markup and styling"
```

---

## Task 7: Feedback form submission logic

**Files:**
- Create: `site/assets/feedback.js`
- Modify: `site/index.html` (add the new `<script>` tag)

**Interfaces:**
- Consumes: the DOM structure from Task 6 (`#feedback-form`, `#feedback-type` radios, `.severity-field`, `.versions-field`, `#feedback-result`), and `currentLanguage()` from `site/assets/main.js` (already global via that file's plain `<script>` inclusion, same pattern `logic.js`/`main.js` already use with each other).
- Produces: nothing consumed by a later task — this is the last piece of Phase 2.

- [ ] **Step 1: Create `site/assets/feedback.js`**

```javascript
(function () {
  const WORKER_URL = 'https://blendershelf-feedback.<account>.workers.dev';

  function showResult(message, isError) {
    const result = document.getElementById('feedback-result');
    if (!result) return;
    result.innerHTML = '';
    const p = document.createElement('p');
    p.className = isError ? 'error' : 'success';
    p.textContent = message;
    result.appendChild(p);
  }

  function updateConditionalFields(form) {
    const isBug = form.querySelector('input[name="type"]:checked')?.value === 'bug';
    const severityField = form.querySelector('.severity-field');
    const versionsField = form.querySelector('.versions-field');
    const blenderVersionInput = form.querySelector('#feedback-blender-version');
    const addonVersionInput = form.querySelector('#feedback-addon-version');

    severityField.hidden = !isBug;
    versionsField.hidden = !isBug;
    blenderVersionInput.required = isBug;
    addonVersionInput.required = isBug;
  }

  function collectFields(form) {
    const data = new FormData(form);
    return {
      type: data.get('type') || '',
      severity: data.get('severity') || '',
      blenderVersion: (data.get('blenderVersion') || '').trim(),
      addonVersion: (data.get('addonVersion') || '').trim(),
      description: (data.get('description') || '').trim(),
      contact: (data.get('contact') || '').trim(),
      website: data.get('website') || '',
    };
  }

  async function submitFeedback(form) {
    const lang = (typeof currentLanguage === 'function') ? currentLanguage() : 'ru';
    const fields = collectFields(form);

    if (!fields.type) {
      showResult(lang === 'ru' ? 'Выберите тип обращения.' : 'Pick a type.', true);
      return;
    }
    if (!fields.description) {
      showResult(lang === 'ru' ? 'Опишите проблему или идею.' : 'Please add a description.', true);
      return;
    }
    if (fields.type === 'bug' && (!fields.severity || !fields.blenderVersion || !fields.addonVersion)) {
      showResult(
        lang === 'ru'
          ? 'Для бага укажите критичность и обе версии.'
          : 'For a bug, fill in severity and both version fields.',
        true
      );
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
      const res = await fetch(WORKER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fields),
      });
      const data = await res.json().catch(() => ({ ok: false }));
      if (res.ok && data.ok) {
        showResult(lang === 'ru' ? 'Спасибо! Обращение отправлено.' : 'Thanks! Your feedback was submitted.', false);
        form.reset();
        updateConditionalFields(form);
      } else {
        throw new Error('submit failed');
      }
    } catch (e) {
      showResult(
        lang === 'ru' ? 'Не получилось отправить, попробуйте позже.' : "Couldn't submit, please try again later.",
        true
      );
    } finally {
      submitButton.disabled = false;
    }
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
      const form = document.getElementById('feedback-form');
      if (!form) return;

      updateConditionalFields(form);
      form.querySelectorAll('input[name="type"]').forEach((radio) => {
        radio.addEventListener('change', () => updateConditionalFields(form));
      });

      form.addEventListener('submit', (e) => {
        e.preventDefault();
        submitFeedback(form);
      });
    });
  }
})();
```
Replace `<account>` with the real Worker subdomain recorded in Task 5, Step 1, before committing.

- [ ] **Step 2: Add the script tag to `site/index.html`**

```html
  <script src="assets/logic.js"></script>
  <script src="assets/main.js"></script>
  <script src="assets/feedback.js"></script>
```
(adds one line after the existing two `<script>` tags, same location as before `</body>`).

- [ ] **Step 3: Manually verify client-side validation**

With the local server running, open the feedback section and confirm:
- Selecting "Bug" reveals the severity dropdown and both version fields; selecting any other type hides them again.
- Submitting with no type selected shows "Pick a type" / "Выберите тип обращения" and does not call the network.
- Submitting "Bug" with severity/versions left blank shows the bug-specific validation message.
- Submitting a valid non-bug report with only a description reaches the network (check via the browser's network panel or `read_network_requests`) — response depends on Task 5's deployed Worker being live already.

- [ ] **Step 4: Commit**

```bash
git add site/assets/feedback.js site/index.html
git commit -m "feat: add feedback form submission logic"
git push
```

---

## Task 8: End-to-end verification on the live site

**Files:** none (verification only)

**Interfaces:**
- Consumes: everything from Tasks 1-7, live on GitHub Pages and Cloudflare.
- Produces: confirmation that Phase 2 actually works for a stranger landing on the public site.

- [ ] **Step 1: Wait for the Pages deploy triggered by Task 7's push, then open the live site**

Open `https://denisghome-wq.github.io/BlenderShelf/#feedback`.

- [ ] **Step 2: Submit a real end-to-end test**

Fill in Type = Question, Description = "End-to-end Phase 2 verification — safe to close.", submit. Confirm the success message appears in the current UI language.

- [ ] **Step 3: Confirm the issue landed correctly**

```bash
gh issue list --repo denisghome-wq/BlenderShelf --label "type:question" --limit 5
```
Expected: the issue from Step 2 appears, titled `[Question] End-to-end Phase 2 verification — safe to close.`, labeled `type:question`.

- [ ] **Step 4: Confirm the honeypot still blocks a bot-shaped request against the live Worker**

```bash
curl -s -X POST https://blendershelf-feedback.<account>.workers.dev \
  -H "Content-Type: application/json" \
  -d '{"type":"bug","description":"live honeypot re-check","website":"http://spam.example"}'
```
Expected: `{"ok":true}` with no corresponding new issue.

- [ ] **Step 5: Close the verification issue**

```bash
gh issue close --repo denisghome-wq/BlenderShelf --comment "End-to-end Phase 2 verification — confirmed working from the live site." <issue-number-from-step-3>
```

Phase 2 is complete once this succeeds: a stranger with no GitHub account can submit feedback from the public site and it shows up as a correctly labeled issue, in either language, and spam submissions are silently absorbed instead of cluttering the tracker.
