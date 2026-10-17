// ДОКУМЕНТ: db/build_final_ext.mjs
// ВЕРСИЯ: v0.5  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-07 16:19 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 00:08 +03:00 (v0.5: Z-EXT-02 (db/03_zavod_ext_02.sql,
//   пакеты Z-RULES-01 и Z-HANDOFF-01) — ограничения четырёх новых таблиц, права на таблицы и шесть функций, отпечатки
//   их тел; итоговая проверка идёт после установки 03;
//   v0.4: аудит Z5 —
//   новый набор способов ограждения: CGROUP_KILLED / JOB_OBJECT_TERMINATED / CONTAINER_TERMINATED;
//   v0.3: аудит Z4 M-Z4-01 —
//   колонка send_runtime_instance, новые подписи отметки и ограждения, проверка экземпляра;
//   v0.2: аудит Z3 M-Z3-01 —
//   отпечатки тел всех функций, которые создаёт или меняет Z-EXT-01, включая claim_outbox_batch;
//   объекты v0.3 расширения: версии политики, закреплённые колонки, ограждение)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: парная дельта-проверка для Z-EXT-01. Собирает db/05_final_state_check_ext01.sql =
//   терминальная проверка H1.31 05 дословно + точный список отличий, которые вносит Z-EXT-01:
//   ограничения, права на колонки, функции и таблицы — правками списков 05; тела функций —
//   добавочным блоком: SHA-256 исходного текста каждой функции расширения (ровно одна функция
//   с таким именем, отпечаток равен отпечатку из db/02_zavod_ext_01.sql). Подмена тела любой из
//   них, в том числе claim_outbox_batch, — отказ FINAL_ZAVOD_FN_BODY_MISMATCH.
//   Каждая правка обязана сработать ровно один раз. Порядок в CI: 05 H1.31 проходит ДО расширения
//   (обёртка), 05_ext01 — ПОСЛЕ, затем проба с подменой claim_outbox_batch обязана упасть.
// ВЫЗОВ: node db/build_final_ext.mjs <05_final_state_check.sql> [--check]

import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const [src, flag] = process.argv.slice(2);
const base = readFileSync(src, 'utf8').replace(/\r\n/g, '\n');
const ext = readFileSync(here('./02_zavod_ext_01.sql'), 'utf8').replace(/\r\n/g, '\n');
const ext02 = readFileSync(here('./03_zavod_ext_02.sql'), 'utf8').replace(/\r\n/g, '\n');
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
// Ограничения: новая область выпуска, таблица версий политики, таблица ограждения.
t = once(t, "'TABLE|bem_core.subject|subject_scope_check|CHECK ((scope = ANY (ARRAY[''WORKING''::text, ''BEM954_PROTOCOL''::text])))'",
  "'TABLE|bem_core.subject|subject_scope_check|CHECK ((scope = ANY (ARRAY[''WORKING''::text, ''BEM954_PROTOCOL''::text, ''ZAVOD_PRODUCT_RELEASE''::text])))'");
