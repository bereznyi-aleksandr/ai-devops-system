// build_package.mjs — воспроизводимый сборщик пакета H1.29.
// PASSPORT: ACTIVE vR49.1, раунд R49, H1.29.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R49 (РАУНД-R49-ПЕРЕНОС-ИМЁН: H1.29; логика программ в R47–R49 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.28/R48; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47 и R49 — раздел 22.2, остальное — раздел 15.42.
// ИСТОРИЯ: прежний активный паспорт. Версия 2.2, раунд R33 (РАУНД-R33-ПЕРЕНОС-ИМЁН: имена
// H1.18 и пакета H1_18_PACKAGE_R33; логика не менялась, кроме
// --expect-edition — тот же раунд, замечание L-H117-R17-02 = B-04).
// Версия 2.1 — раунд R32 (РАУНД-R32-ПЕРЕНОС-ИМЁН: имена H1.17 и пакета
// H1_17_PACKAGE_R32; логика не менялась). Версия 2.0 —
// раунд R31, замечания M-H115-R15-02 и L-H115-R15-01. Версия 1.0 —
// раунд R30, замечание M-H114-R14-03.
//
// Запуск из папки пакета:
//   node build_package.mjs <путь к H1.29>                 — пересборка на месте
//   node build_package.mjs <путь к H1.29> --out <папка>   — сборка в новую папку
//   необязательно: --work <папка> — куда набор подделок кладёт копии документа.
//
// Пакет — чистая функция документа. Всё, что в нём лежит, либо извлечено
// из документа (шесть файлов SQL, обёртка, семь программ), либо выведено
// из извлечённого (опись, отчёты, короткий лист). Времени сборки, имени
// машины, версии node и путей в пакете нет: иначе вторая сборка давала
// бы другие суммы.
//
// Что изменилось против версии 1.0 и зачем (аудит 85).
//   1. Сборщик ничего не перезаписывает. Файл, которого нет, создаётся;
//      файл с теми же байтами остаётся как есть; файл с другими байтами
//      — отказ, и файл не трогается. Версия 1.0 сохраняла прежний файл
//      рядом с пометкой SUPERSEDED, и в пакете R30 скопились пять таких
//      копий, часть — с точкой в конце имени. Пересборка на месте теперь
//      и есть проверка «пакет пересобирается один в один».
//   2. Лишний файл в папке — отказ. Состав папки обязан совпасть с
//      составом сборки до имени.
//   3. Нет путей и node автора. Node — тот, которым запущен сборщик;
//      программы берутся из листингов документа, а не из папки автора.
//   4. Появилась полная опись пакета package_manifest.json: каждый файл,
//      кроме самой описи, с размером, суммой и числом строк. Сумму самой
//      описи закрепляет внешний малый манифест ответа.
//   5. Строки считаются одним правилом (замечание L-H115-R15-01): число
//      переводов строки, завершающий перевод пустой строки не добавляет.
//
// Опись migration_manifest.json по-прежнему покрывает шесть файлов SQL и
// не покрывает обёртку: обёртка несёт сумму описи в себе, и круг не
// разомкнуть. Обёртку защищает полная опись пакета.
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join, basename, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { extract, SQL_FILES, PROGRAMS, lineCount, badNameReason } from './pkg_extract.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const NODE = process.execPath;
const argAfter = (flag) => {
  const i = process.argv.indexOf(flag);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : null;
};
const DOC = process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : null;
if (!DOC) { console.error('нужен путь к документу H1.29: node build_package.mjs <путь>'); process.exit(2); }
const OUT = resolve(argAfter('--out') || HERE);
const WORK = resolve(argAfter('--work') || join(tmpdir(), 'bem954_tamper_r38'));
const EXPECT_EDITION = argAfter('--expect-edition');
if (!EXPECT_EDITION) { console.error('обязателен --expect-edition H1.29'); process.exit(2); }
if (EXPECT_EDITION !== 'H1.29') { console.error('неверный --expect-edition: ' + EXPECT_EDITION + '; ожидается H1.29'); process.exit(2); }
const _passportText = readFileSync(DOC, 'utf8');
if (!/ВЕРСИЯ:\s*\r?\n\s*v1\.29(?:\s|$)/.test(_passportText)) { console.error('паспорт документа не H1.29'); process.exit(2); }
const PACKAGE = 'H1_29_PACKAGE_R49';
// H1.24, PG16_D05: улика живого прогона D-05; обязательна, когда документ
// называет ROUND_FACT[PG16_D05]=EXECUTED_PASS.
const PG16_ARG = argAfter('--pg16-evidence');
const PG16_EVIDENCE = 'EVIDENCE_PG16_D05.txt';

