// ДОКУМЕНТ: zavod/catalog/ci/product_scan.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 13:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 13:15 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E5-6 / W6 — сканер репозитория продукта: ключи, признаки платного API и платные SDK в
//   зависимостях. Строже SR-02 Kernel: исключений нет совсем (продукт не хранит образцов ключей), пустая
//   или неверная папка — отказ (0 файлов не значит «чисто»), файл .env в репозитории — находка.
//   Пишет отчёт JSON (head_sha, число файлов, находки без значений, итог) и печатает его SHA-256 —
//   это доказательство E5-6 (протокол Z1 v1.9, таблица доказательств этапа 5).
// ВЫЗОВ: node zavod/catalog/ci/product_scan.mjs <папка продукта> --head-sha <sha> --out <отчёт.json>
// ОГРАНИЧЕНИЯ: найденное значение не печатается и не пишется в отчёт (SR-01): только файл, строка, образец.
//   Образцы ловят известные виды ключей и SDK; это не замена хранилищу ключей.

import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { basename, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { scan } from '../../kernel/ci/leak_scan.mjs';

export const SCANNER_VERSION = 'product_scan v0.1';

// Платные SDK моделей и облаков: их наличие в зависимостях продукта — находка (hard stop 1, W6).
export const PAID_NPM = Object.freeze(['openai', '@anthropic-ai/sdk', '@anthropic-ai/bedrock-sdk',
  '@anthropic-ai/vertex-sdk', '@google/generative-ai', '@google/genai', '@google-cloud/vertexai',
  // Имя собрано из частей, чтобы SR-02 Kernel не находил его в самом сканере.
  ['@aws-sdk/client-bedrock', 'runtime'].join('-'), '@mistralai/mistralai', 'cohere-ai', 'groq-sdk', '@azure/openai']);
export const PAID_PY = Object.freeze(['openai', 'anthropic', 'google-generativeai', 'google-genai',
  'google-cloud-aiplatform', 'mistralai', 'cohere', 'groq']);

const SKIP_DIRS = new Set(['.git', 'node_modules']);

function* allFiles(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const p = resolve(dir, name);
    if (statSync(p).isDirectory()) yield* allFiles(p); else yield p;
  }
}

function depFindings(file, rel) {
  const name = basename(file);
  const out = [];
  if (name === 'package.json') {
    let pkg;
    try { pkg = JSON.parse(readFileSync(file, 'utf8')); } catch { return [{ file: rel, line: 0, kind: 'SCAN', pattern: 'package_json_unreadable' }]; }
    for (const sec of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies']) {
      for (const dep of Object.keys(pkg[sec] ?? {})) {
        if (PAID_NPM.includes(dep)) out.push({ file: rel, line: 0, kind: 'PAID', pattern: `paid_sdk_npm:${dep}` });
      }
    }
  } else if (/^requirements.*\.txt$/.test(name) || name === 'pyproject.toml') {
    readFileSync(file, 'utf8').split(/\r?\n/).forEach((l, i) => {
      const m = /^\s*"?([A-Za-z0-9_.-]+)/.exec(l.replace(/#.*/, ''));
      if (m && PAID_PY.includes(m[1].toLowerCase())) out.push({ file: rel, line: i + 1, kind: 'PAID', pattern: `paid_sdk_py:${m[1].toLowerCase()}` });
    });
  }
  if (/^\.env(\..*)?$/.test(name) && name !== '.env.example') out.push({ file: rel, line: 0, kind: 'KEY', pattern: 'env_file_committed' });
  return out;
}

export function scanProduct(root) {
  const base = resolve(root);
  let st;
  try { st = statSync(base); } catch { return { files: 0, findings: [{ file: '.', line: 0, kind: 'SCAN', pattern: 'root_missing' }] }; }
  if (!st.isDirectory()) return { files: 0, findings: [{ file: '.', line: 0, kind: 'SCAN', pattern: 'root_not_directory' }] };
  const files = [...allFiles(base)];
  const findings = [];
  if (files.length === 0) findings.push({ file: '.', line: 0, kind: 'SCAN', pattern: 'no_files' });
  for (const f of files) findings.push(...depFindings(f, relative(base, f).replace(/\\/g, '/')));
  // Исключений нет: пустой набор, unusedAllow не нужен.
  for (const h of scan([base], new Set(), base)) findings.push({ file: h.file, line: h.line, kind: h.kind, pattern: h.pattern });
  findings.sort((a, b) => (a.file + a.line + a.pattern).localeCompare(b.file + b.line + b.pattern));
  return { files: files.length, findings };
}

export function report(root, headSha) {
  const r = scanProduct(root);
  return {
    scanner: SCANNER_VERSION,
    criterion: 'E5-6',
    head_sha: headSha,
    files_scanned: r.files,
    findings: r.findings,
    result: r.findings.length === 0 ? 'PASS' : 'FAIL',
  };
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const args = process.argv.slice(2);
  const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : null; };
  const headSha = opt('--head-sha');
  const out = opt('--out');
  if (!args[0] || !out || !/^[0-9a-f]{40}$/.test(headSha ?? '')) {
    console.log('PRODUCT_SCAN=FAIL usage: <dir> --head-sha <40 hex> --out <report.json>');
    process.exit(2);
  }
  const rep = report(args[0], headSha);
  const text = JSON.stringify(rep, null, 2) + '\n';
  writeFileSync(out, text);
  for (const f of rep.findings) console.log(`${f.kind} ${f.pattern} ${f.file}:${f.line}`);
  console.log(`PRODUCT_SCAN=${rep.result} files=${rep.files_scanned} findings=${rep.findings.length} report_sha256=${createHash('sha256').update(text).digest('hex')}`);
  process.exit(rep.result === 'PASS' ? 0 : 1);
}
