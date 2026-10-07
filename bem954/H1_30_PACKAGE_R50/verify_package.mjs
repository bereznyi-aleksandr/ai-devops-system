// verify_package.mjs — проверка пакета H1.30.
// PASSPORT: ACTIVE vR50.1, раунд R50, H1.30.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R50 (РАУНД-R50-ПЕРЕНОС-ИМЁН: H1.30; логика программ в R47–R50 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.29/R49; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47, R49 и R50 — раздел 22.2, остальное — раздел 15.43.
// ИСТОРИЯ: прежний активный паспорт. Версия 1.2, раунд R33 (РАУНД-R33-ПЕРЕНОС-ИМЁН: имена
// H1.18 и пакета R33, прежний документ — H1.17; логика не менялась).
// Версия 1.1 — раунд R32 (РАУНД-R32-ПЕРЕНОС-ИМЁН: имена H1.17 и пакета
// R32, прежний документ — H1.16; логика не менялась). Версия 1.0 —
// раунд R31, замечания M-H115-R15-02 и L-H115-R15-01.
//
// Запуск из папки пакета:
//   node verify_package.mjs <путь к H1.30>
//   node verify_package.mjs <путь к H1.30> --previous <путь к H1.29>
//   node verify_package.mjs <путь к H1.30> --selftest
// Необязательно: --dir <папка пакета> (по умолчанию — папка этой
// программы), --work <папка> (по умолчанию — временная папка системы),
// --report <файл.json>, --no-rebuild (без повторной сборки).
//
// Проверка ничего в папке пакета не пишет и ничего нигде не удаляет.
// Повторная сборка и копии самопроверки ложатся в новые папки с
// уникальными именами внутри рабочей папки.
//
// Что проверяется, по пунктам 3.3 задания R31.
//   A. Состав папки против полной описи package_manifest.json: лишний,
//      пропущенный и изменённый файл — отказ (п. 8). Размер, сумма и
//      число строк сверяются у каждого файла.
//   B. Недопустимые имена: архивная, заменённая, временная, скрытая
//      копия, имя с точкой или пробелом в конце, вложенная папка — отказ
//      (п. 9 и 12). Правило одно для сборщика и для проверки.
//   C. Обязательный состав пакета из п. 3.3 на месте.
//   D. Состав из README, из отчёта, из описи и фактическая папка
//      совпадают до имени (п. 10).
//   E. migration_manifest.json защищает шесть файлов SQL, а обёртка
//      несёт сумму этой описи (п. 5).
//   F. Каждый файл, извлекаемый из документа, совпадает с файлом пакета
//      байт в байт; документ тот, на который ссылаются опись и отчёт.
//   G. Повторная сборка опубликованной командой в новую папку совпадает
//      с пакетом байт в байт по всем файлам (п. 1 и 11).
//   H. С ключом --previous: все строки реестра прежнего документа на
//      месте, новые строки уникальны; сумма прежнего документа равна
//      baseline_sha256 из package_report.json (H1.23, M-R42-01).
//   I. С ключом --selftest: копии пакета с внесённой неисправностью
//      обязаны быть отклонены проверками A–E, каждая — со своей
//      причиной, а точная копия обязана пройти.
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, existsSync, readdirSync,
         statSync, copyFileSync } from 'node:fs';
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
if (!DOC) { console.error('нужен путь к документу H1.30: node verify_package.mjs <путь>'); process.exit(2); }
const EXPECT_EDITION = argAfter('--expect-edition');
if (!EXPECT_EDITION) { console.error('обязателен --expect-edition H1.30'); process.exit(2); }
if (EXPECT_EDITION !== 'H1.30') { console.error('неверный --expect-edition: ' + EXPECT_EDITION + '; ожидается H1.30'); process.exit(2); }
const _passportText = readFileSync(DOC, 'utf8');
if (!/ВЕРСИЯ:\s*\r?\n\s*v1\.30(?:\s|$)/.test(_passportText)) { console.error('паспорт документа не H1.30'); process.exit(2); }
const DIR = resolve(argAfter('--dir') || HERE);
const WORK = resolve(argAfter('--work') || join(tmpdir(), 'bem954_verify_r38'));
const sha = (buf) => createHash('sha256').update(buf).digest('hex');

