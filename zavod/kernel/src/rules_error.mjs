// ДОКУМЕНТ: src/rules_error.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 00:15 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 00:15 +03:00 (v0.1: вынесено из rules_gate.mjs)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: класс отказа проверок правил. Отдельный файл, чтобы kernel.mjs не тянул rules_gate.mjs и
//   engine/src/sshsig.mjs: контейнер рабочего (src/fencer.mjs) видит только папку zavod/kernel.

export class RulesError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}
