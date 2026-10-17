// ДОКУМЕНТ: src/rules_gate.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-17 23:51 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-17 23:51 +03:00 (v0.1: пакет Z-RULES-01, проект v1.2)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверки правил Завода, которые ядро делает само, не веря вызывающему (проект §3.1, §3.3).
//   collectActivation — факты для включения версии правил: PR слит в main (GitHub читает программа gh, только
//     чтение), четыре обязательные проверки от назначенного источника на проверенной версии, merge_commit входит
//     в origin/main, реестр и каждый его файл читаются из объектов коммитов (git cat-file) и совпадают в
//     merge_commit и head_sha, подпись билета ключом оператора (sshsig.mjs) и срок билета не больше 24 часов.
//   checkWorkingCopy — проверка перед арендой (Л.8): рабочая копия чистая, HEAD = origin/main, реестр
//     действующей версии и каждый его файл совпадают с HEAD по объектам git.
// ОГРАНИЧЕНИЯ: токен GitHub хранит gh; этот код его не читает и не печатает. Рабочая копия не меняется, кроме
//   git fetch. Реестр — zavod/rules/RULES_REGISTRY.json; ключ оператора для правил —
//   zavod/rules/OPERATOR_RULES_KEY.pub действующей версии, для самой первой версии — ключ установки ядра.

import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { parseEd25519PublicKey, fingerprint, verifySshSig } from '../../engine/src/sshsig.mjs';

export const REGISTRY_PATH = 'zavod/rules/RULES_REGISTRY.json';
export const RULES_KEY_PATH = 'zavod/rules/OPERATOR_RULES_KEY.pub';
export const RULES_NAMESPACE = 'zavod-rules-activation@v1';
export const REPORT_ACK_NAMESPACE = 'zavod-report-ack@v1';
export const REQUIRED_CHECKS = Object.freeze(['static', 'pg16', 'engine-pg', 'engine-pg-probes']);
const TICKET_MAX_AGE_MS = 24 * 3600 * 1000;
const TICKET_SKEW_MS = 5 * 60 * 1000;
const SHA1 = /^[0-9a-f]{40}$/;
const ROLE_KEY = /^0[1-9]_[^/\\]{1,60}$/;
const ISO_Z = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
// Путь файла реестра: относительный, без «..», без обратной черты, без пустых частей.
const SAFE_PATH = /^(?!.*(?:^|\/)\.\.?(?:\/|$))[^\\/\0][^\\\0]*$/;

export class RulesError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}
const fail = (code, msg = '') => { throw new RulesError(code, msg); };
const sha256 = (b) => createHash('sha256').update(b).digest('hex');

