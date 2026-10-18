// ДОКУМЕНТ: src/roles.mjs
// ВЕРСИЯ: v0.3  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-09 07:00 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-17 23:51 +03:00 (v0.3: пакет Z-RULES-01 —
//   ActivateRules, GetActiveRules, GetChatLease у всех ролей с командами: включение правил от роли не зависит,
//   его держат слитый PR, проверки, выпуск и подпись оператора (проект v1.2 §3.1); команды аренды (TRANSPORT_COMMANDS
//   в kernel.mjs) не принадлежат ни одной роли — их принимает только посредник; v0.2: аудит E4-6
//   M-E46-01 — команда ReleaseAndTransition только у роли kernel)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: машинный список ролей Kernel (этап 4, критерий E4-7) — таблица 3.1 протокола Z1 v1.9,
//   копия в canon/Z1_v1_9_table_3_1.md (сумма раздела закреплена ниже). Для каждой роли — какие команды
//   Kernel ей разрешены. Неизвестная роль — ROLE_UNKNOWN; команда сверх канона — ROLE_FORBIDDEN.
//   Права выведены из столбцов «Разрешено»/«Запрещено» таблицы 3.1 и канона H1.31 §16:
//     «писать состояние напрямую» запрещено директорам и кураторам — у них нет Transition;
//     вердикт — только у аудитора; решение оператора — только у оператора; выпуск и переходы — у Kernel.
// ОГРАНИЧЕНИЯ: роль не даёт прав в базе; права базы задаёт H1.31 (роль bem_kernel_rw, функции bem_control).
//   Надзиратель, Egress, доставщик и сторож команд Kernel не вызывают (пустой список).

export const TABLE_3_1_SECTION_SHA256 = '1a18a62a280a0f03421a5ec4dee387218469469546a6a4778dfe320264bfb842';

// Чтение и включение правил: доступны всем ролям с командами.
const COMMON = ['GetWorkItem', 'GetUsage', 'ActivateRules', 'GetActiveRules', 'GetChatLease'];

// Ключ — машинное имя; z1 — имя строки таблицы 3.1 (столбец «Роль Z1»), дословно.
export const ROLES = Object.freeze({
  operator: { z1: 'Оператор', commands: ['OperatorDecision', ...COMMON] },
  general_director: { z1: 'Генеральный директор', commands: ['RecordEvidence', ...COMMON] },
  director_production: { z1: 'Директор производства', commands: ['CreateWorkItem', 'RecordEvidence', ...COMMON] },
  director_quality: { z1: 'Директор качества и безопасности', commands: ['RecordEvidence', ...COMMON] },
  director_product: { z1: 'Директор продукта и продаж', commands: ['CreateWorkItem', 'RecordEvidence', ...COMMON] },
  worker_curator: { z1: 'Куратор рабочих', commands: ['RecordEvidence', ...COMMON] },
  analyst_executor: { z1: 'Аналитик, Исполнитель', commands: ['RecordEvidence', 'RecordUsage', ...COMMON] },
  auditor: { z1: 'Аудитор', commands: ['RecordVerdict', ...COMMON] },
  kernel: { z1: 'Kernel, Egress, доставщик, сторож', commands: ['CreateWorkItem', 'Transition', 'RecordEvidence',
    'PublishSubject', 'ReleaseSubject', 'ReleaseAndTransition', 'RecordUsage', ...COMMON] },
  egress: { z1: 'Kernel, Egress, доставщик, сторож', commands: [] },
  dispatcher: { z1: 'Kernel, Egress, доставщик, сторож', commands: [] },
  watchdog: { z1: 'Kernel, Egress, доставщик, сторож', commands: [] },
  fencer: { z1: 'Надзиратель ограждения (`src/fencer.mjs`)', commands: [] },
});

for (const r of Object.values(ROLES)) { Object.freeze(r.commands); Object.freeze(r); }

export class RoleError extends Error {
  constructor(code, message) { super(`${code}: ${message}`); this.code = code; }
}

// Разрешена ли команда роли. Неизвестная роль и команда сверх канона — исключение.
export function authorize(role, command) {
  if (typeof role !== 'string' || !Object.hasOwn(ROLES, role)) throw new RoleError('ROLE_UNKNOWN', String(role));
  if (!ROLES[role].commands.includes(command)) throw new RoleError('ROLE_FORBIDDEN', `${role} -> ${command}`);
  return true;
}
