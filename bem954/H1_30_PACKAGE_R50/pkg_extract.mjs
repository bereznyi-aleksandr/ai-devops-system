// pkg_extract.mjs — извлечение файлов пакета из документа H1.30.
// PASSPORT: ACTIVE vR50.1, раунд R50, H1.30.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R50 (РАУНД-R50-ПЕРЕНОС-ИМЁН: H1.30; логика программ в R47–R50 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.29/R49; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47, R49 и R50 — раздел 22.2, остальное — раздел 15.43.
// ИСТОРИЯ: прежний активный паспорт. Версия 2.2, раунд R33 (РАУНД-R33-ПЕРЕНОС-ИМЁН: метки
// программ H1-18, имя документа H1.20; логика не менялась). Версия 2.1 —
// раунд R32 (РАУНД-R32-ПЕРЕНОС-ИМЁН: метки программ H1-17, имя
// документа H1.17; логика не менялась). Версия 2.0 —
// раунд R31, замечание M-H115-R15-02. Версия 1.0 — раунд R30,
// замечание M-H114-R14-03.
//
// Достаёт из документа ровно то, из чего собирается пакет:
//   - шесть канонических файлов SQL — теми же правилами, какими канон
//     читает смысловой сверщик: те же ограды, тот же диапазон разделов
//     25–27, те же финальные маркеры;
//   - обёртку запуска run_migration.mjs — блок js раздела 25;
//   - восемь программ — из помеченных областей листингов раздела 15.
// Пакет становится чистой функцией документа: один документ — один пакет.
//
// Что изменилось против версии 1.0 и зачем.
//   1. Извлечение — функция extract(), её вызывает сборщик. Прежде
//      сборщик запускал этот файл отдельным процессом через зашитый путь
//      к node автора, и на другой машине сборка не шла.
//   2. SQL вне всякого файла больше не пишется файлом-«хвостом»: это
//      отказ. Прежняя версия клала такой SQL в файл со служебным именем, и
//      он оказывался в поставке (замечание M-H115-R15-02).
//   3. Программы тоже достаются отсюда. Раньше их доставал сборщик своим
//      кодом, и правила извлечения были в двух местах.
//
// Запуск отдельно: node pkg_extract.mjs <документ>   — печатает состав.
// Ничего не пишет: запись — дело сборщика.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const TICK = String.fromCharCode(96);

export const SQL_FILES = ['00_cluster_bootstrap.sql', '01_database_migration.sql',
                          '02_upgrade_to_h110.sql', '03_restore_verifier.sql',
                          '04_backup_window.sql', '05_final_state_check.sql'];
// Программы пакета и метки их листингов в документе. Листинг — это файл
// целиком, байт в байт; первая и последняя строки области — ограда.
export const PROGRAMS = [
  ['bem954_registry_check.mjs', 'BEM954-PACKAGE-REGISTRY-LISTING'],
  ['bem954_semantic_check.mjs', 'BEM954-PACKAGE-SEMANTIC-LISTING'],
  ['chk_tamper28.mjs',          'BEM954-PACKAGE-TAMPER-SUITE-LISTING'],
  ['tamper_manifest28.mjs',     'BEM954-PACKAGE-TAMPER-MANIFEST'],
  ['pkg_extract.mjs',           'BEM954-PACKAGE-PKG-EXTRACT-LISTING'],
  ['build_package.mjs',         'BEM954-PACKAGE-BUILD-PACKAGE-LISTING'],
  ['verify_package.mjs',        'BEM954-PACKAGE-VERIFY-PACKAGE-LISTING'],
  ['chk_round_facts.mjs',        'BEM954-PACKAGE-ROUND-FACTS-LISTING'],
];

function fencedBlocks(text) {
  const out = [];
  let pos = 0, big = null, small = null;
  for (const line of text.split('\n')) {
    const here = pos;
    pos += line.length + 1;
    const f = line.match(new RegExp('^(' + TICK + '{3,})(.*)$'));
    if (!f) continue;
    if (f[1].length >= 4) {
      if (big === null) big = f[1].length; else if (f[1].length === big) big = null;
      continue;
    }
    if (big !== null) continue;
    if (small === null) small = { lang: f[2].trim(), at: here + line.length + 1 };
    else { out.push({ lang: small.lang, at: small.at, text: text.slice(small.at, here) }); small = null; }
  }
  return out;
}