t = after(t, 'TABLE|bem_core.outbox|outbox_pkey|PRIMARY KEY (id)', [
  'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_pkey|PRIMARY KEY (kind, version)',
  "TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_kind_check|CHECK ((kind ~ ''^[A-Za-z][A-Za-z0-9_.:-]{0,127}$''::text))",
  'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_version_check|CHECK ((version >= 1))',
  "TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_adapter_version_check|CHECK ((btrim(adapter_version) <> ''''::text))",
  "TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_key_scheme_check|CHECK ((btrim(key_scheme) <> ''''::text))",
  "TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_evidence_check|CHECK ((btrim(evidence) <> ''''::text))",
  'TABLE|bem_control.outbox_send_fence|outbox_send_fence_pkey|PRIMARY KEY (outbox_id, lease_epoch)',
  "TABLE|bem_control.outbox_send_fence|outbox_send_fence_worker_check|CHECK ((btrim(worker) <> ''''::text))",
  "TABLE|bem_control.outbox_send_fence|outbox_send_fence_runtime_instance_check|CHECK ((btrim(runtime_instance) <> ''''::text))",
  "TABLE|bem_control.outbox_send_fence|outbox_send_fence_method_check|CHECK ((method = ANY (ARRAY[''CGROUP_KILLED''::text, ''JOB_OBJECT_TERMINATED''::text, ''CONTAINER_TERMINATED''::text])))",
]);
// Права (ACL): колонки отметки и закреплённой политики, новые функции, новые таблицы.
t = after(t, 'COLUMN|bem_core.outbox.lease_epoch|bem_control_owner|UPDATE|bem_core_owner', [
  'COLUMN|bem_core.outbox.send_started_epoch|bem_control_owner|UPDATE|bem_core_owner',
  'COLUMN|bem_core.outbox.send_policy_version|bem_control_owner|UPDATE|bem_core_owner',
  'COLUMN|bem_core.outbox.send_policy_idempotent|bem_control_owner|UPDATE|bem_core_owner',
  'COLUMN|bem_core.outbox.send_runtime_instance|bem_control_owner|UPDATE|bem_core_owner',
]);
t = after(t, 'FUNCTION|bem_control.claim_outbox_batch(integer, interval, text)|bem_kernel_rw|EXECUTE|bem_control_owner', [
  'FUNCTION|bem_control.mark_outbox_send_started(uuid, bigint, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.mark_outbox_send_started(uuid, bigint, text, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.set_outbox_kind_policy(text, boolean, text, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.set_outbox_kind_policy(text, boolean, text, text, text)|bem_governance|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
  'FUNCTION|bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
]);
// Права владельца на свою таблицу — полный стандартный набор PostgreSQL (как у authority_guard в 05).
const OWNER_PRIVS = ['DELETE', 'INSERT', 'REFERENCES', 'SELECT', 'TRIGGER', 'TRUNCATE', 'UPDATE'];
t = after(t, 'TABLE|bem_control.authority_guard|backup_reader|SELECT|bem_control_owner', [
  ...OWNER_PRIVS.map((p) => `TABLE|bem_control.outbox_kind_policy|bem_control_owner|${p}|bem_control_owner`),
  'TABLE|bem_control.outbox_kind_policy|backup_reader|SELECT|bem_control_owner',
  'TABLE|bem_control.outbox_kind_policy|bem_kernel_rw|SELECT|bem_control_owner',
  ...OWNER_PRIVS.map((p) => `TABLE|bem_control.outbox_send_fence|bem_control_owner|${p}|bem_control_owner`),
  'TABLE|bem_control.outbox_send_fence|backup_reader|SELECT|bem_control_owner',
]);

