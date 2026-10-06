// bem954_semantic_check.mjs — смысловой сверщик канонического кода.
// PASSPORT: ACTIVE vR48.1, раунд R48, H1.28.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R48 (РАУНД-R48-ПЕРЕНОС-ИМЁН: H1.28; логика программ в R47 и R48 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.27/R47; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47 — раздел 22.2, остальное — раздел 15.41.
// ИСТОРИЯ: прежний активный паспорт. Версия 6.3, раунд R32 (РАУНД-R32-СВЕРЩИК; РАУНД-R32-РЕДАКЦИЯ —
// последний абзац документа называет только текущую редакцию; РАУНД-R32-ТЕКСТ —
// текст раздела 5 о записи доказательства сверяется с каноном; и
// РАУНД-R32-СРАВНЕНИЕ: сравнение прав файла 01 и файла 05 берётся целиком, а не
// по словам; замечание
// M-H116-R16-02: точные списки прав в самопроверке файла 01 — модель
// прав снимается после файла 01 и в конце пакета, списки v_acl и
// v_acl_04 сверяются с учётом повторов; повтор имени в секции DECLARE).
// Прежде — версия 5.0, раунд R31 (замечания C-H115-R15-01 и
// M-H115-R15-01: определение триггера целиком — условие WHEN, байты
// аргументов и строка pg_get_triggerdef — на всех трёх уровнях; кто
// выдал каждое право; сравнение терминальных списков с учётом повторов).
// Прежде — версия 4.1, раунд R27 (замечания C-H112-R12-01 и
// M-H112-R12-01: итоговое состояние ролей, членств и прав, а также
// сверка ожиданий живой самопроверки файла 01).
// Запуск: node bem954_semantic_check.mjs [файл]
//         node bem954_semantic_check.mjs [файл] --print-contracts
//         node bem954_semantic_check.mjs [файл] --print-selfcheck
// Третий вид печатает два списка для массивов v_read и v_exec файла 01:
// что именно обязано быть доказано внутри базы bem.
// Второй вид печатает выведенные множества — договор чтения и
// поверхность EXECUTE — по строке на запись и ничего не сверяет.
// Объявленные блоки документа собираются им, а не переписываются
// руками; проверяющий может собрать их сам и сравнить построчно.
//
// Чем он отличается от синтаксического сверщика раздела 15.9.
// Тот проверяет, что КАЖДОЕ НАЗВАННОЕ ИМЯ существует хоть где-то в
// коде. Этого мало: строка покрытия может назвать настоящую функцию и
// настоящий отказ, которые друг с другом не связаны вовсе.
//
// Что изменила версия 2.0. Аудит C-линии показал пять способов обмануть
// версию 1.0, и каждый закрыт здесь:
//   1. Версия 1.0 склеивала ВСЕ блоки ```sql документа. Поясняющий
//      пример из раздела 10 считался кодом наравне с файлом миграции,
//      поэтому убранное право в файле 01 подменялось похожей строкой из
//      пояснения. Теперь разбирается только канонический диапазон —
//      разделы 25, 26 и 27, то есть тексты трёх файлов.
//   2. Версия 1.0 звала функцию по короткому имени. Имя — не подпись:
//      две функции с одним именем и разными аргументами для неё были
//      одной. Ключ — полная подпись «схема.имя(типы)».
//   3. Версия 1.0 не замечала двух определений одной подписи. Теперь
//      повтор допустим, только если тела совпадают побайтно.
//   4. Версия 1.0 читала у GRANT только ПЕРВОГО получателя. Приписка
//      второго прав не меняла для неё вовсе. Теперь читаются все.
//   5. Версия 1.0 сверяла права записи ручным списком из двенадцати
//      таблиц. Теперь договор выводится из тел функций и сверяется в
//      обе стороны: нет недостающего и нет лишнего.
//
// Что изменила версия 3.0. Аудит C-линии добавил в канонический блок
// прав одну строку — GRANT TRUNCATE ON bem_core.evidence — и оба
// сверщика вернули 0. Причина: договор знал ровно три права записи,
// а у таблицы PostgreSQL 16 их семь. Закрыт весь набор:
//   1. у каждого вида объекта свой разрешённый список прав. Таблица:
//      SELECT, INSERT, UPDATE, DELETE. Последовательность: USAGE,
//      SELECT. Схема: USAGE, CREATE. База: CONNECT. Функция: EXECUTE.
//   2. TRUNCATE, REFERENCES и TRIGGER не разрешены нигде и никому:
//      ни одно тело канонического кода их не требует.
//   3. ALL и ALL PRIVILEGES запрещены как вид записи.
//   4. право, которого нет в словаре PostgreSQL 16, — тоже расхождение:
//      молча неизвестное право не пропускается.
//   5. права по умолчанию (ALTER DEFAULT PRIVILEGES) разбираются тем же
//      словарём, а не отдельным упрощённым правилом.
//   6. чтение перестало быть свободным: договор чтения объявлен
//      машинным блоком и сверяется в обе стороны.
//   7. поверхность EXECUTE объявлена множеством «подпись → получатели»,
//      а не числом. Старое число функций больше ничего не доказывает
//      (замечание M-H111-R11-03).
//
// Двенадцать проверок, все статические, ни одна не ходит в базу:
//   1. отказ строки возбуждается названной ею функцией;
//   2. у каждой функции есть REVOKE EXECUTE ... FROM PUBLIC;
//   3. доказательство вставляется ровно в одном месте — в writer;
//   4. граница заказчика: и у функций с аргументом p_tenant_id, и у
//      функций владельца с признаком BYPASSRLS, которые трогают
//      таблицы заказчика вовсе без такого аргумента;
//   5. отказ, который возбуждает только блок DO, привязан к строке
//      покрытия машинной меткой внутри самого блока;
//   6. два определения одной подписи — только побайтно одинаковые;
//   7. договор записи: тела функций против фактических GRANT, в обе
//      стороны, и он же против списка в самопроверке раздела 26.9;
//   8. получатели EXECUTE: читаются все, и объявленный помощник не
//      может быть выдан никому, кроме владельца схемы;
//   9. канонический диапазон замкнут: определений функций вне его нет,
//      а всякое право из пояснения выводится из канонического;
//  10. закрытый набор прав: у каждого вида объекта свой список, и всё
//      сверх него — расхождение с именем роли, объекта и права;
//  11. договор чтения: объявленное множество против фактических GRANT,
//      в обе стороны;
//  12. поверхность EXECUTE: объявленное множество «подпись →
//      получатели» против фактических GRANT EXECUTE, в обе стороны.
//
// Возврат 0 — расхождений нет. 1 — они названы поимённо.

import { readFileSync } from 'node:fs';

const file = process.argv[2] || 'H1_12.md';
const doc = readFileSync(file, 'utf8');
const argAfter = (flag) => {
  const i = process.argv.indexOf(flag);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : null;
};

const uniq = (a) => [...new Set(a)].sort();
const all = (re, text) => [...text.matchAll(new RegExp(re, 'g'))];
const TICK = String.fromCharCode(96);
const F3 = TICK + TICK + TICK;

// --- 0. Канонический диапазон -------------------------------------------
// Канон — это тексты трёх файлов пакета миграции: разделы 25, 26 и 27.
// Всё остальное в документе — пояснение, и кодом не считается. Граница
// берётся по заголовкам, а не по номерам строк, и печатается в отчёте:
// если она поедет, это будет видно сразу.
const headings = [];
for (const m of all('\\n# (\\d+)\\. ', doc)) {
  headings.push({ n: Number(m[1]), at: m.index + 1 });
}
const start = headings.find((h) => h.n === 25);
const after = headings.find((h) => h.n >= 28);
if (!start) { console.error('РАЗДЕЛ 25 НЕ НАЙДЕН'); process.exit(1); }
const canonFrom = start.at;
const canonTo = after ? after.at : doc.length;
const canonSections = headings.filter((h) => h.at >= canonFrom && h.at < canonTo)
  .map((h) => h.n);

// Разбор оград. Ограда из четырёх и более знаков делает область
// непрозрачной целиком: внутри неё лежит исходник самого сверщика, и
// тройные ограды в нём оградами документа не являются.
function fencedBlocks(text) {
  const out = [];
  const lines = text.split('\n');
  let pos = 0;
  let big = null;
  let small = null;
  for (const line of lines) {
    const here = pos;
    pos += line.length + 1;
    const f = line.match(new RegExp('^(' + TICK + '{3,})(.*)$'));
    if (!f) continue;
    if (f[1].length >= 4) {
      if (big === null) big = f[1].length;
      else if (f[1].length === big) big = null;
      continue;
    }
    if (big !== null) continue;
    if (small === null) small = { lang: f[2].trim(), at: here + line.length + 1 };
    else { out.push({ lang: small.lang, at: small.at, text: text.slice(small.at, here) }); small = null; }
  }
  return out;
}

const blocks = fencedBlocks(doc);
const canonBlocks = blocks.filter((b) => b.lang === 'sql' && b.at >= canonFrom && b.at < canonTo);
const outerBlocks = blocks.filter((b) => b.lang === 'sql' && !(b.at >= canonFrom && b.at < canonTo));
const sql = canonBlocks.map((b) => b.text).join('\n');
const outerSql = outerBlocks.map((b) => b.text).join('\n');

// Конец строкового значения. Внутри значения кавычка удваивается:
// 'don''t' — это одно значение, а не два. Прежний разбор искал ближайшую
// кавычку и на удвоенной сбивался: дальше он считал код содержимым
// строки, а содержимое строки — кодом. Найдено при подготовке H1.14,
// в списке замечаний аудита 75 этого не было.
function endOfLiteral(src, at) {
  let j = at + 1;
  while (j < src.length) {
    if (src[j] === "'") {
      if (src[j + 1] === "'") { j += 2; continue; }
      return j;
    }
    j += 1;
  }
  return src.length - 1;
}

// Разметка «здесь код, а здесь значение или пояснение». Нужна везде, где
// слово ищется по всему тексту сразу: одно и то же слово внутри строкового
// значения командой не является.
function codeMask(src) {
  const mask = new Uint8Array(src.length);
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === "'") { i = endOfLiteral(src, i) + 1; continue; }
    if (c === '-' && src[i + 1] === '-') {
      const nl = src.indexOf('\n', i);
      i = nl < 0 ? src.length : nl;
      continue;
    }
    if (c === '$') {
      const t = src.slice(i, i + 40).match(/^\$(\w*)\$/);
      if (t) { i += t[0].length; continue; }   // тело функции — тоже код
    }
    mask[i] = 1;
    i += 1;
  }
  return mask;
}

// --- 1. Разбор текста ----------------------------------------------------
// Пояснения вида "-- ..." выбрасываются: команда, названная в
// пояснении, командой не является. Строковые значения при этом целы.
function stripComments(body) {
  let out = '';
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (c === "'") {
      const end = endOfLiteral(body, i);
      out += body.slice(i, end + 1);
      i = end;
      continue;
    }
    if (c === '-' && body[i + 1] === '-') {
      const nl = body.indexOf('\n', i);
      if (nl < 0) break;
      out += '\n';
      i = nl;
      continue;
    }
    out += c;
  }
  return out;
}

// Деление на команды по точке с запятой на нулевой глубине скобок.
// Одинарные и долларовые кавычки при этом не разрываются.
function statementsOf(body) {
  const out = [];
  let depth = 0;
  let startAt = 0;
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (c === "'") { i = endOfLiteral(body, i); continue; }
    if (c === '$') {
      const t = body.slice(i, i + 40).match(/^\$\w*\$/);
      if (t) { const j = body.indexOf(t[0], i + t[0].length); i = j < 0 ? body.length : j + t[0].length - 1; continue; }
    }
    if (c === '(') depth += 1;
    else if (c === ')') depth -= 1;
    else if (c === ';' && depth === 0) { out.push(body.slice(startAt, i)); startAt = i + 1; }
  }
  if (startAt < body.length) out.push(body.slice(startAt));
  return out;
}

// Список через запятую на нулевой глубине скобок.
function splitTop(text) {
  const out = [];
  let depth = 0;
  let startAt = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "'") { i = endOfLiteral(text, i); continue; }
    if (c === '(') depth += 1;
    else if (c === ')') depth -= 1;
    else if (c === ',' && depth === 0) { out.push(text.slice(startAt, i)); startAt = i + 1; }
  }
  out.push(text.slice(startAt));
  return out.map((x) => x.trim()).filter(Boolean);
}

function cutAt(text, words) {
  let depth = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "'") { i = endOfLiteral(text, i); continue; }
    if (c === '(') depth += 1;
    else if (c === ')') depth -= 1;
    else if (depth === 0 && /\s/.test(c)) {
      const w = text.slice(i + 1, i + 20).match(new RegExp('^(' + words + ')\\b', 'i'));
      if (w) return text.slice(0, i);
    }
  }
  return text;
}

function setColumns(setText) {
  return splitTop(cutAt(setText, 'FROM|WHERE|RETURNING'))
    .map((it) => it.match(/^\s*(?:\w+\.)?(\w+)\s*=/))
    .filter(Boolean).map((m) => m[1]);
}

const norm = (s) => s.replace(/\s+/g, ' ').trim();

// Подпись функции. Имя — не подпись: аргументы входят в неё, и все
// команды прав в PostgreSQL пишутся именно по подписи.
function signatureOf(argText, schema, name) {
  const types = splitTop(stripComments(argText)).map((p) => {
    let t = p.replace(/\s+DEFAULT\s+[\s\S]*$/i, '').trim();
    if (/^OUT\s/i.test(t)) return '';          // OUT в подпись не входит
    t = t.replace(/^(IN|INOUT|VARIADIC)\s+/i, '');
    const sp = t.search(/\s/);
    return sp < 0 ? '' : norm(t.slice(sp + 1));
  }).filter(Boolean);
  return schema + '.' + name + '(' + types.join(', ') + ')';
}

// Тела функций канонического диапазона.
function parseFunctions(src) {
  const out = [];
  const re = /CREATE OR REPLACE FUNCTION\s+(bem_\w+)\.(\w+)\s*\(/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const openParen = m.index + m[0].length - 1;
    let depth = 0;
    let closeParen = -1;
    for (let i = openParen; i < src.length; i++) {
      if (src[i] === '(') depth += 1;
      else if (src[i] === ')') { depth -= 1; if (depth === 0) { closeParen = i; break; } }
    }
    if (closeParen < 0) continue;
    const head = src.slice(closeParen, closeParen + 6000);
    const as = head.match(/\nAS\s+(\$\w*\$)/);
    if (!as) continue;
    const openAt = closeParen + as.index + as[0].length;
    const closeAt = src.indexOf(as[1], openAt);
    if (closeAt < 0) continue;
    out.push({
      schema: m[1],
      name: m[2],
      sig: signatureOf(src.slice(openParen + 1, closeParen), m[1], m[2]),
      args: src.slice(openParen + 1, closeParen),
      head: src.slice(m.index, openAt),
      body: src.slice(openAt, closeAt),
      at: m.index,
      line: src.slice(0, m.index).split('\n').length,
    });
    re.lastIndex = closeAt;
  }
  return out;
}

const parsed = parseFunctions(sql);

// --- Проверка 6. Два определения одной подписи --------------------------
// Повтор допустим только побайтно одинаковый: функция bem_core.current_tenant()
// создаётся и файлом 01, и файлом 02, и это одна функция. Расхождение
// двух копий — два источника правды (замечание M-H110-R10-02).
const bySig = new Map();
const duplicates = [];
for (const f of parsed) {
  if (!bySig.has(f.sig)) { bySig.set(f.sig, f); continue; }
  const first = bySig.get(f.sig);
  if (first.body !== f.body) {
    duplicates.push(f.sig + ': два определения с разными телами, строки ' +
      first.line + ' и ' + f.line);
  }
}
const funcs = bySig;                       // подпись -> функция
const byName = new Map();                  // короткое имя -> [подписи]
for (const [sig, f] of funcs) {
  if (!byName.has(f.name)) byName.set(f.name, []);
  byName.get(f.name).push(sig);
}

// --- Владельцы функций ---------------------------------------------------
// Владелец задан явной командой ALTER FUNCTION ... OWNER TO. Если её
// нет, владельцем становится действующая роль SET ROLE.
const ownerOf = (f) => {
  const re = new RegExp('ALTER FUNCTION\\s+' +
    f.sig.replace(/[.()[\]]/g, (c) => '\\' + c).replace(/,\s*/g, ',\\s*').replace(/\s+/g, '\\s+') +
    '\\s*OWNER TO (\\w+)');
  const m = sql.match(re);
  if (m) return m[1];
  const before = sql.slice(0, f.at);
  const setRole = before.lastIndexOf('\nSET ROLE ');
  const reset = before.lastIndexOf('\nRESET ROLE');
  if (setRole > reset) return before.slice(setRole).match(/SET ROLE (\w+)/)[1];
  return 'schema_migrator';
};
const owners = new Map();
for (const [sig, f] of funcs) owners.set(sig, ownerOf(f));

// --- Владельцы таблиц ----------------------------------------------------
// Владелец таблицы — роль, действовавшая в момент CREATE TABLE. Порядок
// SET ROLE / RESET ROLE читается по каноническому тексту подряд. Это
// нужно договору записи: в свою таблицу владелец пишет своими правами,
// и выданного права там нет вовсе — требовать его значило бы требовать
// лишнюю строку GRANT.
const tableOwner = new Map();
{
  let cur = 'schema_migrator';
  const re = /\bSET\s+ROLE\s+(\w+)|\bRESET\s+ROLE\b|CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(bem_\w+)\.(\w+)/gi;
  let m;
  while ((m = re.exec(sql)) !== null) {
    if (m[1]) cur = m[1].toLowerCase();
    else if (m[2]) tableOwner.set(m[2].toLowerCase() + '.' + m[3].toLowerCase(), cur);
    else cur = 'schema_migrator';
  }
}

// --- Роли с признаком BYPASSRLS -----------------------------------------
// Читаются из таблицы ролей файла 00, а не из памяти. Признак
// NOBYPASSRLS содержит слово BYPASSRLS как часть, поэтому сравнение
// идёт по целому слову.
const bypassRoles = new Set();
for (const m of all("\\('(\\w+)',\\s*\\n?\\s*'([A-Z][^']*)'", sql)) {
  if (/(^|\s)BYPASSRLS(\s|$)/.test(m[2])) bypassRoles.add(m[1]);
}

// --- Таблицы заказчика ---------------------------------------------------
// Список берётся из шага 8: те таблицы, на которых включается защита
// строк и политика tenant_isolation. Добавили таблицу в шаг 8 — она
// сразу попала под проверку 4.
const tenantTables = new Set();
{
  const rls = sql.indexOf('ENABLE ROW LEVEL SECURITY');
  const head = rls < 0 ? -1 : sql.lastIndexOf('FOREACH t IN ARRAY ARRAY[', rls);
  if (head >= 0) {
    const openAt = sql.indexOf('[', head);
    const closeAt = sql.indexOf(']', openAt);
    for (const m of all("'(\\w+)'", sql.slice(openAt, closeAt))) tenantTables.add(m[1]);
  }
}

// --- Объявленные исключения ----------------------------------------------
const vocab = { NO_FUNCTION: [], TENANT_HELPER: [], NO_REVOKE: [], CROSS_TENANT: [] };
{
  const vm = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-SEMANTIC-VOCABULARY\\n([\\s\\S]*?)\\n' + F3));
  const text = vm ? vm[1] : '';
  for (const line of text.split('\n')) {
    const m = line.match(/^(NO_FUNCTION|TENANT_HELPER|NO_REVOKE|CROSS_TENANT)=(.*)$/);
    if (m) vocab[m[1]] = m[2].split(',').map((x) => x.trim()).filter(Boolean);
  }
}
const noFn = new Set(vocab.NO_FUNCTION);
const helper = new Set(vocab.TENANT_HELPER);
const noRevokeOk = new Set(vocab.NO_REVOKE);
const crossTenant = new Set(vocab.CROSS_TENANT);

// --- Разбор прав ---------------------------------------------------------
// Все получатели после TO, а не первый. Приписка второй роли к готовой
// строке — ровно та подделка, которой версия 1.0 не замечала.
function grantsIn(src) {
  const out = [];
  const flat = stripComments(src.replace(/\$(\w*)\$[\s\S]*?\$\1\$/g, ' _BODY_ '));
  for (const raw of statementsOf(flat)) {
    const st = norm(raw);
    const g = st.match(/^(GRANT|REVOKE)\s+([\s\S]*)$/i);
    if (!g) continue;
    const kind = g[1].toUpperCase();
    const rest = g[2];
    const sep = kind === 'GRANT' ? /\s+TO\s+/i : /\s+FROM\s+/i;
    const onAt = rest.search(/\sON\s/i);
    if (onAt < 0) continue;                       // GRANT роль TO роль — членство, не право
    const privText = rest.slice(0, onAt);
    const tail = rest.slice(onAt + 4);
    const cut = tail.split(sep);
    if (cut.length < 2) continue;
    const objText = cut[0].trim();
    const whoText = cut.slice(1).join(' ').replace(/\s+WITH\s+[\s\S]*$/i, '');
    const who = splitTop(whoText).map((x) => x.replace(/;+$/, '').trim()).filter(Boolean);
    const privs = splitTop(privText).map((p) => {
      const c = p.match(/^(\w+)\s*(?:\(([^)]*)\))?$/);
      return c ? { priv: c[1].toUpperCase(), cols: c[2] ? splitTop(c[2]) : null } : null;
    }).filter(Boolean);
    out.push({ kind, privs, objText, who, text: st });
  }
  return out;
}