// Обязательный состав пакета, п. 3.3 задания R31.
// H1.24: улика живого прогона PG16_D05 входит в обязательный состав.
const PG16_EVIDENCE = 'EVIDENCE_PG16_D05.txt';
const REQUIRED = [...SQL_FILES, 'migration_manifest.json', 'run_migration.mjs',
  ...PROGRAMS.map(([f]) => f), 'tamper_report.json',
  'README_PACKAGE.md', 'package_report.json', 'package_manifest.json', PG16_EVIDENCE];

// --- A–E. Папка сама по себе ----------------------------------------------
// Возвращает список бед; пустой список — папка цела. Документ не нужен.
export function checkFolder(dir) {
  const беды = [];
  const имена = [];
  for (const name of readdirSync(dir).sort()) {
    if (statSync(join(dir, name)).isDirectory()) { беды.push('в папке пакета есть папка: ' + name); continue; }
    const why = badNameReason(name);
    if (why) беды.push('недопустимое имя (' + why + '): ' + name);
    имена.push(name);
  }
  // A. Опись.
  let опись = null;
  try { опись = JSON.parse(readFileSync(join(dir, 'package_manifest.json'), 'utf8')); }
  catch (e) { беды.push('нет описи package_manifest.json или она не читается'); return беды; }
  const записи = Array.isArray(опись.files) ? опись.files : [];
  const поОписи = new Map();
  for (const e of записи) {
    if (поОписи.has(e.name)) беды.push('имя повторено в описи: ' + e.name);
    поОписи.set(e.name, e);
  }
  if (поОписи.has('package_manifest.json')) беды.push('опись перечисляет сама себя');
  for (const name of имена) {
    if (name !== 'package_manifest.json' && !поОписи.has(name)) беды.push('лишний файл, которого нет в описи: ' + name);
  }
  for (const [name, e] of поОписи) {
    if (!имена.includes(name)) { беды.push('нет файла из описи: ' + name); continue; }
    const buf = readFileSync(join(dir, name));
    if (buf.length !== e.bytes || sha(buf) !== e.sha256) беды.push('файл изменён против описи: ' + name);
    if (lineCount(buf.toString('utf8')) !== e.lines) беды.push('число строк не совпадает с описью: ' + name);
  }
  // C. Обязательный состав.
  for (const name of REQUIRED) if (!имена.includes(name)) беды.push('нет обязательного файла пакета: ' + name);
  // D. README, отчёт, опись, папка.
  const папка = [...имена].sort().join('\n');
  const поОписиИмена = [...поОписи.keys(), 'package_manifest.json'].sort().join('\n');
  if (поОписиИмена !== папка) беды.push('состав описи расходится с папкой');
  try {
    const readme = readFileSync(join(dir, 'README_PACKAGE.md'), 'utf8').split('\n');
    const i = readme.indexOf('BEM954-PACKAGE-FILES-BEGIN');
    const j = readme.indexOf('BEM954-PACKAGE-FILES-END');
    if (i < 0 || j < i) беды.push('в README нет блока состава');
    else if (readme.slice(i + 1, j).sort().join('\n') !== папка) беды.push('состав README расходится с папкой');
  } catch (e) { беды.push('README_PACKAGE.md не читается'); }
  try {
    const отчёт = JSON.parse(readFileSync(join(dir, 'package_report.json'), 'utf8'));
    if ([...(отчёт.files || [])].sort().join('\n') !== папка) {
      беды.push('состав отчёта package_report.json расходится с папкой');
    }
    if (отчёт.problems && отчёт.problems.length) беды.push('отчёт сборки содержит беды: ' + отчёт.problems.length);
    if (отчёт.expected_edition !== 'H1.30' || отчёт.expected_edition_source !== 'cli') беды.push('package_report.json: expected_edition не H1.30/cli');
    // H1.23, M-R42-01: базовая редакция и её сумма сверяются парой.
    if (отчёт.baseline_edition !== 'H1.29' || отчёт.baseline_sha256 !== 'd50ffc15c63b9fc85947f3484ec7b530dd10f27d0b81c6a68ac834a4e93598ea') беды.push('package_report.json: базовая редакция не H1.29/d50ffc15');
    // H1.24, PG16_D05: живой прогон D-05 выполнен; его улика лежит в пакете,
    // и её сумма записана в отчёте сборки. Содержание улики против файла 01
    // и документа сверяет chk_round_facts.mjs (F2).
    if (отчёт.live_postgres_tests !== 'EXECUTED_PASS') беды.push('package_report.json: live_postgres_tests не EXECUTED_PASS');
    if (!/^[0-9a-f]{64}$/.test(String(отчёт.pg16_evidence_sha256 || ''))) беды.push('package_report.json: нет pg16_evidence_sha256');
    else if (!existsSync(join(dir, PG16_EVIDENCE)) || sha(readFileSync(join(dir, PG16_EVIDENCE))) !== отчёт.pg16_evidence_sha256) {
      беды.push('pg16 evidence: файл пакета не совпадает с pg16_evidence_sha256 отчёта');
    }
    const tr = отчёт.tamper_run;
    if (tr === undefined || tr === null) беды.push('package_report.json: tamper_run отсутствует');
    else if (typeof tr !== 'object' || Array.isArray(tr)) беды.push('package_report.json: tamper_run не объект');
    else {
      let tam = null;
      try { tam = JSON.parse(readFileSync(join(dir, 'tamper_report.json'), 'utf8')); }
      catch (e) { беды.push('tamper_report.json не читается для сверки tamper_run'); }
      if (tam) {
        if (tr.total !== tam.tampers_total || tr.as_expected !== tam.tampers_as_expected || tr.anchor_lost !== tam.tampers_anchor_lost) {
          беды.push('package_report.json: tamper_run числа не совпадают с tamper_report.json');
        }
        if (tr.total !== 247 || tr.as_expected !== 247 || tr.anchor_lost !== 0) беды.push('package_report.json: tamper_run не 247/247/0');
        if (tr.verdict !== tam.verdict) беды.push('package_report.json: tamper_run verdict не совпадает с tamper_report.json');
      }
      if (tr.verdict !== 'OK') беды.push('package_report.json: tamper_run verdict не OK');
    }
  } catch (e) { беды.push('package_report.json не читается'); }
  // E. Опись SQL и обёртка.
  try {
    const описьSql = readFileSync(join(dir, 'migration_manifest.json'));
    const m = JSON.parse(описьSql.toString('utf8'));
    if (Object.keys(m.files || {}).sort().join('\n') !== [...SQL_FILES].sort().join('\n')) {
      беды.push('migration_manifest.json перечисляет не те файлы SQL');
    }
    for (const f of SQL_FILES) {
      if (имена.includes(f) && sha(readFileSync(join(dir, f))) !== (m.files || {})[f]) {
        беды.push('файл SQL не совпадает с migration_manifest.json: ' + f);
      }
    }
    const обёртка = readFileSync(join(dir, 'run_migration.mjs'), 'utf8');
    const вшито = (обёртка.match(/const MANIFEST_SHA256 = '([0-9a-f]{64})';/) || [])[1];
    if (вшито !== sha(описьSql)) беды.push('обёртка несёт не ту сумму migration_manifest.json');
  } catch (e) { беды.push('опись SQL или обёртка не читаются'); }
  return беды;
}

