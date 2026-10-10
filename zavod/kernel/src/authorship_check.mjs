// ДОКУМЕНТ: src/authorship_check.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 13:20 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 13:20 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: критерий E5-2 протокола Z1 v1.9 (W2) — код написан рабочими, ни один автор не принял свою
//   работу. По выгрузке subject_author и audit_record одного предмета: автор — только рабочий (claude:/codex:),
//   не человек; ни один вердикт по действующей версии (head_sha предмета) не поставлен автором; ACCEPT по
//   действующей версии дали ровно поставщики {anthropic, openai}; вердикта человека нет. Выгрузка печатается
//   суммой SHA-256 канонического текста (доказательство E5-2, раздел 9 протокола).
// ОГРАНИЧЕНИЯ: проверяет записанное в Kernel. Сервер (Z-EXT-01) и сам не даёт автору поставить вердикт;
//   эта проверка — независимое доказательство по выгрузке, а не замена серверному правилу.

import { createHash } from 'node:crypto';
import { canonical } from './release_manifest.mjs';

const WORKER = /^(claude|codex):/;
const PAIR = ['anthropic', 'openai'];

// subject — строка bem_core.subject; authors — строки subject_author; verdicts — строки audit_record.
export function checkAuthorship({ subject, authors, verdicts }) {
  const problems = [];
  if (!subject) return { ok: false, problems: ['NO_SUBJECT'], sha256: null };
  if (authors.length === 0) problems.push('NO_AUTHOR');
  for (const a of authors) {
    if (a.subject_id !== subject.id) problems.push(`FOREIGN_AUTHOR_ROW ${a.actor_id}`);
    if (!WORKER.test(String(a.actor_id))) problems.push(`NOT_A_WORKER ${a.actor_id}`);
  }
  const authorIds = new Set(authors.map((a) => a.actor_id));
  const current = [];
  for (const v of verdicts) {
    if (v.subject_id !== subject.id) { problems.push(`FOREIGN_VERDICT_ROW ${v.id}`); continue; }
    if (v.head_sha !== subject.head_sha) continue; // вердикт старой версии не действует
    current.push(v);
    if (authorIds.has(v.auditor_actor)) problems.push(`SELF_REVIEW ${v.auditor_actor}`);
    if (v.auditor_provider === 'human' || /^human:/.test(String(v.auditor_actor))) problems.push(`HUMAN_VERDICT ${v.auditor_actor}`);
  }
  const accepts = current.filter((v) => v.verdict === 'ACCEPT');
  const providers = [...new Set(accepts.map((v) => v.auditor_provider))].sort();
  if (canonical(providers) !== canonical(PAIR)) problems.push(`ACCEPT_PROVIDERS ${providers.join(',') || 'none'}`);
  const text = canonical({
    subject: { id: subject.id, head_sha: subject.head_sha, scope: subject.scope ?? null },
    authors: authors.map((a) => ({ actor_id: a.actor_id, provider: a.provider })).sort((x, y) => x.actor_id.localeCompare(y.actor_id)),
    verdicts: verdicts.map((v) => ({ id: v.id, head_sha: v.head_sha, auditor_actor: v.auditor_actor,
      auditor_provider: v.auditor_provider, verdict: v.verdict })).sort((x, y) => String(x.id).localeCompare(String(y.id))),
  });
  return { ok: problems.length === 0, problems, sha256: createHash('sha256').update(text).digest('hex') };
}

// Выгрузка из Kernel одним клиентом (роль с правом чтения и контекстом заказчика).
export async function loadAuthorship(c, tenantId, subjectId) {
  await c.query("SELECT set_config('app.tenant_id', $1, false)", [tenantId]);
  const one = async (sql) => (await c.query(sql, [subjectId])).rows;
  const [subject] = await one('SELECT id, tenant_id, work_item_id, head_sha, scope FROM bem_core.subject WHERE id = $1');
  const authors = await one('SELECT subject_id, actor_id::text AS actor_id, provider::text AS provider FROM bem_core.subject_author WHERE subject_id = $1');
  const verdicts = await one(`SELECT id, subject_id, head_sha, auditor_actor::text AS auditor_actor,
    auditor_provider::text AS auditor_provider, verdict::text AS verdict
    FROM bem_core.audit_record WHERE subject_id = $1`);
  return { subject, authors, verdicts };
}