// Z-EXT-02: ограничения новых таблиц — текст pg_get_constraintdef дословно (кавычки удваиваются для литерала 05).
const sqlLit = (s) => s.replace(/'/g, "''");
const EXT02_CONSTRAINTS = [
  "TABLE|bem_control.chat_lease_evidence|chat_lease_evidence_content_sha256_check|CHECK ((content_sha256 ~ '^[0-9a-f]{64}$'::text))",
  "TABLE|bem_control.chat_lease_evidence|chat_lease_evidence_generation_check|CHECK ((generation >= 1))",
  "TABLE|bem_control.chat_lease_evidence|chat_lease_evidence_holder_session_check|CHECK ((btrim(holder_session) <> ''::text))",
  "TABLE|bem_control.chat_lease_evidence|chat_lease_evidence_kind_check|CHECK ((kind = ANY (ARRAY['TASK_RESULT'::text, 'ROLE_MEMORY'::text, 'NEXT_STEP'::text])))",
  "TABLE|bem_control.chat_lease_evidence|chat_lease_evidence_lease_id_fkey|FOREIGN KEY (lease_id) REFERENCES bem_control.chat_lease(lease_id)",
  "TABLE|bem_control.chat_lease_evidence|chat_lease_evidence_pkey|PRIMARY KEY (evidence_id)",
  "TABLE|bem_control.chat_lease|chat_lease_chat_number_check|CHECK (((chat_number ~ '^[A-Z][0-9]{5}$'::text) AND (substr(chat_number, 2) <> '00000'::text)))",
  "TABLE|bem_control.chat_lease|chat_lease_closed_pair|CHECK (((status = 'COMPLETED'::text) = ((closed_at IS NOT NULL) AND (completion_evidence_id IS NOT NULL) AND (result_evidence_id IS NOT NULL) AND (memory_evidence_id IS NOT NULL) AND (next_evidence_id IS NOT NULL) AND (report_id IS NOT NULL))))",
  "TABLE|bem_control.chat_lease|chat_lease_code_commit_check|CHECK ((code_commit ~ '^[0-9a-f]{40}$'::text))",
  "TABLE|bem_control.chat_lease|chat_lease_generation_check|CHECK ((generation >= 1))",
  "TABLE|bem_control.chat_lease|chat_lease_generation_unique|UNIQUE (tenant_id, role_key, generation)",
  "TABLE|bem_control.chat_lease|chat_lease_holder_session_check|CHECK (((btrim(holder_session) <> ''::text) AND (holder_session <> 'OPERATOR'::text)))",
  "TABLE|bem_control.chat_lease|chat_lease_number_unique|UNIQUE (tenant_id, role_key, chat_number)",
  "TABLE|bem_control.chat_lease|chat_lease_opened_by_check|CHECK ((btrim(opened_by) <> ''::text))",
  "TABLE|bem_control.chat_lease|chat_lease_pkey|PRIMARY KEY (lease_id)",
  "TABLE|bem_control.chat_lease|chat_lease_role_key_check|CHECK ((role_key ~ '^0[1-9]_[^/\\\\]{1,60}$'::text))",
  "TABLE|bem_control.chat_lease|chat_lease_rules_commit_check|CHECK ((rules_commit ~ '^[0-9a-f]{40}$'::text))",
  "TABLE|bem_control.chat_lease|chat_lease_status_check|CHECK ((status = ANY (ARRAY['OPEN'::text, 'COMPLETED'::text])))",
  "TABLE|bem_control.lease_report|lease_report_ack_triple|CHECK ((((ack_evidence_id IS NULL) = (ack_session IS NULL)) AND ((ack_session IS NULL) = (acked_at IS NULL))))",
  "TABLE|bem_control.lease_report|lease_report_from_session_check|CHECK ((btrim(from_session) <> ''::text))",
  "TABLE|bem_control.lease_report|lease_report_generation_check|CHECK ((generation >= 1))",
  "TABLE|bem_control.lease_report|lease_report_lease_id_fkey|FOREIGN KEY (lease_id) REFERENCES bem_control.chat_lease(lease_id)",
  "TABLE|bem_control.lease_report|lease_report_pkey|PRIMARY KEY (report_id)",
  "TABLE|bem_control.lease_report|lease_report_recipient_shape|CHECK ((((recipient_role_key = 'OPERATOR'::text) AND (recipient_lease_id IS NULL) AND (recipient_generation IS NULL) AND (recipient_session IS NULL)) OR ((recipient_role_key ~ '^0[1-9]_[^/\\\\]{1,60}$'::text) AND (recipient_lease_id IS NOT NULL) AND (recipient_generation IS NOT NULL) AND (recipient_session IS NOT NULL))))",
  "TABLE|bem_control.lease_report|lease_report_report_sha256_check|CHECK ((report_sha256 ~ '^[0-9a-f]{64}$'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_activated_by_check|CHECK ((btrim(activated_by) <> ''::text))",
  "TABLE|bem_control.rules_activation|rules_activation_head_sha_check|CHECK ((head_sha ~ '^[0-9a-f]{40}$'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_key_fingerprint_check|CHECK ((key_fingerprint ~ '^SHA256:[A-Za-z0-9+/]{43}$'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_pkey|PRIMARY KEY (tenant_id, rules_commit)",
  "TABLE|bem_control.rules_activation|rules_activation_pr_number_check|CHECK ((pr_number >= 1))",
  "TABLE|bem_control.rules_activation|rules_activation_pr_url_check|CHECK ((pr_url ~ '^https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*$'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_registry_digest_check|CHECK ((registry_digest ~ '^[0-9a-f]{64}$'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_role_parents_check|CHECK ((jsonb_typeof(role_parents) = 'object'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_rules_commit_check|CHECK ((rules_commit ~ '^[0-9a-f]{40}$'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_superseded_by_check|CHECK ((superseded_by ~ '^[0-9a-f]{40}$'::text))",
  "TABLE|bem_control.rules_activation|rules_activation_superseded_pair|CHECK (((superseded_at IS NULL) = (superseded_by IS NULL)))",
];
t = after(t, 'TABLE|bem_core.outbox|outbox_pkey|PRIMARY KEY (id)', EXT02_CONSTRAINTS.map(sqlLit));
const EXT02_TABLES = ['rules_activation', 'chat_lease', 'chat_lease_evidence', 'lease_report'];
t = after(t, 'TABLE|bem_control.authority_guard|backup_reader|SELECT|bem_control_owner', EXT02_TABLES.flatMap((n) => [
  ...OWNER_PRIVS.map((p) => `TABLE|bem_control.${n}|bem_control_owner|${p}|bem_control_owner`),
  `TABLE|bem_control.${n}|backup_reader|SELECT|bem_control_owner`,
  `TABLE|bem_control.${n}|bem_kernel_rw|SELECT|bem_control_owner`,
]));
const EXT02_FUNCS = {
  activate_rules: 'uuid, text, text, integer, text, uuid, jsonb, jsonb, jsonb',
  open_chat_lease: 'uuid, text, uuid, text, text, text',
  record_lease_evidence: 'uuid, uuid, integer, text, text, text, jsonb',
  file_lease_report: 'uuid, uuid, integer, text, text',
  acknowledge_lease_report: 'uuid, uuid, text, text, text, jsonb',
  complete_chat_lease: 'uuid, uuid, integer, text, uuid, uuid, uuid, uuid',
};
t = after(t, 'FUNCTION|bem_control.claim_outbox_batch(integer, interval, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
  Object.entries(EXT02_FUNCS).flatMap(([n, a]) => ['bem_control_owner', 'bem_kernel_rw']
    .map((who) => `FUNCTION|bem_control.${n}(${a})|${who}|EXECUTE|bem_control_owner`)));

// Отпечатки тел функций расширения: исходный текст между ограничителями $tag$ последнего
// определения функции в 02 — ровно то, что PostgreSQL хранит в pg_proc.prosrc.
const FUNCS = ['publish_subject', 'release_subject', 'reconcile_unknown_outcome', 'claim_outbox_batch',
  'mark_outbox_send_started', 'set_outbox_kind_policy', 'record_outbox_fence'];
function body(name, src = ext) {
  const re = new RegExp(`CREATE (OR REPLACE )?FUNCTION bem_control\\.${name}\\(`, 'g');
  let last = -1;
  for (const m of src.matchAll(re)) last = m.index;
  if (last < 0) throw new Error(`no function ${name}`);
  const tag = /\bAS (\$[A-Za-z_]*\$)/.exec(src.slice(last));
  if (!tag) throw new Error(`no body tag for ${name}`);
  const from = last + tag.index + tag[0].length;
  const to = src.indexOf(tag[1], from);
  if (to < 0) throw new Error(`unterminated body for ${name}`);
  return src.slice(from, to);
}
const prints = [...FUNCS.map((f) => [f, sha(body(f))]),
  ...Object.keys(EXT02_FUNCS).map((f) => [f, sha(body(f, ext02))])];
const fpBlock = `-- Z-EXT-01 (аудит Z3 M-Z3-01) и Z-EXT-02: тела функций расширений совпадают с db/02_zavod_ext_01.sql
-- и db/03_zavod_ext_02.sql.
-- У каждого имени ровно одна функция в bem_control; лишняя перегрузка или подменённое тело — отказ.
DO $zavod_fp$
DECLARE
    r     record;
    v_cnt integer;
    v_got text;
BEGIN
    FOR r IN SELECT * FROM (VALUES
${prints.map(([f, h]) => `        ('${f}', '${h}')`).join(',\n')}
    ) AS x(fn, want) LOOP
        SELECT count(*), min(encode(sha256(convert_to(p.prosrc, 'UTF8')), 'hex'))
          INTO v_cnt, v_got
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'bem_control' AND p.proname = r.fn;
        IF v_cnt <> 1 OR v_got IS DISTINCT FROM r.want THEN
            RAISE EXCEPTION 'FINAL_ZAVOD_FN_BODY_MISMATCH: % (функций %, отпечаток %)', r.fn, v_cnt, v_got;
        END IF;
    END LOOP;
END
$zavod_fp$;

`;
t = once(t, '-- Ни одной команды безопасности после этой строки быть не должно.\n',
  fpBlock + '-- Ни одной команды безопасности после этой строки быть не должно.\n');

const out = `-- ДОКУМЕНТ: db/05_final_state_check_ext01.sql — СОБРАН db/build_final_ext.mjs, руками не править
-- ИСТОЧНИК H1.31 05: sha256 ${sha(base)}
-- РАСШИРЕНИЕ 02: sha256 ${sha(ext)}
-- РАСШИРЕНИЕ 03: sha256 ${sha(ext02)}
-- НАЗНАЧЕНИЕ: терминальная проверка H1.31 05 с точным списком отличий Z-EXT-01 и Z-EXT-02 (см. сборщик).
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