// --- F. Папка против документа --------------------------------------------
function checkAgainstDoc(dir, docBuf) {
  const беды = [];
  const docSha = sha(docBuf);
  for (const f of ['package_manifest.json', 'package_report.json']) {
    try {
      if (JSON.parse(readFileSync(join(dir, f), 'utf8')).document_sha256 !== docSha) {
        беды.push(f + ' описывает другой документ');
      }
    } catch (e) { беды.push(f + ' не читается'); }
  }
  const { files, problems } = extract(docBuf.toString('utf8'));
  беды.push(...problems.map((p) => 'документ: ' + p));
  for (const [name, text] of files) {
    const path = join(dir, name);
    if (!existsSync(path)) { беды.push('нет файла, извлекаемого из документа: ' + name); continue; }
    let ждём = text;
    if (name === 'run_migration.mjs') {
      ждём = text.replace("const MANIFEST_SHA256 = '" + '0'.repeat(64) + "';",
        "const MANIFEST_SHA256 = '" + sha(readFileSync(join(dir, 'migration_manifest.json'))) + "';");
    }
    if (!readFileSync(path).equals(Buffer.from(ждём, 'utf8'))) беды.push('файл пакета не совпадает с документом: ' + name);
  }
  return беды;
}

// --- G. Повторная сборка --------------------------------------------------
function rebuild(dir) {
  mkdirSync(WORK, { recursive: true });
  const out = mkdtempSync(join(WORK, 'rebuild-'));
  const беды = [];
  try {
    execFileSync(NODE, [join(dir, 'build_package.mjs'), DOC, '--expect-edition', EXPECT_EDITION, '--out', out, '--work', join(out + '-tamper'),
                        '--pg16-evidence', join(dir, PG16_EVIDENCE)],
                 { encoding: 'utf8', maxBuffer: 1 << 26 });
  } catch (e) {
    беды.push('повторная сборка вернула ' + e.status);
  }
  const было = readdirSync(dir).sort();
  const стало = existsSync(out) ? readdirSync(out).sort() : [];
  if (было.join('\n') !== стало.join('\n')) беды.push('состав повторной сборки расходится с пакетом');
  let совпало = 0;
  for (const name of было) {
    if (!стало.includes(name)) continue;
    if (readFileSync(join(dir, name)).equals(readFileSync(join(out, name)))) совпало += 1;
    else беды.push('повторная сборка дала другие байты: ' + name);
  }
  return { беды, совпало, всего: было.length, папка: basename(out) };
}

