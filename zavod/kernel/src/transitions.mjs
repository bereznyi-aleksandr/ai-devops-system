// ДОКУМЕНТ: src/transitions.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:25 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: единственная таблица допустимых переходов работы Завода (H1.31 §8.5:
//   «таблица хранится в коде Kernel как единственный источник и передаётся в p_allowed_from»).
// ОГРАНИЧЕНИЯ: статусы — жизненный цикл протокола Z1 §7; изменение таблицы = новая версия файла.

export const INITIAL_STATUS = 'NEW';

// откуда → куда
const EDGES = Object.freeze({
  NEW:         ['PLANNED', 'CANCELLED'],
  PLANNED:     ['IN_PROGRESS', 'BLOCKED', 'CANCELLED'],
  IN_PROGRESS: ['IN_REVIEW', 'BLOCKED', 'CANCELLED'],
  IN_REVIEW:   ['IN_PROGRESS', 'ACCEPTED', 'BLOCKED'],
  ACCEPTED:    ['RELEASED'],
  BLOCKED:     ['PLANNED', 'CANCELLED'],
  RELEASED:    [],
  CANCELLED:   [],
});

export const STATUSES = Object.freeze(Object.keys(EDGES));

// Список исходных статусов, из которых можно попасть в newStatus.
// Пустой список — такого перехода нет; Kernel отказывает до базы.
export function allowedFrom(newStatus) {
  return STATUSES.filter((s) => EDGES[s].includes(newStatus)).sort();
}

export function isAllowed(from, to) {
  return Boolean(EDGES[from]) && EDGES[from].includes(to);
}
