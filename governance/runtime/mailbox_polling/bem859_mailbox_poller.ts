// BEM-859 mailbox poller for Deno/Curator runtime.
const OWNER = 'bereznyi-aleksandr';
const REPO = 'ai-devops-system';
const RESPONSE_PATH = 'governance/audit/mailbox/from_claude/BEM859_PROTOCOL_ALIGNMENT_RESPONSE.md';
const RESULT_PATH = 'governance/runtime/mailbox_polling/BEM859_PROTOCOL_ALIGNMENT_RESULT.md';
const LAST_CHECK_PATH = 'governance/runtime/mailbox_polling/BEM859_LAST_CHECK.md';
const INTERVAL_MS = 60_000;
const FINAL = ['APPROVED','APPROVED_WITH_AMENDMENTS','BLOCKED_WITH_REASON'];
const token = Deno.env.get('AI_SYSTEM_GITHUB_PAT') || Deno.env.get('GITHUB_PAT');
if (!token) throw new Error('Missing GitHub token');
const api = `https://api.github.com/repos/${OWNER}/${REPO}/contents/`;
const headers = { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
function b64(text: string): string { let bin = ''; for (const b of new TextEncoder().encode(text)) bin += String.fromCharCode(b); return btoa(bin); }
function unb64(text: string): string { const bin = atob(text.replace(/\n/g, '')); return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0))); }
async function getFile(path: string): Promise<{ text: string; sha?: string }> { const url = api + encodeURIComponent(path).replaceAll('%2F','/'); const res = await fetch(url, { headers }); if (res.status === 404) return { text: '' }; if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`); const json = await res.json(); return { text: unb64(json.content || ''), sha: json.sha }; }
async function putFile(path: string, content: string, message: string): Promise<void> { const current = await getFile(path); const body: Record<string,string> = { message, content: b64(content) }; if (current.sha) body.sha = current.sha; const url = api + encodeURIComponent(path).replaceAll('%2F','/'); const res = await fetch(url, { method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status} ${await res.text()}`); }
function finalStatus(text: string): string | undefined { return FINAL.find(s => text.includes(s)); }
async function checkOnce(): Promise<void> { const now = new Date().toISOString(); const box = await getFile(RESPONSE_PATH); const status = finalStatus(box.text); if (status) { await putFile(RESULT_PATH, `# BEM-859 protocol alignment result\nStatus: ${status}\nChecked: ${now}\nSource: ${RESPONSE_PATH}\n`, `BEM-862 mailbox final status ${status}`); console.log(`[BEM-859] final status: ${status}`); return; } await putFile(LAST_CHECK_PATH, `# BEM-859 mailbox last check\nStatus: WAITING_FOR_CLAUDE_RESPONSE\nChecked: ${now}\nSource: ${RESPONSE_PATH}\nInterval: 60 seconds\n`, 'BEM-862 mailbox waiting check'); console.log('[BEM-859] waiting for Claude response'); }
await checkOnce();
setInterval(() => { checkOnce().catch(err => console.error('[BEM-859 mailbox poller]', err)); }, INTERVAL_MS);
