// ДОКУМЕНТ: db/build_final_ext.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 16:19 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 16:19 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: парная дельта-проверка для Z-EXT-01. Собирает db/05_final_state_check_ext01.sql =
//   терминальная проверка H1.31 05 дословно + точный список отличий, которые вносит Z-EXT-01.
//   Каждая правка обязана сработать ровно один раз. Итог: после расширения база совпадает с
//   договором H1.31 во всём, кроме перечисленного здесь; лишний или недостающий объект — отказ.
//   Порядок в CI: 05 H1.31 проходит ДО расширения (обёртка), 05_ext01 — ПОСЛЕ.
// ВЫЗОВ: node db/build_final_ext.mjs <05_final_state_check.sql> [--check]

import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const [src, flag] = process.argv.slice(2);
const base = readFileSync(src, 'utf8').replace(/\r\n/g, '\n');
const sha = (s) => createHash('sha256').update(s).digest('hex');

function once(text, from, to) {
  const n = text.split(from).length - 1;
  if (n !== 1) throw new Error(`edit must match once, got ${n}: ${from.slice(0, 120)}`);
  return text.replace(from, () => to);
}
// Вставка строк массива после строки-якоря (якорь оканчивается запятой: порядок в 05 не важен,
// списки сравниваются как множества).
const after = (text, anchor, lines) =>
  once(text, `        '${anchor}',\n`, `        '${anchor}',\n` + lines.map((l) => `        '${l}',\n`).join(''));

let t = base;
// Ограничения: новая область выпуска и таблица политики видов.
t = once(t, "'TABLE|bem_core.subject|subject_scope_check|CHECK ((scope = ANY (ARRAY[''WORKING''::text, ''BEM954_PROTOCOL''::text])))'",
  "'TABLE|bem_core.subject|subject_scope_check|CHECK ((scope = ANY (ARRAY[''WORKING''::text, ''BEM954_PROTOCOL''::text, ''ZAVOD_PRODUCT_RELEASE''::text])))'");
t = after(t, 'TABLE|bem_core.outbox|outbox_pkey|PRIMARY KEY (id)', [
  'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_pkey|PRIMARY KEY (kind)',
  "TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_kind_check|CHECK ((kind ~ ''^[A-Za-z][A-Za-z0-9_.:-]{0,127}$''::text))",
  "TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_evidence_check|CHECK ((btrim(evidence) <> ''''::text))",
]);
// Права (ACL): колонка отметки, две новые функции, таблица политики видов.
t = after(t, 'COLUMN|bem_core.outbox.lease_epoch|bem_control_owner|UPDATE|bem_core_owner', [
  'COLUMN|bem_core.outbox.send_started_epoch|bem_control_owner|UPDATE|bem_core_owner',
]);
t = after(t, 'FUNCTION|bem_control.claim_outbox_batch(integer, interval, text)|bem_kernel_rw|EXECUTE|bem_control_owner', [
  'FUNCTION|bem_control.mark_outbox_send_started(uuid, bigint, text)|bem_control_owner|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.mark_outbox_send_started(uuid, bigint, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.set_outbox_kind_policy(text, boolean, text)|bem_control_owner|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.set_outbox_kind_policy(text, boolean, text)|bem_governance|EXECUTE|bem_control_owner',
]);
// Права владельца на свою таблицу — полный стандартный набор PostgreSQL (как у authority_guard в 05).
const OWNER_PRIVS = ['DELETE', 'INSERT', 'REFERENCES', 'SELECT', 'TRIGGER', 'TRUNCATE', 'UPDATE'];
t = after(t, 'TABLE|bem_control.authority_guard|backup_reader|SELECT|bem_control_owner', [
  ...OWNER_PRIVS.map((p) => `TABLE|bem_control.outbox_kind_policy|bem_control_owner|${p}|bem_control_owner`),
  'TABLE|bem_control.outbox_kind_policy|backup_reader|SELECT|bem_control_owner',
  'TABLE|bem_control.outbox_kind_policy|bem_kernel_rw|SELECT|bem_control_owner',
]);

const out =`-- ДОКУМЕНТ: db/05_final_state_check_ext01.sql — СОБРАН db/build_final_ext.mjs, руками не править
-- ИСТОЧНИК H1.31 05: sha256 ${sha(base)}
-- НАЗНАЧЕНИЕ: терминальная проверка H1.31 05 с точным списком отличий Z-EXT-01 (см. сборщик).
${t}`;

const target = here('./05_final_state_check_ext01.sql');
if (flag === '--check') {
  const have = readFileSync(target, 'utf8').replace(/\r\n/g, '\n');
  if (have !== out) { console.log('ZAVOD_FINAL_EXT_BUILD=STALE'); process.exit(1); }
  console.log(`ZAVOD_FINAL_EXT_BUILD=MATCH sha256=${sha(out)}`);
} else {
  writeFileSync(target, out);
  console.log(`ZAVOD_FINAL_EXT_BUILD=WRITTEN bytes=${Buffer.byteLength(out)} sha256=${sha(out)}`);
}
