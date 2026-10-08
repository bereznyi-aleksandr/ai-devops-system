// ДОКУМЕНТ: src/guards.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 22:46 +03:00 (v0.2: аудит E3-5 M-E35-05 —
//   SR-10 закрыт по умолчанию: нет пути, ошибка чтения, пусто или неизвестный текст — STOP; работа только при RUN)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверки до базы — SR-01 (секрет в команде), SR-10 (выключатель).
// ОГРАНИЧЕНИЯ: поиск секретов по образцам ловит известные виды ключей, а не любой секрет.
//   Найденное значение никогда не печатается и не пишется — только имя образца.

import { readFileSync } from 'node:fs';

// Имя образца → выражение. Значения не логируются (SR-01).
export const SECRET_PATTERNS = Object.freeze([
  ['anthropic_key',   /sk-ant-[A-Za-z0-9_-]{20,}/],
  ['openai_key',      /sk-(?:proj-)?[A-Za-z0-9_-]{32,}/],
  ['github_token',    /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}/],
  ['github_pat',      /github_pat_[A-Za-z0-9_]{40,}/],
  ['aws_access_key',  /\bAKIA[0-9A-Z]{16}\b/],
  ['slack_token',     /\bxox[abprs]-[A-Za-z0-9-]{10,}/],
  ['telegram_token',  /\b\d{8,10}:[A-Za-z0-9_-]{35}\b/],
  ['private_key',     /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/],
  ['jwt',             /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/],
  ['password_field',  /"(?:password|passwd|secret|api_key|apikey|access_token|refresh_token)"\s*:\s*"[^"]{4,}"/i],
]);

// Возвращает имя первого найденного образца или null.
export function findSecret(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value ?? null);
  for (const [name, re] of SECRET_PATTERNS) {
    if (re.test(text)) return name;
  }
  return null;
}

// SR-10. Стоп-файл: первая непустая строка «RUN» — приём команд открыт, «STOP» — закрыт.
// Всё прочее закрывает приём (аудит E3-5 M-E35-05): путь не задан, файл не читается
// (ENOENT, EACCES, EISDIR и любая другая ошибка), файл пуст, первая строка не RUN и не STOP.
// Снятие остановки — перезапись строкой «RUN» (файл не удаляется, правило P4.702).
// reason: RUN | STOP | NO_STOP_FILE | STOP_FILE_UNREADABLE | STOP_FILE_UNKNOWN.
export function stopState(stopFile) {
  if (typeof stopFile !== 'string' || !stopFile.trim()) return { stopped: true, reason: 'NO_STOP_FILE' };
  let text;
  try { text = readFileSync(stopFile, 'utf8'); } catch (e) {
    return { stopped: true, reason: 'STOP_FILE_UNREADABLE', errno: String(e?.code || 'ERROR') };
  }
  const first = (text.split(/\r?\n/).map((s) => s.trim()).find(Boolean) || '').toUpperCase();
  if (first === 'RUN') return { stopped: false, reason: 'RUN' };
  if (first === 'STOP') return { stopped: true, reason: 'STOP' };
  return { stopped: true, reason: 'STOP_FILE_UNKNOWN' };
}

export function isStopped(stopFile) { return stopState(stopFile).stopped; }
