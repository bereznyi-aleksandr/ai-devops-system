// ДОКУМЕНТ: db/build_ext.mjs
// ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 14:19 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 17:55 +03:00 (v0.3: аудит Z4 M-Z4-01 —
//   ограждение сверяется и с экземпляром среды исполнения; новые подписи в самопроверке;
//   v0.2: reconcile_unknown_outcome с условием ограждения — аудит Z3 M-Z3-03)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: собрать db/02_zavod_ext_01.sql = неизменная часть + функции publish_subject,
//   release_subject и reconcile_unknown_outcome из 01 H1.31 дословно с заменами. Каждая замена
//   обязана сработать ровно один раз, иначе сборка падает (защита от тихого расхождения с H1.31).
// ВЫЗОВ: node db/build_ext.mjs <01_database_migration.sql> [--check]
//   --check: собрать в память и сверить с лежащим файлом (CI), ничего не писать.

import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const here = p => fileURLToPath(new URL(p, import.meta.url));
const [src, flag] = process.argv.slice(2);
const h131 = readFileSync(src, 'utf8').replace(/\r\n/g, '\n');
const sha = s => createHash('sha256').update(s).digest('hex');

// Блок функции: от CREATE до следующего CREATE OR REPLACE FUNCTION или, если задан
// конечный якорь, до конца первой строки с ним (за функцией в 01 может идти чужой код).
function block(name, endAnchor) {
  const start = h131.indexOf(`CREATE OR REPLACE FUNCTION bem_control.${name}(`);
  if (start < 0) throw new Error(`no function ${name}`);
  if (endAnchor) {
    const at = h131.indexOf(endAnchor, start);
    if (at < 0) throw new Error(`no end anchor for ${name}`);
    return h131.slice(start, h131.indexOf('\n', at + endAnchor.length) + 1);
  }
  const next = h131.indexOf('\nCREATE OR REPLACE FUNCTION ', start + 10);
  return h131.slice(start, next + 1);
}
function replaceOnce(text, from, to) {
  const n = text.split(from).length - 1;
  if (n !== 1) throw new Error(`replacement must match once, got ${n}: ${from}`);
  return text.replace(from, () => to);
}

const pub = replaceOnce(block('publish_subject'),
  "IF p_scope NOT IN ('WORKING', 'BEM954_PROTOCOL') THEN",
  "IF p_scope NOT IN ('WORKING', 'BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE') THEN");
const rel = replaceOnce(block('release_subject'),
  "IF v_subject.scope = 'BEM954_PROTOCOL' THEN",
  "IF v_subject.scope IN ('BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE') THEN");
const rec = replaceOnce(
  block('reconcile_unknown_outcome',
    'GRANT  EXECUTE ON FUNCTION bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)\n       TO bem_governance;'),
  '    v_new := CASE p_outcome\n',
  `    -- Z-EXT-01 (аудит Z3 M-Z3-03): строка, у которой отправка начиналась, возвращается в
    -- очередь только после записи об ограждении исполнителя этого поколения: иначе он может
    -- возобновиться после сверки и сделать второй внешний вызов.
    IF p_outcome = 'CONFIRMED_NOT_SENT' AND EXISTS (
        SELECT 1
          FROM bem_core.outbox o
         WHERE o.id = p_outbox_id
           AND o.send_started_epoch IS NOT NULL
           AND NOT EXISTS (SELECT 1
                             FROM bem_control.outbox_send_fence f
                            WHERE f.outbox_id        = o.id
                              AND f.lease_epoch      = o.send_started_epoch
                              AND f.runtime_instance = o.send_runtime_instance))
    THEN
        RAISE EXCEPTION 'RECONCILE_NOT_FENCED: исполнитель, начавший отправку, не огражден';
    END IF;

    v_new := CASE p_outcome
`);
const stat = readFileSync(here('./zavod_ext_01_static.sql'), 'utf8').replace(/\r\n/g, '\n');

const out = `-- ДОКУМЕНТ: db/02_zavod_ext_01.sql — СОБРАН db/build_ext.mjs, руками не править
-- ИСТОЧНИК H1.31 01: sha256 ${sha(h131)}
-- НЕИЗМЕННАЯ ЧАСТЬ: db/zavod_ext_01_static.sql sha256 ${sha(stat)}
\\set ON_ERROR_STOP on
BEGIN;
${stat}
-- Функции H1.31 дословно, заменены только условие области и условие сверки (build_ext.mjs, по одной замене).
${pub}
${rel}
${rec}
-- Самопроверка расширения: при любом расхождении транзакция откатывается.
DO $chk$
DECLARE v int;
BEGIN
  SELECT count(*) INTO v FROM pg_constraint
   WHERE conname = 'subject_scope_check'
     AND pg_get_constraintdef(oid) LIKE '%ZAVOD_PRODUCT_RELEASE%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: scope check'; END IF;
  SELECT count(*) INTO v FROM information_schema.columns
   WHERE table_schema = 'bem_core' AND table_name = 'outbox'
     AND column_name IN ('send_started_epoch', 'send_policy_version', 'send_policy_idempotent',
                         'send_runtime_instance');
  IF v <> 4 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: outbox columns'; END IF;
  SELECT count(*) INTO v FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'bem_control'
     AND p.proname IN ('mark_outbox_send_started', 'set_outbox_kind_policy', 'claim_outbox_batch',
                       'record_outbox_fence')
     AND p.prosecdef AND pg_get_userbyid(p.proowner) = 'bem_control_owner';
  IF v <> 4 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: functions'; END IF;
  SELECT count(*) INTO v FROM pg_proc
   WHERE oid = 'bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)'::regprocedure
     AND prosrc LIKE '%RECONCILE_NOT_FENCED%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: reconcile fence'; END IF;
  IF has_function_privilege('bem_kernel_rw', 'bem_control.set_outbox_kind_policy(text, boolean, text, text, text)', 'EXECUTE')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may set policy'; END IF;
  IF has_function_privilege('bem_kernel_rw', 'bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)', 'EXECUTE')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may record fence'; END IF;
  IF has_table_privilege('bem_kernel_rw', 'bem_control.outbox_kind_policy', 'INSERT')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may write policy'; END IF;
  IF has_table_privilege('bem_kernel_rw', 'bem_control.outbox_send_fence', 'INSERT')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may write fence'; END IF;
  IF to_regprocedure('bem_control.mark_outbox_send_started(uuid, bigint, text)') IS NOT NULL
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: mark without runtime instance'; END IF;
  SELECT count(*) INTO v FROM pg_proc
   WHERE oid = 'bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)'::regprocedure
     AND prosrc LIKE '%FENCE_RUNTIME_MISMATCH%' AND prosrc LIKE '%FENCE_EVIDENCE_INCOMPLETE%'
     AND prosrc LIKE '%FENCE_SELF_REPORT%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: fence checks'; END IF;
END
$chk$;
COMMIT;
`;

const target = here('./02_zavod_ext_01.sql');
if (flag === '--check') {
  const have = readFileSync(target, 'utf8').replace(/\r\n/g, '\n');
  if (have !== out) { console.log('ZAVOD_EXT_BUILD=STALE'); process.exit(1); }
  console.log(`ZAVOD_EXT_BUILD=MATCH sha256=${sha(out)}`);
} else {
  writeFileSync(target, out);
  console.log(`ZAVOD_EXT_BUILD=WRITTEN bytes=${Buffer.byteLength(out)} sha256=${sha(out)}`);
}
