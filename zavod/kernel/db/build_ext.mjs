// ДОКУМЕНТ: db/build_ext.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 14:19 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 14:19 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: собрать db/02_zavod_ext_01.sql = неизменная часть + функции publish_subject и
//   release_subject из 01 H1.31 дословно с двумя заменами области. Каждая замена обязана
//   сработать ровно один раз, иначе сборка падает (защита от тихого расхождения с H1.31).
// ВЫЗОВ: node db/build_ext.mjs <01_database_migration.sql> [--check]
//   --check: собрать в память и сверить с лежащим файлом (CI), ничего не писать.

import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const here = p => fileURLToPath(new URL(p, import.meta.url));
const [src, flag] = process.argv.slice(2);
const h131 = readFileSync(src, 'utf8').replace(/\r\n/g, '\n');
const sha = s => createHash('sha256').update(s).digest('hex');

function block(name) {
  const start = h131.indexOf(`CREATE OR REPLACE FUNCTION bem_control.${name}(`);
  if (start < 0) throw new Error(`no function ${name}`);
  const next = h131.indexOf('\nCREATE OR REPLACE FUNCTION ', start + 10);
  return h131.slice(start, next + 1);
}
function replaceOnce(text, from, to) {
  const n = text.split(from).length - 1;
  if (n !== 1) throw new Error(`replacement must match once, got ${n}: ${from}`);
  return text.replace(from, to);
}

const pub = replaceOnce(block('publish_subject'),
  "IF p_scope NOT IN ('WORKING', 'BEM954_PROTOCOL') THEN",
  "IF p_scope NOT IN ('WORKING', 'BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE') THEN");
const rel = replaceOnce(block('release_subject'),
  "IF v_subject.scope = 'BEM954_PROTOCOL' THEN",
  "IF v_subject.scope IN ('BEM954_PROTOCOL', 'ZAVOD_PRODUCT_RELEASE') THEN");
const stat = readFileSync(here('./zavod_ext_01_static.sql'), 'utf8').replace(/\r\n/g, '\n');

const out = `-- ДОКУМЕНТ: db/02_zavod_ext_01.sql — СОБРАН db/build_ext.mjs, руками не править
-- ИСТОЧНИК H1.31 01: sha256 ${sha(h131)}
-- НЕИЗМЕННАЯ ЧАСТЬ: db/zavod_ext_01_static.sql sha256 ${sha(stat)}
\\set ON_ERROR_STOP on
BEGIN;
${stat}
-- Функции H1.31 дословно, замена только условия области (build_ext.mjs, по одной замене).
${pub}
${rel}
-- Самопроверка расширения: при любом расхождении транзакция откатывается.
DO $chk$
DECLARE v int;
BEGIN
  SELECT count(*) INTO v FROM pg_constraint
   WHERE conname = 'subject_scope_check'
     AND pg_get_constraintdef(oid) LIKE '%ZAVOD_PRODUCT_RELEASE%';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: scope check'; END IF;
  SELECT count(*) INTO v FROM information_schema.columns
   WHERE table_schema = 'bem_core' AND table_name = 'outbox' AND column_name = 'send_started_epoch';
  IF v <> 1 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: send_started_epoch'; END IF;
  SELECT count(*) INTO v FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'bem_control'
     AND p.proname IN ('mark_outbox_send_started', 'set_outbox_kind_policy', 'claim_outbox_batch')
     AND p.prosecdef AND pg_get_userbyid(p.proowner) = 'bem_control_owner';
  IF v <> 3 THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: functions'; END IF;
  IF has_function_privilege('bem_kernel_rw', 'bem_control.set_outbox_kind_policy(text, boolean, text)', 'EXECUTE')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may set policy'; END IF;
  IF has_table_privilege('bem_kernel_rw', 'bem_control.outbox_kind_policy', 'INSERT')
  THEN RAISE EXCEPTION 'ZAVOD_EXT_FAILED: kernel may write policy'; END IF;
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
