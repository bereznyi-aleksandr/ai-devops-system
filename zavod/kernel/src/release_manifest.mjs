// ДОКУМЕНТ: src/release_manifest.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:35 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:35 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: SR-13 протокола Z1 v1.9 (угроза T14, критерий E5-7) — манифест выпуска и его сверка
//   Egress до внешнего действия. Манифест связывает числовой id и полное имя репозитория продукта,
//   tenant_id, заказ (work_item_id), предмет, head_sha, сумму файла блокировки, SHA-256 артефакта,
//   номера сборки и тестов, номера вердиктов, строку outbox и Evidence решения оператора; печать
//   manifest_sha256 — сумма канонического текста этих полей. Сверка отказывает при любом несовпадении:
//   артефакт, печать, предмет (только выпущенный ZAVOD_PRODUCT_RELEASE того же tenant_id и заказа),
//   строка outbox (tenant_id, заказ, репозиторий, печать, сумма артефакта), решение оператора
//   (OPERATOR_DECISION с автором-человеком, называющее этот предмет и head_sha).
// ОГРАНИЧЕНИЯ: модуль чистый — данные строк передаёт вызывающий (Egress читает их из Kernel). Неизменяемость
//   записи Evidence манифеста обеспечивает база (H1.31: Evidence только добавляется); здесь — сверка.
//   Подключение к Egress выпуска и запись манифеста в Evidence — следующий шаг этапа 5.

import { createHash } from 'node:crypto';

export const RELEASE_SCOPE = 'ZAVOD_PRODUCT_RELEASE';

export class ReleaseRefused extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.code = code; }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HEX = (n) => new RegExp(`^[0-9a-f]{${n}}$`);
const posInt = (v) => Number.isSafeInteger(v) && v > 0;

// Поля манифеста и их проверка формы. Порядок не важен: печать считается по каноническому тексту.
const SHAPE = {
  repo_id: posInt,
  repo_full_name: (v) => typeof v === 'string' && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(v),
  tenant_id: (v) => UUID.test(v),
  work_item_id: (v) => UUID.test(v),
  subject_id: (v) => UUID.test(v),
  head_sha: (v) => HEX(40).test(v),
  lock_sha256: (v) => HEX(64).test(v),
  artifact_sha256: (v) => HEX(64).test(v),
  build_run: posInt,
  test_run: posInt,
  verdict_ids: (v) => Array.isArray(v) && v.length > 0 && v.every((x) => UUID.test(x)),
  outbox_id: (v) => UUID.test(v),
  decision_evidence_id: (v) => UUID.test(v),
};
export const MANIFEST_FIELDS = Object.keys(SHAPE).sort();

const need = (ok, code, detail) => { if (!ok) throw new ReleaseRefused(code, detail); };
const sha256 = (data) => createHash('sha256').update(data).digest('hex');

// Канонический текст: ключи по алфавиту на всех уровнях, без пробелов.
export function canonical(v) {
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  if (v && typeof v === 'object') {
    return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canonical(v[k])}`).join(',')}}`;
  }
  return JSON.stringify(v);
}

function checkShape(m) {
  need(m && typeof m === 'object', 'BAD_MANIFEST', 'not an object');
  const extra = Object.keys(m).filter((k) => k !== 'manifest_sha256' && !(k in SHAPE));
  need(extra.length === 0, 'BAD_MANIFEST', `unknown field ${extra[0]}`);
  for (const k of MANIFEST_FIELDS) need(SHAPE[k](m[k]), 'BAD_MANIFEST', k);
}

function body(m) {
  return Object.fromEntries(MANIFEST_FIELDS.map((k) => [k, m[k]]));
}

export function sealManifest(fields) {
  checkShape(fields);
  const b = body(fields);
  return { ...b, manifest_sha256: sha256(canonical(b)) };
}

// Сверка перед внешним действием. Возвращает печать манифеста или бросает ReleaseRefused.
export function verifyRelease({ manifest, artifact, subject, outbox, decision }) {
  checkShape(manifest);
  const seal = sha256(canonical(body(manifest)));
  need(manifest.manifest_sha256 === seal, 'MANIFEST_TAMPERED', 'seal does not match fields');

  need(artifact instanceof Uint8Array, 'ARTIFACT_MISMATCH', 'no artifact bytes');
  need(sha256(artifact) === manifest.artifact_sha256, 'ARTIFACT_MISMATCH', 'artifact sha256');

  need(subject && subject.id === manifest.subject_id, 'SUBJECT_MISMATCH', 'subject id');
  need(subject.scope === RELEASE_SCOPE, 'BAD_SCOPE', `subject scope ${subject.scope}`);
  need(subject.released_at != null, 'NOT_RELEASED', 'subject is not released');
  need(subject.head_sha === manifest.head_sha, 'HEAD_MISMATCH', 'subject head_sha');
  need(subject.tenant_id === manifest.tenant_id, 'TENANT_MISMATCH', 'subject tenant_id');
  need(subject.work_item_id === manifest.work_item_id, 'ORDER_MISMATCH', 'subject work_item_id');

  need(outbox && outbox.id === manifest.outbox_id, 'OUTBOX_MISMATCH', 'outbox id');
  need(outbox.tenant_id === manifest.tenant_id, 'TENANT_MISMATCH', 'outbox tenant_id');
  need(outbox.work_item_id === manifest.work_item_id, 'ORDER_MISMATCH', 'outbox work_item_id');
  const p = outbox.payload || {};
  need(p.repo_id === manifest.repo_id && p.repo_full_name === manifest.repo_full_name,
    'REPO_MISMATCH', 'outbox repository');
  need(p.manifest_sha256 === seal, 'MANIFEST_MISMATCH', 'outbox manifest seal');
  need(p.artifact_sha256 === manifest.artifact_sha256, 'ARTIFACT_MISMATCH', 'outbox artifact sha256');

  const d = decision || {};
  const dp = d.payload || {};
  need(d.id === manifest.decision_evidence_id && d.kind === 'OPERATOR_DECISION',
    'NO_OPERATOR_DECISION', 'decision evidence');
  need(d.tenant_id === manifest.tenant_id, 'NO_OPERATOR_DECISION', 'decision tenant_id');
  need(d.provider === 'human' && /^human:/.test(d.actor_id || ''), 'NO_OPERATOR_DECISION',
    'decision author is not human');
  need(dp.decision_code === RELEASE_SCOPE && dp.decision?.subject_id === manifest.subject_id
    && dp.decision?.head_sha === manifest.head_sha, 'NO_OPERATOR_DECISION', 'decision does not name this release');
  return seal;
}

// Egress выпуска: внешний вызов только после успешной сверки.
export async function releaseViaEgress(rows, send) {
  const seal = verifyRelease(rows);
  return send({ manifest_sha256: seal, outbox_id: rows.outbox.id });
}
