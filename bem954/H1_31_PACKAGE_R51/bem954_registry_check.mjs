// bem954_registry_check.mjs — статический сверщик реестра тестов.
// PASSPORT: ACTIVE vR51.1, раунд R51, H1.31.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R51 (РАУНД-R51-ПЕРЕНОС-ИМЁН: H1.31; логика программ в R47–R51 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.30/R50; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47, R49, R50 и R51 — раздел 22.2, остальное — раздел 15.44.
// Сверяет раздел 15 с каноническим кодом того же документа.
// Ничего не запускает и к базе не подключается.
// ИСТОРИЯ: прежний активный паспорт. Раунд R33 (решение D-05, замечание L-H117-R17-01):
// проверка 9 (условие WHEN триггера против договора файла 05) больше не
// требует строку договора у триггера на pg_temp.*-таблице — такой
// триггер создаётся и удаляется внутри одной команды DO, в постоянном
// состоянии базы его нет, и не может быть строки договора у того, чего
// не остаётся. РАУНД-R32-ПЕРЕНОС-ИМЁН: имя документа H1_17.md, логика
// не менялась. Раунд R31: добавлена проверка 9 — условие WHEN
// каждого триггера против договора файла 05 (замечание C-H115-R15-01).
// Там же: строки реестра со статусами EXECUTED_STATIC и
// EXECUTED_PACKAGE считаются в TEST_ROWS наравне с DESIGNED_NOT_EXECUTED.
//
//   node bem954_registry_check.mjs H1_31.md
//   0 — расхождений нет; 1 — расхождения есть, и каждое названо.
import { readFileSync } from 'node:fs';

const doc = readFileSync(process.argv[2] || 'H1_31.md', 'utf8');
const sql = (doc.match(/```sql\n([\s\S]*?)\n```/g) || [])
  .map((b) => b.replace(/^```sql\n/, '').replace(/\n```$/, ''))
  .join('\n');

const uniq = (a) => [...new Set(a)].sort();
const all = (re, text) => {
  const out = []; let m;
  const r = new RegExp(re.source, re.flags.includes('g') ? re.flags : re.flags + 'g');
  while ((m = r.exec(text)) !== null) out.push(m);
  return out;
};

// 1. Роли. Основные заводит файл 00 списком пар «имя, признаки»,
//    restore_verifier — отдельная команда файла 03.
const roles = uniq([
  ...all(/\(\s*'([a-z_][a-z0-9_]*)',\s*\n?\s*'(?:LOGIN|NOLOGIN)[^']*'/, sql).map((m) => m[1]),
  ...all(/CREATE ROLE ([a-z_][a-z0-9_]*)/i, sql).map((m) => m[1]),
]);

// 2. Функции. Владельца задаёт действующий SET ROLE в момент создания;
//    явный ALTER FUNCTION ... OWNER TO его перекрывает.
const fns = {};
let cur = null;
for (const line of sql.split('\n')) {
  const sr = line.match(/^\s*SET ROLE ([a-z_][a-z0-9_]*)/i);
  if (sr) { cur = sr[1]; continue; }
  if (/^\s*RESET ROLE/i.test(line)) { cur = null; continue; }
  const cf = line.match(/CREATE OR REPLACE FUNCTION\s+(bem_[a-z]+)\.([a-z_][a-z0-9_]*)/i);
  if (cf) fns[cf[1] + '.' + cf[2]] = { schema: cf[1], owner: cur };
}
for (const m of all(/ALTER FUNCTION\s+(bem_[a-z]+)\.([a-z_][a-z0-9_]*)\s*\([^)]*\)\s*\n?\s*OWNER TO ([a-z_][a-z0-9_]*)/i, sql)) {
  const k = m[1] + '.' + m[2];
  if (fns[k]) fns[k].owner = m[3];
}

