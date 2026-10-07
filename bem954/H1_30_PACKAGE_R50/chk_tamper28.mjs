// chk_tamper28.mjs — прогон набора подделок H1.30.
// PASSPORT: ACTIVE vR50.1, раунд R50, H1.30.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R50 (РАУНД-R50-ПЕРЕНОС-ИМЁН: H1.30; логика программ в R47–R50 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.29/R49; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47, R49 и R50 — раздел 22.2, остальное — раздел 15.43.
// ИСТОРИЯ: прежний активный паспорт. Версия 5.0, раунд R33 (РАУНД-R33-РЕДАКЦИЯ: ожидаемая
// редакция документа для смыслового сверщика приходит только извне — ключом
// --expect-edition обязателен и передаётся при каждом
// прогоне, в том числе на подделанных копиях; закрывает замечание
// L-H117-R17-02 = B-04: совместная подделка паспорта и последнего абзаца на
// одно и то же число больше не проходит. Уровень отказа обязателен и у
// новых строк K-R17, той же проверкой, что у K-R15/K-R16). Прежде — версия
// 4.0, раунд R32
// (РАУНД-R32-ПОДДЕЛКИ: уровень отказа обязателен и у строк K-R16; логика
// прогона не менялась). Прежде — версия 3.0,
// раунд R31, замечания C-H115-R15-01 и
// M-H115-R15-02. Заменяет версию 2.0 раунда R28 (архив:
// chk_tamper28.R30-final.ARCHIVED.mjs в мастерской автора).
// (РАУНД-R32-ПЕРЕНОС-ИМЁН: имя документа H1.17, рабочая папка r32;
// соответствующая логика переноса не менялась, а версия 4.0 в этом же
// раунде поднята по другой причине, названной выше; замечание
// L-H117-R17-03 = L-C-03.)
// (РАУНД-R33-ПЕРЕНОС-ИМЁН: имя документа H1.18, рабочая папка r33;
// соответствующая логика переноса тоже не менялась, а версия 5.0 поднята
// по другой причине, названной выше.)
// Запуск: node chk_tamper28.mjs <файл H1.30> [--expect-edition H1.30] [--report отчёт.json] [--work папка]
//         node chk_tamper28.mjs <файл H1.30> --print-table   (таблица 15.18)
//         node chk_tamper28.mjs <файл H1.30> --print-rows    (строки реестра)
//
// Что изменилось против версии 2.0 и зачем.
//
// 1. Третий вид случая — «оба». Подделку I-H115-01 аудита 85 (условие
//    constraint-триггера заменено на WHEN (true)) обязаны ловить ОБА
//    сверщика. Случай вида «оба» прогоняется через каждый, и ожидаемый
//    код сверяется у каждого отдельно. Один пойманный из двух — провал.
//
// 2. Поле level — ожидаемый уровень отказа. Код 1 говорит «что-то не
//    так», но не говорит, что именно. Аудит 85 потребовал, чтобы подделка
//    доказывала отказ нужного уровня, а не любой. level называет поле
//    отчёта сверщика и, после двоеточия, начало строки: подделка поймана
//    правильно, только если в этом поле появилась новая строка с этим
//    началом. У новых случаев раунда R31 level обязателен.
//
// 3. Программа больше не привязана к машине автора. Node берётся тот,
//    которым запущен сам прогон (process.execPath), а не зашитый путь;
//    сверщики и манифест ищутся рядом с этим файлом, а не в текущей
//    папке. Проверяющий аудита 85 запускал прогон своим node 24 и
//    получил ошибку запуска вместо результата.
//
// 4. Копии документа пишутся в рабочую папку ВНЕ папки программы. Прежде
//    сто шестьдесят копий по мегабайту ложились рядом с пакетом, и
//    проверка состава пакета не могла отличить их от его файлов. Папка
//    задаётся ключом --work; по умолчанию — подпапка временной папки
//    системы. Папку внутри папки программы прогон отвергает.
//
// 5. В отчёте нет путей этой машины: только имена файлов. Версии node
//    в отчёте тоже нет — она печатается в консоль. Отчёт лежит в пакете,
//    и пересборка на другом node иначе дала бы другую сумму отчёта.
//
// 6. Листинги сверяются с файлами у всех семи программ пакета. Список
//    программ и их меток один — в pkg_extract.mjs; прежде у прогона был
//    свой список из четырёх, и сборщик с проверкой в него не входили.
//
// Что сохранено из версии 2.0: случаи лежат в манифесте, у каждого есть
// ожидаемый код, листинги сверяются с файлами побайтно, любое
// расхождение с ожиданием валит весь прогон.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join, basename, resolve, sep } from 'node:path';
import { tmpdir } from 'node:os';
import { cases, rows } from './tamper_manifest28.mjs';
import { PROGRAMS } from './pkg_extract.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const node = process.execPath;
const REG = 'bem954_registry_check.mjs';
const SEM = 'bem954_semantic_check.mjs';
const argAfter = (flag) => {
  const i = process.argv.indexOf(flag);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : null;
};
const file = process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : 'H1_30.md';
const base = readFileSync(file, 'utf8');
const sha = (t) => createHash('sha256').update(t, 'utf8').digest('hex');