const sha = (buf) => createHash('sha256').update(buf).digest('hex');
const ZEROS = '0'.repeat(64);
const беды = [];
const шаг = (n, t) => console.log('шаг ' + n + ': ' + t);

// Запись без перезаписи. Возвращает, что сделано; расхождение — беда.
const записано = [];
function положить(name, text) {
  const path = join(OUT, name);
  const buf = Buffer.from(text, 'utf8');
  записано.push(name);
  if (existsSync(path)) {
    if (readFileSync(path).equals(buf)) return 'совпадает';
    беды.push('файл в папке отличается от собранного и не тронут: ' + name);
    return 'ОТЛИЧАЕТСЯ';
  }
  writeFileSync(path, buf);
  return 'создан';
}

mkdirSync(OUT, { recursive: true });
const docBuf = readFileSync(DOC);
const doc = docBuf.toString('utf8');

// --- Шаг 1. Извлечение ----------------------------------------------------
шаг(1, 'извлечение из документа: шесть файлов SQL, обёртка, семь программ');
const { files, problems } = extract(doc);
беды.push(...problems);
if (problems.length) {
  for (const b of беды) console.error('  ' + b);
  process.exit(1);
}

// --- Шаги 2–5. Суммы, опись, сумма описи, обёртка -------------------------
шаг(2, 'суммы SHA-256 шести файлов SQL');
const суммы = {};
for (const f of SQL_FILES) суммы[f] = sha(Buffer.from(files.get(f), 'utf8'));
шаг(3, 'опись migration_manifest.json');
const описьТекст = JSON.stringify({
  document: 'H1.29 R49',
  note: 'опись покрывает только шесть файлов SQL; обёртка в неё не входит намеренно',
  reproducible: 'времени сборки здесь нет: опись обязана быть чистой функцией документа',
  files: суммы,
}, null, 2) + '\n';
шаг(4, 'сумма самой описи');
const суммаОписи = sha(Buffer.from(описьТекст, 'utf8'));
console.log('  ' + суммаОписи);
шаг(5, 'вставка суммы описи в обёртку');
const строкаНулей = "const MANIFEST_SHA256 = '" + ZEROS + "';";
let обёртка = files.get('run_migration.mjs');
if (обёртка.split(строкаНулей).length - 1 !== 1) {
  беды.push('в обёртке документа нет ровно одной строки с нулевой суммой описи');
} else {
  обёртка = обёртка.replace(строкаНулей, "const MANIFEST_SHA256 = '" + суммаОписи + "';");
}

// --- Шаг 6. Запись ---------------------------------------------------------
шаг(6, 'запись без перезаписи');
for (const f of SQL_FILES) console.log('  ' + f + ': ' + положить(f, files.get(f)));
console.log('  migration_manifest.json: ' + положить('migration_manifest.json', описьТекст));
console.log('  run_migration.mjs: ' + положить('run_migration.mjs', обёртка));
for (const [f] of PROGRAMS) console.log('  ' + f + ': ' + положить(f, files.get(f)));

// --- Шаг 7. Перепроверка с диска ------------------------------------------
шаг(7, 'перепроверка: всё перечитано с диска');
const описьСДиска = JSON.parse(readFileSync(join(OUT, 'migration_manifest.json'), 'utf8'));
for (const f of SQL_FILES) {
  if (sha(readFileSync(join(OUT, f))) !== описьСДиска.files[f]) беды.push('сумма файла не сошлась с описью: ' + f);
}
const обёрткаСДиска = readFileSync(join(OUT, 'run_migration.mjs'), 'utf8');
const вшито = (обёрткаСДиска.match(/const MANIFEST_SHA256 = '([0-9a-f]{64})';/) || [])[1];
if (вшито !== sha(readFileSync(join(OUT, 'migration_manifest.json')))) беды.push('в обёртке не та сумма описи');
if (вшито === ZEROS) беды.push('в обёртке остались нули');
try { execFileSync(NODE, ['--check', join(OUT, 'run_migration.mjs')]); }
catch (e) { беды.push('обёртка не разбирается как JavaScript'); }
for (const [f] of PROGRAMS) {
  try { execFileSync(NODE, ['--check', join(OUT, f)]); }
  catch (e) { беды.push('программа не разбирается как JavaScript: ' + f); }
}