// --- H. Строки реестра прежнего документа ---------------------------------
// Те же правила, что у сверщика реестра: раздел 15 без листингов,
// идентификатор — первый столбец строки таблицы. Строка реестра — только
// та, что кончается столбцом статуса: таблица раздела 15.18 тоже
// начинается с номера строки, но строкой реестра не является, и её
// номера — ссылки, а не повторы.
function registryIds(text) {
  const T = String.fromCharCode(96);
  const LISTING = new RegExp('^(' + T + '{4,})[^\\n]*\\n[\\s\\S]*?\\n\\1[ \\t]*(?=\\n|$)', 'gm');
  const STATUS = /`(DESIGNED_NOT_EXECUTED|EXECUTED_STATIC|EXECUTED_PACKAGE)` \|$/;
  const from = text.indexOf('\n# 15. ');
  const to = text.indexOf('\n# 16. ');
  if (from < 0 || to < from) return null;
  const ids = [];
  for (const line of text.slice(from, to).replace(LISTING, '').split('\n')) {
    if (!STATUS.test(line)) continue;
    const m = line.match(/^\|\s*`?(K[A-Z0-9-]*\d)`?\s*\|/)
      || line.match(/^\|\s*T\d+\s*\|\s*`?(K\d+)`?\s*\|/)
      || line.match(/^\|\s*DISP-\d+\s*\|\s*`?(KD\d+)`?\s*\|/);
    if (m) ids.push(m[1]);
  }
  return ids;
}