// R33, замечание L-H117-R17-02 (=B-04). Ожидаемая редакция не может браться
// из текста самого документа: совместная подделка паспорта и последнего
// абзаца на одно и то же чужое число тогда согласна сама с собой, и отказа
// нет. Единственный источник ожидания — обязательный ключ --expect-edition;
// имя и текст входного документа не используются как fallback. Значение
// передаётся каждому прогону
// смыслового сверщика — и по чистому документу, и по каждой подделанной
// копии, — поэтому подделка текста копии его не меняет.
const EXPECT_EDITION = argAfter('--expect-edition');
if (!EXPECT_EDITION) { console.error('обязателен --expect-edition H1.30'); process.exit(2); }
if (EXPECT_EDITION !== 'H1.30') { console.error('неверный --expect-edition: ' + EXPECT_EDITION + '; ожидается H1.30'); process.exit(2); }
const _passportText = base;
if (!/ВЕРСИЯ:\s*\r?\n\s*v1\.30(?:\s|$)/.test(_passportText)) { console.error('паспорт документа не H1.30'); process.exit(2); }

const WORK = resolve(argAfter('--work') || join(tmpdir(), 'bem954_tamper_r38'));
if (WORK === resolve(HERE) || WORK.startsWith(resolve(HERE) + sep)) {
  console.error('РАБОЧАЯ ПАПКА ВНУТРИ ПАПКИ ПРОГОНА: копии легли бы рядом с пакетом');
  process.exit(2);
}
mkdirSync(WORK, { recursive: true });

// Набор лежит внутри того самого документа, который он подделывает, и это
// создаёт две беды сразу.
//
// Первая — столкновение якорей. Якорь подделки — кусок текста канона; но
// тот же кусок стоит и в листинге набора, и в листинге манифеста. Замена
// по первому вхождению попала бы туда, канон остался бы цел, сверщик
// вернул бы 0 — и подделка считалась бы непойманной по причине, к
// безопасности отношения не имеющей.
//
// Вторая — круг в суммах. Отчёт называет сумму документа; отчёт лежит в
// документе; вставка отчёта меняет сумму. Такой отчёт не перепроверить.
//
// Обе беды снимает одно действие: до первой подделки из текста вырезаются
// четыре области, ограниченные строками-метками. Прогон идёт по остатку.
const MARKS = [
  ['BEM954-PACKAGE-TAMPER-SUITE-LISTING-BEGIN', 'BEM954-PACKAGE-TAMPER-SUITE-LISTING-END'],
  ['BEM954-PACKAGE-TAMPER-MANIFEST-BEGIN', 'BEM954-PACKAGE-TAMPER-MANIFEST-END'],
  ['BEM954-PACKAGE-TAMPER-REPORT-BEGIN', 'BEM954-PACKAGE-TAMPER-REPORT-END'],
  // Таблица раздела 15.18 печатается этим же прогоном, и вставка её в
  // документ сдвинула бы сумму остатка ровно так же, как вставка отчёта.
  ['<!-- BEM954-PACKAGE-COVERAGE-TABLE-BEGIN -->', '<!-- BEM954-PACKAGE-COVERAGE-TABLE-END -->'],
];
function stripMarked(text) {
  const out = [];
  let skipTo = null;
  let cut = 0;
  for (const line of text.split('\n')) {
    if (skipTo === null) {
      const pair = MARKS.find((p) => line.trim() === p[0]);
      if (pair) { skipTo = pair[1]; cut += 1; continue; }
      out.push(line);
    } else if (line.trim() === skipTo) {
      skipTo = null;
    }
  }
  if (skipTo !== null) { console.error('МЕТКА НЕ ЗАКРЫТА: ' + skipTo); process.exit(2); }
  return { text: out.join('\n'), cut };
}
const stripped = stripMarked(base);
const clean = stripped.text;
const cleanFile = join(WORK, 'chk_tamper28_clean.md');
writeFileSync(cleanFile, clean);