// --- Шаг 8. Сверщики ------------------------------------------------------
шаг(8, 'оба сверщика пакета по документу');
const код = (prog) => {
  const args = [join(OUT, prog), DOC];
  args.push('--expect-edition', EXPECT_EDITION);
  try { execFileSync(NODE, args, { encoding: 'utf8', maxBuffer: 1 << 26 }); return 0; }
  catch (e) { return e.status === null || e.status === undefined ? -1 : e.status; }
};
const кодРеестр = код('bem954_registry_check.mjs');
const кодСмысл = код('bem954_semantic_check.mjs');
if (кодРеестр !== 0) беды.push('сверщик реестра вернул ' + кодРеестр);
if (кодСмысл !== 0) беды.push('смысловой сверщик вернул ' + кодСмысл);
console.log('  реестр ' + кодРеестр + ', смысл ' + кодСмысл);

// --- Шаг 9. Набор подделок ------------------------------------------------
шаг(9, 'набор подделок пакета по документу');
mkdirSync(WORK, { recursive: true });
const отчётПрогона = join(WORK, 'build_tamper_report.json');
let вывод = '';
try {
  вывод = execFileSync(NODE, [join(OUT, 'chk_tamper28.mjs'), DOC, '--expect-edition', EXPECT_EDITION, '--report', отчётПрогона, '--work', WORK],
                       { encoding: 'utf8', maxBuffer: 1 << 26 });
} catch (e) {
  вывод = (e.stdout || '') + (e.stderr || '');
  беды.push('набор подделок не прошёл');
}
let прогон = null;
let прогонObj = null;
try {
  прогон = readFileSync(отчётПрогона, 'utf8');
  прогонObj = JSON.parse(прогон);
} catch (e) { беды.push('набор подделок не записал/не дал прочитать JSON-отчёт'); }
const итог = прогонObj ? {
  total: прогонObj.tampers_total,
  as_expected: прогонObj.tampers_as_expected,
  anchor_lost: прогонObj.tampers_anchor_lost,
  verdict: прогонObj.verdict,
} : null;
if (!итог || итог.total !== 247 || итог.as_expected !== 247 || итог.anchor_lost !== 0 || итог.verdict !== 'OK') {
  беды.push('итог набора подделок не равен 247/247, anchor_lost=0, OK');
}
console.log('  tamper_run: ' + (итог ? ('всего ' + итог.total + ', ожидаемо ' + итог.as_expected + ', якорь потерян ' + итог.anchor_lost + ', ' + итог.verdict) : 'НЕТ'));
if (прогон !== null) console.log('  tamper_report.json: ' + положить('tamper_report.json', прогон));