// --- I. Самопроверка ------------------------------------------------------
// Каждая копия лежит в своей новой папке. Причина отказа сверяется с
// ожидаемой: отказ по чужой причине — провал самопроверки.
function copyPackage(from, to, skip = []) {
  mkdirSync(to, { recursive: true });
  for (const name of readdirSync(from)) if (!skip.includes(name)) copyFileSync(join(from, name), join(to, name));
}
function rewriteEntry(dir, name, patch) {
  const path = join(dir, 'package_manifest.json');
  const m = JSON.parse(readFileSync(path, 'utf8'));
  for (const e of m.files) if (e.name === name) patch(e, readFileSync(join(dir, name)));
  writeFileSync(path, JSON.stringify(m, null, 2) + '\n');
}
function rewritePackageReport(dir, patch) {
  const p = join(dir, 'package_report.json');
  const obj = JSON.parse(readFileSync(p, 'utf8'));
  patch(obj);
  writeFileSync(p, JSON.stringify(obj, null, 2) + '\n');
  rewriteEntry(dir, 'package_report.json', (e, buf) => {
    e.bytes = buf.length; e.sha256 = sha(buf); e.lines = lineCount(buf.toString('utf8'));
  });
}
const FAULTS = [
  ['S00', 'точная копия пакета', null, () => {}],
  ['S01', 'лишний файл', 'лишний файл, которого нет в описи: notes.md',
    (d) => writeFileSync(join(d, 'notes.md'), 'черновик\n')],
  ['S02', 'пропущенный файл', 'нет файла из описи: 03_restore_verifier.sql', null, ['03_restore_verifier.sql']],
  ['S03', 'изменённый файл', 'файл изменён против описи: 00_cluster_bootstrap.sql',
    (d) => writeFileSync(join(d, '00_cluster_bootstrap.sql'), readFileSync(join(d, '00_cluster_bootstrap.sql'), 'utf8') + '-- правка\n')],
  ['S04', 'архивная копия', 'недопустимое имя (архивная или заменённая копия): build_package.R30-final.ARCHIVED.mjs',
    (d) => copyFileSync(join(d, 'build_package.mjs'), join(d, 'build_package.R30-final.ARCHIVED.mjs'))],
  ['S05', 'заменённая копия', 'недопустимое имя (архивная или заменённая копия): run_migration.mjs.SUPERSEDED-R30',
    (d) => copyFileSync(join(d, 'run_migration.mjs'), join(d, 'run_migration.mjs.SUPERSEDED-R30'))],
  ['S06', 'временный файл', 'недопустимое имя (временный файл): tamper_report.json.tmp',
    (d) => copyFileSync(join(d, 'tamper_report.json'), join(d, 'tamper_report.json.tmp'))],
  ['S07', 'имя с точкой в конце', 'недопустимое имя (имя кончается точкой или пробелом): README_PACKAGE.md.',
    (d) => copyFileSync(join(d, 'README_PACKAGE.md'), join(d, 'README_PACKAGE.md.'))],
  ['S08', 'вложенная папка', 'в папке пакета есть папка: old',
    (d) => mkdirSync(join(d, 'old'))],
  ['S09', 'число строк в описи неверно', 'число строк не совпадает с описью: README_PACKAGE.md',
    (d) => rewriteEntry(d, 'README_PACKAGE.md', (e) => { e.lines += 1; })],
  ['S10', 'состав README расходится с папкой', 'состав README расходится с папкой',
    (d) => {
      const p = join(d, 'README_PACKAGE.md');
      writeFileSync(p, readFileSync(p, 'utf8').replace('BEM954-PACKAGE-FILES-END', 'notes.md\nBEM954-PACKAGE-FILES-END'));
      rewriteEntry(d, 'README_PACKAGE.md', (e, buf) => {
        e.bytes = buf.length; e.sha256 = sha(buf); e.lines = lineCount(buf.toString('utf8'));
      });
    }],
  ['S11', 'опись SQL не совпадает с файлом', 'файл SQL не совпадает с migration_manifest.json: 01_database_migration.sql',
    (d) => {
      const p = join(d, 'migration_manifest.json');
      const m = JSON.parse(readFileSync(p, 'utf8'));
      m.files['01_database_migration.sql'] = '0'.repeat(64);
      writeFileSync(p, JSON.stringify(m, null, 2) + '\n');
      rewriteEntry(d, 'migration_manifest.json', (e, buf) => {
        e.bytes = buf.length; e.sha256 = sha(buf); e.lines = lineCount(buf.toString('utf8'));
      });
    }],
  ['S12', 'tamper_run отсутствует', 'package_report.json: tamper_run отсутствует',
    (d) => rewritePackageReport(d, (o) => { delete o.tamper_run; })],
  ['S13', 'tamper_run нет итога', 'package_report.json: tamper_run не объект',
    (d) => rewritePackageReport(d, (o) => { o.tamper_run = 'нет итога'; })],
  ['S14', 'tamper_run неверные числа', 'package_report.json: tamper_run числа не совпадают с tamper_report.json',
    (d) => rewritePackageReport(d, (o) => { o.tamper_run.total = 234; })],
  ['S15', 'tamper_run verdict не OK', 'package_report.json: tamper_run verdict не OK',
    (d) => rewritePackageReport(d, (o) => { o.tamper_run.verdict = 'ПРОВАЛ'; })],
  ['S16', 'сумма базовой редакции от другого документа', 'package_report.json: базовая редакция не H1.29/d50ffc15',
    (d) => rewritePackageReport(d, (o) => { o.baseline_sha256 = 'cad2131cd8be7907ae49b4ee5dbbc391d6a94e8af9fb3334dd707e4b8b03d338'; })],
  ['S17', 'имя базовой редакции неверно', 'package_report.json: базовая редакция не H1.29/d50ffc15',
    (d) => rewritePackageReport(d, (o) => { o.baseline_edition = 'H1.28'; })],
  ['S18', 'улика PG16_D05 изменена', 'pg16 evidence: файл пакета не совпадает с pg16_evidence_sha256 отчёта',
    (d) => {
      const p = join(d, PG16_EVIDENCE);
      writeFileSync(p, readFileSync(p, 'utf8').replace('FINAL_RESULT=PASS', 'FINAL_RESULT=FAIL'));
      rewriteEntry(d, PG16_EVIDENCE, (e, buf) => {
        e.bytes = buf.length; e.sha256 = sha(buf); e.lines = lineCount(buf.toString('utf8'));
      });
    }],
];
function selftest(dir) {
  mkdirSync(WORK, { recursive: true });
  const root = mkdtempSync(join(WORK, 'selftest-'));
  const rows = [];
  for (const [id, name, want, spoil, skip = []] of FAULTS) {
    const d = join(root, id);
    copyPackage(dir, d, skip);
    if (spoil) spoil(d);
    const беды = checkFolder(d);
    const ok = want === null ? беды.length === 0 : беды.includes(want);
    rows.push({ id, name, expect: want === null ? 'проходит' : 'отказ: ' + want,
                actual: беды.length === 0 ? 'проходит' : 'отказ: ' + (want && беды.includes(want) ? want : беды[0]),
                problems: беды.length, ok });
  }
  return rows;
}