// --- Листинги против файлов на диске -------------------------------------
// Замечание L-H113-R13-02. Утверждение «листинг совпадает с файлом» было
// написано словом. Слово проверить нельзя, поэтому здесь оно заменено
// сравнением байтов. Область листинга ограничена парой меток, внутри неё
// первая и последняя строки — ограда блока, остальное — сам файл. Файл
// ищется рядом с программой, а не в текущей папке.
const LISTINGS = PROGRAMS.map(([disk, mark]) => [disk, mark + '-BEGIN', mark + '-END']);
const listingProblems = [];
const listingRows = [];
{
  const lines = base.split('\n');
  for (const [disk, open, close] of LISTINGS) {
    const i = lines.findIndex((l) => l.trim() === open);
    const j = lines.findIndex((l, k) => k > i && l.trim() === close);
    if (i < 0 || j < 0) { listingProblems.push('области листинга нет в документе: ' + disk); continue; }
    const body = lines.slice(i + 2, j - 1).join('\n');
    let onDisk;
    try { onDisk = readFileSync(join(HERE, disk), 'utf8'); }
    catch (e) { listingProblems.push('файла нет рядом с прогоном: ' + disk); continue; }
    const ok = body === onDisk;
    if (!ok) {
      listingProblems.push('листинг не совпадает с файлом побайтно: ' + disk
        + ' (в документе ' + body.length + ', на диске ' + onDisk.length + ')');
    }
    listingRows.push({ file: disk, embedded_sha256: sha(body), file_sha256: sha(onDisk), equal: ok });
  }
}

// --- Способы правки ------------------------------------------------------
// Ровно шесть, и каждый — три строки. Манифест содержит данные, а
// исполняет их этот разбор: подделка не может принести с собой код.
const MARK00 = '-- BEM954-FINAL-SECURITY-CHECKPOINT: 00_cluster_bootstrap.sql';
const EARLY  = 'GRANT CONNECT ON DATABASE bem';

function applyOne(text, c) {
  if (c.op === 'plain') {
    return text.includes(c.from) ? text.replace(c.from, () => c.to) : null;
  }
  if (c.op === 'last') {
    const i = text.lastIndexOf(c.from);
    return i < 0 ? null : text.slice(0, i) + c.to + text.slice(i + c.from.length);
  }
  if (c.op === 'in_function') {
    // Та же строка встречается в пяти функциях сразу, а подделать нужно
    // ровно одну.
    const head = 'CREATE OR REPLACE FUNCTION bem_control.' + c.fn + '(';
    const i = text.lastIndexOf(head);
    if (i < 0) return null;
    const j = text.indexOf('\n$$;', i);
    if (j < 0) return null;
    const body = text.slice(i, j);
    if (!body.includes(c.from)) return null;
    return text.slice(0, i) + body.replace(c.from, () => c.to) + text.slice(j);
  }
  if (c.op === 'after_mark') {
    return applyOne(text, { op: 'plain', from: MARK00, to: MARK00 + '\n' + c.cmd });
  }
  if (c.op === 'before_mark') {
    return applyOne(text, { op: 'plain', from: EARLY, to: c.cmd + '\n' + EARLY });
  }
  if (c.op === 'pair') {
    let t = text;
    for (const step of c.list) {
      t = applyOne(t, step);
      if (t === null) return null;
    }
    return t;
  }
  console.error('НЕИЗВЕСТНЫЙ СПОСОБ ПРАВКИ: ' + c.op);
  process.exit(2);
}

