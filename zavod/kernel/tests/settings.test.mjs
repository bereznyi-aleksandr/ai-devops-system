// ДОКУМЕНТ: tests/settings.test.mjs
// ВЕРСИЯ: v0.2  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-31 17:16 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-03 09:03 +02:00 (v0.2: аудит M-F33-FINAL-R1-01 —
//   образец сервера без P1_*, путь к архиву движка в службе = имя в пакете, порт 8091 в службе и инструкции; Claude,
//   сессия 8fd25409-2d3b-4441-b2b9-3ecafca2c1b6; v0.1: этап 3.3.2.1 и 3.3.2.4)
// ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
// НАЗНАЧЕНИЕ: файл настроек Завода (src/settings.mjs) без базы данных: образец сервера проходит; путь Windows на
//   Linux, ключ-секрет, лишний ключ, повтор, кавычки и относительный путь — отказ; без PGHOST на Linux — сокет.
//   И главное для переезда: в коде ядра и движка нет путей компьютера оператора (C:\, node-portable, папка пользователя).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseSettings, readSettingsFile, requireSetting, pgConnection, SettingsError, LINUX_PG_SOCKET_DIR }
  from '../src/settings.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const EXAMPLE = join(HERE, '..', '..', 'ops', 'server', 'zavod.env.example');
const code = (fn) => { try { fn(); } catch (e) { assert.ok(e instanceof SettingsError, String(e)); return e.code; } return 'NO_ERROR'; };

test('образец /etc/zavod/zavod.env проходит проверку как на Linux', () => {
  const s = readSettingsFile(EXAMPLE, { platform: 'linux' });
  assert.equal(s.PGHOST, LINUX_PG_SOCKET_DIR);
  assert.equal(s.ZAVOD_RUNTIME_DIR, '/var/lib/zavod');
  assert.ok(Object.isFrozen(s));
});

test('образец сервера стыкуется с пакетом: нет P1_*, архив и порт движка одни во всех файлах', () => {
  const s = readSettingsFile(EXAMPLE, { platform: 'linux' });
  assert.deepEqual(Object.keys(s).filter((k) => k.startsWith('P1_')), []);
  const ops = join(HERE, '..', '..', 'ops', 'server');
  const unit = readFileSync(join(ops, 'zavod-engine.service'), 'utf8');
  const pkg = readFileSync(join(ops, 'build_server_package.py'), 'utf8');
  const guide = readFileSync(join(ops, 'INSTALL_SERVER.md'), 'utf8');
  // Архив, который запускает служба, должен быть тем, что кладёт пакет; иначе — имя расхождения.
  const engineWar = (u) => {
    const war = u.match(/ -jar \/opt\/zavod\/current\/(\S+\.war) /);
    if (!war) return 'NO_JAR';
    return pkg.includes(`'${war[1]}': war_with_drivers(`) ? 'OK' : 'WAR_NOT_IN_PACKAGE';
  };
  assert.equal(engineWar(unit), 'OK');
  assert.equal(engineWar(unit.replace('engine/flowable-rest-postgres.war', 'flowable/flowable-rest.war')),
    'WAR_NOT_IN_PACKAGE');
  assert.equal(unit.match(/--server\.port=(\d+)/)?.[1], '8091');
  assert.ok(guide.includes('127.0.0.1:8091'));
  // Образец с прежней строкой пилота отклоняется этой проверкой.
  const old = parseSettings('P1_FLOWABLE_WAR=/opt/zavod/flowable/flowable-rest.war\n', { platform: 'linux' });
  assert.deepEqual(Object.keys(old).filter((k) => k.startsWith('P1_')), ['P1_FLOWABLE_WAR']);
});

