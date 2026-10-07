// ДОКУМЕНТ: ci/leak_scan.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:25 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: SR-02 — сканер утечек ключей и признаков платного API для CI любого репозитория Завода.
//   Код возврата 1 при находке — слияние запрещено. Найденное значение НЕ печатается:
//   только файл, строка и имя образца (SR-01).
// ВЫЗОВ: node ci/leak_scan.mjs <корень> [--allow <файл-исключений>]
// ОГРАНИЧЕНИЯ: образцы ловят известные виды ключей; это не замена хранилищу ключей.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { SECRET_PATTERNS } from '../src/guards.mjs';

// Признаки платного маршрута (hard stop 1): прямые вызовы API по ключу.
export const PAID_PATTERNS = Object.freeze([
  ['anthropic_api_host', /api\.anthropic\.com/],
  ['openai_api_host',    /api\.openai\.com/],
  ['anthropic_key_env',  /\bANTHROPIC_API_KEY\b/],
  ['openai_key_env',     /\bOPENAI_API_KEY\b/],
  ['bedrock_vertex',     /\b(?:bedrock-runtime|aiplatform\.googleapis\.com)\b/],
  ['claude_bare_mode',   /claude[^\n]{0,40}--bare\b/],
]);

const SKIP_DIRS = new Set(['.git', 'node_modules', 'dist', 'build', '.cache']);
const TEXT_EXT = new Set(['', '.js', '.mjs', '.cjs', '.ts', '.json', '.yml', '.yaml', '.md', '.txt', '.sh',
  '.ps1', '.cmd', '.bat', '.sql', '.py', '.toml', '.ini', '.env', '.cfg', '.conf', '.xml', '.html', '.css']);

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) yield* walk(p);
    else if (st.size < 2_000_000 && TEXT_EXT.has(extname(name).toLowerCase())) yield p;
  }
}

// allow: строки вида «путь|образец» или «путь|*» — осознанные исключения (файлы с описанием образцов).
export function scan(root, allow = new Set()) {
  const hits = [];
  for (const file of walk(root)) {
    const rel = relative(root, file).replace(/\\/g, '/');
    const lines = readFileSync(file, 'utf8').split(/\r?\n/);
    lines.forEach((line, i) => {
      for (const [kind, set] of [['KEY', SECRET_PATTERNS], ['PAID', PAID_PATTERNS]]) {
        for (const [name, re] of set) {
          if (re.test(line) && !allow.has(`${rel}|${name}`) && !allow.has(`${rel}|*`)) {
            hits.push({ file: rel, line: i + 1, kind, pattern: name });
          }
        }
      }
    });
  }
  return hits;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const root = process.argv[2] || '.';
  const ai = process.argv.indexOf('--allow');
  const allow = new Set();
  if (ai > 0) {
    for (const l of readFileSync(process.argv[ai + 1], 'utf8').split(/\r?\n/)) {
      const t = l.trim();
      if (t && !t.startsWith('#')) allow.add(t);
    }
  }
  const hits = scan(root, allow);
  for (const h of hits) console.log(`${h.kind} ${h.pattern} ${h.file}:${h.line}`);
  console.log(hits.length ? `LEAK_SCAN=FAIL (${hits.length})` : 'LEAK_SCAN=PASS');
  process.exit(hits.length ? 1 : 0);
}