// --- Шаг 9а. Улика живого прогона PG16_D05 (H1.24) ------------------------
// Факт документа решает, нужна ли улика. Улика обязана назвать этот самый
// документ и этот самый файл 01: иначе она доказывает что-то о другом пакете.
шаг('9а', 'улика живого прогона PG16_D05');
const pg16Fact = (doc.match(/^ROUND_FACT\[PG16_D05\]=(\S+)$/m) || [])[1] || 'MISSING';
let pg16Live = 'DESIGNED_NOT_EXECUTED';
let pg16Sha = null;
if (pg16Fact === 'EXECUTED_PASS') {
  if (!PG16_ARG || !existsSync(PG16_ARG)) беды.push('ROUND_FACT[PG16_D05]=EXECUTED_PASS требует --pg16-evidence с существующим файлом');
  else {
    const t = readFileSync(PG16_ARG, 'utf8');
    const поле = (k) => { const m = t.match(new RegExp('^' + k + '=(.*)$', 'm')); return m ? m[1].trim() : null; };
    const sql01 = sha(Buffer.from(files.get('01_database_migration.sql') || '', 'utf8'));
    if (поле('STATUS') !== 'EXECUTED_PASS' || поле('FINAL_RESULT') !== 'PASS' || поле('POSITIVE_RESULT') !== 'PASS'
        || поле('NEGATIVE_RESULT') !== 'PASS' || поле('SECRETS_INCLUDED') !== 'NO') беды.push('улика PG16_D05: итог не EXECUTED_PASS/PASS/PASS/PASS/NO');
    if (!/^PostgreSQL 16\./.test(поле('POSTGRESQL_VERSION') || '')) беды.push('улика PG16_D05: версия сервера не PostgreSQL 16');
    if (поле('SOURCE_DOCUMENT_SHA256') !== sha(docBuf)) беды.push('улика PG16_D05: SOURCE_DOCUMENT_SHA256 не равен сумме документа');
    if (поле('SQL_FILE_SHA256') !== sql01) беды.push('улика PG16_D05: SQL_FILE_SHA256 не равен сумме файла 01 этого документа');
    console.log('  ' + PG16_EVIDENCE + ': ' + положить(PG16_EVIDENCE, t));
    pg16Live = 'EXECUTED_PASS';
    pg16Sha = sha(Buffer.from(t, 'utf8'));
  }
} else if (pg16Fact !== 'DESIGNED_NOT_EXECUTED') беды.push('неизвестное значение ROUND_FACT[PG16_D05]: ' + pg16Fact);
console.log('  PG16_D05: ' + pg16Live);

// --- Шаг 10. Состав, лист, отчёт, опись -----------------------------------
шаг(10, 'состав пакета, короткий лист, отчёт и полная опись');
const состав = [...new Set([...записано, 'README_PACKAGE.md', 'package_report.json', 'package_manifest.json'])].sort();
const лист = [
  '# Пакет ' + PACKAGE,
  '',
  'Документ: `' + basename(DOC) + '`, SHA-256 `' + sha(docBuf) + '`.',
  '',
  '## Как проверить и пересобрать',
  '',
  'Команды запускаются из этой папки. Node — любой версии не ниже 20.',
  '',
  '```text',
  'node verify_package.mjs "<путь к H1.29>" --expect-edition H1.29',
  'node build_package.mjs "<путь к H1.29>" --expect-edition H1.29 --pg16-evidence EVIDENCE_PG16_D05.txt',
  'node build_package.mjs "<путь к H1.29>" --expect-edition H1.29 --pg16-evidence EVIDENCE_PG16_D05.txt --out "<новая пустая папка>"',
  '```',
  '',
  'Первая команда — независимая проверка: состав папки против описи,',
  'суммы, строки, листинги документа против файлов и чистая повторная',
  'сборка во временную папку с побайтной сверкой. Вторая — пересборка на',
  'месте: сборщик ничего не перезаписывает, и любое расхождение с',
  'документом — отказ. Третья собирает пакет заново в пустую папку.',
  '',
  'Набор подделок кладёт копии документа во временную папку системы, а',
  'не сюда; другая папка задаётся ключом `--work`.',
  '',
  '## Состав',
  '',
  'Список ниже сверяет `verify_package.mjs`: он обязан совпасть с описью',
  '`package_manifest.json`, с полем `files` отчёта `package_report.json` и с',
  'фактической папкой — до имени.',
  '',
  '```text',
  'BEM954-PACKAGE-FILES-BEGIN',
  ...состав,
  'BEM954-PACKAGE-FILES-END',
  '```',
  '',
  '## Чего пакет не доказывает',
  '',
  'Сборка и проверка доказывают целостность и связность пакета, а не',
  'поведение базы. Единственная улика живого прогона внутри пакета —',
  '`EVIDENCE_PG16_D05.txt` (проверка D-05 на PostgreSQL 16.15); сборщик',
  'принимает её, только если она называет этот документ и этот файл 01.',
  'Остальные живые прогоны (чистая установка, повтор, файл 03, окно',
  'копирования, путь 02 + 01 с формы H1.6) выполняются после сборки и',
  'описываются отдельным отчётом раунда с журналами и суммами.',
  '',
].join('\n');
console.log('  README_PACKAGE.md: ' + положить('README_PACKAGE.md', лист));