// Объект права приводится к списку опорных строк. Список схем
// раскрывается: «ON SCHEMA a, b, c» — это три права, а не одно.
function objectKeys(objText) {
  const t = objText.trim();
  let m = t.match(/^ALL\s+(TABLES|SEQUENCES|FUNCTIONS|ROUTINES)\s+IN\s+SCHEMA\s+([\s\S]*)$/i);
  if (m) return splitTop(m[2]).map((s) => 'ALL' + m[1].toUpperCase() + ':' + s);
  m = t.match(/^SCHEMA\s+([\s\S]*)$/i);
  if (m) return splitTop(m[1]).map((s) => 'SCHEMA:' + s);
  m = t.match(/^FUNCTION\s+([\s\S]*)$/i);
  if (m) return splitTop(m[1]).map((s) => 'FUNCTION:' + norm(s).toLowerCase());
  m = t.match(/^DATABASE\s+([\s\S]*)$/i);
  if (m) return splitTop(m[1]).map((s) => 'DATABASE:' + s);
  return splitTop(t.replace(/^TABLE\s+/i, '')).map((s) => 'TABLE:' + norm(s));
}

const canonGrants = grantsIn(sql);
const outerGrants = grantsIn(outerSql);

// --- Итоговое состояние прав (замечание M-H112-R12-01) -------------------
// H1.12 складывала все GRANT и не вычитала поздний REVOKE. Поэтому
// обязательное право можно было выдать, а следующей строкой снять, и
// договор всё равно считался выполненным. Здесь команды проигрываются
// по порядку: GRANT добавляет, REVOKE снимает, REVOKE ALL снимает весь
// подходящий набор.
const aclFinal = new Set();
const revokeLines = [];
for (const g of canonGrants) {
  const keys = objectKeys(g.objText);
  if (g.kind === 'GRANT') {
    for (const o of keys) for (const p of g.privs) for (const w of g.who) {
      aclFinal.add(p.priv + '|' + o + '|' + w);
    }
    continue;
  }
  revokeLines.push(norm(g.text));
  const wipeAll = g.privs.some((p) => p.priv === 'ALL');
  for (const o of keys) for (const w of g.who) {
    if (wipeAll) {
      for (const k of [...aclFinal]) {
        const at = k.indexOf('|');
        const rest = k.slice(at + 1);
        const cut = rest.lastIndexOf('|');
        if (rest.slice(0, cut) === o && rest.slice(cut + 1) === w) aclFinal.delete(k);
      }
    } else {
      for (const p of g.privs) aclFinal.delete(p.priv + '|' + o + '|' + w);
    }
  }
}
const alive = (priv, obj, who) => aclFinal.has(priv + '|' + obj + '|' + who);

// Каждый REVOKE канона объявляется отдельно. Без этого правила снятие
// права ловится только там, где право объявлено договором; объявленный
// список закрывает и остальные случаи.
const revokeDeclared = new Set();
{
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-REVOKE-CONTRACT\\n([\\s\\S]*?)\\n' + F3));
  if (m) for (const line of m[1].split('\n')) {
    const t = norm(line);
    if (t && !t.startsWith('#')) revokeDeclared.add(t);
  }
}
const revokeUndeclared = [];
const revokeStale = [];
{
  const actual = new Set(revokeLines);
  if (revokeDeclared.size === 0) revokeUndeclared.push('блока BEM954-PACKAGE-REVOKE-CONTRACT в документе нет');
  else {
    for (const r of [...actual].sort()) if (!revokeDeclared.has(r)) revokeUndeclared.push('не объявлен: ' + r);
    for (const r of [...revokeDeclared].sort()) if (!actual.has(r)) revokeStale.push('объявлен, но в каноне нет: ' + r);
  }
}

// --- Итоговое состояние ролей (замечание C-H112-R12-01) ------------------
// Роли файла 00 создаются динамически, через таблицу VALUES внутри блока
// DO, а роль файла 03 — строкой внутри EXECUTE. Поэтому читается сырой
// текст канона, а не разобранные команды: иначе обе дороги пропадают.
const ROLE_FLAGS = ['LOGIN', 'SUPERUSER', 'CREATEDB', 'CREATEROLE', 'REPLICATION', 'BYPASSRLS', 'INHERIT'];
const roleState = new Map();
// Сырой текст признаков каждой роли. Из него выводится договор о пароле,
// сроке годности и настройках сеанса (замечание M-H113-R13-04): по флагам
// этого не видно, а команда, задающая пароль, выглядит так же обычно, как
// команда, задающая право входа.
const roleAttrText = new Map();
const blank = () => ({ LOGIN: false, SUPERUSER: false, CREATEDB: false, CREATEROLE: false,
                       REPLICATION: false, BYPASSRLS: false, INHERIT: true, CONNLIMIT: -1 });
function applyAttrs(name, attrs, create) {
  if (!roleState.has(name)) roleState.set(name, blank());
  else if (create) roleState.set(name, blank());
  roleAttrText.set(name, (roleAttrText.get(name) || '') + ' ; ' + attrs);
  const st = roleState.get(name);
  const up = ' ' + attrs.toUpperCase() + ' ';
  for (const f of ROLE_FLAGS) {
    if (new RegExp('\\bNO' + f + '\\b').test(up)) st[f] = false;
    else if (new RegExp('\\b' + f + '\\b').test(up)) st[f] = true;
  }
  const cl = up.match(/\bCONNECTION LIMIT\s+(-?\d+)\b/);
  if (cl) st.CONNLIMIT = Number(cl[1]);
}
// Таблица VALUES шага 1 файла 00: имя роли и её признаки. Соседние
// строковые куски склеиваются — признаки одной роли записаны в двух.
for (const m of all("\\('([a-z_]+)',\\s*((?:'[^']*'\\s*)+)\\)", sql)) {
  const attrs = [...m[2].matchAll(/'([^']*)'/g)].map((x) => x[1]).join(' ');
  if (!/\b(NO)?(LOGIN|SUPERUSER|BYPASSRLS|CREATEROLE)\b/i.test(attrs)) continue;
  applyAttrs(m[1], attrs, true);
}
// Обычные команды: и настоящие, и лежащие строкой внутри EXECUTE.
const ATTR_WORDS = new Set(['CURRENT_USER', 'SESSION_USER', 'ALL', 'PASSWORD', 'CONNECTION', 'VALID', 'RESET', 'SET',
  ...ROLE_FLAGS, ...ROLE_FLAGS.map((f) => 'NO' + f)]);
for (const m of all("\\b(CREATE|ALTER)\\s+ROLE\\s+([A-Za-z_][\\w]*)\\s*([^';]*)", sql)) {
  if (ATTR_WORDS.has(m[2].toUpperCase())) continue;
  applyAttrs(m[2], m[3] || '', m[1].toUpperCase() === 'CREATE');
}
const roleDeclared = new Map();
{
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-ROLE-ATTRIBUTES\\n([\\s\\S]*?)\\n' + F3));
  if (m) for (const line of m[1].split('\n')) {
    const t = norm(line);
    if (!t || t.startsWith('#')) continue;
    const c = t.split('|').map((x) => x.trim());
    if (c.length !== 9) continue;
    roleDeclared.set(c[0], { LOGIN: c[1] === 'yes', SUPERUSER: c[2] === 'yes', CREATEDB: c[3] === 'yes',
                             CREATEROLE: c[4] === 'yes', REPLICATION: c[5] === 'yes', BYPASSRLS: c[6] === 'yes',
                             INHERIT: c[7] === 'yes', CONNLIMIT: Number(c[8]) });
  }
}
const roleMismatch = [];
if (roleDeclared.size === 0) roleMismatch.push('блока BEM954-PACKAGE-ROLE-ATTRIBUTES в документе нет');
else {
  for (const [name, st] of [...roleState].sort()) {
    const d = roleDeclared.get(name);
    if (!d) { roleMismatch.push('роль не объявлена: ' + name); continue; }
    for (const k of [...ROLE_FLAGS, 'CONNLIMIT']) {
      if (st[k] !== d[k]) roleMismatch.push(name + ': ' + k + ' в коде ' + st[k] + ', объявлено ' + d[k]);
    }
  }
  for (const name of [...roleDeclared.keys()].sort()) {
    if (!roleState.has(name)) roleMismatch.push('объявлена, но в каноне не создаётся: ' + name);
  }
}

// --- Итоговый граф членств ------------------------------------------------
// Строку членства нельзя пропускать только потому, что в ней нет слова ON.
const memberState = new Map();
function memberKey(role, member) { return role + '|' + member; }
for (const raw of statementsOf(stripComments(sql.replace(/\$(\w*)\$[\s\S]*?\$\1\$/g, ' _BODY_ ')))) {
  const st = norm(raw);
  if (/\sON\s/i.test(st)) continue;
  let m = st.match(/^GRANT\s+([\w\s,]+?)\s+TO\s+([\w\s,]+?)(?:\s+WITH\s+([\s\S]*?))?;?$/i);
  if (m) {
    const opt = (m[3] || '').toUpperCase();
    for (const role of splitTop(m[1])) for (const mem of splitTop(m[2])) {
      const k = memberKey(role, mem);
      if (!memberState.has(k)) {
        const self = roleState.get(mem);
        memberState.set(k, { admin: false, inherit: self ? self.INHERIT : true, set: true });
      }
      const v = memberState.get(k);
      if (/\bADMIN\s+OPTION\b/.test(opt)) v.admin = true;
      if (/\bINHERIT\s+TRUE\b/.test(opt)) v.inherit = true;
      if (/\bINHERIT\s+FALSE\b/.test(opt)) v.inherit = false;
      if (/\bSET\s+TRUE\b/.test(opt)) v.set = true;
      if (/\bSET\s+FALSE\b/.test(opt)) v.set = false;
    }
    continue;
  }
  m = st.match(/^REVOKE\s+(?:ADMIN\s+OPTION\s+FOR\s+)?([\w\s,]+?)\s+FROM\s+([\w\s,]+?);?$/i);
  if (m) {
    for (const role of splitTop(m[1])) for (const mem of splitTop(m[2])) memberState.delete(memberKey(role, mem));
  }
}
const memberDeclared = new Set();
{
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-ROLE-MEMBERSHIPS\\n([\\s\\S]*?)\\n' + F3));
  if (m) for (const line of m[1].split('\n')) {
    const t = norm(line);
    if (t && !t.startsWith('#')) memberDeclared.add(t);
  }
}
const memberActual = new Set();
for (const [k, v] of memberState) {
  const [role, mem] = k.split('|');
  memberActual.add([role, mem, 'BOOTSTRAP_SUPERUSER', v.admin ? 'yes' : 'no',
                    v.inherit ? 'yes' : 'no', v.set ? 'yes' : 'no'].join('|'));
}
const memberMismatch = [];
if (memberDeclared.size === 0) memberMismatch.push('блока BEM954-PACKAGE-ROLE-MEMBERSHIPS в документе нет');
else {
  for (const r of [...memberActual].sort()) if (!memberDeclared.has(r)) memberMismatch.push('членство не объявлено: ' + r);
  for (const r of [...memberDeclared].sort()) if (!memberActual.has(r)) memberMismatch.push('объявлено, но в каноне нет: ' + r);
}

// --- Финальный контрольный маркер ---------------------------------------
// Проверка, стоящая в середине файла, не проверяет ничего: команду можно
// дописать после неё. Каждый канонический файл заканчивается маркером, и
// после маркера ни одной команды безопасности быть не должно.
const MARKER = 'BEM954-FINAL-SECURITY-CHECKPOINT';
const SECURITY_RE = /^(CREATE|ALTER|DROP)\s+ROLE\b|^(GRANT|REVOKE)\b|^ALTER\s+DEFAULT\s+PRIVILEGES\b|\bOWNER\s+TO\b|^SET\s+ROLE\b|^REASSIGN\s+OWNED\b/i;
const MARKED_FILES = ['00_cluster_bootstrap.sql', '01_database_migration.sql',
                      '02_upgrade_to_h110.sql', '03_restore_verifier.sql',
                      '04_backup_window.sql', '05_final_state_check.sql'];
const markerProblems = [];
{
  const seen = new Map();
  for (const f of MARKED_FILES) seen.set(f, 0);
  for (const b of canonBlocks) {
    const at = b.text.lastIndexOf('-- ' + MARKER);
    for (const m of all('--\\s*' + MARKER + ':\\s*(\\S+)', b.text)) {
      if (seen.has(m[1])) seen.set(m[1], seen.get(m[1]) + 1);
      else markerProblems.push('маркер названного файла нет в списке: ' + m[1]);
    }
    if (at < 0) continue;
    const tailText = b.text.slice(at);
    for (const raw of statementsOf(stripComments(tailText.replace(/\$(\w*)\$[\s\S]*?\$\1\$/g, ' _BODY_ ')))) {
      const st = norm(raw);
      if (SECURITY_RE.test(st)) markerProblems.push('после маркера стоит команда безопасности: ' + st.slice(0, 90));
    }
  }
  for (const [f, n] of seen) {
    if (n === 0) markerProblems.push('нет финального маркера файла ' + f);
    if (n > 1) markerProblems.push('маркер файла ' + f + ' встречается ' + n + ' раза');
  }
}

// Опорные тройки «право|объект|получатель» — для проверки 9.
function triples(list) {
  const out = new Set();
  for (const g of list) {
    if (g.kind !== 'GRANT') continue;
    for (const o of objectKeys(g.objText)) {
      for (const p of g.privs) {
        for (const w of g.who) out.add(p.priv + '|' + o + '|' + w);
      }
    }
  }
  return out;
}

// --- Карта «функция → возбуждаемые отказы» ------------------------------
const raisesOf = new Map();
for (const [sig, f] of funcs) {
  raisesOf.set(sig, new Set(
    all("RAISE EXCEPTION\\s+'([A-Z][A-Z0-9_]{2,})", f.body).map((x) => x[1])));
}
// Карта вызовов по подписям: имя в теле ведёт ко всем подписям этого
// имени. Функция отвечает и за отказы своих помощников.
const callsOf = new Map();
for (const [sig, f] of funcs) {
  const set = new Set();
  for (const x of all('bem_(?:control|core)\\.(\\w+)\\s*\\(', f.body)) {
    for (const s of (byName.get(x[1]) || [])) if (s !== sig) set.add(s);
  }
  callsOf.set(sig, set);
}
const closureOf = (sig) => {
  const seen = new Set([sig]);
  const stack = [sig];
  while (stack.length) {
    for (const next of (callsOf.get(stack.pop()) || [])) {
      if (!seen.has(next)) { seen.add(next); stack.push(next); }
    }
  }
  return seen;
};

const doBlockList = all('\\nDO \\$\\$([\\s\\S]*?)\\n\\$\\$;', sql).map((m) => m[1]);
const doRaises = new Set(
  all("RAISE EXCEPTION\\s+'([A-Z][A-Z0-9_]{2,})", doBlockList.join('\n')).map((x) => x[1]));

// --- Раздел 15 и его строки ---------------------------------------------
const from15 = doc.indexOf('\n# 15. ');
const to16 = doc.indexOf('\n# 16. ');
if (from15 < 0 || to16 < 0 || to16 < from15) {
  console.error('РАЗДЕЛ 15 НЕ НАЙДЕН');
  process.exit(1);
}
const reg = doc.slice(from15, to16);

const rows = [];
for (const line of reg.split('\n')) {
  const m = line.match(/^\|\s*`?(K[A-Z0-9-]*\d)`?\s*\|/)
         || line.match(/^\|\s*T\d+\s*\|\s*`?(K\d+)`?\s*\|/)
         || line.match(/^\|\s*DISP-\d+\s*\|\s*`?(KD\d+)`?\s*\|/);
  if (!m) continue;
  const ticked = all('`([^`\\n]+)`', line).map((x) => x[1]);
  // Строка пишет имя и со скобками, и без них, и с полной подписью.
  // Любая запись ведёт ко всем подписям этого имени.
  const asSigs = (t) => {
    let bare = t.replace(/\([\s\S]*$/, '');
    bare = bare.replace(/^bem_(?:control|core)\./, '');
    return byName.get(bare) || [];
  };
  const sigs = [];
  for (const t of ticked) for (const s of asSigs(t)) sigs.push(s);
  rows.push({
    id: m[1],
    fns: uniq(sigs),
    errs: uniq(ticked.filter((t) => /^[A-Z][A-Z0-9_]{2,}$/.test(t))),
  });
}

// --- Проверка 1. Ожидание против ветки ----------------------------------
const fnRaises = new Set();
for (const set of raisesOf.values()) for (const e of set) fnRaises.add(e);
const everyRaise = new Set([...fnRaises, ...doRaises]);
const doOnly = (e) => !fnRaises.has(e) && doRaises.has(e);
let doOnlyCount = 0;

const doCover = new Map();
const coverSeen = new Set();
for (const b of doBlockList) {
  const ids = [];
  for (const x of all('ПОКРЫТИЕ:([^\\n]*)', b)) {
    for (const y of all('K-[A-Z0-9-]*\\d', x[1])) ids.push(y[0]);
  }
  if (ids.length === 0) continue;
  for (const id of ids) coverSeen.add(id);
  for (const x of all("RAISE EXCEPTION\\s+'([A-Z][A-Z0-9_]{2,})", b)) {
    if (!doCover.has(x[1])) doCover.set(x[1], new Set());
    for (const id of ids) doCover.get(x[1]).add(id);
  }
}

const wrongBranch = [];
const doMismatch = [];
const rowsWithoutFn = [];
for (const row of rows) {
  const errs = row.errs.filter((e) => everyRaise.has(e) && !doOnly(e));
  for (const e of row.errs.filter(doOnly)) {
    doOnlyCount += 1;
    const set = doCover.get(e);
    if (!set || !set.has(row.id)) {
      doMismatch.push(row.id + ': ждёт ' + e + ', но блок DO с этим отказом' +
        ' эту строку в покрытии не объявляет');
    }
  }
  if (errs.length === 0) continue;
  if (row.fns.length === 0) {
    if (!noFn.has(row.id)) rowsWithoutFn.push(row.id + ': ' + errs.join(','));
    continue;
  }
  const reachable = new Set();
  for (const sig of row.fns) {
    for (const reached of closureOf(sig)) {
      for (const e of (raisesOf.get(reached) || [])) reachable.add(e);
    }
  }
  for (const e of errs) {
    if (!reachable.has(e)) {
      wrongBranch.push(row.id + ': ждёт ' + e + ', но функции ' +
        row.fns.join(', ') + ' его не возбуждают');
    }
  }
}
const staleCover = [...coverSeen].filter((id) => !rows.some((r) => r.id === id));
const staleNoFn = [...noFn].filter(
  (id) => !rowsWithoutFn.includes(id) && rows.some((r) => r.id === id && r.fns.length > 0));

// --- Проверка 2. REVOKE у каждой функции --------------------------------
const noRevoke = [];
const staleNoRevoke = [];
const revokedPublic = new Set();
for (const g of canonGrants) {
  if (g.kind !== 'REVOKE') continue;
  if (!g.who.includes('PUBLIC')) continue;
  if (!g.privs.some((p) => p.priv === 'EXECUTE')) continue;
  for (const o of objectKeys(g.objText)) if (o.startsWith('FUNCTION:')) revokedPublic.add(o.slice(9));
}
for (const [sig, f] of funcs) {
  if (/\)\s*\nRETURNS trigger/.test(f.head)) continue;   // триггерную зовёт сервер
  const has = revokedPublic.has(sig.toLowerCase());
  if (!has && !noRevokeOk.has(f.name)) noRevoke.push(sig);
  if (has && noRevokeOk.has(f.name)) staleNoRevoke.push(sig);
}
for (const n of noRevokeOk) if (!byName.has(n)) staleNoRevoke.push(n + ': такой функции нет');

// --- Проверка 3. Где разрешено вставлять доказательство -----------------
const stmt = '^[ \\t]*INSERT INTO bem_core\\.evidence';
const countStmt = (t) => (t.match(new RegExp(stmt, 'gm')) || []).length;
const inserts = countStmt(sql);
const writerSigs = byName.get('evidence_write') || [];
const writerBody = writerSigs.length ? funcs.get(writerSigs[0]).body : '';
const insertsInWriter = countStmt(writerBody);
const evidenceDoor = [];
if (writerSigs.length === 0) evidenceDoor.push('функции evidence_write нет');
if (writerSigs.length > 1) evidenceDoor.push('подписей evidence_write больше одной: ' + writerSigs.join(', '));
if (insertsInWriter !== 1) evidenceDoor.push('в evidence_write вставок: ' + insertsInWriter);
if (inserts !== 1) evidenceDoor.push('вставок доказательства во всём каноне: ' + inserts + ', разрешена одна');

// --- Проверка 4. Граница заказчика --------------------------------------
const tenantBad = [];
const tenantList = [];
const crossList = [];
const touchRe = new RegExp('bem_core\\.(' + [...tenantTables].join('|') + ')\\b|current_actor_checked\\s*\\(');

for (const [sig, f] of funcs) {
  const hasArg = /p_tenant_id\s+uuid/.test(f.args);
  const body = stripComments(f.body);
  const touches = tenantTables.size > 0 && touchRe.test(body);
  const ownerBypasses = bypassRoles.has(owners.get(sig));
  if (!hasArg && !(touches && ownerBypasses)) continue;
  if (f.name === 'assert_tenant') continue;

  if (hasArg) tenantList.push(sig); else crossList.push(sig);
  if (helper.has(f.name)) continue;        // помощник, зовётся после границы

  const guards = ['bem_control.assert_tenant(', 'bem_control.assert_authority(']
    .map((x) => body.indexOf(x)).filter((i) => i >= 0);
  const guard = guards.length ? Math.min(...guards) : -1;
  const firstTouch = (() => {
    const re = new RegExp(touchRe.source, 'g');
    let m;
    while ((m = re.exec(body)) !== null) {
      if (m.index < body.indexOf('\nBEGIN')) continue;   // DECLARE — не чтение
      return m.index;
    }
    return -1;
  })();

  if (guard < 0) {
    if (!hasArg) {
      // Функция без аргумента заказчика, владелец которой обходит защиту
      // строк, видит строки ВСЕХ заказчиков. Это бывает нужно — партию
      // исходящих забирает один доставщик на всю установку, — но тогда
      // это объявляется вслух и проверяется отдельной строкой покрытия.
      if (!crossTenant.has(f.name)) {
        tenantBad.push(sig + ': трогает таблицы заказчика без границы и без аргумента,' +
          ' владелец ' + owners.get(sig) + ' обходит защиту строк — нет объявления CROSS_TENANT');
      }
    } else {
      tenantBad.push(sig + ': нет границы — ни assert_tenant, ни assert_authority');
    }
  } else if (firstTouch >= 0 && firstTouch < guard) {
    tenantBad.push(sig + ': обращение к данным заказчика раньше границы');
  }
}
// Объявление обязано быть правдой: если функция и без объявления прошла
// бы проверку, объявление устарело и держит дыру открытой на будущее.
const staleCross = [...crossTenant].filter(
  (n) => !crossList.some((sig) => funcs.get(sig).name === n));