// Возвращает { files: Map имя -> текст, problems: [] }. Ничего не пишет.
export function extract(doc) {
  const problems = [];
  const files = new Map();
  const headings = [];
  for (const m of doc.matchAll(/\n# (\d+)\. /g)) headings.push({ n: Number(m[1]), at: m.index + 1 });
  const start = headings.find((h) => h.n === 25);
  const after = headings.find((h) => h.n >= 28);
  if (!start) return { files, problems: ['в документе нет раздела 25'] };
  const canonFrom = start.at;
  const canonTo = after ? after.at : doc.length;

  const blocks = fencedBlocks(doc);
  const inCanon = (b) => b.at >= canonFrom && b.at < canonTo;
  const sqlBlocks = blocks.filter((b) => b.lang === 'sql' && inCanon(b));
  const js = blocks.filter((b) => (b.lang === 'js' || b.lang === 'javascript') && inCanon(b));

  // Канон режется по финальным маркерам: строка маркера называет файл, к
  // которому относится всё от предыдущего маркера до неё. Сама строка
  // маркера в файл входит — на диске она его последняя значимая строка.
  let buf = [];
  for (const b of sqlBlocks) {
    buf.push(b.text);
    const m = b.text.match(/^--\s*BEM954-FINAL-SECURITY-CHECKPOINT:\s*(\S+)\s*$/m);
    if (m) {
      if (files.has(m[1])) problems.push('маркер файла повторён: ' + m[1]);
      files.set(m[1], buf.join('\n') + '\n');
      buf = [];
    }
  }
  if (buf.join('').trim()) problems.push('в каноне есть SQL после последнего маркера, не относящийся ни к одному файлу');
  for (const f of files.keys()) if (!SQL_FILES.includes(f)) problems.push('лишний файл SQL в каноне: ' + f);
  for (const f of SQL_FILES) if (!files.has(f)) problems.push('в каноне нет файла ' + f);

  // Обёртка лежит отдельным блоком js в разделе 25.
  const wrappers = js.filter((b) => b.text.includes('MANIFEST_SHA256'));
  if (wrappers.length !== 1) problems.push('блоков обёртки с MANIFEST_SHA256 в каноне ' + wrappers.length + ' вместо одного');
  else files.set('run_migration.mjs', wrappers[0].text.endsWith('\n') ? wrappers[0].text : wrappers[0].text + '\n');

  // Программы — из помеченных областей листингов.
  const lines = doc.split('\n');
  for (const [file, mark] of PROGRAMS) {
    const open = lines.map((l, k) => (l.trim() === mark + '-BEGIN' ? k : -1)).filter((k) => k >= 0);
    const close = lines.map((l, k) => (l.trim() === mark + '-END' ? k : -1)).filter((k) => k >= 0);
    if (open.length !== 1 || close.length !== 1 || close[0] <= open[0] + 1) {
      problems.push('в документе нет ровно одной области ' + mark);
      continue;
    }
    files.set(file, lines.slice(open[0] + 2, close[0] - 1).join('\n'));
  }
  return { files, problems };
}

// Одно правило подсчёта строк для всего пакета (замечание L-H115-R15-01):
// число переводов строки, и ещё одна, если после последнего перевода
// что-то есть. Завершающий перевод строки не добавляет пустую строку.
export const lineCount = (text) => (text.match(/\n/g) || []).length
  + (text.length > 0 && !text.endsWith('\n') ? 1 : 0);

// Имена, которых в поставке быть не может (замечание M-H115-R15-02, пункты
// 9 и 12 задания R31). Пакет R30 содержал копии SUPERSEDED, «хвост» с
// пометкой ARCHIVED и имена с точкой в конце: Windows такое имя
// показывает, а обычными средствами не открывает и не копирует.
// Возвращает причину или null. Одно правило для сборщика и для проверки.
export function badNameReason(name) {
  if (/[. ]$/.test(name)) return 'имя кончается точкой или пробелом';
  if (/ARCHIVED|SUPERSEDED|DEPRECATED|FIRSTRUN/i.test(name)) return 'архивная или заменённая копия';
  if (/(^|[._-])(tmp|temp)([._-]|$)|\.bak$|~$|^~/i.test(name)) return 'временный файл';
  if (name.startsWith('.')) return 'скрытый файл';
  return null;
}

const self = resolve(fileURLToPath(import.meta.url)).toLowerCase();
if (process.argv[1] && resolve(process.argv[1]).toLowerCase() === self) {
  const file = process.argv[2];
  if (!file) { console.error('нужен путь к документу H1.30'); process.exit(2); }
  const { files, problems } = extract(readFileSync(file, 'utf8'));
  for (const [name, text] of files) {
    const b = Buffer.from(text, 'utf8');
    console.log(name.padEnd(28) + String(b.length).padStart(8) + '  '
      + createHash('sha256').update(b).digest('hex').slice(0, 16) + '  строк ' + lineCount(text));
  }
  for (const p of problems) console.log('БЕДА: ' + p);
  process.exit(problems.length ? 1 : 0);
}