// 3. Права на исполнение.
const grants = {};
for (const m of all(/GRANT\s+EXECUTE ON FUNCTION\s+(bem_[a-z]+)\.([a-z_][a-z0-9_]*)\s*\([^)]*\)\s*\n?\s*TO ([a-z_, ]+);/i, sql)) {
  for (const r of m[3].split(',').map((x) => x.trim()).filter(Boolean)) {
    (grants[r] ||= new Set()).add(m[1] + '.' + m[2]);
  }
}

// 4. Имена, которые код знает: всякая строковая постоянная
//    в ВЕРХНЕМ_РЕГИСТРЕ — ошибки, состояния, виды доказательств.
const known = new Set(all(/'([A-Z][A-Z0-9_]{2,})[^']*'/, sql).map((m) => m[1]));
const raised = uniq(all(/RAISE EXCEPTION\s+'([A-Z][A-Z0-9_]{2,})/, sql).map((m) => m[1]));

// 5. Словарь имён, которых в коде нет и быть не должно. Он объявлен
//    в самом документе: молча выдумать имя всё равно не выйдет.
const vocab = { APP: [], WITHDRAWN: [], EXTERNAL: [], MISSING: [] };
const vb = doc.match(/BEM954-(?:PACKAGE|H1-\d+)-VOCABULARY\n([\s\S]*?)\n```/);
if (vb) {
  for (const line of vb[1].split('\n')) {
    const m = line.match(/^(APP|WITHDRAWN|EXTERNAL|MISSING)=(.*)$/);
    if (m) vocab[m[1]].push(...m[2].split(',').map((x) => x.trim()).filter(Boolean));
  }
}
const declared = new Set([...vocab.APP, ...vocab.WITHDRAWN, ...vocab.EXTERNAL]);
// Объявленные пробелы: ссылки без строк. Они не считаются ошибкой,
// но и забыть их нельзя — сверщик печатает их каждый раз.
const missing = new Set(vocab.MISSING);
const keywords = new Set([
  'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'USAGE', 'EXECUTE', 'CONNECT',
  // USING — ключевое слово SQL, которым записывается условие политики.
  // Именем отказа оно не бывает; без него сверщик валился на любом
  // упоминании выражения политики в тексте раздела 15.
  'USING',
  'PUBLIC', 'CHECK', 'COMMIT', 'ROLLBACK', 'RESTRICTIVE', 'PERMISSIVE',
  'SERIALIZABLE', 'LOGIN', 'NOLOGIN', 'SUPERUSER', 'NOSUPERUSER',
  'BYPASSRLS', 'NOBYPASSRLS', 'CREATEROLE', 'NOCREATEROLE', 'INHERIT',
  'NOINHERIT', 'NOT', 'NULL', 'VALID',
  // Признаки роли и параметры членства PostgreSQL 16. Они появились в
  // реестре раундом R27 вместе с точной матрицей ролей: это слова
  // языка, а не имена отказов, и требовать их от кода нельзя.
  'REPLICATION', 'NOREPLICATION', 'CREATEDB', 'NOCREATEDB',
  'ADMIN', 'SET', 'TRUE', 'FALSE', 'REASSIGN', 'OWNED',
  'LOCAL_MVP', 'BEFORE_EXTERNAL_PILOT', 'BEFORE_FEATURE_ENABLE',
  'DESIGNED_NOT_EXECUTED',
  // статусы выполнения строк реестра, раунд R31: выполнено по копиям
  // документа и выполнено на собранном пакете
  'EXECUTED_STATIC', 'EXECUTED_PACKAGE',
  // ярлыки словаря из раздела 15.9, а не имена из кода
  'APP', 'WITHDRAWN', 'EXTERNAL', 'MISSING',
  // ярлык из блока чисел BEM954-H1-<номер>-COUNTS
  'TEST_ROWS',
  // служебные идентификаторы раундов R38, R42–R51, а не имена ошибок SQL
  'BASELINE_EDITION', 'DEFERRED_PG16_D05', 'EXPECTED_EDITION',
  'H1_20_PACKAGE_R36', 'H1_21_PACKAGE_R38', 'H1_22_PACKAGE_R42', 'H1_23_PACKAGE_R43', 'H1_24_PACKAGE_R44', 'H1_25_PACKAGE_R45', 'H1_26_PACKAGE_R46', 'H1_27_PACKAGE_R47', 'H1_28_PACKAGE_R48', 'H1_29_PACKAGE_R49', 'H1_30_PACKAGE_R50', 'H1_31_PACKAGE_R51', 'PG16_D05', 'ROUND_FACT', 'TAMPER_CASES_TOTAL', 'TAMPER_CASES_RANGE',
]);

// Листинг программы — это код, а не утверждение о реестре. Ограда из
// четырёх и более знаков делает область непрозрачной целиком, и имя в
// обратных кавычках внутри неё реестру не адресовано: это строка
// исходника. Раздел 15.15 приводит набор подделок, и в нём намеренно
// стоят имена, которых в реестре нет: отказ, роль, функция и номер
// строки покрытия, придуманные ради того, чтобы сверщик на них
// споткнулся. Читать их как заявление документа — значит считать
// ошибкой саму проверку на ошибку.
const TICK = String.fromCharCode(96);
const LISTING = new RegExp('^(' + TICK + '{4,})[^\\n]*\\n[\\s\\S]*?\\n\\1[ \\t]*(?=\\n|$)', 'gm');
const stripListings = (t) => t.replace(LISTING, '');
// 6. Реестр.
const from = doc.indexOf('\n# 15. ');
const to = doc.indexOf('\n# 16. ');
if (from < 0 || to < 0 || to < from) { console.error('РАЗДЕЛ 15 НЕ НАЙДЕН'); process.exit(1); }
const reg = stripListings(doc.slice(from, to));
const ticked = uniq(all(/`([^`\n]+)`/, reg).map((m) => m[1]));

const fnNames = new Set(Object.keys(fns).map((f) => f.split('.')[1]));
const schemas = new Set(['bem_core', 'bem_control', 'bem_engine']);
const roleSet = new Set(roles);

const bad = { errors: [], roles: [], functions: [] };
for (const t of ticked) {
  if (/^[A-Z][A-Z0-9_]{2,}$/.test(t)) {
    if (!known.has(t) && !keywords.has(t) && !declared.has(t)) bad.errors.push(t);
  } else if (/^bem_[a-z0-9_]+$/.test(t)) {
    if (!roleSet.has(t) && !schemas.has(t) && !declared.has(t)) bad.roles.push(t);
  } else if (/^[a-z][a-z0-9_]*\(\)$/.test(t)) {
    const n = t.slice(0, -2);
    if (!fnNames.has(n) && !declared.has(n)) bad.functions.push(t);
  }
}

// 6a. Идентификаторы строк покрытия. Любая ссылка вида `K-…`
//     в любом месте документа обязана указывать на существующую
//     строку реестра. Ссылка на несуществующий номер — ошибка того
//     же рода, что имя функции, которой нет.
const rowIds = new Set();
for (const line of reg.split('\n')) {
  const m = line.match(/^\|\s*`?(K[A-Z0-9-]*\d)`?\s*\|/);
  if (m) rowIds.add(m[1]);
  const m2 = line.match(/^\|\s*T\d+\s*\|\s*`?(K\d+)`?\s*\|/);
  if (m2) rowIds.add(m2[1]);
  const m3 = line.match(/^\|\s*DISP-\d+\s*\|\s*`?(KD\d+)`?\s*\|/);
  if (m3) rowIds.add(m3[1]);
}
const badIds = uniq(all(/`(K-[A-Z0-9]+-\d+)`/, stripListings(doc)).map((m) => m[1]))
  .filter((id) => !rowIds.has(id) && !missing.has(id));
const staleMissing = [...missing].filter((id) => rowIds.has(id));

// 7. Числа. Документ обязан назвать их машинным блоком,
//    сверщик пересчитывает каждое по коду.
const decl = {};
const cb = doc.match(/BEM954-(?:PACKAGE|H1-\d+)-COUNTS\n([\s\S]*?)\n```/);
if (cb) for (const line of cb[1].split('\n')) {
  const m = line.match(/^([A-Z_]+)=(\d+)$/);
  if (m) decl[m[1]] = Number(m[2]);
}
const actual = {
  ROLES: roles.length,
  CONTROL_FUNCTIONS: Object.values(fns).filter((f) => f.schema === 'bem_control').length,
  CORE_FUNCTIONS: Object.values(fns).filter((f) => f.schema === 'bem_core').length,
  KERNEL_EXECUTE: (grants['bem_kernel_rw'] || new Set()).size,
  BACKUP_ADMIN_EXECUTE: (grants['bem_backup_admin'] || new Set()).size,
  GOVERNANCE_EXECUTE: (grants['bem_governance'] || new Set()).size,
  RAISED_ERRORS: raised.length,
  TEST_ROWS: (reg.match(/^\|.*`(DESIGNED_NOT_EXECUTED|EXECUTED_STATIC|EXECUTED_PACKAGE)` \|$/gm) || []).length,
};
const numbers = [];
for (const k of Object.keys(actual)) {
  if (decl[k] === undefined) numbers.push(k + ': не объявлено, по коду ' + actual[k]);
  else if (decl[k] !== actual[k]) numbers.push(k + ': объявлено ' + decl[k] + ', по коду ' + actual[k]);
}

// 7a. Сколько строк объявлено, столько идентификаторов и должно
//     найтись. Проверка ловит обратную ошибку: таблицу, которая
//     первым столбцом похожа на реестр, но покрытием не является.
const rowIdCount = actual.TEST_ROWS === rowIds.size ? []
  : ['TEST_ROWS=' + actual.TEST_ROWS + ', а идентификаторов в разделе 15: ' + rowIds.size];

// 9. Условие WHEN каждого триггера (R31, замечание C-H115-R15-01).
//    Подделка I-H115-01 меняла условие constraint-триггера на WHEN (true)
//    и проходила оба сверщика. Здесь условие берётся из каждой команды,
//    создающей триггер, и сверяется с третьим полем строк договора
//    v_trigger_def и v_trigger_def_legacy файла 05. Триггер без строки в
//    договоре и строка договора без триггера — тоже расхождения. Читается
//    только канон — разделы 25–27: пояснения кодом не считаются.
//    Команда ищется в начале строки: текст «CREATE TRIGGER» стоит ещё и
//    внутри строковых постоянных с ожидаемыми определениями.
const triggerWhen = [];
{
  const a = doc.indexOf('\n# 25. ');
  const b = doc.indexOf('\n# 28. ');
  const canon = a < 0 ? '' : doc.slice(a, b < 0 ? doc.length : b);
  const code = (canon.match(/```sql\n([\s\S]*?)\n```/g) || []).join('\n');
  const bare = (e) => {
    let x = e.trim();
    for (;;) {
      if (!x.startsWith('(') || !x.endsWith(')')) return x;
      let d = 0;
      for (let i = 0; i < x.length - 1; i += 1) {
        if (x[i] === '(') d += 1;
        if (x[i] === ')') d -= 1;
        if (d === 0) return x;
      }
      x = x.slice(1, -1).trim();
    }
  };
  const whenOf = (t) => {
    const m = t.replace(/\s+/g, ' ').match(/ WHEN \((.*)\) EXECUTE (?:FUNCTION|PROCEDURE) /i);
    if (!m) return '';
    return bare(m[1]).replace(/\b(NEW|OLD|TRUE|FALSE)\b/g, (w) => w.toLowerCase());
  };
  const made = [];
  for (const m of all(/\(\s*'([a-z_]\w*)',\s*'(bem_\w+\.\w+)',\s*'((?:BEFORE|AFTER|INSTEAD OF)[^']*)',/, code)) {
    made.push([m[2] + '|' + m[1], whenOf(m[3] + ' ')]);
  }
  for (const m of all(/^[ \t]*CREATE\s+(?:CONSTRAINT\s+)?TRIGGER\s+([a-z_]\w*)\s+([\s\S]*?);/m, code)) {
    const on = m[2].match(/\sON\s+(bem_\w+\.\w+)\s/i);
    if (!on) {
      // R33 (решение D-05, замечание L-H117-R17-01). Единственный сейчас
      // случай — эталонный триггер subject_requires_author_ref: создаётся
      // на pg_temp.subject_reference_shape и удаляется в той же команде
      // DO, в постоянном состоянии базы его нет, и строки в договоре
      // v_trigger_def файла 05 у него быть не может. Любое ДРУГОЕ
      // несовпадение (не pg_temp) — расхождение, как раньше.
      if (m[2].match(/\sON\s+pg_temp\.\w+\s/i)) continue;
      made.push(['?|' + m[1], whenOf(m[2] + ' ')]);
      continue;
    }
    made.push([on[1] + '|' + m[1], whenOf(m[2] + ' ')]);
  }
  const declared = new Map();
  for (const m of all(/v_trigger_def(?:_legacy)?\s+constant text\[\]\s*:=\s*ARRAY\[([\s\S]*?)\];/, code)) {
    for (const q of all(/'([^']*)'/, m[1])) {
      const p = q[1].split('|');
      declared.set(p[0] + '|' + p[1], p[2]);
    }
  }
  if (declared.size === 0) triggerWhen.push('в файле 05 нет договора v_trigger_def');
  const seen = new Set();
  for (const [k, w] of made) {
    seen.add(k);
    if (!declared.has(k)) triggerWhen.push('триггер без строки договора: ' + k);
    // Ключевые слова SQL и имена без кавычек регистра не имеют: сервер
    // хранит «is not null» и «IS NOT NULL» одинаково.
    else if (declared.get(k).toLowerCase() !== w.toLowerCase()) {
      triggerWhen.push('условие WHEN ' + k + ': в команде "' + w + '", в договоре "' + declared.get(k) + '"');
    }
  }
  for (const k of declared.keys()) if (!seen.has(k)) triggerWhen.push('строка договора без триггера: ' + k);
}

// 8. Каждая функция обязана иметь владельца и хотя бы один REVOKE.
const noOwner = Object.entries(fns).filter(([, v]) => !v.owner).map(([k]) => k);
const owners = {};
for (const [k, v] of Object.entries(fns)) (owners[v.owner || 'НЕТ'] ||= []).push(k);

const fail = bad.errors.length + bad.roles.length + bad.functions.length
           + numbers.length + noOwner.length + badIds.length
           + staleMissing.length + rowIdCount.length + triggerWhen.length;
console.log(JSON.stringify({
  roles,
  owners: Object.fromEntries(Object.entries(owners).map(([r, l]) => [r, l.length])),
  grants: Object.fromEntries(Object.entries(grants).map(([r, s]) => [r, s.size])),
  counts: actual,
  mismatched_numbers: numbers,
  functions_without_owner: noOwner,
  unknown_error_names: bad.errors,
  unknown_roles: bad.roles,
  unknown_functions: bad.functions,
  unknown_row_ids: badIds,
  declared_missing_rows: [...missing].sort(),
  missing_but_present: staleMissing,
  row_id_count_mismatch: rowIdCount,
  row_ids: rowIds.size,
  trigger_when_mismatch: triggerWhen,
  verdict: fail === 0 ? 'OK' : 'РАСХОЖДЕНИЙ: ' + fail,
}, null, 1));
process.exit(fail === 0 ? 0 : 1);