// --- Проверка 8. Получатели EXECUTE -------------------------------------
const execGrants = new Map();               // подпись -> набор получателей
for (const g of canonGrants) {
  if (g.kind !== 'GRANT') continue;
  if (!g.privs.some((p) => p.priv === 'EXECUTE')) continue;
  for (const o of objectKeys(g.objText)) {
    if (!o.startsWith('FUNCTION:')) continue;
    const sig = o.slice(9);
    if (!execGrants.has(sig)) execGrants.set(sig, new Set());
    for (const w of g.who) if (alive('EXECUTE', o, w)) execGrants.get(sig).add(w);
  }
}
const reachableHelper = [];
for (const n of helper) {
  for (const sig of (byName.get(n) || [])) {
    const who = execGrants.get(sig.toLowerCase());
    if (!who) continue;
    const bad = [...who].filter((w) => w !== 'bem_control_owner');
    if (bad.length) {
      reachableHelper.push(n + ': право на исполнение выдано ролям ' + bad.join(', ') +
        ' — границу обязана ставить сама функция');
    }
  }
}
const staleHelper = [...helper].filter((n) => !tenantList.some((sig) => funcs.get(sig).name === n));
const grantWithoutRevoke = [];
for (const sig of execGrants.keys()) {
  if (!revokedPublic.has(sig)) grantWithoutRevoke.push(sig + ': право выдано, а PUBLIC не отозван');
}

// --- Проверка 7. Договор записи -----------------------------------------
function dmlOf(rawBody) {
  const body = stripComments(rawBody);
  const found = [];
  for (const st of statementsOf(body)) {
    const ins = st.match(/INSERT\s+INTO\s+(bem_\w+)\.(\w+)/i);
    if (ins) {
      const table = ins[1] + '.' + ins[2];
      found.push({ op: 'INSERT', table, cols: [] });
      const oc = st.match(/ON\s+CONFLICT[\s\S]*?DO\s+UPDATE\s+SET([\s\S]*)$/i);
      if (oc) found.push({ op: 'UPDATE', table, cols: setColumns(oc[1]) });
      continue;
    }
    const upd = st.match(/UPDATE\s+(bem_\w+)\.(\w+)(?:\s+(?!SET)\w+)?\s+SET([\s\S]*)$/i);
    if (upd) { found.push({ op: 'UPDATE', table: upd[1] + '.' + upd[2], cols: setColumns(upd[3]) }); continue; }
    const del = st.match(/DELETE\s+FROM\s+(bem_\w+)\.(\w+)/i);
    if (del) found.push({ op: 'DELETE', table: del[1] + '.' + del[2], cols: [] });
  }
  return found;
}

const need = new Map();                     // 'роль|таблица|право|колонка' -> подпись
for (const [sig, f] of funcs) {
  const owner = owners.get(sig);
  for (const d of dmlOf(f.body)) {
    // Своей таблице владелец пишет без выданного права: у него права
    // собственные. Проверка 18 раздела 26.9 исключает владельца по той
    // же причине, поэтому и договор обязан его исключать.
    if (tableOwner.get(d.table.toLowerCase()) === owner) continue;
    if (d.op === 'UPDATE' && d.cols.length) {
      for (const c of d.cols) need.set([owner, d.table, 'UPDATE', c].join('|'), sig);
    } else {
      need.set([owner, d.table, d.op, ''].join('|'), sig);
    }
  }
}
const contract = [...need.keys()].sort();

// Фактически выданные права записи.
const WRITE = ['INSERT', 'UPDATE', 'DELETE'];
const SCHEMAS = ['bem_core', 'bem_control', 'bem_engine'];
const grantedExact = new Set();             // роль|таблица|право|колонка (пусто = вся таблица)
const grantedWide = [];                     // широкие права, в договор не ложатся
for (const g of canonGrants) {
  if (g.kind !== 'GRANT') continue;
  for (const p of g.privs) {
    if (!WRITE.includes(p.priv) && p.priv !== 'ALL') continue;
    for (const o of objectKeys(g.objText)) {
      const wide = o.startsWith('ALLTABLES:') || o.startsWith('ALLSEQUENCES:');
      const table = o.startsWith('TABLE:') ? o.slice(6) : null;
      if (wide || p.priv === 'ALL' || !table) {
        if (SCHEMAS.some((s) => o.includes(s))) {
          for (const w of g.who) grantedWide.push(p.priv + ' ' + o + ' -> ' + w);
        }
        continue;
      }
      if (!SCHEMAS.includes(table.split('.')[0])) continue;
      for (const w of g.who) {
        if (!alive(p.priv, o, w)) continue;
        if (p.cols) for (const c of p.cols) grantedExact.add([w, table, p.priv, c].join('|'));
        else grantedExact.add([w, table, p.priv, ''].join('|'));
      }
    }
  }
}
// Право на всю таблицу покрывает право на любую её колонку.
const covers = (row) => {
  if (grantedExact.has(row)) return true;
  const [who, table, priv, col] = row.split('|');
  if (col && grantedExact.has([who, table, priv, ''].join('|'))) return true;
  return false;
};
const dmlMissing = contract.filter((r) => !covers(r)).map((r) => r + '  (нужна ' + need.get(r) + ')');
const contractSet = new Set(contract);
const dmlSurplus = [...grantedExact].filter((r) => {
  if (contractSet.has(r)) return false;
  const [who, table, priv, col] = r.split('|');
  if (col === '') return ![...contractSet].some((c) => c.startsWith([who, table, priv, ''].join('|')));
  return true;
}).sort();
// Право по умолчанию тоже право: ALTER DEFAULT PRIVILEGES ... GRANT INSERT
// обошёл бы обе стороны договора.
const defaultWrites = [];
for (const st of statementsOf(stripComments(sql.replace(/\$(\w*)\$[\s\S]*?\$\1\$/g, ' _BODY_ ')))) {
  const s = norm(st);
  if (!/^ALTER DEFAULT PRIVILEGES/i.test(s)) continue;
  if (/\bGRANT\s+[^;]*\b(INSERT|UPDATE|DELETE|ALL)\b/i.test(s)) defaultWrites.push(s.slice(0, 120));
}

// Договор против списка в самопроверке раздела 26.9.
const embedded = [];
{
  const m = sql.match(/v_dml\s+constant text\[\]\s*:=\s*ARRAY\[([\s\S]*?)\];/);
  if (m) for (const x of all("'([^']*)'", m[1])) embedded.push(x[1]);
}
const embeddedSorted = [...embedded].sort();
const dmlSelfCheck = [];
if (embedded.length === 0) dmlSelfCheck.push('списка v_dml в самопроверке нет');
else {
  for (const r of contract) if (!embeddedSorted.includes(r)) dmlSelfCheck.push('нет в самопроверке: ' + r);
  for (const r of embeddedSorted) if (!contractSet.has(r)) dmlSelfCheck.push('лишнее в самопроверке: ' + r);
}

// --- Проверка 9. Замкнутость канонического диапазона --------------------
const outsideFns = [];
for (const b of outerBlocks) {
  for (const m of all('CREATE OR REPLACE FUNCTION\\s+(bem_\\w+)\\.(\\w+)', b.text)) {
    outsideFns.push(m[1] + '.' + m[2] + ' — определение функции вне канонического диапазона');
  }
}
const canonTriples = triples(canonGrants);
const outsideGrants = [];
for (const t of triples(outerGrants)) {
  if (!canonTriples.has(t)) outsideGrants.push(t + ' — право из пояснения, которого нет в каноне');
}

// --- Проверка 10. Закрытый набор прав -----------------------------------
// У каждого вида объекта свой разрешённый список. Всё, чего в нём нет,
// названо поимённо: роль, объект, право и строка-источник.
const PRIV_OK = {
  TABLE:        ['SELECT', 'INSERT', 'UPDATE', 'DELETE'],
  ALLTABLES:    ['SELECT', 'INSERT', 'UPDATE', 'DELETE'],
  DEFTABLES:    ['SELECT'],
  SEQUENCE:     ['USAGE', 'SELECT'],
  ALLSEQUENCES: ['USAGE', 'SELECT'],
  DEFSEQUENCES: ['USAGE', 'SELECT'],
  SCHEMA:       ['USAGE', 'CREATE'],
  DATABASE:     ['CONNECT'],
  FUNCTION:     ['EXECUTE'],
  ALLFUNCTIONS: ['EXECUTE'],
  ALLROUTINES:  ['EXECUTE'],
  DEFFUNCTIONS: ['EXECUTE'],
  DEFROUTINES:  ['EXECUTE'],
};
// Словарь прав PostgreSQL 16 целиком. MAINTAIN сюда не входит: он
// появился в PostgreSQL 17, и в коде для 16 это неизвестное право.
const PG16_PRIVS = new Set([
  'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER',
  'USAGE', 'CREATE', 'CONNECT', 'TEMPORARY', 'TEMP', 'EXECUTE', 'SET', 'ALTER SYSTEM',
]);
const unknownPrivs = [];
const forbiddenPrivs = [];

// Права по умолчанию разбираются тем же словарём.
function defaultRowsIn(src) {
  const rows = [];
  for (const st of statementsOf(stripComments(src.replace(/\$(\w*)\$[\s\S]*?\$\1\$/g, ' _BODY_ ')))) {
    const s = norm(st);
    const m = s.match(/^ALTER DEFAULT PRIVILEGES\s+(?:FOR ROLE \w+\s+)?(?:IN SCHEMA ([\w\s,]+?)\s+)?(GRANT|REVOKE)\s+([\s\S]*?)\s+ON\s+(TABLES|SEQUENCES|FUNCTIONS|ROUTINES|TYPES|SCHEMAS)\s+(?:TO|FROM)\s+([\s\S]*)$/i);
    if (!m) continue;
    const schemas = m[1] ? splitTop(m[1]) : ['(все схемы)'];
    const kind = 'DEF' + m[4].toUpperCase();
    const privs = splitTop(m[3]).map((x) => x.trim().toUpperCase());
    const who = splitTop(m[5]).map((x) => x.replace(/;+$/, '').trim()).filter(Boolean);
    for (const sc of schemas) for (const pr of privs) for (const w of who) {
      rows.push({ kind: m[2].toUpperCase(), key: kind + ':' + sc, priv: pr, who: w, text: s.slice(0, 110) });
    }
  }
  return rows;
}
const defaultRows = defaultRowsIn(sql);

const checkPriv = (priv, key, who, source) => {
  const kind = key.split(':')[0];
  if (priv === 'ALL' || priv === 'ALL PRIVILEGES' || priv === 'PRIVILEGES') {
    forbiddenPrivs.push(who + ' | ' + key + ' | ALL | ' + source);
    return;
  }
  if (!PG16_PRIVS.has(priv)) {
    unknownPrivs.push(who + ' | ' + key + ' | ' + priv + ' | ' + source);
    return;
  }
  const ok = PRIV_OK[kind];
  if (!ok) { unknownPrivs.push(who + ' | ' + key + ' | ' + priv + ' | неизвестный вид объекта | ' + source); return; }
  if (!ok.includes(priv)) forbiddenPrivs.push(who + ' | ' + key + ' | ' + priv + ' | ' + source);
};

for (const g of canonGrants) {
  if (g.kind !== 'GRANT') continue;
  for (const o of objectKeys(g.objText)) {
    for (const pr of g.privs) for (const w of g.who) checkPriv(pr.priv, o, w, g.text.slice(0, 110));
  }
}
for (const d of defaultRows) {
  if (d.kind !== 'GRANT') continue;
  checkPriv(d.priv, d.key, d.who, d.text);
}

// --- Проверка 11. Договор чтения ----------------------------------------
// Право чтения — тоже право. H1.11 сверяла в обе стороны только запись,
// поэтому лишний SELECT никем не ловился. Здесь множество объявлено и
// сверяется в обе стороны; EXECUTE сюда не входит — он в проверке 12.
const WRITE_PRIVS = ['INSERT', 'UPDATE', 'DELETE'];
const readActual = new Set();
for (const g of canonGrants) {
  if (g.kind !== 'GRANT') continue;
  for (const o of objectKeys(g.objText)) {
    if (o.startsWith('FUNCTION:') || o.startsWith('ALLFUNCTIONS:') || o.startsWith('ALLROUTINES:')) continue;
    for (const pr of g.privs) {
      if (WRITE_PRIVS.includes(pr.priv)) continue;
      for (const w of g.who) if (alive(pr.priv, o, w)) readActual.add(w + '|' + o + '|' + pr.priv);
    }
  }
}
for (const d of defaultRows) {
  if (d.kind !== 'GRANT') continue;
  if (WRITE_PRIVS.includes(d.priv)) continue;
  if (d.key.startsWith('DEFFUNCTIONS:') || d.key.startsWith('DEFROUTINES:')) continue;
  readActual.add(d.who + '|' + d.key + '|' + d.priv);
}
const readDeclared = new Set();
{
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-READ-CONTRACT\\n([\\s\\S]*?)\\n' + F3));
  if (m) for (const line of m[1].split('\n')) {
    const t = line.trim();
    if (t && !t.startsWith('#')) readDeclared.add(t);
  }
}
const readMissing = [];
const readSurplus = [];
if (readDeclared.size === 0) readMissing.push('блока BEM954-PACKAGE-READ-CONTRACT в документе нет');
else {
  for (const r of [...readActual].sort()) if (!readDeclared.has(r)) readMissing.push('не объявлено: ' + r);
  for (const r of [...readDeclared].sort()) if (!readActual.has(r)) readSurplus.push('объявлено, но в каноне нет: ' + r);
}

// --- Проверка 12. Поверхность EXECUTE -----------------------------------
// Число функций ничего не доказывает: оно совпадает и тогда, когда одну
// функцию подменили другой (замечание M-H111-R11-03). Сверяется
// множество «подпись → получатели», а не счёт.
const execActual = new Set();
for (const [sig, who] of execGrants) {
  execActual.add(sig + ' -> ' + [...who].sort().join(','));
}
const execDeclared = new Set();
{
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-EXECUTE-SURFACE\\n([\\s\\S]*?)\\n' + F3));
  if (m) for (const line of m[1].split('\n')) {
    const t = norm(line);
    if (t && !t.startsWith('#')) execDeclared.add(t);
  }
}
const execMissing = [];
const execSurplus = [];
if (execDeclared.size === 0) execMissing.push('блока BEM954-PACKAGE-EXECUTE-SURFACE в документе нет');
else {
  for (const r of [...execActual].sort()) if (!execDeclared.has(r)) execMissing.push('не объявлено: ' + r);
  for (const r of [...execDeclared].sort()) if (!execActual.has(r)) execSurplus.push('объявлено, но в каноне нет: ' + r);
}


// --- Проверка 15. Ожидания живой самопроверки файла 01 -------------------
// Замечание M-H112-R12-01, пункт 4. H1.12 доказывала внутри базы только
// отсутствие лишнего: договор чтения использовался как разрешающий
// набор, а поверхность EXECUTE — как набор запретов. Наличия каждой
// обязательной строки живая проверка не требовала, поэтому снятое
// право она не замечала.
//
// Здесь сверяются ожидания. Списки v_read и v_exec, написанные в файле
// 01, обязаны совпасть с тем, что выводится из самого канона. Иначе
// список в SQL стал бы вторым ручным договором, который расходится с
// первым молча.
//
// Канон режется по финальным маркерам, но кончается файл НЕ строкой
// маркера, а концом той ограды, внутри которой маркер стоит. Под
// маркером, в той же ограде, стоит завершающее пояснение файла, и оно
// принадлежит своему файлу. Прежнее правило отдавало это пояснение
// следующему файлу, а пояснение последнего не доставалось никому —
// увидели это только тогда, когда пакет впервые нарезали на диск (R30).
const fileSql = new Map();
{
  let buf = [];
  for (const b of canonBlocks) {
    buf.push(b.text);
    const m = b.text.match(/^--\s*BEM954-FINAL-SECURITY-CHECKPOINT:\s*(\S+)\s*$/m);
    if (m) { fileSql.set(m[1], buf.join('\n')); buf = []; }
  }
}
// Порядок запуска пакета: файл 00 отдельно на кластере, затем 02 и 01
// одной транзакцией в базе bem (раздел 26.0). Файл 03 работает в
// восстановленной копии и на базу bem не влияет, поэтому в ожидание
// живой проверки не входит.
const DB_ORDER = ['00_cluster_bootstrap.sql', '02_upgrade_to_h110.sql',
                  '01_database_migration.sql'];
function foldAcl(src) {
  const set = new Set();
  for (const g of grantsIn(src)) {
    const keys = objectKeys(g.objText);
    if (g.kind === 'GRANT') {
      for (const o of keys) for (const p of g.privs) for (const w of g.who) set.add(p.priv + '|' + o + '|' + w);
      continue;
    }
    const wipeAll = g.privs.some((p) => p.priv === 'ALL');
    for (const o of keys) for (const w of g.who) {
      if (wipeAll) {
        for (const r of [...set]) { const q = r.split('|'); if (q[1] === o && q[2] === w) set.delete(r); }
      } else for (const p of g.privs) set.delete(p.priv + '|' + o + '|' + w);
    }
  }
  for (const d of defaultRowsIn(src)) {
    const k = d.priv + '|' + d.key + '|' + d.who;
    if (d.kind === 'GRANT') set.add(k); else set.delete(k);
  }
  return set;
}
const dbAcl = foldAcl(DB_ORDER.map((f) => fileSql.get(f) || '').join('\n'));
const expectRead = new Set();
const expectExec = new Set();
for (const r of dbAcl) {
  const [priv, obj, who] = r.split('|');
  if (obj.startsWith('FUNCTION:')) {
    if (priv === 'EXECUTE') expectExec.add(obj.slice(9) + '|' + who);
    continue;
  }
  if (/^(ALLFUNCTIONS|ALLROUTINES|DEFFUNCTIONS|DEFROUTINES|DEFTYPES|DEFSCHEMAS):/.test(obj)) continue;
  if (WRITE_PRIVS.includes(priv)) continue;
  expectRead.add(who + '|' + obj + '|' + priv);
}

