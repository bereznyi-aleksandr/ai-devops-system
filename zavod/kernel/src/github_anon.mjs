// ДОКУМЕНТ: src/github_anon.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 13:52 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 13:52 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.2 §4.B (D5) — чтение открытого GitHub API без входа для
//   проверки правил (src/rules_gate.mjs, параметр gh) под учётной записью zavod-kernel: у неё нет и не будет
//   входа в GitHub. Хранилище публичное. Разрешены только три вида путей, которые зовёт rules_gate; защита ветки
//   main берётся из открытого ответа repos/<repo>/branches/main. Нет данных или ответ не 200 — исключение (отказ).
// ОГРАНИЧЕНИЯ: синхронный вызов (rules_gate синхронный): запрос делает дочерний node этого же файла с пустым
//   окружением — переменные с ключами GitHub в него не попадают. Перенаправления не выполняются.

import https from 'node:https';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const GITHUB_API = 'https://api.github.com/';
const REPO = '[A-Za-z0-9_.-]+\\/[A-Za-z0-9_.-]+';
const PROTECTION = new RegExp(`^repos\\/(${REPO})\\/branches\\/main\\/protection\\/required_status_checks$`);
const ALLOWED = [
  new RegExp(`^repos\\/${REPO}\\/pulls\\/[1-9][0-9]{0,8}$`),
  new RegExp(`^repos\\/${REPO}\\/commits\\/[0-9a-f]{40}\\/check-runs\\?per_page=100$`),
  new RegExp(`^repos\\/${REPO}\\/branches\\/main$`),
];
const SELF = fileURLToPath(import.meta.url);

export class GithubAnonError extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.code = code; }
}

// Один запрос в дочернем процессе: путь проверяется до запуска, окружение пустое (кроме SystemRoot для сети Windows).
export function fetchJsonSync(path, { timeoutMs = 20_000 } = {}) {
  if (!ALLOWED.some((r) => r.test(path))) throw new GithubAnonError('GITHUB_PATH_NOT_ALLOWED', path);
  let out;
  try {
    out = execFileSync(process.execPath, [SELF, path], { encoding: 'utf8', windowsHide: true, timeout: timeoutMs,
      maxBuffer: 16 << 20, env: process.env.SystemRoot ? { SystemRoot: process.env.SystemRoot } : {} });
  } catch (e) {
    throw new GithubAnonError('GITHUB_FETCH_FAILED', String(e?.stderr || e?.code || 'error').trim().slice(0, 120));
  }
  try { return JSON.parse(out); } catch { throw new GithubAnonError('GITHUB_BAD_JSON', path); }
}

// gh для createRulesGate: тот же интерфейс, что defaultGh (путь API -> разобранный JSON).
export function anonGh({ fetchJson = fetchJsonSync } = {}) {
  return (path) => {
    const m = PROTECTION.exec(path);
    if (m) {
      const b = fetchJson(`repos/${m[1]}/branches/main`);
      const rsc = b && b.protection && b.protection.required_status_checks;
      if (b?.protected !== true || !rsc || !Array.isArray(rsc.checks)) {
        throw new GithubAnonError('GITHUB_PROTECTION_UNAVAILABLE', m[1]);
      }
      return rsc;
    }
    if (!ALLOWED.some((r) => r.test(path))) throw new GithubAnonError('GITHUB_PATH_NOT_ALLOWED', path);
    return fetchJson(path);
  };
}

// Дочерний процесс: GET без заголовка Authorization; только код 200 и JSON; иначе код выхода 2.
function childMain(path) {
  const req = https.get(GITHUB_API + path, { headers: { 'user-agent': 'zavod-kernel',
    accept: 'application/vnd.github+json', 'x-github-api-version': '2022-11-28' }, timeout: 15_000 }, (res) => {
    const chunks = [];
    res.on('data', (c) => chunks.push(c));
    res.on('end', () => {
      if (res.statusCode !== 200) { process.stderr.write(`HTTP_${res.statusCode}`); process.exit(2); }
      process.stdout.write(Buffer.concat(chunks));
    });
  });
  req.on('timeout', () => { req.destroy(); process.stderr.write('TIMEOUT'); process.exit(2); });
  req.on('error', (e) => { process.stderr.write(String(e.code || 'NET')); process.exit(2); });
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const path = process.argv[2] || '';
  if (!ALLOWED.some((r) => r.test(path))) { process.stderr.write('PATH_NOT_ALLOWED'); process.exit(2); }
  childMain(path);
}
