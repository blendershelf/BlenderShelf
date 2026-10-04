import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { corsHeaders } from '../worker/src/index.js';

const req = (origin) => new Request('https://w.example/', { method: 'POST', headers: origin ? { Origin: origin } : {} });

test('both sites are echoed back, anything else falls back to the first allowed origin', () => {
  assert.equal(corsHeaders(req('https://easyshelf-addon.github.io'))['Access-Control-Allow-Origin'], 'https://easyshelf-addon.github.io');
  assert.equal(corsHeaders(req('https://blendershelf.github.io'))['Access-Control-Allow-Origin'], 'https://blendershelf.github.io');
  assert.equal(corsHeaders(req('https://evil.example'))['Access-Control-Allow-Origin'], 'https://blendershelf.github.io');
  assert.equal(corsHeaders(req(null))['Vary'], 'Origin');
});

test('the issue body says which site it came from', async () => {
  let sent;
  globalThis.fetch = async (_url, init) => { sent = JSON.parse(init.body); return { ok: true }; };
  const post = (origin) => worker.fetch(new Request('https://w.example/', {
    method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'question', description: 'does it work on Blender 5?' }),
  }), { GITHUB_OWNER: 'o', GITHUB_REPO: 'r', GITHUB_ISSUE_TOKEN: 't' });
  const res = await post('https://easyshelf-addon.github.io');
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'https://easyshelf-addon.github.io');
  assert.match(sent.body, /_Site: easyshelf-addon\.github\.io_/);
});