// --- Прогон ---------------------------------------------------------------
const docBuf = readFileSync(DOC);
const итог = { tool: 'verify_package', passport: 'ACTIVE vR50.1, раунд R50, H1.30',
               package: basename(DIR), document: basename(DOC), document_sha256: sha(docBuf),
               expected_edition: EXPECT_EDITION, expected_edition_source: 'cli' };
const все = [];

const папка = checkFolder(DIR);
итог.folder_problems = папка;
все.push(...папка);
console.log('A–E. папка против описи, имён, README, отчёта и описи SQL: ' + (папка.length ? 'БЕД ' + папка.length : 'чисто'));

const док = checkAgainstDoc(DIR, docBuf);
итог.document_problems = док;
все.push(...док);
console.log('F. файлы пакета против документа: ' + (док.length ? 'БЕД ' + док.length : 'совпадают'));

try {
  execFileSync(NODE, [join(DIR, 'chk_round_facts.mjs'), DOC, join(DIR, 'tamper_report.json'), join(DIR, 'package_report.json'),
                      '--pg16-evidence', join(DIR, PG16_EVIDENCE)], { encoding: 'utf8' });
  итог.round_facts = 'OK';
  console.log('F2. ROUND_FACT: совпадают');
} catch (e) {
  const msg = ((e.stderr || e.stdout || '') + '').trim() || ('код ' + e.status);
  итог.round_facts = msg; все.push('ROUND_FACT: ' + msg); console.log('F2. ROUND_FACT: ПРОВАЛ');
}