// Ключи объекта по порядку: одинаковые данные дают одинаковый текст при любом порядке ключей.
export function canonicalJson(v) {
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`;
  if (v && typeof v === 'object') {
    return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(v[k])}`).join(',')}}`;
  }
  return JSON.stringify(v);
}

export function defaultGh(path) {
  return JSON.parse(execFileSync('gh', ['api', path], { encoding: 'utf8', windowsHide: true, maxBuffer: 16 << 20 }));
}
export function gitRunner(repoDir, bin = 'git') {
  return (args) => execFileSync(bin, ['-C', repoDir, ...args], { windowsHide: true, maxBuffer: 64 << 20 });
}

// Разбор реестра: формат, список файлов, иерархия ролей (каждая роль ведёт к OPERATOR без петель).
export function parseRegistry(bytes) {
  let reg;
  try { reg = JSON.parse(Buffer.from(bytes).toString('utf8')); } catch { fail('RULES_REGISTRY_BAD', 'not json'); }
  if (!reg || reg.format !== 'zavod-rules-registry@v1') fail('RULES_REGISTRY_BAD', 'format');
  if (!Array.isArray(reg.files) || reg.files.length === 0) fail('RULES_REGISTRY_BAD', 'files');
  const seen = new Set();
  for (const f of reg.files) {
    if (typeof f !== 'string' || !SAFE_PATH.test(f) || f.includes('//') || f.endsWith('/') || f === REGISTRY_PATH
      || seen.has(f)) fail('RULES_REGISTRY_BAD', `file ${f}`);
    seen.add(f);
  }
  const parents = reg.role_parents;
  if (!parents || typeof parents !== 'object' || Array.isArray(parents) || Object.keys(parents).length === 0) {
    fail('RULES_REGISTRY_BAD', 'role_parents');
  }
  const keys = Object.keys(parents);
  for (const k of keys) {
    if (!ROLE_KEY.test(k) || typeof parents[k] !== 'string') fail('RULES_REGISTRY_BAD', `role ${k}`);
    let cur = k;
    for (let steps = 0; cur !== 'OPERATOR'; steps += 1) {
      cur = Object.hasOwn(parents, cur) ? parents[cur] : null;
      if (cur === null || steps >= keys.length) fail('RULES_REGISTRY_BAD', `role chain ${k}`);
    }
  }
  return { files: [...reg.files].sort(), role_parents: Object.fromEntries(keys.sort().map((k) => [k, parents[k]])) };
}

export function createRulesGate({ repoDir, repo, gh = defaultGh, git = gitRunner(repoDir), bootstrapKeyLine = null,
  now = () => Date.now(), fetch = true } = {}) {
  const blob = (commit, path) => {
    try { return git(['cat-file', 'blob', `${commit}:${path}`]); } catch { return null; }
  };
  const revParse = (ref) => git(['rev-parse', '--verify', `${ref}^{commit}`]).toString('utf8').trim();

  // Реестр и файлы из объекта коммита: { files, role_parents, digest, blobs: Map(path -> sha256) }.
  function readRules(commit) {
    const regBytes = blob(commit, REGISTRY_PATH);
    if (!regBytes) fail('RULES_REGISTRY_MISSING', `${REGISTRY_PATH} @ ${commit}`);
    const reg = parseRegistry(regBytes);
    const blobs = new Map([[REGISTRY_PATH, sha256(regBytes)]]);
    for (const f of reg.files) {
      const b = blob(commit, f);
      if (!b) fail('RULES_FILE_MISSING', `${f} @ ${commit}`);
      blobs.set(f, sha256(b));
    }
    const lines = [...blobs.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([p, h]) => `${p}\t${h}\n`);
    return { ...reg, blobs, digest: sha256(lines.join('')) };
  }

  function sameRules(a, b) {
    if (a.blobs.size !== b.blobs.size) return false;
    for (const [p, h] of a.blobs) if (b.blobs.get(p) !== h) return false;
    return true;
  }

  // Ключ, которым оператор подписывает билеты правил и подтверждения отчётов.
  function operatorKey(activeRulesCommit) {
    let line = bootstrapKeyLine;
    if (activeRulesCommit) {
      const b = blob(activeRulesCommit, RULES_KEY_PATH);
      if (!b) fail('RULES_KEY_MISSING', `${RULES_KEY_PATH} @ ${activeRulesCommit}`);
      line = b.toString('utf8').trim();
    }
    if (!line) fail('RULES_KEY_MISSING', 'no bootstrap key');
    let raw;
    try { raw = parseEd25519PublicKey(line); } catch { fail('RULES_KEY_MISSING', 'bad key'); }
    return { raw, fp: fingerprint(raw) };
  }

  function verifyTicket({ ticketText, signature, namespace, activeRulesCommit }) {
    if (typeof ticketText !== 'string' || typeof signature !== 'string') fail('RULES_SIGNATURE_MISSING', 'ticket');
    const key = operatorKey(activeRulesCommit);
    if (!verifySshSig({ armored: signature, message: Buffer.from(ticketText, 'utf8'), namespace, rawKey: key.raw })) {
      fail('RULES_SIGNATURE_INVALID', namespace);
    }
    let ticket;
    try { ticket = JSON.parse(ticketText); } catch { fail('RULES_SIGNATURE_MISMATCH', 'ticket json'); }
    if (!ticket || typeof ticket !== 'object' || Array.isArray(ticket)) fail('RULES_SIGNATURE_MISMATCH', 'ticket');
    return { ticket, key, signed_ticket_sha256: sha256(Buffer.from(ticketText, 'utf8')) };
  }

  // Факты для bem_control.activate_rules. Ни одно значение не берётся из запроса, кроме номера PR и предмета;
  // их ядро сверяет с GitHub и с подписанным билетом.
  function collectActivation({ tenantId, prNumber, subjectId, ticketText, signature, activeRulesCommit }) {
    if (!Number.isInteger(prNumber) || prNumber < 1) fail('RULES_BAD_PR', String(prNumber));
    if (!repo || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) fail('RULES_REPO_UNSET', String(repo));
    const pr = gh(`repos/${repo}/pulls/${prNumber}`);
    if (pr?.merged !== true) fail('RULES_PR_NOT_MERGED', String(prNumber));
    if (pr.base?.ref !== 'main') fail('RULES_PR_NOT_MAIN', String(pr.base?.ref));
    const commit = pr.merge_commit_sha;
    const head = pr.head?.sha;
    if (!SHA1.test(commit || '') || !SHA1.test(head || '')) fail('RULES_PR_BAD_SHA', 'merge/head');
    const prUrl = `https://github.com/${repo}/pull/${prNumber}`;
    if (pr.html_url !== prUrl) fail('RULES_PR_BAD_URL', String(pr.html_url));

    // Назначенный источник каждой обязательной проверки — из защиты ветки main.
    const prot = gh(`repos/${repo}/branches/main/protection/required_status_checks`);
    const required = (prot?.checks || []).map((c) => ({ context: c.context, app_id: c.app_id ?? null }));
    const runsAll = gh(`repos/${repo}/commits/${head}/check-runs?per_page=100`)?.check_runs || [];
    const checkRuns = [];
    for (const name of REQUIRED_CHECKS) {
      const req = required.find((c) => c.context === name);
      if (!req || !Number.isInteger(req.app_id)) fail('RULES_CHECK_SOURCE_UNASSIGNED', name);
      // Последний завершённый прогон назначенного источника на этой версии; чужие приложения не считаются.
      const runs = runsAll.filter((r) => r.name === name && r.head_sha === head && r.app?.id === req.app_id
        && r.status === 'completed' && ISO_Z.test(r.completed_at || ''))
        .sort((a, b) => (a.completed_at < b.completed_at ? 1 : a.completed_at > b.completed_at ? -1 : b.id - a.id));
      if (runs.length === 0) fail('RULES_CHECK_NOT_PASSED', name);
      const r = runs[0];
      if (r.conclusion !== 'success') fail('RULES_CHECK_NOT_PASSED', `${name}: ${r.conclusion}`);
      checkRuns.push({ name, check_run_id: r.id, app_id: r.app.id, head_sha: r.head_sha,
        conclusion: r.conclusion, completed_at: r.completed_at });
    }

    // Неизменяемые объекты git: merge_commit в origin/main; реестр одинаков в merge_commit и head_sha.
    if (fetch) git(['fetch', '--quiet', 'origin', 'main']);
    try { git(['merge-base', '--is-ancestor', commit, 'origin/main']); } catch { fail('RULES_COMMIT_NOT_IN_MAIN', commit); }
    const atMerge = readRules(commit);
    const atHead = readRules(head);
    if (!sameRules(atMerge, atHead)) fail('RULES_REGISTRY_CHANGED_AFTER_AUDIT', `${head} -> ${commit}`);

    const { ticket, key, signed_ticket_sha256 } = verifyTicket({ ticketText, signature,
      namespace: RULES_NAMESPACE, activeRulesCommit });
    const want = { tenant_id: tenantId, merge_commit: commit, head_sha: head, pr_number: prNumber,
      registry_digest: atMerge.digest, subject_id: subjectId, role_parents: atMerge.role_parents };
    for (const [k, v] of Object.entries(want)) {
      if (canonicalJson(ticket[k]) !== canonicalJson(v)) fail('RULES_SIGNATURE_MISMATCH', k);
    }
    if (!ISO_Z.test(ticket.issued_at || '')) fail('RULES_SIGNATURE_EXPIRED', 'issued_at');
    const age = now() - Date.parse(ticket.issued_at);
    if (age > TICKET_MAX_AGE_MS || age < -TICKET_SKEW_MS) fail('RULES_SIGNATURE_EXPIRED', ticket.issued_at);

    return {
      commit, head_sha: head, pr_number: prNumber, registry_digest: atMerge.digest, role_parents: atMerge.role_parents,
      github: { base: 'main', merged: true, merge_commit: commit, head_sha: head, pr_number: prNumber, pr_url: prUrl,
        required_checks: required, check_runs: checkRuns },
      signature: { namespace: RULES_NAMESPACE, key_fingerprint: key.fp, signed_ticket_sha256, ticket },
    };
  }

  // Подпись оператора под подтверждением отчёта: билет {tenant_id, report_id, report_sha256}.
  function verifyReportAck({ tenantId, reportId, reportSha256, ticketText, signature, activeRulesCommit }) {
    const { ticket, key, signed_ticket_sha256 } = verifyTicket({ ticketText, signature,
      namespace: REPORT_ACK_NAMESPACE, activeRulesCommit });
    const want = { tenant_id: tenantId, report_id: reportId, report_sha256: reportSha256 };
    if (canonicalJson(ticket) !== canonicalJson(want)) fail('REPORT_NOT_RECIPIENT', 'ticket');
    return { namespace: REPORT_ACK_NAMESPACE, key_fingerprint: key.fp, signed_ticket_sha256, ticket: want };
  }

  // Проверка перед арендой (Л.8).
  function checkWorkingCopy(rulesCommit) {
    if (!SHA1.test(rulesCommit || '')) fail('LEASE_NO_ACTIVE_RULES', String(rulesCommit));
    if (git(['status', '--porcelain', '--untracked-files=normal']).toString('utf8').trim() !== '') {
      fail('RULES_WORKTREE_DIRTY', repoDir);
    }
    if (fetch) git(['fetch', '--quiet', 'origin', 'main']);
    const headCommit = revParse('HEAD');
    if (headCommit !== revParse('origin/main')) fail('RULES_HEAD_NOT_MAIN', headCommit);
    if (!sameRules(readRules(rulesCommit), readRules(headCommit))) fail('RULES_WORKTREE_DIFFERS', headCommit);
    return { code_commit: headCommit, rules_commit: rulesCommit };
  }

  return { collectActivation, verifyReportAck, checkWorkingCopy, readRules };
}