// Что на самом деле написано в массивах файла 01.
function arrayRows(src, varName) {
  const re = new RegExp(varName + '\\s+constant\\s+text\\[\\]\\s*:=\\s*ARRAY\\[([\\s\\S]*?)\\];');
  const m = src.match(re);
  if (!m) return null;
  return (m[1].match(/'[^']*'/g) || []).map((x) => x.slice(1, -1));
}
const selfcheckProblems = [];
{
  const f01 = fileSql.get('01_database_migration.sql') || '';
  const pairs = [['v_read', expectRead], ['v_exec', expectExec]];
  for (const [name, want] of pairs) {
    const got = arrayRows(f01, name);
    if (got === null) { selfcheckProblems.push(name + ': массива в файле 01 нет'); continue; }
    const have = new Set(got);
    if (have.size !== got.length) selfcheckProblems.push(name + ': в массиве есть повторы');
    for (const r of [...want].sort()) if (!have.has(r)) selfcheckProblems.push(name + ': не доказывается ' + r);
    for (const r of [...have].sort()) if (!want.has(r)) selfcheckProblems.push(name + ': доказывается лишнее ' + r);
  }
}

// --- Закрытый список форм команд (раздел 4.1 аудита 75) ------------------
// Прежний разбор искал ЗНАКОМОЕ. Значит, всё незнакомое проходило мимо
// молча: `ALTER USER` — тот же `ALTER ROLE` другим словом, имя роли в
// двойных кавычках, переименование роли, пароль строкой. Проверка,
// построенная на списке знакомых образцов, доказывает только то, что
// названные образцы не встретились, и ничего не говорит об остальном.
//
// Теперь наоборот. Канон обязан целиком состоять из объявленных форм.
// Команда, не совпавшая ни с одной формой, — отказ по умолчанию. Это и
// есть «закрытый формат»: список разрешённого, а не список запрещённого.
const RID  = '[a-z_][a-z0-9_]*';
const ROBJ = RID + '(?:\\.' + RID + ')?';
const WHO  = '(?:PUBLIC|' + RID + ')';
const many = (x) => x + '(?:\\s*,\\s*' + x + ')*';
const SIG  = ROBJ + '\\s*\\([^()]*\\)';
const PRIV = '(?:SELECT|INSERT|UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER|CREATE'
           + '|CONNECT|TEMPORARY|TEMP|EXECUTE|USAGE|MAINTAIN|ALL)(?:\\s*\\([^()]*\\))?';
const OBJ  = '(?:ALL (?:TABLES|SEQUENCES|FUNCTIONS|ROUTINES) IN SCHEMA ' + many(RID)
           + '|SCHEMA ' + many(RID)
           + '|DATABASE ' + many(RID)
           + '|FUNCTION ' + many(SIG)
           + '|TABLE ' + many(ROBJ)
           + '|' + many(ROBJ) + ')';
const ATTR = '(?:LOGIN|NOLOGIN|SUPERUSER|NOSUPERUSER|CREATEDB|NOCREATEDB'
           + '|CREATEROLE|NOCREATEROLE|REPLICATION|NOREPLICATION'
           + '|BYPASSRLS|NOBYPASSRLS|INHERIT|NOINHERIT'
           + '|CONNECTION LIMIT -?\\d+|PASSWORD NULL)';
const MEMOPT = '(?:WITH (?:ADMIN OPTION|ADMIN (?:TRUE|FALSE)|INHERIT (?:TRUE|FALSE)'
             + '|SET (?:TRUE|FALSE))(?:, (?:ADMIN|INHERIT|SET) (?:TRUE|FALSE))*)';
const DEFOBJ = '(?:TABLES|SEQUENCES|FUNCTIONS|ROUTINES|TYPES|SCHEMAS)';

const SECURITY_FORMS = [
  ['право на объект',    '^GRANT ' + many(PRIV) + ' ON ' + OBJ + ' TO ' + many(RID) + '$'],
  ['отзыв права',        '^REVOKE ' + many(PRIV) + ' ON ' + OBJ + ' FROM ' + many(WHO) + '$'],
  ['членство',           '^GRANT ' + many(RID) + ' TO ' + many(RID) + '(?: ' + MEMOPT + ')?$'],
  ['отзыв членства',     '^REVOKE ' + many(RID) + ' FROM ' + many(RID) + '$'],
  ['права по умолчанию', '^ALTER DEFAULT PRIVILEGES(?: FOR ROLE ' + many(RID) + ')?'
                         + '(?: IN SCHEMA ' + many(RID) + ')? (?:GRANT ' + many(PRIV)
                         + ' ON ' + DEFOBJ + ' TO ' + many(RID)
                         + '|REVOKE ' + many(PRIV) + ' ON ' + DEFOBJ + ' FROM ' + many(WHO) + ')$'],
  ['владелец функции',   '^ALTER FUNCTION ' + SIG + ' OWNER TO ' + RID + '$'],
  ['владелец таблицы',   '^ALTER TABLE ' + ROBJ + ' OWNER TO ' + RID + '$'],
  ['схема с владельцем', '^CREATE SCHEMA IF NOT EXISTS ' + RID + ' AUTHORIZATION ' + RID + '$'],
  ['смена роли',         '^SET ROLE ' + RID + '$'],
  ['возврат роли',       '^RESET ROLE$'],
  ['признаки роли',      '^ALTER ROLE ' + RID + '(?: ' + ATTR + ')+$'],
  ['сброс настроек роли', '^ALTER ROLE ' + RID + ' RESET ALL$'],
  ['создание роли',      '^CREATE ROLE ' + RID + '(?: ' + ATTR + ')*$'],
].map(([why, re]) => [why, new RegExp(re, 'i')]);

// Запреты действуют и на обычные команды, и на динамические шаблоны.
// Каждый назван словами: отказ должен объяснять, что именно нельзя.
const BANNED = [
  ['ALTER USER — то же, что ALTER ROLE, другим словом', /^ALTER\s+USER\b/i],
  ['CREATE USER — то же, что CREATE ROLE с LOGIN', /^CREATE\s+USER\b/i],
  ['DROP USER', /^DROP\s+USER\b/i],
  ['ALTER GROUP', /^ALTER\s+GROUP\b/i],
  ['CREATE GROUP', /^CREATE\s+GROUP\b/i],
  ['DROP ROLE', /^DROP\s+ROLE\b/i],
  ['переименование роли', /^ALTER\s+ROLE\b.*\bRENAME\s+TO\b/i],
  ['подмена личности сеанса', /^SET\s+SESSION\s+AUTHORIZATION\b/i],
  ['настройка сеанса у роли', /^ALTER\s+ROLE\b.*\bSET\b/i],
  ['выборочный сброс настроек', /^ALTER\s+ROLE\b.*\bRESET\s+(?!ALL$)/i],
  ['пароль строкой', /^(CREATE|ALTER)\s+ROLE\b.*\bPASSWORD\s+'/i],
  ['срок годности', /^(CREATE|ALTER)\s+ROLE\b.*\bVALID\s+UNTIL\b/i],
  ['право передавать право', /\bWITH\s+GRANT\s+OPTION\b/i],
  ['передача владения пачкой', /^REASSIGN\s+OWNED\b/i],
  ['удаление принадлежащего', /^DROP\s+OWNED\b/i],
  ['изменение настроек сервера', /^ALTER\s+SYSTEM\b/i],
  ['метка безопасности', /^SECURITY\s+LABEL\b/i],
  ['чтение из программы', /\bFROM\s+PROGRAM\b/i],
  ['установка расширения', /^CREATE\s+EXTENSION\b/i],
  // Четыре формы позднего снятия защиты. Каждая была подделкой аудита 75
  // (I14, I15, I16, I17) и проходила: широкая форма «правка таблицы»
  // принимала ALTER TABLE с любым хвостом.
  ['снятие построчной защиты', /^ALTER\s+TABLE\b[\s\S]*\bDISABLE\s+ROW\s+LEVEL\s+SECURITY\b/i],
  ['отключение триггера', /^ALTER\s+TABLE\b[\s\S]*\bDISABLE\s+TRIGGER\b/i],
  // R31. Режим REPLICA или ALWAYS меняет у триггера поле tgenabled так же,
  // как DISABLE: триггер перестаёт срабатывать в обычном сеансе или
  // начинает срабатывать там, где не должен. Прежде эту форму
  // принимала широкая «правка таблицы».
  ['смена режима триггера', /^ALTER\s+TABLE\b[\s\S]*\bENABLE\s+(REPLICA|ALWAYS)\s+TRIGGER\b/i],
  ['удаление политики', /^DROP\s+POLICY\b/i],
  ['удаление триггера без пересоздания', /^DROP\s+TRIGGER\s+(?!IF\s+EXISTS\b)/i],
  ['имя в двойных кавычках',
    /^(GRANT|REVOKE|SET\s+ROLE|CREATE\s+ROLE|ALTER\s+ROLE|ALTER\s+FUNCTION|ALTER\s+TABLE|CREATE\s+SCHEMA|ALTER\s+DEFAULT)\b.*"/i],
];

const SHAPE_FORMS = [
  ['ключ psql', /^\\set [A-Z_]+ (on|off)$/i],
  ['курсор-сторож', new RegExp('^DECLARE ' + RID + ' CURSOR FOR SELECT 1$', 'i')],
  ['закрыть курсор', new RegExp('^CLOSE ' + RID + '$', 'i')],
  ['анонимный блок', /^DO /i],
  ['начало транзакции', /^BEGIN$/i],
  ['фиксация', /^COMMIT$/i],
  ['переход в базу', new RegExp('^\\\\connect ' + RID + '$', 'i')],
  ['таблица', /^CREATE TABLE IF NOT EXISTS /i],
  ['тип', /^CREATE TYPE /i],
  ['область значений', /^CREATE DOMAIN /i],
  ['указатель', /^CREATE (UNIQUE )?INDEX (IF NOT EXISTS )?/i],
  ['построчная защита', /^ALTER TABLE \S+ ENABLE ROW LEVEL SECURITY$/i],
  ['жёсткая построчная защита', /^ALTER TABLE \S+ FORCE ROW LEVEL SECURITY$/i],
  ['снятие жёсткого режима на время', /^ALTER TABLE \S+ NO FORCE ROW LEVEL SECURITY$/i],
  ['правка таблицы', /^ALTER TABLE /i],
  ['функция', /^CREATE OR REPLACE FUNCTION /i],
  ['триггер', /^CREATE TRIGGER /i],
  ['снять триггер', /^DROP TRIGGER IF EXISTS /i],
  ['политика', /^CREATE POLICY /i],
  ['правка политики', /^ALTER POLICY /i],
  ['вставка', /^INSERT INTO /i],
  ['правка строк', /^UPDATE /i],
  ['чтение', /^SELECT /i],
  ['возврат роли', /^RESET ROLE$/i],
  ['схема с владельцем', /^CREATE SCHEMA IF NOT EXISTS /i],
];

const vocabProblems = [];
const vocabCounts = new Map();
{
  const noBodies = sql.replace(/\$(\w*)\$[\s\S]*?\$\1\$/g, ' _BODY_ ');
  // Команда psql начинается с обратной косой черты и точки с запятой не
  // имеет. Без этой строки она склеивалась со следующей за ней командой.
  const noMeta = noBodies.split('\n')
    .map((l) => (/^\s*\\/.test(l) ? l.replace(/\s+$/, '') + ';' : l)).join('\n');
  // К командам безопасности для закрытого списка причисляются ещё две
  // формы: возврат роли и создание схемы с владельцем. В маркерной
  // проверке их нет намеренно — там речь о командах, меняющих права.
  const VOCAB_SECURITY_RE = new RegExp(
    SECURITY_RE.source + '|^RESET\\s+ROLE\\b|\\bAUTHORIZATION\\b', 'i');
  for (const raw of statementsOf(stripComments(noMeta))) {
    const st = norm(raw);
    if (!st) continue;
    let banned = null;
    for (const [why, re] of BANNED) if (re.test(st)) { banned = why; break; }
    if (banned) {
      vocabProblems.push('запрещённая форма — ' + banned + ': ' + st.slice(0, 110));
      continue;
    }
    const isSecurity = VOCAB_SECURITY_RE.test(st);
    const forms = isSecurity ? SECURITY_FORMS : SHAPE_FORMS;
    let hit = null;
    for (const [why, re] of forms) if (re.test(st)) { hit = why; break; }
    if (hit === null) {
      vocabProblems.push((isSecurity ? 'команда безопасности вне закрытого списка: '
                                     : 'команда вне закрытого списка: ') + st.slice(0, 110));
      continue;
    }
    vocabCounts.set(hit, (vocabCounts.get(hit) || 0) + 1);
  }
}

// --- Закрытый список динамических команд ---------------------------------
// Команда, собранная из строки во время работы, статическому разбору не
// видна: в тексте стоит `EXECUTE format(...)`, а что именно выполнится,
// решает подставленное значение. Поэтому объявляется точный набор
// шаблонов. Любой новый или изменённый шаблон — расхождение.
// Границу честно: набор замкнут по тексту шаблона, а подставляемые
// значения проверяются не здесь. Значения признаков роли в файле 00
// закрыты отдельно — блоком BEM954-PACKAGE-ROLE-ATTRIBUTES.
const dynActual = new Set();
const dynProblems = [];
{
  // Шаблон часто склеен из нескольких кусков в кавычках. Берётся первый
  // довод вызова целиком, а не первая строка: иначе половина шаблона
  // остаётся непроверенной, и дописать в неё можно что угодно.
  // Слово EXECUTE встречается и внутри строковых значений — например в
  // теле триггера, записанном строкой. Считать его командой нельзя:
  // разбор с этого места пойдёт со сбитой чётностью кавычек и примет
  // код за значение. Поэтому сначала размечается, где код, а где нет.
  const mask = codeMask(sql);
  const re = /\bEXECUTE\s+/gi;
  let m;
  while ((m = re.exec(sql)) !== null) {
    if (!mask[m.index]) continue;                       // слово внутри значения
    let i = m.index + m[0].length;
    if (/^(ON|FUNCTION|PROCEDURE)\b/i.test(sql.slice(i, i + 10))) continue;
    const f = sql.slice(i, i + 10).match(/^format\s*\(\s*/i);
    if (f) i += f[0].length;
    const parts = [];
    let depth = 0;
    for (let j = i; j < sql.length; j++) {
      const c = sql[j];
      if (c === "'") {
        const end = endOfLiteral(sql, j);
        parts.push(sql.slice(j + 1, end).replace(/''/g, "'"));
        j = end;
        continue;
      }
      if (c === '$') {
        const t = sql.slice(j, j + 40).match(/^\$(\w*)\$/);
        if (t) {
          const k = sql.indexOf(t[0], j + t[0].length);
          const end = k < 0 ? sql.length : k;
          parts.push(sql.slice(j + t[0].length, end));
          j = end + t[0].length - 1;
          continue;
        }
      }
      if (c === '(') { depth += 1; continue; }
      if (c === ')') { if (depth === 0) break; depth -= 1; continue; }
      if ((c === ',' || c === ';') && depth === 0) break;
    }
    const t = norm(parts.join(''));
    if (t) dynActual.add(t);
    else dynProblems.push('исполнение собранной строки без видимого шаблона рядом с: '
                          + norm(sql.slice(m.index, m.index + 70)));
  }
}
for (const t of [...dynActual].sort()) {
  for (const [why, re] of BANNED) {
    if (re.test(t)) dynProblems.push('запрещённая форма в динамической команде — ' + why + ': ' + t.slice(0, 110));
  }
}
{
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-DYNAMIC-STATEMENTS\\n([\\s\\S]*?)\\n' + F3));
  const declared = new Set(m ? m[1].split('\n').map((x) => x.trim()).filter(Boolean) : []);
  if (declared.size === 0) dynProblems.push('блока BEM954-PACKAGE-DYNAMIC-STATEMENTS в документе нет');
  else {
    for (const t of [...dynActual].sort()) if (!declared.has(t)) dynProblems.push('динамическая команда не объявлена: ' + t.slice(0, 110));
    for (const t of [...declared].sort()) if (!dynActual.has(t)) dynProblems.push('объявлена, но в каноне нет: ' + t.slice(0, 110));
  }
}

// --- Окно мигратора: что он получает и чем это ограничено ----------------
// Замечание C-H113-R13-01. Дыра была не в одной команде, а в самом
// полномочии: мигратору выдавали членство в роли с CREATEROLE, и любая
// команда файла 01 могла стать ею. Поэтому проверяется не пример, а
// класс: список выданных ролей закрыт, и ни одна роль из него не имеет
// права менять чужие роли.
const migratorProblems = [];
const migratorGrants = (() => {
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-MIGRATOR-GRANTS\\n([\\s\\S]*?)\\n' + F3));
  return new Set(m ? m[1].split('\n').map((x) => x.trim()).filter(Boolean) : []);
})();
// Список, который обёртка выдаёт мигратору, читается из её листинга и
// печатается ключом --print-contracts: объявленный блок сверяется с кодом,
// а не наоборот.
const wrapperText = (() => {
  // Искать от начала документа нельзя: этот самый файл лежит в разделе
  // 15.11 листингом, и строка-якорь встречается в нём первой. Сверщик
  // нашёл бы сам себя и объявил, что списка в обёртке нет. Поэтому
  // поиск идёт от заголовка раздела 25, где стоит настоящая обёртка.
  const at = doc.indexOf('\n# 25. ');
  const i = doc.indexOf('// run_migration.mjs — внешняя обёртка окна мигратора.',
                        at < 0 ? 0 : at);
  if (i < 0) return '';
  const j = doc.indexOf('\n' + F3 + '\n', i);
  return j < 0 ? doc.slice(i) : doc.slice(i, j);
})();
const wrapperListOf = (re) => {
  const m = wrapperText.match(re);
  if (!m) return null;
  return new Set(norm(m[1]).split(/\s*,\s*/).map((x) => x.trim()).filter(Boolean));
};
const wrapperGranted = wrapperListOf(/GRANT\s+([\s\S]*?)\s+TO schema_migrator;/);
const wrapperRevoked = wrapperListOf(/REVOKE\s+([\s\S]*?)\s+FROM schema_migrator;/);
if (migratorGrants.size === 0) migratorProblems.push('блока BEM954-PACKAGE-MIGRATOR-GRANTS в документе нет');
else {
  if (!wrapperText) migratorProblems.push('листинга обёртки run_migration.mjs в документе нет');
  const granted = wrapperGranted;
  const revoked = wrapperRevoked;
  const same = (a, name) => {
    if (a === null) { migratorProblems.push(name + ': списка в обёртке нет'); return; }
    for (const r of [...migratorGrants].sort()) if (!a.has(r)) migratorProblems.push(name + ': не хватает ' + r);
    for (const r of [...a].sort()) if (!migratorGrants.has(r)) migratorProblems.push(name + ': лишнее ' + r);
  };
  same(granted, 'выдача в openWindow');
  same(revoked, 'отзыв в closeWindow');

  // 2. Ни одна выданная роль не умеет менять чужие роли.
  for (const r of [...migratorGrants].sort()) {
    const st = roleState.get(r);
    if (!st) { migratorProblems.push('выданная роль не объявлена в признаках: ' + r); continue; }
    for (const attr of ['SUPERUSER', 'CREATEROLE', 'CREATEDB', 'REPLICATION']) {
      if (st[attr]) migratorProblems.push('выданная мигратору роль имеет признак ' + attr + ': ' + r);
    }
    if (st.LOGIN) migratorProblems.push('выданная мигратору роль умеет входить: ' + r);
  }
  // 3. Ни одна выданная роль не администрирует другую роль.
  for (const line of memberActual) {
    const p = line.split('|');
    if (migratorGrants.has(p[1]) && p[3] === 'yes') {
      migratorProblems.push('выданная мигратору роль администрирует роль ' + p[0] + ': ' + p[1]);
    }
  }
  // 4. В файлах мигратора нет смены роли на роль вне списка.
  for (const f of ['01_database_migration.sql', '02_upgrade_to_h110.sql']) {
    const src = fileSql.get(f);
    if (src === undefined) { migratorProblems.push('в каноне нет файла ' + f); continue; }
    for (const m of all('(?:^|\\n)\\s*SET ROLE\\s+(' + RID + ')', src)) {
      if (!migratorGrants.has(m[1])) migratorProblems.push(f + ': смена роли на роль вне окна: ' + m[1]);
    }
  }
}

// --- Договор о пароле, сроке годности и настройках сеанса ----------------
// Замечание M-H113-R13-04. Признаки роли ничего не говорят о том, есть ли
// у неё пароль, до какого числа она годна и какие настройки сеанса ей
// назначены. А это ровно те три вещи, которыми тихая правка делает роль
// пригодной для входа злоумышленника. Договор выводится из канона и
// сверяется с объявленным блоком; живую базу по нему проверяет файл 05.
//
// Значения паролей здесь не читаются и не печатаются ни при каких
// условиях: сравнивается только признак «задан» или «не задан». Хеш
// пароля — такой же секрет, как сам пароль.
const roleSecretRows = [];
const secretProblems = [];
{
  for (const [name] of [...roleState].sort()) {
    const t = roleAttrText.get(name) || '';
    const pwd = /\bPASSWORD\s+'/i.test(t) ? 'set'
              : (/\bPASSWORD\s+NULL\b/i.test(t) ? 'null' : 'none');
    const val = /\bVALID\s+UNTIL\b/i.test(t) ? 'set' : 'none';
    const cfg = /\bSET\s+\w+\s*=/i.test(t) ? 'set' : 'none';
    roleSecretRows.push([name, 'password:' + pwd, 'valid_until:' + val, 'config:' + cfg].join('|'));
    if (pwd === 'set') secretProblems.push('пароль задан в каноне строкой: ' + name);
    if (val === 'set') secretProblems.push('срок годности задан в каноне: ' + name);
    if (cfg === 'set') secretProblems.push('настройка сеанса задана в каноне: ' + name);
  }
  const m = doc.match(new RegExp('BEM954-(?:PACKAGE|H1-\\d+)-ROLE-SECRETS\\n([\\s\\S]*?)\\n' + F3));
  const declared = m ? m[1].split('\n').map((x) => norm(x)).filter(Boolean) : [];
  if (declared.length === 0) secretProblems.push('блока BEM954-PACKAGE-ROLE-SECRETS в документе нет');
  else {
    const have = new Set(declared);
    for (const r of roleSecretRows) if (!have.has(r)) secretProblems.push('не объявлено: ' + r);
    for (const r of declared) if (!roleSecretRows.includes(r)) secretProblems.push('объявлено, но в каноне нет: ' + r);
  }
}

// --- Списки для терминальной проверки, файл 05 (M-H113-R13-01) ----------
// Терминальная проверка стоит последней во всём пакете и читает итоговое
// состояние кластера. Её списки выводятся отсюда, из канона, а не пишутся
// руками: иначе они стали бы вторым договором, который молча расходится
// с первым. Роль проверки восстановления в них не входит — её создаёт
// файл 03 и только в восстановленной копии, в рабочем кластере её нет.
const RESTORE_ONLY = new Set(['restore_verifier']);
const termRoles = [];
for (const [name, st] of [...roleState].sort()) {
  if (RESTORE_ONLY.has(name)) continue;
  termRoles.push([name, st.LOGIN ? 'yes' : 'no', st.SUPERUSER ? 'yes' : 'no',
                  st.CREATEDB ? 'yes' : 'no', st.CREATEROLE ? 'yes' : 'no',
                  st.REPLICATION ? 'yes' : 'no', st.BYPASSRLS ? 'yes' : 'no',
                  st.INHERIT ? 'yes' : 'no', String(st.CONNLIMIT)].join('|'));
}
const termSecrets = roleSecretRows.filter((r) => !RESTORE_ONLY.has(r.split('|')[0]));
const termMembers = [...memberActual].sort();
const termLogin = termRoles.filter((r) => r.split('|')[1] === 'yes').map((r) => r.split('|')[0]);

// Итоговые права считаются по порядку запуска пакета в рабочей базе,
// и файл 04 в этот порядок входит: он запускается последним и добавляет
// право вызывать четыре функции окна копирования.
const DB_ORDER_FINAL = [...DB_ORDER, '04_backup_window.sql'];
const finalAcl = foldAcl(DB_ORDER_FINAL.map((f) => fileSql.get(f) || '').join('\n'));
const termRead = new Set();
const termExec = new Set();
for (const r of finalAcl) {
  const [priv, obj, who] = r.split('|');
  if (obj.startsWith('FUNCTION:')) {
    if (priv === 'EXECUTE') termExec.add(obj.slice(9) + '|' + who);
    continue;
  }
  if (/^(ALLFUNCTIONS|ALLROUTINES|DEFFUNCTIONS|DEFROUTINES|DEFTYPES|DEFSCHEMAS):/.test(obj)) continue;
  if (WRITE_PRIVS.includes(priv)) continue;
  termRead.add(who + '|' + obj + '|' + priv);
}

// Владелец, режим исполнения и путь поиска каждой функции. Функция с
// SECURITY DEFINER и незакреплённым путём поиска — открытая дверь:
// вызывающий подставляет свою схему и подменяет вызов внутри тела.
const termFunc = [];
for (const [sig, f] of [...funcs].sort()) {
  const secdef = /\bSECURITY\s+DEFINER\b/i.test(f.head) ? 'definer' : 'invoker';
  // Весь proconfig, а не только путь поиска: вторая настройка меняет
  // поведение тела так же тихо (замечание M-H114-R14-01). Настройки
  // сортируются, потому что в каталоге их порядок — порядок написания.
  const sets = [];
  for (const m of all('\\bSET\\s+(\\w+)\\s*=\\s*([^\\n]+)', f.head)) {
    sets.push(m[1] + '=' + norm(m[2]).replace(/;$/, '').replace(new RegExp(String.fromCharCode(39), 'g'), ''));
  }
  termFunc.push([sig, owners.get(sig) || '?', secdef,
                 sets.length ? [...sets].sort().join(';') : 'none'].join('|'));
}

const termRls = [...tenantTables].sort().map((t) => 'bem_core.' + t);
// Договор политики выводится из самого шаблона канона, а не пишется
// здесь числом полей. Шаблонов два — создающий и изменяющий, — и они
// обязаны говорить одно и то же: разойдясь, они дали бы базе одно
// состояние после установки и другое после повторного прогона.
const policyProblems = [];
const termPolicy = (() => {
  const seen = [];
  // Соседние строковые значения склеиваются, как это делает сервер:
  // шаблон написан тремя кусками подряд и целиком в тексте не лежит.
  const glued = sql.replace(new RegExp('\\x27\\s*\\n\\s*\\x27', 'g'), '');
  for (const kind of ['CREATE', 'ALTER']) {
    const m = glued.match(new RegExp(kind
      + '\\s+POLICY\\s+(\\w+)\\s+ON\\s+bem_core\\.%I(?:\\s+TO\\s+([\\w, ]+?))?'
      + '\\s+USING\\s*\\((.+)\\)\\s+WITH\\s+CHECK\\s*\\((.+)\\)\\x27', 'm'));
    if (!m) { policyProblems.push('в каноне нет шаблона ' + kind + ' POLICY'); continue; }
    const roles = norm(m[2] || 'public').split(/\s*,\s*/).sort().join(',');
    const strip = (e) => '(' + norm(e).replace(/bem_core\./g, '') + ')';
    seen.push([m[1], roles, strip(m[3]), strip(m[4])].join('\u0001'));
  }
  if (seen.length === 2 && seen[0] !== seen[1]) {
    policyProblems.push('шаблоны CREATE POLICY и ALTER POLICY описывают разные политики');
  }
  if (!seen.length) return [];
  const [name, roles, using, check] = seen[0].split('\u0001');
  return termRls.map((t) => [t, name, 'ALL', 'PERMISSIVE', roles, using, check].join('|'));
})();
// Разбор тела команды CREATE TRIGGER закрытой грамматикой.
//
// R30 (C-H114-R14-01) дал отпечаток из одиннадцати полей — тот же, что
// сверяет файл 05: схема.таблица | имя | маска событий | столбцы |
// функция | режим | ограничение | отложенность | начальная отложенность
// | WHEN | аргументы.
//
// R31 (C-H115-R15-01). Об условии WHEN отпечаток знал только «есть или
// нет», об аргументах — только их число. Подделка I-H115-01 меняла
// условие constraint-триггера на WHEN (true) и проходила все три уровня
// проверки. Теперь тот же разбор даёт и определение целиком: текст
// условия в том виде, в каком его печатает сервер, байты аргументов и
// строку pg_get_triggerdef(oid, true) при пути поиска pg_catalog. Строку
// сервер строит по каталогу, а не по тексту команды, поэтому здесь она
// собирается по тем же правилам: события всегда в порядке INSERT,
// DELETE, UPDATE, TRUNCATE; у constraint-триггера режим отложенности
// написан всегда; имена NEW и OLD в условии — строчными.
//
// Маска — разряды каталога pg_trigger: 1 строка, 2 BEFORE, 4 INSERT,
// 8 DELETE, 16 UPDATE, 32 TRUNCATE, 64 INSTEAD. Неизвестная форма даёт
// null, и это расхождение, а не пропуск: закрытость важнее полноты.
// Условие WHEN разбирается тоже закрытой грамматикой: true, false и
// «NEW.столбец IS [NOT] NULL». Всё прочее — расхождение: как сервер
// напечатает другое выражение, без живой базы не проверить.
const TRG_ID = /^[a-z_][a-z0-9_]*$/;
function whenText(raw) {
  if (raw === undefined) return '';
  let e = raw.trim();
  const wrapped = (x) => {
    if (!x.startsWith('(') || !x.endsWith(')')) return false;
    let depth = 0;
    for (let i = 0; i < x.length; i += 1) {
      if (x[i] === '(') depth += 1;
      if (x[i] === ')') depth -= 1;
      if (depth === 0 && i < x.length - 1) return false;
    }
    return true;
  };
  while (wrapped(e)) e = e.slice(1, -1).trim();
  if (/^(true|false)$/i.test(e)) return e.toLowerCase();
  const k = e.match(/^(NEW|OLD)\.([a-z_][a-z0-9_]*) IS (NOT )?NULL$/i);
  if (k) return k[1].toLowerCase() + '.' + k[2] + ' IS ' + (k[3] ? 'NOT ' : '') + 'NULL';
  return null;
}
function triggerParse(name, body, isConstraint) {
  if (!TRG_ID.test(name)) return null;
  const t = String(body).replace(/\s+/g, ' ').trim();
  const m = t.match(/^(BEFORE|AFTER|INSTEAD OF) (.*?) ON (bem_\w+\.\w+) (.*)$/i);
  if (!m) return null;
  const [, timing, events, table, rest] = m;
  let type = 0;
  if (/^BEFORE$/i.test(timing)) type |= 2;
  else if (/^INSTEAD OF$/i.test(timing)) type |= 64;
  const seen = new Set();
  const cols = [];
  for (const raw of events.split(/ OR /i)) {
    const u = raw.trim().match(/^UPDATE OF (.+)$/i);
    const e = u ? 'UPDATE' : raw.trim().toUpperCase();
    const bit = { INSERT: 4, DELETE: 8, UPDATE: 16, TRUNCATE: 32 }[e];
    if (!bit || seen.has(e)) return null;
    seen.add(e);
    type |= bit;
    if (u) {
      for (const c of u[1].split(',')) {
        if (!TRG_ID.test(c.trim())) return null;
        cols.push(c.trim());
      }
    }
  }
  const r = rest.match(/^(?:(NOT )?(DEFERRABLE) )?(?:INITIALLY (DEFERRED|IMMEDIATE) )?FOR EACH (ROW|STATEMENT) (?:WHEN \((.*)\) )?EXECUTE (?:FUNCTION|PROCEDURE) (bem_\w+\.\w+) ?\(([^)]*)\)$/i);
  if (!r) return null;
  const [, notDef, defer, initially, level, whenRaw, fn, argText] = r;
  if (!isConstraint && (defer || initially)) return null;
  const initDeferred = /^DEFERRED$/i.test(initially || '');
  if (notDef && initDeferred) return null;
  const deferrable = Boolean(defer && !notDef) || initDeferred;
  if (/^ROW$/i.test(level)) type |= 1;
  const when = whenText(whenRaw);
  if (when === null) return null;
  const args = [];
  if (argText.trim() !== '') {
    for (const a of argText.split(',')) {
      const q = a.trim().match(/^'([^'\\]*)'$/);
      if (!q) return null;
      args.push(q[1]);
    }
  }
  const ev = [];
  if (type & 4) ev.push('INSERT');
  if (type & 8) ev.push('DELETE');
  if (type & 16) ev.push(cols.length ? 'UPDATE OF ' + cols.join(', ') : 'UPDATE');
  if (type & 32) ev.push('TRUNCATE');
  const def = (isConstraint ? 'CREATE CONSTRAINT TRIGGER ' : 'CREATE TRIGGER ') + name
    + ' ' + timing.toUpperCase() + ' ' + ev.join(' OR ') + ' ON ' + table + ' '
    + (isConstraint ? (deferrable ? '' : 'NOT ') + 'DEFERRABLE INITIALLY '
                      + (initDeferred ? 'DEFERRED ' : 'IMMEDIATE ') : '')
    + 'FOR EACH ' + ((type & 1) ? 'ROW ' : 'STATEMENT ')
    + (when ? 'WHEN (' + when + ') ' : '')
    + 'EXECUTE FUNCTION ' + fn + '(' + args.map((a) => "'" + a + "'").join(', ') + ')';
  const flag = (b) => (b ? 't' : 'f');
  const argsHex = Buffer.from(args.map((a) => a + '\0').join(''), 'utf8').toString('hex');
  return {
    name, table, isConstraint, when, def,
    print: [table, name, type, cols.join(','), fn + '()', 'O', flag(isConstraint),
            flag(deferrable), flag(initDeferred), flag(when !== ''), args.length].join('|'),
    line: [table, name, when, argsHex, def].join('|'),
  };
}

// Триггеры одного канонического файла. Два источника: строки списка
// шага 7, откуда команда собирается через EXECUTE format, и написанные
// целиком команды CREATE TRIGGER. У строк списка дополнительно
// сверяются объявленные там же ожидания: тот, кто поправил тело, но не
// поправил маску, условие или определение, останавливается уже здесь.
//
// Написанная целиком команда ищется только в начале строки. С R31 текст
// «CREATE TRIGGER ...» стоит ещё и внутри строковых постоянных — это
// ожидаемые определения, — и командой он не является.
const trgProblems = [];
function triggersOf(src, label) {
  const found = [];
  const V = "\\(\\s*'([a-z_]\\w*)',\\s*'(bem_\\w+\\.\\w+)',\\s*'((?:BEFORE|AFTER|INSTEAD OF)[^']*)',"
          + "\\s*(\\d+)::smallint,\\s*'([^']*)'::text,\\s*'([^']*)'::text"
          + "(?:,\\s*'([^']*)'::text,\\s*'([^']*)'::text)?\\s*\\)";
  for (const m of all(V, src)) {
    const p = triggerParse(m[1], m[3], false);
    if (p === null) { trgProblems.push(label + ': не разобрано тело триггера ' + m[1]); continue; }
    const fp = p.print.split('|');
    if (fp[2] !== m[4]) trgProblems.push(label + ': ' + m[1] + ': по телу маска ' + fp[2] + ', объявлено ' + m[4]);
    if (fp[3] !== m[5]) trgProblems.push(label + ': ' + m[1] + ': по телу столбцы "' + fp[3] + '", объявлено "' + m[5] + '"');
    if (fp[4] !== m[6]) trgProblems.push(label + ': ' + m[1] + ': по телу функция ' + fp[4] + ', объявлено ' + m[6]);
    if (fp[0] !== m[2]) trgProblems.push(label + ': ' + m[1] + ': по телу таблица ' + fp[0] + ', объявлено ' + m[2]);
    if (m[7] === undefined) {
      trgProblems.push(label + ': ' + m[1] + ': в строке списка нет ожидаемых условия WHEN и определения');
    } else {
      if (p.when !== m[7]) trgProblems.push(label + ': ' + m[1] + ': по телу условие WHEN "' + p.when + '", объявлено "' + m[7] + '"');
      if (p.def !== m[8]) trgProblems.push(label + ': ' + m[1] + ': по телу определение "' + p.def + '", объявлено "' + m[8] + '"');
    }
    found.push(p);
  }
  for (const m of src.matchAll(/^[ \t]*CREATE\s+(CONSTRAINT\s+)?TRIGGER\s+([a-z_]\w*)\s+([\s\S]*?);/gm)) {
    const p = triggerParse(m[2], m[3], Boolean(m[1]));
    if (p === null) {
      // R33 (решение D-05, замечание L-H117-R17-01). Эталонный триггер
      // subject_requires_author_ref создаётся на pg_temp.subject_reference_shape
      // и удаляется в той же команде DO — в постоянном состоянии базы его
      // нет, и разбирать его как обычный триггер схемы (таблица bem_*) не
      // нужно. triggerParse требует ON bem_\w+\.\w+ и вернёт null для любой
      // pg_temp-таблицы — это ожидаемо, не расхождение. Любая ДРУГАЯ
      // неразобранная команда CREATE TRIGGER — расхождение, как раньше.
      if (m[3].match(/\sON\s+pg_temp\.\w+\s/i)) continue;
      trgProblems.push(label + ': не разобрана команда CREATE TRIGGER ' + m[2]);
      continue;
    }
    found.push(p);
  }
  return {
    found,
    prints: [...new Set(found.map((p) => p.print))].sort(),
    lines: [...new Set(found.map((p) => p.line))].sort(),
  };
}

const trg01 = triggersOf(fileSql.get('01_database_migration.sql') || '', 'файл 01');
const trg02 = triggersOf(fileSql.get('02_upgrade_to_h110.sql') || '', 'файл 02');
const termTrigger = trg01.prints;
const termTriggerLegacy = trg02.prints;
const termTriggerDef = trg01.lines;
const termTriggerDefLegacy = trg02.lines;

// --- Жёсткий режим снимается только на время -----------------------------
// Пакет снимает жёсткий режим защиты нарочно: FORCE действует и на
// владельца, а владельцу нужно один раз пересчитать строки. Опасно не
// само снятие, а невозвращённое снятие. Поэтому правило про порядок:
// последняя команда о жёстком режиме для каждой таблицы в каждом файле
// обязана этот режим включать. Подделка I15 снимала его и не возвращала.
const rlsForceProblems = [];
for (const [f, src] of fileSql) {
  const last = new Map();
  for (const m of all('ALTER TABLE\\s+(bem_\\w+\\.\\w+)\\s+(NO )?FORCE ROW LEVEL SECURITY', src)) {
    last.set(m[1], m[2] ? 'снят' : 'включён');
  }
  for (const [t, state] of [...last].sort()) {
    if (state === 'снят') rlsForceProblems.push(f + ': жёсткий режим защиты снят и не возвращён: ' + t);
  }
}

// --- Удаление триггера только вместе с созданием -------------------------
const triggerDropProblems = [];
for (const [f, src] of fileSql) {
  for (const m of all('DROP TRIGGER IF EXISTS\\s+([a-z_]\\w*)\\s+ON\\s+(bem_\\w+\\.\\w+)', src)) {
    const re = new RegExp('^[ \\t]*CREATE (?:CONSTRAINT )?TRIGGER\\s+' + m[1] + '\\b[\\s\\S]{0,800}?\\sON\\s+' + m[2].replace('.', '\\.'), 'im');
    if (!re.test(src)) {
      triggerDropProblems.push(f + ': триггер снят и не создан заново: ' + m[2] + '|' + m[1]);
    }
  }
}

// --- Точное множество прав доступа --------------------------------------
// Замечание M-H114-R14-02. Прежняя сверка прав была односторонней: она
// выводила из канона «что должно быть выдано» и смотрела, выдано ли.
// Лишнего она не искала вовсе — по устройству, а не по недосмотру. Так у
// PUBLIC осталось право TEMPORARY на рабочую базу, и ни один сверщик и ни
// одна из 120 подделок H1.14 этого не показали.
//
// Здесь строится ПОЛНОЕ множество прав, какое будет в каталоге после
// пакета: команды выдачи и отзыва проигрываются в том порядке, в каком
// их подаёт обёртка. Моделируются три вещи, без которых множество не
// совпало бы с каталогом ни при какой подделке:
//
//   1. Список прав объекта пуст, пока по объекту не было ни одной выдачи
//      и ни одного отзыва: права владельца в этом случае подразумеваются.
//      Первая же команда список проявляет, и строка владельца в нём
//      появляется.
//   2. У функции в подразумеваемом наборе есть PUBLIC с правом вызова, у
//      базы — PUBLIC с правом подключения и с правом временных таблиц.
//   3. Право по столбцам (`GRANT UPDATE (a, b) ON t`) хранится отдельно,
//      в списке прав столбца. Записать его как право на таблицу значило
//      бы потерять лишнее право по столбцу.
//
// Грамматика закрытая: неразобранная команда прав попадает в расхождения,
// а не пропускается молча. Молчаливый пропуск — это и есть дыра.
const aclProblems = [];
// R32. Срез прав после файла 01 и строки, которые добавляет файл 04.
let termAcl01 = [];
let termAcl04 = [];
const termAcl = (() => {
  const OWNER_PRIV = {
    TABLE:    ['DELETE', 'INSERT', 'REFERENCES', 'SELECT', 'TRIGGER', 'TRUNCATE', 'UPDATE'],
    SEQUENCE: ['SELECT', 'UPDATE', 'USAGE'],
    FUNCTION: ['EXECUTE'],
    SCHEMA:   ['CREATE', 'USAGE'],
    DATABASE: ['CONNECT', 'CREATE', 'TEMPORARY'],
  };
  const PUBLIC_PRIV = {
    FUNCTION: ['EXECUTE'],
    DATABASE: ['CONNECT', 'TEMPORARY'],
  };
  const SEP = String.fromCharCode(0);
  const acl = new Map();
  const own = new Map();
  const def = new Map();
  const fnOwn = new Map();
  let role = null;
  const kk = (kind, name) => kind + SEP + name;
  const cut = (s) => s.split(',').map((x) => x.trim().replace(/^"|"$/g, '')).filter(Boolean);

  function parts(s, kind) {
    const t = s.trim();
    if (/^ALL(\s+PRIVILEGES)?$/i.test(t)) return OWNER_PRIV[kind].map((p) => ({ priv: p, cols: [] }));
    const out = [];
    const re = /([A-Za-z]+(?:\s+[A-Za-z]+)*)\s*(\(([^)]*)\))?\s*(?:,|$)/g;
    let m;
    while ((m = re.exec(t)) !== null) {
      const priv = m[1].trim().toUpperCase();
      if (priv) out.push({ priv, cols: m[3] ? cut(m[3]) : [] });
    }
    return out;
  }
  const plain = (s, kind) => parts(s, kind).map((p) => p.priv);

  function show(kind, name) {
    const k = kk(kind, name);
    if (acl.has(k)) return acl.get(k);
    const m = new Map();
    const o = kind === 'FUNCTION' ? fnOwn.get(name.replace(/\(.*$/, '')) : own.get(k);
    if (o) m.set(o, new Set(OWNER_PRIV[kind]));
    const pub = PUBLIC_PRIV[kind];
    if (pub) m.set('PUBLIC', new Set(pub));
    acl.set(k, m);
    return m;
  }
  function put(kind, name, who, privs, add) {
    const m = show(kind, name);
    for (const w of who) {
      if (!m.has(w)) { if (!add) continue; m.set(w, new Set()); }
      const s = m.get(w);
      // Отзыв снимает и право передачи: так устроен сам PostgreSQL.
      for (const p of privs) { if (add) s.add(p); else { s.delete(p); s.delete(p + '*'); } }
      if (!add && s.size === 0) m.delete(w);
    }
  }

  function play(label, src) {
    for (const m of src.matchAll(/^[ \t]*(SET\s+ROLE\s+[a-z_]+|RESET\s+ROLE|CREATE\s+SCHEMA(?:\s+IF\s+NOT\s+EXISTS)?\s+[a-z_]+\s+AUTHORIZATION\s+[a-z_]+|CREATE\s+(?:TABLE|SEQUENCE)(?:\s+IF\s+NOT\s+EXISTS)?\s+[a-z_]+\.[a-z_]+|CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+[a-z_]+\.[a-z_]+|ALTER\s+(?:TABLE|SCHEMA|FUNCTION|SEQUENCE)\s+[^;]*?OWNER\s+TO\s+[a-z_]+)/gmi)) {
      const t = m[1].replace(/\s+/g, ' ');
      let g;
      if ((g = t.match(/^SET ROLE ([a-z_]+)$/i))) { role = g[1]; continue; }
      if (/^RESET ROLE$/i.test(t)) { role = null; continue; }
      if ((g = t.match(/^CREATE SCHEMA(?: IF NOT EXISTS)? ([a-z_]+) AUTHORIZATION ([a-z_]+)$/i))) {
        own.set(kk('SCHEMA', g[1]), g[2]); continue;
      }
      if ((g = t.match(/^CREATE (?:TABLE|SEQUENCE)(?: IF NOT EXISTS)? ([a-z_]+\.[a-z_]+)$/i))) {
        const kind = /TABLE/i.test(t) ? 'TABLE' : 'SEQUENCE';
        if (!own.get(kk(kind, g[1]))) own.set(kk(kind, g[1]), role);
        continue;
      }
      if ((g = t.match(/^CREATE (?:OR REPLACE )?FUNCTION ([a-z_]+\.[a-z_]+)$/i))) {
        const prev = fnOwn.get(g[1]);
        fnOwn.set(g[1], prev && prev !== role ? '?' : role);
        continue;
      }
      if ((g = t.match(/^ALTER (TABLE|SCHEMA|FUNCTION|SEQUENCE) (.+?) OWNER TO ([a-z_]+)$/i))) {
        const kind = g[1].toUpperCase();
        if (kind === 'FUNCTION') fnOwn.set(g[2].trim().replace(/\(.*$/, ''), g[3]);
        else own.set(kk(kind, g[2].trim()), g[3]);
      }
    }

    for (const st of src.matchAll(/^[ \t]*(GRANT|REVOKE|ALTER\s+DEFAULT\s+PRIVILEGES)\b[\s\S]*?;/gmi)) {
      const raw = st[0].replace(/--[^\n]*/g, ' ').replace(/\s+/g, ' ').trim();
      let m;
      m = raw.match(/^ALTER DEFAULT PRIVILEGES FOR ROLE ([a-z_]+) IN SCHEMA ([a-z_]+) (GRANT|REVOKE) (.+?) ON (TABLES|SEQUENCES|FUNCTIONS|ROUTINES) (?:TO|FROM) (.+?);?$/i);
      if (m) {
        const typ = { TABLES: 'r', SEQUENCES: 'S', FUNCTIONS: 'f', ROUTINES: 'f' }[m[5].toUpperCase()];
        const k = m[1] + SEP + m[2] + SEP + typ;
        if (!def.has(k)) def.set(k, new Map());
        const map = def.get(k);
        const privs = plain(m[4], { r: 'TABLE', S: 'SEQUENCE', f: 'FUNCTION' }[typ]);
        for (const w of cut(m[6].replace(/\s+WITH\s+GRANT\s+OPTION$/i, ''))) {
          if (/^GRANT$/i.test(m[3])) {
            if (!map.has(w)) map.set(w, new Set());
            for (const p of privs) map.get(w).add(p);
          } else if (map.has(w)) {
            for (const p of privs) map.get(w).delete(p);
            if (map.get(w).size === 0) map.delete(w);
          }
        }
        continue;
      }
      const add = /^GRANT\b/i.test(raw);
      if (/^GRANT [a-z_]+ TO /i.test(raw) && !/ ON /i.test(raw)) continue;
      if (/^REVOKE [a-z_]+ FROM /i.test(raw) && !/ ON /i.test(raw)) continue;
      if (/^REVOKE (ADMIN|INHERIT|SET) OPTION FOR /i.test(raw)) continue;

      m = raw.match(new RegExp('^(?:GRANT|REVOKE) (.+?) ON (?:(SCHEMA|DATABASE|TABLE|SEQUENCE|FUNCTION|PROCEDURE|ROUTINE|ALL TABLES IN SCHEMA|ALL SEQUENCES IN SCHEMA|ALL FUNCTIONS IN SCHEMA|ALL ROUTINES IN SCHEMA) )?(.+?)'
        + (add ? ' TO ' : ' FROM ') + '(.+?);?$', 'i'));
      if (!m) { aclProblems.push('команда прав не разобрана (' + label + '): ' + raw.slice(0, 110)); continue; }

      const what = (m[2] || 'TABLE').toUpperCase();
      const objs = cut(m[3]);
      const who = cut(m[4].replace(/\s+WITH\s+GRANT\s+OPTION$/i, '').replace(/\s+(RESTRICT|CASCADE)$/i, ''));
      // Право передавать право дальше записывается звёздочкой — так же,
      // как его читает из каталога проверка файла 05.
      const star = /\s+WITH\s+GRANT\s+OPTION\s*;?\s*$/i.test(m[4]) ? '*' : '';
      const starred = (t, k) => plain(t, k).map((p) => p + star);
      if (what === 'SCHEMA' || what === 'DATABASE' || what === 'SEQUENCE') {
        for (const o of objs) put(what, o, who, starred(m[1], what), add);
      } else if (what === 'TABLE') {
        for (const o of objs) for (const { priv, cols } of parts(m[1], 'TABLE')) {
          if (cols.length === 0) { put('TABLE', o, who, [priv + star], add); continue; }
          show('TABLE', o);
          for (const c of cols) put('COLUMN', o + '.' + c, who, [priv + star], add);
        }
      } else if (/^(FUNCTION|PROCEDURE|ROUTINE)$/.test(what)) {
        put('FUNCTION', m[3].trim().replace(/\s+/g, ' '), who, starred(m[1], 'FUNCTION'), add);
      } else {
        const kind = /TABLES/.test(what) ? 'TABLE' : (/SEQUENCES/.test(what) ? 'SEQUENCE' : 'FUNCTION');
        const privs = starred(m[1], kind);
        for (const k of [...own.keys()].filter((x) => x.startsWith(kind + SEP + objs[0] + '.'))) {
          put(kind, k.split(SEP)[1], who, privs, add);
        }
      }
    }
  }

  // Двух владельцев канон командой не объявляет: схема `public` с
  // PostgreSQL 15 принадлежит `pg_database_owner`, а владелец базы стоит
  // в строке `CREATE DATABASE ... OWNER ...`, собранной на ходу.
  own.set(kk('SCHEMA', 'public'), 'pg_database_owner');
  const db = sql.match(/CREATE DATABASE ([a-z_]+) OWNER ([a-z_]+)/i);
  if (db) own.set(kk('DATABASE', db[1]), db[2]);
  else aclProblems.push('в каноне нет строки CREATE DATABASE ... OWNER ...');

  let after01 = null;
  for (const f of ['00_cluster_bootstrap.sql', '01_database_migration.sql', '04_backup_window.sql']) {
    const src = fileSql.get(f);
    if (!src) { aclProblems.push('в каноне нет файла ' + f); continue; }
    if (f === '04_backup_window.sql') after01 = snapshot(false);
    play(f, src);
  }

  // R31 (M-H115-R15-01). Последнее поле строки — кто выдал право. Модель
  // PostgreSQL 16: выдачу суперпользователем и членом роли-владельца
  // сервер записывает от имени владельца, смена владельца переписывает
  // выдавшего на нового владельца, а иной выдавший возможен только
  // через право передавать право — его канон запрещает. Поэтому
  // выдавший всегда равен владельцу объекта в конце пакета: у столбца —
  // владельцу таблицы, у записи прав по умолчанию — роли FOR ROLE.
  //
  // R32 (M-H116-R16-02). Модель снимается дважды: перед файлом 04 и в
  // конце пакета. Самопроверка файла 01 идёт до файла 04, и функций окна
  // резервного копирования в этот момент ещё нет; файл 05 идёт после и
  // видит их. Разница между снимками — строки, которые добавляет файл 04.
  function grantorOf(kind, name) {
    if (kind === 'FUNCTION') return fnOwn.get(name.replace(/\(.*$/, ''));
    if (kind === 'COLUMN') return own.get(kk('TABLE', name.replace(/\.[^.]+$/, '')));
    return own.get(kk(kind, name));
  }
  function snapshot(report) {
    const rows = [];
    for (const [k, m] of acl) {
      const [kind, name] = k.split(SEP);
      const g = grantorOf(kind, name);
      if (report && (!g || g === '?')) aclProblems.push('не выведен владелец, который выдаёт право: ' + kind + '|' + name);
      for (const [w, st] of m) for (const p of [...st].sort()) rows.push(kind + '|' + name + '|' + w + '|' + p + '|' + (g || '?'));
    }
    for (const [k, m] of def) {
      const [o, s0, t0] = k.split(SEP);
      for (const [w, st] of m) for (const p of [...st].sort()) rows.push('DEFAULT|' + o + '|' + s0 + '|' + t0 + '|' + w + '|' + p + '|' + o);
    }
    return rows.sort();
  }
  const term = snapshot(true);
  const countOf = (a) => a.reduce((mm, r) => mm.set(r, (mm.get(r) || 0) + 1), new Map());
  // Строки из a сверх тех, что есть в b, с учётом повторов.
  const beyond = (a, b) => {
    const cb = countOf(b);
    const out = [];
    for (const r of a) {
      const n = cb.get(r) || 0;
      if (n > 0) cb.set(r, n - 1); else out.push(r);
    }
    return out;
  };
  termAcl01 = after01 || term;
  termAcl04 = beyond(term, termAcl01).sort();
  // Файл 04 не должен снимать права, выданные до него: иначе «все или ни
  // одной» в файле 01 не описывает повторный прогон.
  for (const r of beyond(termAcl01, term).slice(0, 3)) aclProblems.push('файл 04 снимает право, выданное до него: ' + r);
  // И должен добавлять права только функциям окна: остальное файл 01 в
  // повторном прогоне уже видит выданным.
  for (const r of termAcl04) {
    if (!/^FUNCTION\|bem_control\.backup_window_[a-z_]+\(/.test(r)) {
      aclProblems.push('файл 04 выдаёт право не на функцию окна: ' + r);
    }
  }
  return term;
})();

// --- Файл 05 сверяется с каноном ----------------------------------------
// Десять списков терминальной проверки выведены из канона машинно, но в
// документе они лежат как текст файла 05. Без этой сверки любую строку
// в них можно было бы тихо поправить, и файл 05 принимал бы ослабленное
// состояние за верное. Сверяется каждый список целиком, в обе стороны.
const term05 = fileSql.get('05_final_state_check.sql') || '';
const arrayOf = (name) => {
  const m = term05.match(new RegExp('\\n\\s*' + name + '\\s+constant text\\[\\]\\s*:=\\s*ARRAY\\[([\\s\\S]*?)\\];'));
  if (!m) return null;
  return m[1].split('\n').map((x) => x.trim()).filter(Boolean)
    .map((x) => x.replace(/,$/, '').trim())
    .filter((x) => x.startsWith("'"))
    .map((x) => x.slice(1, x.lastIndexOf("'")).replace(/''/g, "'"));
};
const terminalProblems = [];
if (!term05) terminalProblems.push('в каноне нет файла 05_final_state_check.sql');
else {
  const pairs = [['v_roles', termRoles], ['v_members', termMembers],
                 ['v_secrets', termSecrets], ['v_login', termLogin],
                 ['v_rls', termRls], ['v_policy', termPolicy],
                 ['v_trigger', termTrigger],
                 ['v_trigger_legacy', termTriggerLegacy],
                 ['v_trigger_def', termTriggerDef],
                 ['v_trigger_def_legacy', termTriggerDefLegacy], ['v_func', termFunc],
                 ['v_read', [...termRead].sort()], ['v_exec', [...termExec].sort()],
                 ['v_acl', termAcl]];
  for (const [name, want] of pairs) {
    const got = arrayOf(name);
    if (got === null) { terminalProblems.push('в файле 05 нет списка ' + name); continue; }
    // R31 (M-H115-R15-01): списки сравниваются с учётом повторов. Через
    // множество строка, записанная в договор дважды, была не видна, а
    // файл 05 с R31 сравнивает права тоже с учётом повторов.
    const count = (a) => a.reduce((mm, r) => mm.set(r, (mm.get(r) || 0) + 1), new Map());
    const g = count(got);
    const w = count(want);
    for (const [r, n] of w) {
      const k = g.get(r) || 0;
      if (k === 0) terminalProblems.push(name + ': не хватает ' + r);
      else if (k < n) terminalProblems.push(name + ': записано ' + k + ' раз, выведено ' + n + ': ' + r);
    }
    for (const [r, n] of g) {
      const k = w.get(r) || 0;
      if (k === 0) terminalProblems.push(name + ': лишнее ' + r);
      else if (n > k) terminalProblems.push(name + ': повтор строки, записано ' + n + ' раз, выведено ' + k + ': ' + r);
    }
  }
}

// --- R32. Списки прав в файле 01 и повторы объявлений --------------------
// Замечание M-H116-R16-02. Самопроверка файла 01 сверяла права тремя
// списками без выдавшего (второй v_read, v_seq, v_defacl) и без числа
// повторов, а файл 05 с R31 — точным списком. Теперь у файла 01 два
// списка — v_acl (состояние после этого файла) и v_acl_04 (строки, которые
// добавит файл 04), — выведенные из той же модели, что список файла 05, и
// сверяемые с учётом повторов: через множество строка, записанная в
// договор дважды, была бы не видна.
{
  const f01 = fileSql.get('01_database_migration.sql') || '';
  const count = (a) => a.reduce((mm, r) => mm.set(r, (mm.get(r) || 0) + 1), new Map());
  for (const [name, want] of [['v_acl', termAcl01], ['v_acl_04', termAcl04]]) {
    const got = arrayRows(f01, name);
    if (got === null) { selfcheckProblems.push(name + ': массива в файле 01 нет'); continue; }
    const g = count(got);
    const w = count(want);
    for (const [r, n] of w) {
      const k = g.get(r) || 0;
      if (k === 0) selfcheckProblems.push(name + ': не хватает ' + r);
      else if (k < n) selfcheckProblems.push(name + ': записано ' + k + ' раз, выведено ' + n + ': ' + r);
    }
    for (const [r, n] of g) {
      const k = w.get(r) || 0;
      if (k === 0) selfcheckProblems.push(name + ': лишнее ' + r);
      else if (n > k) selfcheckProblems.push(name + ': повтор строки, записано ' + n + ' раз, выведено ' + k + ': ' + r);
    }
  }
}

// Добавка (11). PostgreSQL 16 (pl_gram.y, decl_varname) отвечает
// «duplicate declaration» на второе объявление того же имени в одной
// секции DECLARE. Файл 01 объявлял v_read дважды: сверщик брал первое
// объявление и молчал, а база не приняла бы файл вовсе. Теперь повтор имени
// в секции DECLARE любого файла канона — расхождение.
const declDupProblems = [];
{
  // Имя — истинный идентификатор PostgreSQL 16, извлечённый из первого слова
  // каждого объявления. Строковые постоянные и пояснения пропускаются: в них
  // бывают и «;», и «--». R33, замечание M-H117-R17-02 (=B-02): имя в двойных
  // кавычках (например "dup_b17") тоже разбирается — как отдельный вид
  // литерала, с `""` как экранированной кавычкой внутри, — и берётся ДОСЛОВНО,
  // с точным регистром; без кавычек имя сворачивается в нижний регистр (только
  // ASCII), поэтому "dup_b17" (в кавычках, строчными) и dup_b17 (без кавычек)
  // считаются одним и тем же именем.
  const declNames = (sec) => {
    const names = [];
    let cur = '';
    let i = 0;
    let inStr = false;
    while (i < sec.length) {
      const c = sec[i];
      if (inStr) {
        cur += c;
        if (c === "'" && sec[i + 1] === "'") { cur += "'"; i += 2; continue; }
        if (c === "'") inStr = false;
        i += 1;
        continue;
      }
      if (c === "'") { inStr = true; cur += c; i += 1; continue; }
      // R33 (B-02): имя в двойных кавычках — второй вид литерала, свой знак
      // экранирования (удвоенная кавычка), и он не должен путаться с (--) и (').
      if (c === '"') {
        cur += c;
        i += 1;
        while (i < sec.length) {
          if (sec[i] === '"' && sec[i + 1] === '"') { cur += '""'; i += 2; continue; }
          cur += sec[i];
          if (sec[i] === '"') { i += 1; break; }
          i += 1;
        }
        continue;
      }
      if (c === '-' && sec[i + 1] === '-') {
        while (i < sec.length && sec[i] !== '\n') i += 1;
        continue;
      }
      if (c === ';') { names.push(cur.trim()); cur = ''; i += 1; continue; }
      cur += c;
      i += 1;
    }
    if (cur.trim()) names.push(cur.trim());
    // Кавычка в начале — имя берётся дословно, `""` внутри снимается до одной
    // кавычки. Иначе — обычное правило: первая буква/подчёркивание и далее ещё
    // цифры, `$` и не-ASCII символы, свёрнутые в нижний регистр (только ASCII).
    return names.map((decl) => {
      if (decl[0] === '"') {
        const m = decl.match(/^"((?:[^"]|"")*)"/);
        return m ? m[1].replace(/""/g, '"') : null;
      }
      const m = decl.match(/^([A-Za-z_][A-Za-z0-9_$\u0080-\uFFFF]*)/);
      return m ? m[1].replace(/[A-Z]/g, (ch) => ch.toLowerCase()) : null;
    }).filter((x) => x !== null && x !== '');
  };
  for (const [fname, src] of fileSql) {
    const lines = src.split('\n');
    for (let n = 0; n < lines.length; n += 1) {
      if (lines[n].trim() !== 'DECLARE') continue;
      const indent = lines[n].match(/^\s*/)[0];
      let m = n + 1;
      while (m < lines.length && lines[m] !== indent + 'BEGIN') m += 1;
      if (m >= lines.length) continue;
      const seen = new Map();
      for (const x of declNames(lines.slice(n + 1, m).join('\n'))) seen.set(x, (seen.get(x) || 0) + 1);
      for (const [x, k] of seen) {
        if (k > 1) {
          declDupProblems.push('файл ' + fname + ': имя ' + x + ' объявлено ' + k
            + ' раза в одной секции DECLARE (строка ' + (n + 1) + ' файла)');
        }
      }
    }
  }
}

// --- R32. Текст против канона: запись доказательства ---------------------
// (РАУНД-R32-ТЕКСТ: код). Добавка автора, 26.09. Разделы 5.2 и 5.3 H1.16
// называли запись доказательства прямой — «да, INSERT на
// bem_core.evidence», — тогда как раздел 4.3, команда REVOKE INSERT ON
// bem_core.evidence в файле 01 и тест K-R8-08 говорят обратное: право
// отозвано, доказательство пишет только record_evidence. Ни один из
// аудитов P1–P5B противоречия не заметил: сверщики читали код, а не то,
// что о нём сказано словами. Теперь, пока канон отзывает право, раздел 5
// не вправе называть запись прямой.
const proseProblems = [];
{
  const revoked = /REVOKE\s+INSERT\s+ON\s+bem_core\.evidence\s+FROM\s+bem_kernel_rw/.test(sql);
  const a5 = doc.indexOf('\n# 5. ');
  const b5 = a5 < 0 ? -1 : doc.indexOf('\n# 6. ', a5);
  const sec5 = a5 < 0 || b5 < 0 ? '' : doc.slice(a5, b5);
  if (!sec5) proseProblems.push('раздела 5 нет в документе');
  if (!revoked) {
    proseProblems.push('в каноне нет REVOKE INSERT ON bem_core.evidence FROM bem_kernel_rw: текст раздела 5 сверить не с чем');
  } else if (sec5) {
    const row = sec5.split('\n').find((l) => l.startsWith('| Записать доказательство '));
    if (!row) {
      proseProblems.push('в разделе 5.2 нет строки «Записать доказательство»');
    } else {
      const cells = row.split('|').map((c) => c.trim());
      if (!/^нет(?![А-Яа-яЁё])/.test(cells[2] || '')) {
        proseProblems.push('раздел 5.2: право на запись доказательства названо выданным, а канон его отзывает: ' + (cells[2] || ''));
      }
      if (!(cells[3] || '').includes('bem_control.record_evidence')) {
        proseProblems.push('раздел 5.2: единственный путь записи доказательства не назван: bem_control.record_evidence');
      }
    }
    const said = [
      [new RegExp('оставлен[аоы]?\\s+прямой'), 'запись доказательства «оставлена прямой»'],
      [new RegExp('да,\\s*' + TICK + 'INSERT' + TICK + '\\s+на\\s+' + TICK + 'bem_core\\.evidence' + TICK),
       '«да, INSERT на bem_core.evidence»'],
    ];
    for (const [re, what] of said) {
      if (re.test(sec5)) proseProblems.push('раздел 5: ' + what + ', а канон отзывает право INSERT');
    }
  }
}

// --- R32/R33. Последний абзац и паспорт: редакция берётся СНАРУЖИ -----------
// (РАУНД-R32-РЕДАКЦИЯ: код, изменено РАУНД-R33-РЕДАКЦИЯ). Замечание L-H116-R16-02
// (R32) сверяло последний абзац с версией ИЗ ПАСПОРТА ТОГО ЖЕ ДОКУМЕНТА. Источник
// самоссылочный: совместная подделка, понижающая паспорт и абзац на одно и то же
// число сразу, согласна сама с собой, и отказа не было (замечание L-H117-R17-02
// = B-04, найдено запуском B-NI-4 аудитора). Теперь ожидаемая редакция приходит
// только СНАРУЖИ: ключ --expect-edition (высший приоритет) или имя входного
// файла (H1_17.md, H1_21.md и т. п. — тот файл, что назвали в командной строке,
// а не текст внутри него). Паспорт документа сверяется с этим значением как
// рядовая величина, а не как образец для абзаца.
const editionProblems = [];
{
  const fromFlag = argAfter('--expect-edition');
  const nameMatch = String(file).match(/H1_(\d+)(?=[._]|$)/);
  const fromName = nameMatch ? 'H1.' + nameMatch[1] : null;
  const expected = fromFlag || fromName;
  if (!expected) {
    editionProblems.push('нет независимого источника ожидаемой редакции: ни --expect-edition, ни имя файла её не задают');
  } else {
    const v = /ВЕРСИЯ:\s*\nv(\d+)\.(\d+)/.exec(doc);
    const at = doc.lastIndexOf('**Последнее и главное.**');
    if (!v) {
      editionProblems.push('в паспорте документа нет строки версии');
    } else {
      const passport = 'H' + v[1] + '.' + v[2];
      if (passport !== expected) {
        editionProblems.push('паспорт называет редакцию ' + passport + ', а ожидается ' + expected);
      }
      if (at < 0) {
        editionProblems.push('в конце документа нет абзаца «Последнее и главное»');
      } else {
        const named = doc.slice(at).match(/H\d+\.\d+/g) || [];
        if (!named.includes(expected)) editionProblems.push('последний абзац не называет ожидаемую редакцию ' + expected);
        for (const n of new Set(named)) {
          if (n !== expected) editionProblems.push('последний абзац называет чужую редакцию ' + n + ', а ожидается ' + expected);
        }
      }
    }
  }
}

// --- Постоянное условие ветвления ---------------------------------------
// Подделка I-H114-02 оставляет проверку на месте и меняет только её
// условие на постоянное: `IF false THEN RAISE EXCEPTION ...`. Ни один
// договор при этом не расходится, а отказ больше никогда не случится.
//
// Слова-связки постоянного условия перечислены закрытым списком. Если
// после их удаления в условии не осталось ни одного имени, условие ни
// от чего не зависит — это расхождение.
const constGuard = [];
{
  const WORDS = new Set(['true', 'false', 'null', 'not', 'and', 'or',
                         'is', 'distinct', 'from', 'unknown']);
  for (const m of all('\\b(ELSIF|IF)\\s+([^;]{1,200}?)\\s+THEN\\b', sql)) {
    const cond = m[2].replace(/[()]/g, ' ').replace(/\s+/g, ' ').trim();
    const names = (cond.match(/[A-Za-z_][A-Za-z_0-9.]*/g) || [])
      .filter((w) => !WORDS.has(w.toLowerCase()));
    if (names.length === 0) {
      constGuard.push('постоянное условие ветвления: ' + m[1] + ' ' + cond + ' THEN');
    }
  }
}

// --- Блочные пояснения в каноне запрещены -------------------------------
// Пояснение вида /* ... */ может закрывать команду целиком или только её
// начало, и тогда разборщик и сервер читают текст по-разному. Канон
// такими пояснениями не пользуется ни разу, поэтому правило простое:
// их там нет вовсе. Запрет дешевле, чем разбор всех случаев.
const blockCommentProblems = [];
for (const m of all('/\\*', sql)) {
  blockCommentProblems.push('блочное пояснение в каноне, знак ' + m.index);
}

// --- Кто записан выдавшим членство --------------------------------------
// Замечание M-H113-R13-03. PostgreSQL 16 пишет выдавшим начального
// суперпользователя кластера — роль с постоянным номером 10, — а не того,
// кто выполнил команду. Сверка с current_user отказывала на верном
// состоянии. Договор один, и он проверяется по тексту канона.
const grantorProblems = [];
{
  const hits = [...all('\\bm\\.grantor\\s*(<>|=|!=)\\s*([^\\s);]+)', sql)];
  if (hits.length < 2) {
    grantorProblems.push('сравнений pg_auth_members.grantor в каноне меньше двух: ' + hits.length);
  }
  for (const h of hits) {
    if (h[2] !== '10') {
      grantorProblems.push('выдавший членство сверяется не с начальным суперпользователем: ' + h[1] + ' ' + h[2]);
    }
  }
}

// --- Форма обёртки ------------------------------------------------------
// Обёртка обязана сверить сумму описи, сверить сумму каждого файла и
// подать psql уже прочитанные байты. Если она передаст имя файла, между
// сверкой суммы и запуском появится окно подмены — и сверка станет
// украшением.
const wrapperShape = [];
if (!wrapperText) wrapperShape.push('листинга обёртки run_migration.mjs в документе нет');
else {
  const W = wrapperText;
  const count = (t) => W.split(t).length - 1;
  const at = (t) => W.indexOf(t);
  const need = (t, why) => { if (!W.includes(t)) wrapperShape.push(why + ': нет ' + t); };
  const once = (t, why) => {
    const n = count(t);
    if (n !== 1) wrapperShape.push(why + ': вхождений ' + n + ' вместо одного: ' + t);
  };

  // Прежние пять проверок наличия остаются: они про другое — про то, что
  // обёртка подаёт серверу ровно те байты, которые сверила.
  for (const [mark, why] of [['if (got !== MANIFEST_SHA256) {', 'обёртка не сверяет сумму самой описи'],
                             ['const got = sumOf(buf);', 'обёртка не считает сумму прочитанных байтов'],
                             ['if (got !== want) {', 'обёртка не сверяет сумму файла с описью'],
                             ["'-f', '-'],", 'обёртка не подаёт psql текст на стандартный вход'],
                             ['{ input: text,', 'обёртка не передаёт psql уже прочитанный текст']]) {
    need(mark, why);
  }

  // 1. Достижимость. Вызов терминальной проверки обязан стоять ровно в
  //    объявленной форме: своей строкой внутри try, и следующей строкой —
  //    подъём признака. Условная ветвь, ранний возврат или перестановка
  //    эту форму ломают, и подделка I-H114-03 ломает её первой.
  const BARRIER = 'try {\n  runAs(ADMIN_USER, finalText);\n'
                + '  finalReceipt.terminal_check_passed = true;\n} catch (e) {';
  if (!W.includes(BARRIER)) {
    wrapperShape.push('терминальная проверка стоит не в объявленной форме '
      + '(try, вызов, подъём признака, catch) — вызов мог стать условным или переставленным');
  }
  once('runAs(ADMIN_USER, finalText);', 'вызов терминальной проверки');

  // 2. Использование итога. Признак поднимается ровно одной строкой, и
  //    эта строка — внутри объявленной формы. Присвоение true где-либо
  //    ещё означает успех без проверки.
  once('finalReceipt.terminal_check_passed = true;', 'подъём признака терминальной проверки');
  once('terminal_check_passed: false,', 'начальное значение признака');
  const truthy = (W.match(/terminal_check_passed\s*=\s*true/g) || []).length;
  if (truthy !== 1) {
    wrapperShape.push('признак терминальной проверки ставится в true ' + truthy + ' раз вместо одного');
  }

  // 3. Порядок. Миграция, закрытие окна, окно копирования — всё до
  //    терминальной проверки; успех — после неё.
  const barrierAt = at('runAs(ADMIN_USER, finalText);');
  const order = [
    ["runAs('schema_migrator', texts.join('\\n'));", 'миграция мигратором'],
    ['if (!receipt.receipt_written) {', 'проверка записи квитанции окна'],
    ['runAs(ADMIN_USER, backupText);', 'файл окна копирования'],
  ];
  for (const [mark, why] of order) {
    const k = at(mark);
    if (k < 0) { wrapperShape.push('в обёртке нет шага «' + why + '»: ' + mark); continue; }
    if (k > barrierAt && barrierAt >= 0) {
      wrapperShape.push('шаг «' + why + '» стоит после терминальной проверки, а обязан до неё');
    }
  }

  // 4. Успех невозможен до проверки. Выход с нулём один, он последний, и
  //    перед ним стоит отдельная проверка признака.
  once('process.exit(0);', 'выход с успехом');
  const zeroAt = at('process.exit(0);');
  const guardAt = at('if (finalReceipt.terminal_check_passed !== true) {');
  if (guardAt < 0) {
    wrapperShape.push('перед выходом с успехом нет отдельной проверки признака терминальной проверки');
  } else if (!(barrierAt < guardAt && guardAt < zeroAt)) {
    wrapperShape.push('проверка признака стоит не между терминальной проверкой и выходом с успехом');
  }

  // 5. Квитанция обязательна на успешном пути (замечание M-H114-R14-05).
  need('finalSha = writeFinal();', 'успешный путь не пишет финальную квитанцию сам');
  need('process.exit(7);', 'осечка записи финальной квитанции не даёт ненулевого кода');
  need('renameSync(tmp, RECEIPT_FILE);', 'квитанция пишется не переименованием временного файла');
  need('fsyncSync(fd);', 'квитанция не сбрасывается на диск до переименования');
  need("const back = readFileSync(RECEIPT_FILE, 'utf8');\n  if (back !== text) {",
       'квитанция не перечитывается с диска перед сверкой');
  need('for (const f of RECEIPT_FIELDS) {', 'обязательные поля готовой квитанции не проверяются');
  need('if (sha !== sumOf(readFileSync(RECEIPT_FILE))) {',
       'сумма готовой квитанции не сверяется с тем, что лежит на диске');
}

// --- R31. Три уровня договора триггеров ---------------------------------
// Замечание C-H115-R15-01. Каждый уровень сверяется здесь с тем, что
// выводится из самой команды CREATE:
//   1. немедленная сверка файла 01 — столбцы want_when и want_def строк
//      списка (сверены выше, в triggersOf) и две постоянные
//      constraint-триггера v_want_when и v_want_def;
//   2. самопроверка файла 01, пункт 15 — два литерала: отпечаток из
//      одиннадцати полей и список определений. Порядок строк в литерале
//      тот же, что даёт сервер при ORDER BY ... COLLATE "C";
//   3. файл 05 — списки v_trigger_def и v_trigger_def_legacy (сверены в
//      общем цикле терминальных списков).
// Прежде литерал пункта 15 не сверялся ни с чем: его можно было
// поправить вместе с каноном, и самопроверка приняла бы что угодно.
const triggerDefProblems = [];
{
  const f01 = fileSql.get('01_database_migration.sql') || '';
  const lits = (re, label) => {
    const m = f01.match(re);
    if (!m) { triggerDefProblems.push('в самопроверке файла 01 нет сверки ' + label); return null; }
    return [...m[1].matchAll(/(?<![A-Za-z])'([^']*)'/g)].map((x) => x[1]);
  };
  const same = (label, got, want) => {
    if (got === null) return;
    for (const r of want) if (!got.includes(r)) triggerDefProblems.push(label + ': не хватает ' + r);
    for (const r of got) if (!want.includes(r)) triggerDefProblems.push(label + ': лишнее ' + r);
    if (got.length === want.length && got.every((r) => want.includes(r))
        && got.join('\n') !== want.join('\n')) {
      triggerDefProblems.push(label + ': строки стоят не в порядке сортировки COLLATE "C"');
    }
  };
  same('файл 01, пункт 15, отпечатки', lits(/IF v_txt <>\s*([\s\S]*?)\n\s*THEN/, 'отпечатков триггеров'), termTrigger);
  same('файл 01, пункт 15, определения', lits(/IF v_tdef <>\s*([\s\S]*?)\n\s*THEN/, 'определений триггеров'), termTriggerDef);

  const ww = f01.match(/\n\s*v_want_when\s*:= '([^']*)';/);
  const wd = f01.match(/\n\s*v_want_def\s*:= '([^']*)';/);
  const con = trg01.found.filter((p) => p.isConstraint);
  if (!ww || !wd) triggerDefProblems.push('в немедленной сверке файла 01 нет постоянных v_want_when и v_want_def');
  else if (con.length !== 1) triggerDefProblems.push('constraint-триггеров в файле 01 ' + con.length + ', а сверка рассчитана на один');
  else {
    if (ww[1] !== con[0].when) triggerDefProblems.push('файл 01: по команде условие WHEN "' + con[0].when + '", в v_want_when "' + ww[1] + '"');
    if (wd[1] !== con[0].def) triggerDefProblems.push('файл 01: по команде определение "' + con[0].def + '", в v_want_def "' + wd[1] + '"');
  }
  // Сами сравнения. Без них объявленные ожидания — просто текст.
  for (const [t, why] of [
    ['WHEN v_when <> r.want_when', 'немедленная сверка не сравнивает условие WHEN'],
    ["                 WHEN v_args <> ''\n", 'немедленная сверка не сравнивает байты аргументов'],
    ['WHEN v_def <> r.want_def', 'немедленная сверка не сравнивает определение целиком'],
    ['WHEN v_when <> v_want_when', 'сверка constraint-триггера не сравнивает условие WHEN'],
    ["             WHEN v_args <> ''         THEN", 'сверка constraint-триггера не сравнивает байты аргументов'],
    ['WHEN v_def <> v_want_def', 'сверка constraint-триггера не сравнивает определение целиком'],
  ]) if (!f01.includes(t)) triggerDefProblems.push('файл 01: ' + why + ': нет ' + t);
  if (!term05.includes('FROM unnest(CASE WHEN v_ok THEN v_trigger_def')) {
    triggerDefProblems.push('файл 05 не сравнивает определения триггеров со списком v_trigger_def');
  }
  for (const [name, src] of [['01', f01], ['05', term05]]) {
    const n = (src.match(/pg_get_triggerdef\(tg\.oid, true\)/g) || []).length;
    const k = (src.match(/set_config\('search_path', 'pg_catalog, pg_temp', true\)/g) || []).length;
    if (n === 0) triggerDefProblems.push('файл ' + name + ' не читает определение триггера у сервера');
    if (k === 0) triggerDefProblems.push('файл ' + name + ' читает определение без закреплённого пути поиска');
  }
  // Режим срабатывания меняется и изнутри блока. Словарь форм смотрит
  // только команды верхнего уровня: тело блока DO он пропускает, а
  // модель триггера строится по CREATE. ALTER TABLE ... DISABLE TRIGGER
  // внутри блока пересоздания оставлял триггер на месте, с верным
  // определением, но выключенным (подделка T23 раунда R31). Поэтому
  // здесь просматривается весь канон — тела блоков и строковые
  // постоянные тоже, пояснения нет. session_replication_role = replica
  // выключает сразу все обычные триггеры сеанса.
  for (const [name, src] of fileSql) {
    const re = /\b(DISABLE\s+TRIGGER|ENABLE\s+(?:REPLICA|ALWAYS)\s+TRIGGER|session_replication_role)\b/gi;
    for (const m of stripComments(src).matchAll(re)) {
      triggerDefProblems.push('файл ' + name + ': меняется режим срабатывания триггеров: '
        + m[1].replace(/\s+/g, ' '));
    }
  }
}

// R33 (замечание L-H117-R17-01 = L-C-02, решение D-05). Раздел 15.28
// H1.17 назвал приём «не реализован»: точное сравнение tgqual::text
// настоящего триггера с tgqual::text эталонного триггера той же формы —
// вместо сравнения со строкой-константой v_want_when/v_want_def,
// набранной в том же файле (не независимый источник). Здесь смотрится
// текст SQL, а не поведение сервера: живого PostgreSQL 16 нет, само
// сравнение остаётся DESIGNED_NOT_EXECUTED. Проверяется, что приём в
// документе есть целиком, а не только по имени: эталонная таблица той
// же формы, ДВА независимых чтения каталога pg_trigger (настоящей
// таблицы и временной — не одно и то же чтение дважды), сравнение
// IS DISTINCT FROM и отказ RAISE EXCEPTION. Удаление всего фрагмента и
// ослабление сравнения (более мягкое условие или отказ, замененный
// наблюдением) — расхождение.
{
  const f01 = fileSql.get('01_database_migration.sql') || '';
  if (!f01.includes('subject_requires_author_ref')) {
    triggerDefProblems.push('файл 01: нет эталонного триггера subject_requires_author_ref для сравнения tgqual::text (решение D-05)');
  } else {
    const flat = f01.replace(/\s+/g, ' ');
    if (!flat.includes("CREATE TEMP TABLE subject_reference_shape (LIKE bem_core.subject)")) {
      triggerDefProblems.push('файл 01: эталонная таблица subject_reference_shape не той же формы (нет LIKE bem_core.subject)');
    }
    const readsReal = flat.includes("tgname = 'subject_requires_author' AND tg.tgrelid = 'bem_core.subject'::regclass");
    const readsRef = flat.includes("tgname = 'subject_requires_author_ref' AND tg.tgrelid = 'pg_temp.subject_reference_shape'::regclass");
    if (!readsReal || !readsRef) {
      triggerDefProblems.push('файл 01: сравнение tgqual::text не читает настоящий и эталонный триггер двумя разными чтениями каталога');
    }
    if ((flat.match(/tgqual::text/g) || []).length < 2) {
      triggerDefProblems.push('файл 01: сравнение не берёт tgqual::text отдельно у настоящего и у эталонного триггера');
    }
    if (!flat.includes('v_tgqual_real IS DISTINCT FROM v_tgqual_ref')) {
      triggerDefProblems.push('файл 01: сравнение tgqual::text ослаблено — нет IS DISTINCT FROM между настоящим и эталонным значением');
    }
    if (!flat.includes("RAISE EXCEPTION 'TRIGGER_TGQUAL_MISMATCH")) {
      triggerDefProblems.push('файл 01: расхождение tgqual::text не приводит к отказу RAISE EXCEPTION');
    }
  }
}

// --- R31. Форма сверки прав ----------------------------------------------
// Замечание M-H115-R15-01. Файл 05 обязан читать выдавшего в каждом из
// шести списков прав каталога и сравнивать с договором с учётом повторов:
// EXCEPT сводит одинаковые строки в одну, и повтор в договоре или в
// каталоге проходит молча. Файл 01 обязан требовать, чтобы каждое право
// выдал владелец.
const aclGrantorProblems = [];
{
  const f01 = fileSql.get('01_database_migration.sql') || '';
  const a = term05.indexOf('-- 10. Права доступа целиком');
  const b = term05.indexOf('-- 11. ', a);
  const step = a < 0 || b < 0 ? '' : term05.slice(a, b);
  if (!step) aclGrantorProblems.push('в файле 05 нет шага 10 — сверки прав целиком');
  const code = step.replace(/--[^\n]*/g, '');
  const lists = (code.match(/aclexplode\(/g) || []).length;
  const joins = (code.match(/LEFT JOIN pg_roles gr ON gr\.oid = a\.grantor/g) || []).length;
  const cells = (code.match(/\|\| '\|' \|\| coalesce\(gr\.rolname, a\.grantor::text\)/g) || []).length;
  if (lists !== 6) aclGrantorProblems.push('файл 05: списков прав каталога ' + lists + ' вместо шести');
  if (joins !== lists || cells !== lists) {
    aclGrantorProblems.push('файл 05: выдавший читается не во всех списках прав: списков ' + lists
      + ', соединений с выдавшим ' + joins + ', полей выдавшего ' + cells);
  }
  if (/\bEXCEPT\b/i.test(code)) aclGrantorProblems.push('файл 05: права сравниваются через EXCEPT, повтор строки не виден');
  for (const t of ['FROM unnest(v_acl_got) AS r GROUP BY r', 'FROM unnest(v_acl) AS r GROUP BY r',
                   'WHERE x.n_got > x.n_want', 'WHERE x.n_want > x.n_got']) {
    if (!code.includes(t)) aclGrantorProblems.push('файл 05: права сравниваются не с учётом повторов: нет ' + t);
  }
  if (!f01.includes('WHERE i.grantor <> i.owner OR i.is_grantable')) {
    aclGrantorProblems.push('в самопроверке файла 01 нет правила «каждое право выдаёт владелец»');
  }

  // R32. Проверки 20–22 файла 01 — та же форма, что шаг 10 файла 05:
  // шесть списков каталога с выдавшим, сравнение с учётом повторов и
  // охрана «все или ни одной» для прав функций окна.
  const a1 = f01.indexOf('-- 20. Права доступа целиком');
  const b1 = a1 < 0 ? -1 : f01.indexOf('-- 22а. ', a1);
  const step1 = a1 < 0 || b1 < 0 ? '' : f01.slice(a1, b1);
  if (!step1) aclGrantorProblems.push('в файле 01 нет проверок 20–22 — сверки прав целиком');
  const code1 = step1.replace(/--[^\n]*/g, '');
  const lists1 = (code1.match(/aclexplode\(/g) || []).length;
  const joins1 = (code1.match(/LEFT JOIN pg_roles gr ON gr\.oid = a\.grantor/g) || []).length;
  const cells1 = (code1.match(/\|\| '\|' \|\| coalesce\(gr\.rolname, a\.grantor::text\)/g) || []).length;
  if (step1 && lists1 !== 6) aclGrantorProblems.push('файл 01: списков прав каталога ' + lists1 + ' вместо шести');
  if (step1 && (joins1 !== lists1 || cells1 !== lists1)) {
    aclGrantorProblems.push('файл 01: выдавший читается не во всех списках прав: списков ' + lists1
      + ', соединений с выдавшим ' + joins1 + ', полей выдавшего ' + cells1);
  }
  if (/\bEXCEPT\b/i.test(code1)) aclGrantorProblems.push('файл 01: права сравниваются через EXCEPT, повтор строки не виден');
  if (step1) {
    for (const t of ['FROM unnest(v_acl_got) AS r GROUP BY r', 'FROM unnest(v_acl_want) AS r GROUP BY r',
                     'WHERE x.n_got > x.n_want', 'WHERE x.n_want > x.n_got']) {
      if (!code1.includes(t)) aclGrantorProblems.push('файл 01: права сравниваются не с учётом повторов: нет ' + t);
    }
    for (const t of ["'DATABASE|'", "'SCHEMA|'", "'SEQUENCE|'", "'TABLE|'", "'COLUMN|'", "'FUNCTION|'", "'DEFAULT|'"]) {
      if (!code1.includes(t)) aclGrantorProblems.push('файл 01: в сверке каталога нет вида прав ' + t);
    }
    for (const t of ['IF v_cnt NOT IN (0, cardinality(v_acl_04)) THEN', 'v_acl_want := v_acl;',
                     'v_acl_want := v_acl || v_acl_04;']) {
      if (!code1.includes(t)) aclGrantorProblems.push('файл 01: нет охраны «все или ни одной» для прав функций окна: нет ' + t);
    }
    // R32: запрос каталога прав — двойник шага 10 файла 05. Запрос идёт слово в слово; пробелы и
    // переводы строк не различие.
    const cte = (c) => {
      const i = c.indexOf('WITH nsp AS (');
      const j = i < 0 ? -1 : c.indexOf('INTO v_acl_got FROM got;', i);
      return i < 0 || j < 0 ? null : c.slice(i, j).replace(/\s+/g, ' ').trim();
    };
    const c1 = cte(code1);
    const c5 = cte(code);
    if (c1 === null || c5 === null || c1 !== c5) {
      aclGrantorProblems.push('файл 01: запрос прав каталога не совпадает с запросом шага 10 файла 05');
    }
    // R32 (РАУНД-R32-СРАВНЕНИЕ: код). Сравнение с договором — тоже двойник.
    // Подмена «договора» на сам каталог в одной из двух сверок или
    // ослабленное условие отказа раньше проходили: проверялось лишь, что
    // нужные слова есть где-то в шаге. Теперь обе сверки берутся целиком,
    // от первого SELECT до последнего END IF, и сравниваются после трёх
    // замен: имя списка договора, текст отказа и пробелы. Текст отказа
    // заменяется, но слова RAISE EXCEPTION и аргументы остаются: отказ,
    // ослабленный до уведомления, тоже расхождение.
    const cmp = (c, listName) => {
      const i = c.indexOf("SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_got - x.n_want)");
      if (i < 0) return null;
      return c.slice(i)
        .replace(/RAISE\s+EXCEPTION\s+'[^']*'/g, "RAISE EXCEPTION '…'")
        .replace(new RegExp('\\b' + listName + '\\b', 'g'), 'v_acl_договор')
        .replace(/\s+/g, ' ').trim();
    };
    const m1 = cmp(code1, 'v_acl_want');
    const m5 = cmp(code, 'v_acl');
    if (m1 === null || m5 === null || m1 !== m5) {
      aclGrantorProblems.push('сравнение прав в файле 01 (пункт 22) и в файле 05 (шаг 10) разошлось');
    }
    // R33 (замечание M-H117-R17-01 = B-01). Проверка выше сравнивает файл 01
    // с файлом 05 ДРУГ С ДРУГОМ — они близнецы, и совместная правка одного и
    // того же слова в обоих сразу (FULL JOIN -> LEFT JOIN) оставляет их
    // равными друг другу; парная сверка тогда не отказывает. Здесь —
    // независимый, непарный инвариант: в каждом сравнении САМОМ ПО СЕБЕ —
    // ровно два соединения, и оба именно FULL JOIN; другого вида соединения
    // (LEFT/RIGHT/INNER/простой JOIN) в этом фрагменте быть не должно. Это
    // проверяется у каждого файла отдельно, без сверки со вторым, поэтому
    // совместная подделка ловится у обоих сразу, а не ускользает через
    // равенство близнецов.
    const joinShapeOf = (text) => ({
      total: (text.match(/\bJOIN\b/g) || []).length,
      full: (text.match(/\bFULL\s+JOIN\b/g) || []).length,
    });
    for (const [label, m] of [['файл 01 (пункт 22)', m1], ['файл 05 (шаг 10)', m5]]) {
      if (m === null) continue;
      const { total, full } = joinShapeOf(m);
      if (total !== 2 || full !== 2) {
        aclGrantorProblems.push(label + ': сравнение прав использует не два FULL JOIN — соединений всего '
          + total + ', из них FULL JOIN ' + full);
      }
    }
    // Ветвление «все или ни одной» целиком: если до файла 04 строк нет,
    // ждём v_acl; если они есть — v_acl и v_acl_04. Перестановка ветвей
    // оставляла на месте каждую из трёх строк по отдельности.
    const branch = 'IF v_cnt = 0 THEN v_acl_want := v_acl; ELSE v_acl_want := v_acl || v_acl_04; END IF;';
    if (!code1.replace(/\s+/g, ' ').includes(branch)) {
      aclGrantorProblems.push('файл 01: нет охраны «все или ни одной» для прав функций окна: нет ' + branch);
    }
  }
}

// --- Печать выведенных множеств -----------------------------------------
if (process.argv.includes('--print-terminal')) {
  const put = (name, rows) => {
    console.log('BEM954-PACKAGE-TERMINAL-' + name);
    for (const r of rows) console.log(r);
    console.log('');
  };
  put('ROLES', termRoles);
  put('MEMBERS', termMembers);
  put('SECRETS', termSecrets);
  put('LOGIN', termLogin);
  put('READ', [...termRead].sort());
  put('EXEC', [...termExec].sort());
  put('FUNC', termFunc);
  put('RLS', termRls);
  put('POLICY', termPolicy);
  put('TRIGGER', termTrigger);
  put('TRIGGER-LEGACY', termTriggerLegacy);
  put('TRIGGER-DEF', termTriggerDef);
  put('TRIGGER-DEF-LEGACY', termTriggerDefLegacy);
  put('ACL', termAcl);
  put('ACL01', termAcl01);
  put('ACL04', termAcl04);
  process.exit(0);
}
if (process.argv.includes('--print-selfcheck')) {
  console.log('BEM954-PACKAGE-SELFCHECK-READ');
  for (const r of [...expectRead].sort()) console.log(r);
  console.log('');
  console.log('BEM954-PACKAGE-SELFCHECK-EXEC');
  for (const r of [...expectExec].sort()) console.log(r);
  process.exit(0);
}
if (process.argv.includes('--print-contracts')) {
  console.log('BEM954-PACKAGE-READ-CONTRACT');
  for (const r of [...readActual].sort()) console.log(r);
  console.log('');
  console.log('BEM954-PACKAGE-EXECUTE-SURFACE');
  for (const r of [...execActual].sort()) console.log(r);
  console.log('');
  console.log('BEM954-PACKAGE-REVOKE-CONTRACT');
  for (const r of [...new Set(revokeLines)].sort()) console.log(r);
  console.log('');
  console.log('BEM954-PACKAGE-ROLE-ATTRIBUTES');
  for (const [name, st] of [...roleState].sort()) {
    console.log([name, st.LOGIN ? 'yes' : 'no', st.SUPERUSER ? 'yes' : 'no', st.CREATEDB ? 'yes' : 'no',
                 st.CREATEROLE ? 'yes' : 'no', st.REPLICATION ? 'yes' : 'no', st.BYPASSRLS ? 'yes' : 'no',
                 st.INHERIT ? 'yes' : 'no', String(st.CONNLIMIT)].join('|'));
  }
  console.log('');
  console.log('BEM954-PACKAGE-ROLE-MEMBERSHIPS');
  for (const r of [...memberActual].sort()) console.log(r);
  console.log('');
  console.log('BEM954-PACKAGE-ROLE-SECRETS');
  for (const r of roleSecretRows) console.log(r);
  console.log('');
  console.log('BEM954-PACKAGE-MIGRATOR-GRANTS');
  for (const r of [...(wrapperGranted || [])].sort()) console.log(r);
  console.log('');
  console.log('BEM954-PACKAGE-DYNAMIC-STATEMENTS');
  for (const r of [...dynActual].sort()) console.log(r);
  process.exit(0);
}

// --- Права роли проверки восстановления на схемы (H1.24, M-R43-01) -------
// Аудит R43 заменил условие свёртки схем на WHERE true, и оба сверщика
// вернули 0. Свёртка обязана убирать ровно одно право — USAGE роли
// restore_verifier на bem_control без права передачи; файл 03 обязан
// снять прежние права роли на три схемы до выдачи и сверить точный
// список прав после неё. Образцы склеены из частей: их текст не совпадает
// с каноном, и подделка канона не попадает в этот листинг.
// H1.25, L-R44-01 (аудит R44): в обоих местах исключение действует только
// для права, выданного владельцем схемы (условие на grantor).
const restoreAclProblems = [];
{
  const n01 = norm(stripComments(fileSql.get('01_database_migration.sql') || ''));
  const n03 = norm(stripComments(fileSql.get('03_restore_verifier.sql') || ''));
  const times = (t, frag) => t.split(norm(frag)).length - 1;
  const digestKeep = 'FROM aclexplode(n.nspacl) e WHERE NOT (n.nspname = ' + "'bem_control' AND e.grantee <> 0 AND "
    + "pg_get_userbyid(e.grantee) = 'restore_verifier' AND e.privilege_type = 'USAGE' AND NOT " + "e.is_grantable AND e.grantor = "
    + "n.nspowner)) z), '-')) AS line";
  if (times(n01, digestKeep) !== 1 || times(n01, 'unnest(' + 'n.nspacl)') !== 0
      || times(n01, "concat_ws('|', " + "'v3', 'schema',") !== 1) {
    restoreAclProblems.push('файл 01: свёртка схем убирает не ровно одно право USAGE роли restore_verifier на bem_control');
  }
  const revokeAll = ['bem_core', 'bem_engine', 'bem_control'].map((s) => 'REVOKE CREATE, USAGE ON SCHEMA ' + s + ' FROM ' + 'restore_verifier;').join(' ');
  const grantOne = 'GRANT USAGE ON SCHEMA ' + 'bem_control TO restore_verifier;';
  const ri = n03.indexOf(norm(revokeAll));
  const gi = n03.indexOf(norm(grantOne));
  if (times(n03, revokeAll) !== 1 || times(n03, grantOne) !== 1 || ri < 0 || gi < ri) {
    restoreAclProblems.push('файл 03: прежние права роли на три схемы не сняты до выдачи USAGE');
  }
  const create = "IF has_schema_privilege('restore_verifier', 'bem_control', 'CREATE') OR "
    + "has_schema_privilege('restore_verifier', 'bem_core', 'CREATE') OR has_schema_privilege('restore_verifier', "
    + "'bem_engine', 'CREATE') THEN RAISE " + "EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: есть право CREATE на схему';";
  if (times(n03, create) !== 1) restoreAclProblems.push('файл 03: нет отказа при праве CREATE роли на схему');
  const exact = "WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control') AND e.grantee = 'restore_verifier'::regrole "
    + "AND NOT (n.nspname = 'bem_control' AND e.privilege_type = 'USAGE' AND NOT e.is_grantable AND e.grantor = "
    + "n.nspowner); IF v_cnt <> 0 THEN RAISE "
    + "EXCEPTION 'RESTORE_VERIFIER_TOO_WIDE: лишних прав " + "роли на схемы: %', v_cnt;";
  if (times(n03, exact) !== 1) restoreAclProblems.push('файл 03: нет сверки точного списка прав роли на схемы');
}

// --- Ограничения целиком (H1.26, D1 проб R46, п. 16) -----------------------
// Живая проба R46: после снятия UNIQUE outbox_idem_uniq и составного FK
// subject_author_subject_fk повтор файла 01 вернул код 0, но ни того, ни
// другого не вернул, а файл 05 расхождения не увидел. Канон — список
// v_constraints файла 05 (точное множество видов p, u, f, c). Каждая его
// строка таблицы обязана стоять в файле 01 ровно одним кортежем, строка
// домена — починкой шага 2; ссылка FK обязана идти после своей цели; три
// блока сверки обязаны и добавлять, и отказывать при другой форме; файл 05
// обязан отказывать и при нехватке, и при лишнем.
const constraintProblems = [];
{
  const raw01 = stripComments(fileSql.get('01_database_migration.sql') || '');
  const raw05 = stripComments(fileSql.get('05_final_state_check.sql') || '');
  const n01 = norm(raw01);
  const n05 = norm(raw05);
  const times = (t, frag) => t.split(norm(frag)).length - 1;
  const m = raw05.match(/v_constraints constant text\[\] := ARRAY\[\n([\s\S]*?)\];\n/);
  const canon = [];
  if (!m) constraintProblems.push('файл 05: нет списка ограничений v_constraints');
  else {
    const seen = new Set();
    for (const line of m[1].split(',\n')) {
      const mm = line.trim().match(/^'(.*)'$/);
      const v = mm ? mm[1].replace(/''/g, "'") : '';
      const parts = v.split('|');
      if (!mm || parts.length < 4 || !['TABLE', 'DOMAIN'].includes(parts[0])) {
        constraintProblems.push('файл 05: строка списка не разобрана: ' + line.trim().slice(0, 80));
        continue;
      }
      if (seen.has(v)) constraintProblems.push('файл 05: строка списка повторена: ' + v.slice(0, 80));
      seen.add(v);
      canon.push({ kind: parts[0], obj: parts[1], con: parts[2], def: parts.slice(3).join('|') });
    }
    if (canon.length !== 74) constraintProblems.push('файл 05: в списке ограничений ' + canon.length + ' строк вместо 74');
  }
  const q = (s) => "'" + s.replace(/'/g, "''") + "'";
  const at = new Map();
  for (const c of canon) {
    if (c.kind === 'DOMAIN') {
      if (times(n01, 'ALTER DOMAIN ' + c.obj + ' ADD CONSTRAINT ' + c.con) !== 1) {
        constraintProblems.push('файл 01: нет ограничения домена в починке шага 2: ' + c.obj + ' ' + c.con);
      }
      continue;
    }
    const tuple = '(' + q(c.obj) + ', ' + q(c.con) + ', ' + q(c.def) + ')';
    const k = raw01.split(tuple).length - 1;
    if (k !== 1) constraintProblems.push('файл 01: нет ограничения ровно одним кортежем (' + k + '): ' + c.obj + ' ' + c.con);
    else at.set(c.obj + '|' + c.def.replace(/^(PRIMARY KEY|UNIQUE) /, 'KEY '), raw01.indexOf(tuple));
    if (k === 1) at.set('@' + c.con, raw01.indexOf(tuple));
  }
  const tuples = raw01.match(/^ {12}\('bem_(?:core|control)\.[a-z_]+', '[a-z_]+', '/gm) || [];
  const tables = canon.filter((c) => c.kind === 'TABLE').length;
  if (tuples.length !== tables) constraintProblems.push('файл 01: кортежей ограничений ' + tuples.length + ', а в списке файла 05 — ' + tables);
  for (const c of canon) {
    const fk = c.def.match(/^FOREIGN KEY \([^)]*\) REFERENCES ([a-z_]+\.[a-z_]+)\(([^)]*)\)/);
    if (!fk || !at.has('@' + c.con)) continue;
    const target = at.get(fk[1] + '|KEY (' + fk[2] + ')');
    if (target === undefined || target > at.get('@' + c.con)) {
      constraintProblems.push('файл 01: ссылка стоит раньше своей цели: ' + c.obj + ' ' + c.con);
    }
  }
  const add = "IF NOT FOUND THEN EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', r.tbl, r.con, r.def);";
  const deny = 'ELSIF v_def IS DISTINCT FROM r.def THEN RAISE EXCEPTION '
    + "'MIGRATION_FAILED: CONSTRAINT_DEFINITION_MISMATCH: % %: ожидалось %, найдено %',";
  if (times(n01, add) !== 3 || times(n01, deny) !== 3) {
    constraintProblems.push('файл 01: ветвей «добавить» и «отказ при другой форме» не по три');
  }
  const miss = "IF v_miss IS NOT NULL THEN RAISE EXCEPTION 'FINAL_CONSTRAINT_MISMATCH: объявленных ограничений нет: %', v_miss;";
  const extra = "IF v_extra IS NOT NULL THEN RAISE EXCEPTION 'FINAL_CONSTRAINT_MISMATCH: ограничений сверх договора: %', v_extra;";
  const scope = "WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control') AND c.contype IN ('p', 'u', 'f', 'c'))";
  if (times(n05, miss) !== 1 || times(n05, extra) !== 1 || times(n05, scope) !== 1) {
    constraintProblems.push('файл 05: нет отказа при нехватке или при лишнем ограничении');
  }
}

// --- Назначение проверяющих BEM-954 (H1.26, D2 проб R46, п. 20) ----------
// Живая проба R46: запрет «проверяющий из компании любого автора» делал
// предмет BEM-954 с автором-моделью невыпускаемым — множество
// {anthropic, openai} не набиралось никогда. Запрет снят; назначение
// обязано по-прежнему требовать полномочие координатора и отказывать
// автору, самому себе и координатору-автору, а выпуск — требовать точного
// множества компаний.
const bem954AssignProblems = [];
{
  const raw01 = stripComments(fileSql.get('01_database_migration.sql') || '');
  const body = (fn) => {
    const head = 'CREATE OR REPLACE FUNCTION bem_control.' + fn + '(';
    const i = raw01.lastIndexOf(head);
    if (i < 0) return '';
    const j = raw01.indexOf('\n$$;', i);
    return norm(raw01.slice(i, j < 0 ? undefined : j));
  };
  const assign = body('assign_auditor');
  const release = body('release_subject');
  if (!assign) bem954AssignProblems.push('assign_auditor: функции нет');
  else {
    if (/BEM954_SAME_PROVIDER_AUDITOR|a\.provider = v_provider/.test(assign)) {
      bem954AssignProblems.push('assign_auditor: снова запрет проверяющего из компании автора');
    }
    for (const need of ["assert_authority('AUDIT_COORDINATOR', p_tenant_id)",
                        "RAISE EXCEPTION 'SELF_ASSIGNMENT_FORBIDDEN: %', p_auditor;",
                        "RAISE EXCEPTION 'SELF_AUDIT_FORBIDDEN: %', p_auditor;",
                        "RAISE EXCEPTION 'COORDINATOR_IS_AUTHOR: %', v_actor;"]) {
      if (assign.split(norm(need)).length - 1 !== 1) bem954AssignProblems.push('assign_auditor: нет проверки: ' + need.slice(0, 60));
    }
  }
  if (!/BEM954_PROVIDER_SET_MISMATCH/.test(release)) {
    bem954AssignProblems.push('release_subject: нет отказа при множестве компаний не {anthropic, openai}');
  }
}

// --- Итог ---------------------------------------------------------------
const fail = wrongBranch.length + doMismatch.length + staleCover.length
           + rowsWithoutFn.length + staleNoFn.length
           + noRevoke.length + staleNoRevoke.length + evidenceDoor.length
           + tenantBad.length + staleHelper.length + staleCross.length
           + reachableHelper.length + grantWithoutRevoke.length
           + duplicates.length + dmlMissing.length + dmlSurplus.length
           + grantedWide.length + defaultWrites.length + dmlSelfCheck.length
           + outsideFns.length + outsideGrants.length
           + unknownPrivs.length + forbiddenPrivs.length
           + readMissing.length + readSurplus.length
           + execMissing.length + execSurplus.length
           + revokeUndeclared.length + revokeStale.length
           + roleMismatch.length + memberMismatch.length + markerProblems.length
           + selfcheckProblems.length
           + vocabProblems.length + dynProblems.length + migratorProblems.length
           + secretProblems.length + terminalProblems.length
           + blockCommentProblems.length + grantorProblems.length
           + wrapperShape.length + triggerDropProblems.length
           + trgProblems.length + policyProblems.length + constGuard.length
           + aclProblems.length + triggerDefProblems.length + aclGrantorProblems.length
           + rlsForceProblems.length + declDupProblems.length
           + proseProblems.length + editionProblems.length
           + restoreAclProblems.length
           + constraintProblems.length + bem954AssignProblems.length;

console.log(JSON.stringify({
  canonical_sections: canonSections,
  canonical_sql_blocks: canonBlocks.length,
  explanatory_sql_blocks: outerBlocks.length,
  functions: funcs.size,
  definitions: parsed.length,
  rows: rows.length,
  tenant_tables: [...tenantTables].sort(),
  bypass_rls_roles: [...bypassRoles].sort(),
  tenant_functions: tenantList.length,
  cross_tenant_functions: crossList.length,
  dml_contract_rows: contract.length,
  evidence_inserts: inserts,
  do_block_errors_in_rows: doOnlyCount,
  wrong_branch: wrongBranch,
  do_block_coverage_mismatch: doMismatch,
  stale_do_block_coverage: staleCover,
  rows_without_function: rowsWithoutFn,
  declared_no_function: [...noFn].sort(),
  stale_no_function: staleNoFn,
  functions_without_revoke: noRevoke,
  declared_no_revoke: [...noRevokeOk].sort(),
  stale_no_revoke: staleNoRevoke,
  declared_tenant_helpers: [...helper].sort(),
  stale_tenant_helpers: staleHelper,
  reachable_tenant_helpers: reachableHelper,
  declared_cross_tenant: [...crossTenant].sort(),
  stale_cross_tenant: staleCross,
  grant_without_revoke: grantWithoutRevoke,
  duplicate_definitions: duplicates,
  evidence_door: evidenceDoor,
  tenant_boundary: tenantBad,
  dml_missing: dmlMissing,
  dml_surplus: dmlSurplus,
  dml_wide_grants: grantedWide,
  dml_default_privileges: defaultWrites,
  dml_self_check: dmlSelfCheck,
  definitions_outside_canon: outsideFns,
  grants_outside_canon: outsideGrants,
  selfcheck_read_rows: expectRead.size,
  selfcheck_exec_rows: expectExec.size,
  selfcheck_problems: selfcheckProblems,
  read_contract_rows: readActual.size,
  execute_surface_rows: execActual.size,
  unknown_privileges: unknownPrivs,
  forbidden_privileges: forbiddenPrivs,
  read_contract_missing: readMissing,
  read_contract_surplus: readSurplus,
  execute_surface_missing: execMissing,
  execute_surface_surplus: execSurplus,
  acl_final_rows: aclFinal.size,
  revoke_statements: revokeLines.length,
  revoke_undeclared: revokeUndeclared,
  revoke_stale: revokeStale,
  role_rows: roleState.size,
  role_mismatch: roleMismatch,
  membership_rows: memberActual.size,
  membership_mismatch: memberMismatch,
  final_marker_problems: markerProblems,
  statement_forms: Object.fromEntries([...vocabCounts].sort((a, b) => b[1] - a[1])),
  vocabulary_problems: vocabProblems,
  dynamic_statements: dynActual.size,
  dynamic_problems: dynProblems,
  migrator_problems: migratorProblems,
  role_secret_rows: roleSecretRows.length,
  role_secret_problems: secretProblems,
  terminal_rows: {
    roles: termRoles.length, members: termMembers.length,
    secrets: termSecrets.length, login: termLogin.length,
    rls: termRls.length, policy: termPolicy.length,
    trigger: termTrigger.length, trigger_def: termTriggerDef.length,
    trigger_def_legacy: termTriggerDefLegacy.length, acl: termAcl.length,
    acl_after_file_01: termAcl01.length, acl_window_functions: termAcl04.length,
    func: termFunc.length,
    read: termRead.size, exec: termExec.size,
  },
  acl_problems: aclProblems,
  constant_guard_problems: constGuard,
  policy_template_problems: policyProblems,
  trigger_parse_problems: trgProblems,
  trigger_definition_problems: triggerDefProblems,
  acl_grantor_problems: aclGrantorProblems,
  declaration_duplicate_problems: declDupProblems,
  prose_problems: proseProblems,
  edition_problems: editionProblems,
  terminal_problems: terminalProblems,
  block_comment_problems: blockCommentProblems,
  grantor_problems: grantorProblems,
  wrapper_shape_problems: wrapperShape,
  trigger_drop_problems: triggerDropProblems,
  rls_force_problems: rlsForceProblems,
  restore_acl_problems: restoreAclProblems,
  constraint_problems: constraintProblems,
  bem954_assign_problems: bem954AssignProblems,
  verdict: fail === 0 ? 'OK' : 'РАСХОЖДЕНИЙ: ' + fail,
}, null, 1));

process.exit(fail === 0 ? 0 : 1);