if (!process.argv.includes('--no-rebuild')) {
  const r = rebuild(DIR);
  итог.rebuild = { files_equal: r.совпало, files_total: r.всего, problems: r.беды };
  все.push(...r.беды);
  console.log('G. повторная сборка: совпало ' + r.совпало + ' из ' + r.всего + (r.беды.length ? ', БЕД ' + r.беды.length : ''));
} else {
  итог.rebuild = 'не выполнялась: ключ --no-rebuild';
  console.log('G. повторная сборка пропущена ключом --no-rebuild');
}

const PREV = argAfter('--previous');
if (PREV) {
  const было = registryIds(readFileSync(PREV, 'utf8'));
  const стало = registryIds(docBuf.toString('utf8'));
  const беды = [];
  // H1.23, M-R42-01: --previous обязан быть документом из baseline_sha256 отчёта.
  let базаОтчёта = null;
  try { базаОтчёта = JSON.parse(readFileSync(join(DIR, 'package_report.json'), 'utf8')).baseline_sha256; } catch (e) { базаОтчёта = null; }
  if (sha(readFileSync(PREV)) !== базаОтчёта) беды.push('--previous не совпадает с baseline_sha256 отчёта');
  if (!было || !стало) беды.push('в одном из документов нет раздела 15');
  else {
    const setСтало = new Set(стало);
    const пропали = [...new Set(было)].filter((id) => !setСтало.has(id));
    const повторы = стало.filter((id, k) => стало.indexOf(id) !== k);
    const новые = [...setСтало].filter((id) => !new Set(было).has(id));
    if (пропали.length) беды.push('пропали прежние строки реестра: ' + пропали.join(', '));
    if (повторы.length) беды.push('строки реестра повторены: ' + [...new Set(повторы)].join(', '));
    итог.previous = { document: basename(PREV), previous_ids: new Set(было).size,
                      current_ids: setСтало.size, preserved: new Set(было).size - пропали.length,
                      new_ids: новые.sort(), duplicates: [...new Set(повторы)], problems: беды };
    console.log('H. строки реестра: было ' + new Set(было).size + ', сохранено ' + (new Set(было).size - пропали.length)
                + ', новых ' + новые.length + ', повторов ' + повторы.length);
  }
  все.push(...беды);
}

if (process.argv.includes('--selftest')) {
  const rows = selftest(DIR);
  итог.selftest = rows;
  for (const r of rows) {
    console.log('I. ' + r.id + ' ' + r.name + ': ждали «' + r.expect + '», получили «' + r.actual + '» — '
                + (r.ok ? 'верно' : 'НЕВЕРНО'));
    if (!r.ok) все.push('самопроверка ' + r.id + ' не дала ожидаемого результата');
  }
}

итог.problems = все;
итог.verdict = все.length ? 'ПРОВАЛ' : 'OK';
const at = argAfter('--report');
if (at) writeFileSync(at, JSON.stringify(итог, null, 2) + '\n');
for (const b of все) console.error('  ' + b);
console.log('итог: ' + итог.verdict);
process.exit(все.length ? 1 : 0);