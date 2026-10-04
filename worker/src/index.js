import { buildIssuePayload, isValidType, isValidSeverity } from './issueBuilder.js';

// Both sites post to this one Worker; every report lands in the same GitHub repo.
export const ALLOWED_ORIGINS = ['https://blendershelf.github.io', 'https://easyshelf-addon.github.io'];

export function corsHeaders(request) {
  const origin = request.headers.get('Origin');
  return {
    'Access-Control-Allow-Origin': ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
    'Vary': 'Origin',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function json(status, body, cors) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...cors },
  });
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request);
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== 'POST') {
      return json(405, { ok: false, error: 'method not allowed' }, cors);
    }

    let fields;
    try {
      fields = await request.json();
    } catch (e) {
      return json(400, { ok: false, error: 'invalid JSON' }, cors);
    }
    if (!fields || typeof fields !== 'object') {
      return json(400, { ok: false, error: 'invalid payload' }, cors);
    }

    // Honeypot: a real visitor never fills this hidden field. Report success
    // without ever touching the GitHub API, so a bot's own success signal
    // tells it nothing changed and it has no reason to try a different field.
    if (fields.website) {
      return json(200, { ok: true }, cors);
    }

    // The client only offers the valid type/severity values, but this endpoint
    // is public and unauthenticated — anyone can POST to it directly, so the
    // server enforces the same allowlist rather than trusting the client.
    if (!isValidType(fields.type)) {
      return json(400, { ok: false, error: 'invalid type' }, cors);
    }
    if (fields.type === 'bug' && !isValidSeverity(fields.severity)) {
      return json(400, { ok: false, error: 'invalid severity' }, cors);
    }
    if (!fields.description || !String(fields.description).trim()) {
      return json(400, { ok: false, error: 'description required' }, cors);
    }

    const { title, labels, body: issueBody } = buildIssuePayload(fields);
    const origin = request.headers.get('Origin');
    // which site the report came from (both sites share this repo)
    const body = ALLOWED_ORIGINS.includes(origin) ? `${issueBody}

_Site: ${origin.replace('https://', '')}_` : issueBody;

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
      return json(502, { ok: false, error: 'GitHub API error' }, cors);
    }

    return json(200, { ok: true }, cors);
  },
};
