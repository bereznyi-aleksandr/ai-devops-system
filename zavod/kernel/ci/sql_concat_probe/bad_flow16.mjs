// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow16.mjs — проба 3.3.10.2 (самопроверка R15): пакет по пути
//   к node_modules и по абсолютному пути мимо закрытого списка модулей.
// ДАТА: 2026-11-02 10:42 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
import postgres from '../node_modules/postgres/src/index.js';
import { execaCommand } from '/usr/lib/node_modules/execa/index.js';
export { postgres, execaCommand };