const отчёт = JSON.stringify({
  package: PACKAGE,
  builder_passport: 'ACTIVE vR49.1, раунд R49, H1.29',
  baseline_edition: 'H1.28',
  baseline_sha256: 'cad2131cd8be7907ae49b4ee5dbbc391d6a94e8af9fb3334dd707e4b8b03d338',
  document: basename(DOC),
  document_sha256: sha(docBuf),
  expected_edition: EXPECT_EDITION,
  expected_edition_source: 'cli',
  round_facts: ['ROUND_FACT[BASELINE_EDITION]=H1.28', 'ROUND_FACT[EXPECTED_EDITION]=' + EXPECT_EDITION, 'ROUND_FACT[TAMPER_CASES_TOTAL]=' + (прогонObj ? прогонObj.tampers_total : 'MISSING'), 'ROUND_FACT[TAMPER_CASES_RANGE]=' + (прогонObj ? прогонObj.tamper_cases_range : 'MISSING'), 'ROUND_FACT[PG16_D05]=' + pg16Live],
  tamper_cases_range: прогонObj ? прогонObj.tamper_cases_range : null,
  manifest_sha256: суммаОписи,
  wrapper_sha256: sha(Buffer.from(обёрткаСДиска, 'utf8')),
  registry_check_exit: кодРеестр,
  semantic_check_exit: кодСмысл,
  tamper_run: итог,
  live_postgres_tests: pg16Live,
  project_context: 'PROJECT_CONTEXT.txt v1.7',
  project_context_sha256: 'aa657f02d2f8b4d7d33e928edfa2358f6e28dc0298d2b6af7d2127efdb00ebc9',
  pg16_evidence_format: 'EVIDENCE_PG16_D05_FORMAT_v1_0.md v1.0',
  pg16_evidence_format_sha256: '8e4285d75033a5133259f45c816cce717c2a2d69d3b5a851ad64435a2f0a1f45',
  c1_9_expected_sha256: 'f88fdb9d4ee6cd6ae3488360a8868b74492a7a91a94eb831f94616c5d5e0cd23',
  c1_9_sha256_source: 'contract_constant_not_measured_in_R49',
  pg16_evidence_sha256: pg16Sha,
  line_rule: 'число переводов строки; завершающий перевод пустой строки не добавляет',
  files: состав,
  problems: беды.slice(),
}, null, 2) + '\n';
console.log('  package_report.json: ' + положить('package_report.json', отчёт));

const опись = { package: PACKAGE, document: basename(DOC), document_sha256: sha(docBuf),
                note: 'каждый файл пакета, кроме самой описи; её сумму закрепляет малый манифест ответа',
                line_rule: 'число переводов строки; завершающий перевод пустой строки не добавляет',
                files: [] };
for (const f of состав.filter((x) => x !== 'package_manifest.json')) {
  const path = join(OUT, f);
  if (!existsSync(path)) { беды.push('нет файла для описи: ' + f); continue; }
  const buf = readFileSync(path);
  опись.files.push({ name: f, bytes: buf.length, sha256: sha(buf), lines: lineCount(buf.toString('utf8')) });
}
console.log('  package_manifest.json: ' + положить('package_manifest.json', JSON.stringify(опись, null, 2) + '\n'));

// --- Шаг 11. Лишнее в папке -----------------------------------------------
шаг(11, 'в папке нет ничего сверх состава');
for (const name of readdirSync(OUT)) {
  if (statSync(join(OUT, name)).isDirectory()) { беды.push('в папке пакета есть папка: ' + name); continue; }
  const why = badNameReason(name);
  if (why) беды.push('недопустимое имя (' + why + '): ' + name);
  if (!состав.includes(name)) беды.push('лишний файл в папке пакета: ' + name);
}

console.log('---');
console.log('файлов в составе: ' + состав.length);
console.log('сумма описи SQL: ' + суммаОписи);
if (existsSync(join(OUT, 'package_manifest.json'))) {
  console.log('сумма полной описи: ' + sha(readFileSync(join(OUT, 'package_manifest.json'))));
}
if (беды.length) {
  console.error('БЕД: ' + беды.length);
  for (const b of беды) console.error('  ' + b);
  process.exit(1);
}
console.log('ПАКЕТ СОБРАН И ПРОВЕРЕН');