// ДОКУМЕНТ: src/order_history.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:50 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 07:50 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: критерий E5-1 протокола Z1 v1.9 (W1) — история заказа: после заявки оператор не переносит
//   сообщения. По выгрузке command_log одного заказа: человек (actor_id human:…) может быть автором только
//   первой строки (внесение заявки); любая следующая строка от человека — MANUAL_RELAY. Решение оператора
//   на узле 19 — Evidence OPERATOR_DECISION, а не переход, поэтому в command_log его нет и правилу оно не
//   противоречит. Выгрузка печатается суммой SHA-256 канонического текста (доказательство E5-1, раздел 9).
// ОГРАНИЧЕНИЯ: проверяет только то, что записано в Kernel; перенос сообщений мимо Kernel виден по отсутствию
//   строк, а не по этой проверке (её дополняет проверка пути статусов в CI).

import { createHash } from 'node:crypto';
import { canonical } from './release_manifest.mjs';

const isHuman = (a) => /^human:/.test(String(a || ''));

// rows — строки command_log одного заказа. Возвращает { ok, problems, sha256 }.
export function checkOrderHistory(rows, workItemId) {
  const problems = [];
  const own = [...rows].sort((a, b) => new Date(a.created_at) - new Date(b.created_at)
    || String(a.command_id).localeCompare(String(b.command_id)));
  if (own.length === 0) problems.push('EMPTY_HISTORY');
  own.forEach((r, i) => {
    if (r.work_item_id !== workItemId) problems.push(`FOREIGN_ROW ${r.command_id}`);
    if (i > 0 && isHuman(r.actor_id)) problems.push(`MANUAL_RELAY ${r.command_id} ${r.actor_id}`);
  });
  const text = canonical(own.map((r) => ({ command_id: r.command_id, actor_id: r.actor_id,
    result_revision: r.result_revision, kind: r.kind ?? null, created_at: new Date(r.created_at).toISOString() })));
  return { ok: problems.length === 0, problems, sha256: createHash('sha256').update(text).digest('hex') };
}