// --- Прогон ---------------------------------------------------------------
// Короткие имена сверщиков — это ключи поля level у случая вида «оба».
const SHORT = { [REG]: 'реестр', [SEM]: 'смысл' };
const checkersOf = (kind) => {
  if (kind === 'син') return [REG];
  if (kind === 'смысл') return [SEM];
  if (kind === 'оба') return [REG, SEM];
  console.error('НЕИЗВЕСТНЫЙ ВИД СЛУЧАЯ: ' + kind);
  process.exit(2);
};
const runFull = (checker, f) => {
  try {
    return { status: 0,
             out: execFileSync(node, [join(HERE, checker), f, '--expect-edition', EXPECT_EDITION],
                               { encoding: 'utf8', maxBuffer: 1 << 26 }) };
  } catch (e) {
    return { status: e.status === undefined || e.status === null ? -1 : e.status,
             out: (e.stdout || '') + (e.stderr || '') };
  }
};
const run = (checker, f) => runFull(checker, f).status;

// Код возврата говорит только «поймана». Чтобы отчёт доказывал ещё и ЧЕМ
// поймана, берётся первая строка, которой в выводе по чистому тексту не
// было, а в выводе по копии появилась. Сравнение с чистым выводом, а не
// список «полей расхождений»: перечислять поля пришлось бы руками, и они
// разошлись бы со сверщиком при первой же его правке. Это слова самой
// программы, а не подпись случая: подпись можно написать любую.
const parsed = (out) => {
  try { return JSON.parse(out.slice(out.indexOf('{'))); } catch (e) { return null; }
};
const newLines = (baseObj, r, key) => {
  const v = r && r[key];
  if (!Array.isArray(v)) return [];
  const was = new Set(Array.isArray(baseObj && baseObj[key]) ? baseObj[key] : []);
  return v.filter((x) => typeof x === 'string' && !was.has(x));
};
const reasonOf = (baseObj, out) => {
  const r = parsed(out);
  if (!r) return null;
  for (const k of Object.keys(r)) {
    const add = newLines(baseObj, r, k);
    if (add.length) return k + ': ' + add[0].slice(0, 160);
  }
  return null;
};
// Уровень отказа: «поле» или «поле: начало строки». Поймана правильно,
// если в этом поле отчёта появилась новая строка с этим началом. Не
// первая попавшаяся: подделка может задеть и соседнюю проверку, и это
// не ошибка — ошибка, если НУЖНАЯ проверка промолчала.
const levelHit = (baseObj, out, level) => {
  const i = level.indexOf(': ');
  const key = i < 0 ? level : level.slice(0, i);
  const head = i < 0 ? '' : level.slice(i + 2);
  const hit = newLines(baseObj, parsed(out), key).find((x) => x.startsWith(head));
  return hit === undefined ? null : key + ': ' + hit.slice(0, 160);
};
const levelFor = (c, checker) => {
  if (!c.level) return null;
  if (typeof c.level === 'string') return c.level;
  return c.level[SHORT[checker]] || null;
};

// Фактическая разница между чистым текстом и копией: первая и последняя
// различающиеся строки, остальное одинаково. Разница берётся сравнением
// текстов, а не из подписи случая: подпись можно написать любую.
const diffOf = (a, b) => {
  const x = a.split('\n');
  const y = b.split('\n');
  let i = 0;
  while (i < x.length && i < y.length && x[i] === y[i]) i += 1;
  let j = 0;
  while (j < x.length - i && j < y.length - i
         && x[x.length - 1 - j] === y[y.length - 1 - j]) j += 1;
  const cut = (s) => (s.length > 120 ? s.slice(0, 117) + '...' : s);
  return { line: i + 1,
           removed: x.slice(i, x.length - j).map(cut),
           added:   y.slice(i, y.length - j).map(cut) };
};

