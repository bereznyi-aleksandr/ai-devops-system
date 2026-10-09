// ДОКУМЕНТ: ci/leak_scan.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 23:00 +03:00 (v0.2: аудит E3-5 M-E35-04 —
//   исключение только для точной строки: «путь|образец|SHA-256 строки»; исключение целого файла
//   («путь|*») и неполная запись — отказ сканера; несколько целей, в CI — и workflow;
//   --strict-allow: неиспользованное исключение — отказ)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: SR-02 — сканер утечек ключей и признаков платного API для CI любого репозитория Завода.
//   Код возврата 1 при находке — слияние запрещено. Найденное значение НЕ печатается:
//   только файл, строка и имя образца (SR-01).
// ВЫЗОВ: node ci/leak_scan.mjs <цель>... [--base <папка>] [--allow <файл-исключений>] [--strict-allow]
//   Цель — папка или файл. Пути в исключениях считаются от --base (по умолчанию текущая папка).
// ОГРАНИЧЕНИЯ: образцы ловят известные виды ключей; это не замена хранилищу ключей.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, relative, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { SECRET_PATTERNS } from '../src/guards.mjs';

// Признаки платного маршрута (hard stop 1): прямые вызовы API по ключу.
export const PAID_PATTERNS = Object.freeze([
  ['anthropic_api_host', /api\.anthropic\.com/],
  ['openai_api_host',    /api\.openai\.com/],
  ['anthropic_key_env',  /\bANTHROPIC_API_KEY\b/],
  ['openai_key_env',     /\bOPENAI_API_KEY\b/],
  // Записи ниже составлены так, чтобы не совпадать сами с собой ([-] вместо «-»): исключений нет.
  ['bedrock_vertex',     /\b(?:bedrock[-]runtime|aiplatform\.googleapis\.com)\b/],
  ['claude_bare_mode',   /claude[^\n]{0,40}-[-]bare\b/],
]);

const SKIP_DIRS = new Set(['.git', 'node_modules', 'dist', 'build', '.cache']);
const TEXT_EXT = new Set(['', '.js', '.mjs', '.cjs', '.ts', '.json', '.yml', '.yaml', '.md', '.txt', '.sh',
  '.ps1', '.cmd', '.bat', '.sql', '.py', '.toml', '.ini', '.env', '.cfg', '.conf', '.xml', '.html', '.css']);

function* walk(dir) {
  if (statSync(dir).isFile()) { yield dir; return; }
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) yield* walk(p);
    else if (st.size < 2_000_000 && TEXT_EXT.has(extname(name).toLowerCase())) yield p;
  }
}

export const lineHash = (line) => createHash('sha256').update(line, 'utf8').digest('hex');

// Исключение — ровно «путь|образец|sha256 строки». Подстановок нет: правка строки, добавление
// второй такой строки или ключ в другом месте файла исключением не покрываются.
const ALLOW_RE = /^[^|*\s]+\|[a-z_]+\|[0-9a-f]{64}$/;
export function parseAllow(text) {
  const allow = new Set();
  for (const l of text.split(/\r?\n/)) {
    const t = l.trim();
    if (!t || t.startsWith('#')) continue;
    if (!ALLOW_RE.test(t)) throw new Error(`ALLOW_ENTRY_INVALID: ${t.split('|').slice(0, 2).join('|')}`);
    allow.add(t);
  }
  return allow;
}

// targets — папки или файлы; base — откуда считаются пути в отчёте и исключениях.
export function scan(targets, allow = new Set(), base = process.cwd()) {
  const hits = [];
  const used = new Set();
  for (const target of [].concat(targets)) {
    for (const file of walk(target)) {
      const rel = relative(base, file).replace(/\\/g, '/');
      const lines = readFileSync(file, 'utf8').split(/\r?\n/);
      lines.forEach((line, i) => {
        for (const [kind, set] of [['KEY', SECRET_PATTERNS], ['PAID', PAID_PATTERNS]]) {
          for (const [name, re] of set) {
            if (!re.test(line)) continue;
            const key = `${rel}|${name}|${lineHash(line)}`;
            if (allow.has(key)) { used.add(key); continue; }
            hits.push({ file: rel, line: i + 1, kind, pattern: name });
          }
        }
      });
    }
  }
  return Object.assign(hits, { unusedAllow: [...allow].filter((k) => !used.has(k)) });
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const args = process.argv.slice(2);
  const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args.splice(i, 2)[1] : null; };
  const strict = args.includes('--strict-allow');
  if (strict) args.splice(args.indexOf('--strict-allow'), 1);
  const allowFile = opt('--allow');
  const base = resolve(opt('--base') || '.');
  let allow = new Set();
  try { if (allowFile) allow = parseAllow(readFileSync(allowFile, 'utf8')); } catch (e) {
    console.log(`LEAK_SCAN=FAIL ${String(e.message).slice(0, 200)}`);
    process.exit(2);
  }
  const hits = scan(args.length ? args : ['.'], allow, base);
  for (const h of hits) console.log(`${h.kind} ${h.pattern} ${h.file}:${h.line}`);
  const stale = strict ? hits.unusedAllow : [];
  for (const k of stale) console.log(`ALLOW_UNUSED ${k.split('|').slice(0, 2).join('|')}`);
  const bad = hits.length + stale.length;
  console.log(bad ? `LEAK_SCAN=FAIL (${hits.length} hits, ${stale.length} unused allow)` : 'LEAK_SCAN=PASS');
  process.exit(bad ? 1 : 0);
}
