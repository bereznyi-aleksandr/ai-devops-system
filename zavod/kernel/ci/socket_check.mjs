// ДОКУМЕНТ: ci/socket_check.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-31 17:34 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-31 17:34 +02:00 (v0.1: этап 3.3.2.4)
// ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
// НАЗНАЧЕНИЕ: доказательство «ядро подключается через сокет» (этап 3.3.2.4, протокол v3.1, И.7 п. 3). Подключение
//   берётся из src/settings.mjs (pgConnection) точно так же, как в src/server.mjs; PGHOST не задан. База должна
//   ответить, что вход пришёл не по сети (inet_client_addr() пуст), и под пользователем Linux (вход peer).
// ВЫЗОВ: из zavod/kernel на машине Linux с PostgreSQL 16: node ci/socket_check.mjs. Строка KERNEL_SOCKET=PASS — успех.
// ОГРАНИЧЕНИЯ: только чтение; секретов и паролей нет (вход peer без пароля).

import { createRequire } from 'node:module';
import { userInfo } from 'node:os';
import { pgConnection, LINUX_PG_SOCKET_DIR } from '../src/settings.mjs';

const pg = createRequire(import.meta.url)('pg');
const fail = (m) => { console.error(`KERNEL_SOCKET=FAIL ${m}`); process.exit(1); };

if (process.env.PGHOST) fail('PGHOST is set: the check needs the default connection');
const conn = pgConnection(process.env, { max: 1 });
if (conn.host !== LINUX_PG_SOCKET_DIR) fail(`default host ${conn.host}, expected ${LINUX_PG_SOCKET_DIR}`);

const pool = new pg.Pool(conn);
try {
  const { rows: [r] } = await pool.query(
    'select current_user as who, inet_client_addr() as client_addr, current_database() as db');
  console.log(`socket=${conn.host} user=${r.who} db=${r.db} client_addr=${r.client_addr}`);
  if (r.client_addr !== null) fail('connection came over the network, not the socket');
  if (r.who !== userInfo().username) fail(`database user ${r.who} is not the Linux user ${userInfo().username}`);
  console.log('KERNEL_SOCKET=PASS');
} finally {
  await pool.end();
}