// Парная правка трогает два далёких места сразу, и разница «от первой
// до последней несовпавшей строки» захватила бы всё между ними — десять
// тысяч строк ни о чём. Поэтому у парной правки разница считается по
// каждому шагу отдельно.
const mutationOf = (c, text) => (c.op !== 'pair'
  ? diffOf(clean, text)
  : { parts: c.list.map((step) => diffOf(clean, applyOne(clean, step))) });

// Четыре прогона, а не два: сверщики обязаны вернуть 0 и по доставленному
// документу, и по остатку, из которого делаются копии.
const docReg = run(REG, file);
const docSem = run(SEM, file);
const cleanRegRun = runFull(REG, cleanFile);
const cleanSemRun = runFull(SEM, cleanFile);
const cleanReg = cleanRegRun.status;
const cleanSem = cleanSemRun.status;
const baseOf = { [REG]: parsed(cleanRegRun.out), [SEM]: parsed(cleanSemRun.out) };

// У новых случаев раундов R31, R32 и R33 уровень отказа обязателен: без
// него случай доказывал бы только «что-то сломалось».
// H1.24: строки K-R43 (M-R43-01) тоже обязаны называть уровень отказа; H1.25 — и K-R44; H1.26 — и K-R46.
const needsLevel = (c) => /^K-R(1[567]|4[346])-/.test(String(c.row)) && c.expect !== 0;

const out = [];
let asExpected = 0;
let lost = 0;
for (const c of cases) {
  const text = applyOne(clean, c);
  const head = { id: c.id, kind: c.kind, name: c.name, row: c.row, level: c.level || null };
  if (text === null) {
    lost += 1;
    out.push({ ...head, status: 'ЯКОРЬ НЕ НАЙДЕН', expected: c.expect, actual: null, ok: false });
    continue;
  }
  if (text === clean) {
    lost += 1;
    out.push({ ...head, status: 'ПРАВКА НИЧЕГО НЕ ИЗМЕНИЛА', expected: c.expect, actual: null, ok: false });
    continue;
  }
  const copy = 'chk_tamper28_' + c.id + '.md';
  writeFileSync(join(WORK, copy), text);
  const checks = [];
  for (const checker of checkersOf(c.kind)) {
    const res = runFull(checker, join(WORK, copy));
    const level = levelFor(c, checker);
    const hit = level && c.expect !== 0 ? levelHit(baseOf[checker], res.out, level) : null;
    checks.push({ checker, actual: res.status, reason: reasonOf(baseOf[checker], res.out),
                  level, level_hit: hit,
                  level_ok: level && c.expect !== 0 ? hit !== null : null });
  }
  const codesOk = checks.every((k) => k.actual === c.expect);
  const levelsOk = checks.every((k) => k.level_ok !== false);
  const levelMissing = needsLevel(c) && checks.some((k) => !k.level);
  const ok = codesOk && levelsOk && !levelMissing;
  if (ok) asExpected += 1;
  const actual = checks.length === 1 ? checks[0].actual
    : checks.map((k) => SHORT[k.checker] + ' ' + k.actual).join(', ');
  let status;
  if (!codesOk) status = 'НЕ ПО ОЖИДАНИЮ';
  else if (levelMissing) status = 'НЕТ УРОВНЯ ОТКАЗА';
  else if (!levelsOk) status = 'НЕ ТОТ УРОВЕНЬ ОТКАЗА';
  else status = c.expect === 0 ? 'верно пропущена' : 'поймана';
  out.push({ ...head, checker: checks.map((k) => k.checker).join(' + '), copy,
             sha256: sha(text), mutation: mutationOf(c, text),
             expected: c.expect, actual, ok, checks,
             reason: checks[0].level_hit || checks[0].reason, status });
}

const negatives = cases.filter((c) => c.expect !== 0).length;
const positives = cases.length - negatives;
const verdict = (docReg === 0 && docSem === 0 && cleanReg === 0 && cleanSem === 0
                 && asExpected === cases.length && lost === 0
                 && listingProblems.length === 0) ? 'OK' : 'ПРОВАЛ';

const aNumbers = cases.map((c) => (String(c.name || '').match(/^A(\d+):/) || [])[1])
  .filter((x) => x !== undefined).map(Number);