test('отказы файла настроек', () => {
  const linux = (t) => code(() => parseSettings(t, { platform: 'linux' }));
  assert.equal(linux('ZAVOD_RUNTIME_DIR=C:/AI/multiagent-runtime\n'), 'SETTING_WINDOWS_PATH');
  assert.equal(linux('P1_PRODUCT_CLONE=/var/lib\\zavod\n'), 'SETTING_WINDOWS_PATH');
  assert.equal(linux('PGHOST=C:\\pg\n'), 'SETTING_WINDOWS_PATH');
  assert.equal(linux('ZAVOD_GITHUB_TOKEN=x\n'), 'SETTINGS_SECRET_KEY');
  assert.equal(linux('PGPASSWORD=x\n'), 'SETTINGS_SECRET_KEY');
  assert.equal(linux('ZAVOD_UNKNOWN=x\n'), 'SETTINGS_UNKNOWN_KEY');
  assert.equal(linux('PGPORT=5432\nPGPORT=5433\n'), 'SETTINGS_DUPLICATE_KEY');
  assert.equal(linux('PGDATABASE="bem"\n'), 'SETTING_BAD_VALUE');
  assert.equal(linux('PGDATABASE= bem\n'), 'SETTING_BAD_VALUE');
  assert.equal(linux('PGDATABASE=\n'), 'SETTING_EMPTY');
  assert.equal(linux('export PGPORT=5432\n'), 'SETTINGS_BAD_LINE');
  assert.equal(linux('PGPORT=70000\n'), 'SETTING_BAD_PORT');
  assert.equal(linux('KERNEL_DISPATCH_MS=0\n'), 'SETTING_BAD_INT');
  assert.equal(linux('KERNEL_STOP_FILE=kernel.stop\n'), 'SETTING_PATH_NOT_ABSOLUTE');
  assert.equal(linux('# комментарий\n\nPGHOST=127.0.0.1\r\n'), 'NO_ERROR');
  // На компьютере оператора (до подписи 3.8) пути Windows допустимы.
  assert.equal(code(() => parseSettings('ZAVOD_RUNTIME_DIR=C:/AI/multiagent-runtime\n', { platform: 'win32' })), 'NO_ERROR');
});

test('подключение к базе: Linux — сокет, Windows — 127.0.0.1, явный PGHOST сильнее', () => {
  assert.deepEqual(pgConnection({}, { platform: 'linux' }), { host: LINUX_PG_SOCKET_DIR, port: 5432, database: 'bem' });
  assert.deepEqual(pgConnection({}, { platform: 'win32' }), { host: '127.0.0.1', port: 5432, database: 'bem' });
  assert.deepEqual(pgConnection({ PGHOST: '127.0.0.1', PGPORT: '54337', PGDATABASE: 'x', PGUSER: 'bem_kernel_rw' },
    { platform: 'linux', max: 1 }), { host: '127.0.0.1', port: 54337, database: 'x', user: 'bem_kernel_rw', max: 1 });
});

test('обязательная настройка без значения — отказ, без подстановки пути', () => {
  assert.equal(code(() => requireSetting('P1_PRODUCT_CLONE', {})), 'SETTING_REQUIRED');
  assert.equal(requireSetting('P1_PRODUCT_CLONE', { P1_PRODUCT_CLONE: '/var/lib/zavod/p1' }), '/var/lib/zavod/p1');
});

// Этап 3.3.2.1: «в коде нет путей C:\». Части только для Windows (win/, функции PowerShell оператора, тесты
// Job Object) — по списку 3.3.1, класс B; в остальном коде путь компьютера оператора — отказ.
const ROOT = join(HERE, '..', '..');
const WINDOWS_ONLY = [/^kernel[\\/]win[\\/]/, /^ops[\\/]operator[\\/]/, /^kernel[\\/]tests[\\/]settings\.test\.mjs$/];
const PC_PATH = /(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])|node-portable|node\.exe|o\.bereznyi|codex-runtimes|multiagent-runtime|multiagent-project|zavod-runtime/i;
const WINDOWS_ONLY_LINES = [/System32\\\\?OpenSSH\\\\?ssh-keygen\.exe/, /\/c\/Windows\/Microsoft\.NET/];

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    if (n === 'node_modules' || n.startsWith('.')) continue;
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p); else if (/\.(mjs|js|py|sh|sql|json|yml|yaml|service)$/.test(n)) yield p;
  }
}

test('в коде Завода нет путей компьютера оператора (кроме частей только для Windows)', () => {
  const bad = [];
  for (const p of walk(ROOT)) {
    const rel = p.slice(ROOT.length + 1);
    if (WINDOWS_ONLY.some((re) => re.test(rel))) continue;
    readFileSync(p, 'utf8').split(/\r?\n/).forEach((l, i) => {
      if (PC_PATH.test(l) && !WINDOWS_ONLY_LINES.some((re) => re.test(l))) bad.push(`${rel}:${i + 1}`);
    });
  }
  assert.deepEqual(bad, []);
});
