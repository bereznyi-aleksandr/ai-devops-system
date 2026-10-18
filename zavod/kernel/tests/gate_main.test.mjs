// ДОКУМЕНТ: tests/gate_main.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 13:52 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 13:52 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.3 §4.A–B — разбор gate.json (отказ вместо значений по умолчанию),
//   порядок старта точки входа (учётка ОС и файл остановки — до ключей и базы), чтение GitHub без входа
//   (только разрешённые пути, защита ветки из открытого ответа, отказ при нехватке данных). База и сеть не нужны.

import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseConfig, startGate, connectionFor } from '../src/gate_main.mjs';
import { anonGh, fetchJsonSync } from '../src/github_anon.mjs';

const dir = mkdtempSync(join(tmpdir(), 'zavod-gate-main-'));
const stop = join(dir, 'STOP');
writeFileSync(stop, 'RUN\n');
const P = (n) => join(dir, n);
const good = () => ({
  db: { host: '127.0.0.1', port: 54390, database: 'bem', ca: P('ca.crt') },
  kernelCert: { cert: P('k.crt'), key: P('k.key') },
  rulesCert: { cert: P('r.crt'), key: P('r.key') },
  gate: { port: 18960, key: P('gate.pem') },
  health: { port: 18961 },
  stopFile: stop,
  expectedUser: 'zavod-kernel',
  rules: { repo: 'owner/repo', repoDir: P('rules'), git: P('git.exe') },
});
const code = (fn) => { try { fn(); } catch (e) { return e.code; } return 'NO_ERROR'; };

test('gate.json: правильный разбирается, значения по умолчанию только у dispatchMs', () => {
  const c = parseConfig(JSON.stringify(good()));
  assert.equal(c.db.host, '127.0.0.1');
  assert.equal(c.dispatchMs, 5000);
  assert.equal(c.rules.bootstrapKeyFile, null);
  assert.ok(Object.isFrozen(c));
});

test('gate.json: неизвестный ключ, чужой адрес базы, относительный путь, общий порт — отказ', () => {
  const cases = [
    [{ ...good(), password: 'x' }, 'GATE_CONFIG_UNKNOWN_KEY'],
    [{ ...good(), db: { ...good().db, host: '0.0.0.0' } }, 'GATE_CONFIG_DB_HOST'],
    [{ ...good(), db: { ...good().db, host: 'localhost' } }, 'GATE_CONFIG_DB_HOST'],
    [{ ...good(), stopFile: 'run/STOP' }, 'GATE_CONFIG_PATH'],
    [{ ...good(), kernelCert: { cert: P('k.crt') } }, 'GATE_CONFIG_CERT'],
    [{ ...good(), kernelCert: { cert: P('k.crt'), key: P('k.key'), pass: 'x' } }, 'GATE_CONFIG_CERT'],
    [{ ...good(), gate: { port: 54390, key: P('gate.pem') } }, 'GATE_CONFIG_PORT'],
    [{ ...good(), gate: { port: 80, key: P('gate.pem') } }, 'GATE_CONFIG_PORT'],
    [{ ...good(), rules: { ...good().rules, repo: 'owner/repo; rm' } }, 'GATE_CONFIG_RULES'],
    [{ ...good(), expectedUser: '' }, 'GATE_CONFIG_USER'],
    [{ ...good(), dispatchMs: 10 }, 'GATE_CONFIG_DISPATCH'],
  ];
  for (const [cfg, want] of cases) assert.equal(code(() => parseConfig(JSON.stringify(cfg))), want, JSON.stringify(cfg).slice(0, 80));
  assert.equal(code(() => parseConfig('{')), 'GATE_CONFIG_JSON');
  assert.equal(code(() => parseConfig('[]')), 'GATE_CONFIG_JSON');
});

test('подключение к базе: TLS со своим CA, проверка сервера, клиентский сертификат своей роли', () => {
  const c = parseConfig(JSON.stringify(good()));
  const read = (p) => Buffer.from(`file:${p}`);
  const k = connectionFor(c, 'kernel', read);
  const r = connectionFor(c, 'rules', read);
  assert.equal(k.ssl.rejectUnauthorized, true);
  assert.equal(String(k.ssl.ca), `file:${P('ca.crt')}`);
  assert.equal(String(k.ssl.cert), `file:${P('k.crt')}`);
  assert.equal(String(r.ssl.key), `file:${P('r.key')}`);
  assert.equal(k.user, undefined, 'роль задаёт ядро, не настройки');
  assert.equal(k.password, undefined);
});

test('старт: чужая учётка ОС — отказ до чтения ключей и подключения к базе', async () => {
  const c = parseConfig(JSON.stringify(good()));
  let touched = false;
  const readFile = () => { touched = true; throw new Error('must not read'); };
  await assert.rejects(startGate(c, { userInfo: () => ({ username: 'o.bereznyi' }), readFile }),
    (e) => e.code === 'GATE_WRONG_OS_USER');
  assert.equal(touched, false);
});

test('старт: нет файла остановки — отказ до чтения ключей', async () => {
  const c = parseConfig(JSON.stringify({ ...good(), stopFile: P('NO_STOP') }));
  let touched = false;
  await assert.rejects(startGate(c, { userInfo: () => ({ username: 'ZAVOD-KERNEL' }),
    readFile: () => { touched = true; throw new Error('must not read'); } }), (e) => e.code === 'GATE_STOP_FILE_REQUIRED');
  assert.equal(touched, false);
});

test('GitHub без входа: разрешены только пути проверки правил', () => {
  const seen = [];
  const gh = anonGh({ fetchJson: (p) => { seen.push(p); return { ok: p }; } });
  assert.deepEqual(gh('repos/o/r/pulls/12'), { ok: 'repos/o/r/pulls/12' });
  const sha = 'a'.repeat(40);
  gh(`repos/o/r/commits/${sha}/check-runs?per_page=100`);
  for (const bad of ['repos/o/r/issues', 'user', 'repos/o/r/pulls/12/files', 'repos/o/r/commits/main/check-runs?per_page=100',
    '../x', 'repos/o/r/branches/dev/protection/required_status_checks']) {
    assert.equal(code(() => gh(bad)), 'GITHUB_PATH_NOT_ALLOWED', bad);
  }
  assert.equal(code(() => fetchJsonSync('repos/o/r/issues')), 'GITHUB_PATH_NOT_ALLOWED');
  assert.deepEqual(seen, ['repos/o/r/pulls/12', `repos/o/r/commits/${sha}/check-runs?per_page=100`]);
});

test('GitHub без входа: защита ветки — из открытого ответа ветки main; нет данных — отказ', () => {
  const checks = [{ context: 'static', app_id: 15368 }];
  const gh = anonGh({ fetchJson: (p) => {
    assert.equal(p, 'repos/o/r/branches/main');
    return { protected: true, protection: { required_status_checks: { checks, contexts: ['static'] } } };
  } });
  assert.deepEqual(gh('repos/o/r/branches/main/protection/required_status_checks').checks, checks);
  for (const body of [{ protected: false, protection: { required_status_checks: { checks } } }, { protected: true },
    { protected: true, protection: { required_status_checks: { contexts: ['static'] } } }, null]) {
    const g = anonGh({ fetchJson: () => body });
    assert.equal(code(() => g('repos/o/r/branches/main/protection/required_status_checks')), 'GITHUB_PROTECTION_UNAVAILABLE');
  }
});
