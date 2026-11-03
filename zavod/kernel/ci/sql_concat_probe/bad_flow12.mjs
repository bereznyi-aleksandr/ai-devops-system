// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow12.mjs — проба (аудит M3310-R11-03): пример аудитора entry.mjs
//   (импорт своего *.cjs) и импорт файлов формата, который сканер не разбирает.
// ДАТА: 2026-11-02 07:26 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import run from './extra12.cjs'; export function go(db, input) { run(db,input); }
import more from './bad_flow12.ts';
import other from '#extra';
export { more, other };