const tamperCasesRange = aNumbers.length
  ? ('A' + String(Math.min(...aNumbers)).padStart(2, '0') + '-A' + String(Math.max(...aNumbers)).padStart(2, '0'))
  : null;

const report = {
  suite: 'chk_tamper28',
  passport: 'ACTIVE vR50.1, раунд R50, H1.30',
  manifest: 'tamper_manifest28.mjs',
  document: basename(file),
  document_sha256: sha(base),
  expected_edition: EXPECT_EDITION,
  expected_edition_source: 'cli',
  round_facts: ['ROUND_FACT[BASELINE_EDITION]=H1.29', 'ROUND_FACT[EXPECTED_EDITION]=' + EXPECT_EDITION, 'ROUND_FACT[TAMPER_CASES_TOTAL]=' + cases.length, 'ROUND_FACT[TAMPER_CASES_RANGE]=' + tamperCasesRange, 'ROUND_FACT[PG16_D05]=' + ((base.match(/^ROUND_FACT\[PG16_D05\]=(\S+)$/m) || [])[1] || 'MISSING')],
  tamper_cases_range: tamperCasesRange,
  stripped_regions: stripped.cut,
  stripped_input: basename(cleanFile),
  stripped_input_sha256: sha(clean),
  work_dir: 'вне папки прогона; путь в отчёт не пишется',
  document_registry_exit: docReg,
  document_semantic_exit: docSem,
  clean_registry_exit: cleanReg,
  clean_semantic_exit: cleanSem,
  listings: listingRows,
  listing_problems: listingProblems,
  tampers_total: cases.length,
  tampers_negative: negatives,
  tampers_positive: positives,
  tampers_both_checkers: cases.filter((c) => c.kind === 'оба').length,
  tampers_with_level: cases.filter((c) => c.level).length,
  tampers_as_expected: asExpected,
  tampers_anchor_lost: lost,
  registry_rows_covered: [...new Set(cases.map((c) => c.row))].sort().length,
  rows: out,
  verdict,
};

// --- Печать для документа --------------------------------------------------
if (process.argv.includes('--print-rows')) {
  for (const r of out) console.log([r.id, r.row, r.kind, r.name, r.expected, r.actual].join(' | '));
  process.exit(0);
}
if (process.argv.includes('--print-table')) {
  // Таблица раздела 15.18: строка реестра, случаи, ожидание, факт.
  const byRow = new Map();
  for (const r of out) {
    if (!byRow.has(r.row)) byRow.set(r.row, []);
    byRow.get(r.row).push(r);
  }
  console.log('| строка реестра | что проверяет | случаи набора | ждали | получили |');
  console.log('|---|---|---|---|---|');
  for (const [row, list] of [...byRow].sort()) {
    const ids = list.map((r) => r.id).join(', ');
    const want = [...new Set(list.map((r) => r.expected))].join(' и ');
    const got = [...new Set(list.map((r) => String(r.actual)))].join(' и ');
    console.log('| `' + row + '` | ' + (rows[row] || '?') + ' | ' + ids
                + ' | ' + want + ' | ' + got + ' |');
  }
  process.exit(0);
}

const at = argAfter('--report');
if (at) writeFileSync(at, JSON.stringify(report, null, 1));
for (const r of out) {
  console.log([r.id, r.status, r.row, r.name,
               'ждали ' + r.expected + ', получили ' + r.actual,
               (r.sha256 || '').slice(0, 12)].join(' | '));
}
for (const p of listingProblems) console.log('ЛИСТИНГ: ' + p);
console.log('доставленный документ: реестр ' + docReg + ', смысл ' + docSem);
console.log('остаток без вырезанных областей: реестр ' + cleanReg + ', смысл ' + cleanSem
            + ', вырезано областей ' + stripped.cut);
console.log('случаев ' + cases.length + ' (ждут 1: ' + negatives + ', ждут 0: ' + positives
            + ', через оба сверщика: ' + report.tampers_both_checkers
            + ', с уровнем отказа: ' + report.tampers_with_level
            + '), по ожиданию ' + asExpected + ', якорь потерян ' + lost);
console.log('node ' + process.version + ' (в отчёт не пишется)');
console.log('итог: ' + verdict);
process.exit(verdict === 'OK' ? 0 : 1);