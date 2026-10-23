// ДОКУМЕНТ: install/pg_probe.mjs
// ВЕРСИЯ: v0.2  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:27 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 17:11 +03:00
// ИСПОЛНИТЕЛЬ: Claude (v0.1 сессия fd43469f; v0.2 сессия 9951b86f — запуск из командной строки для установщика)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.4 §4.C–D — настоящие попытки входа в базу ядра (RG27-04):
//   что обязано пройти и что обязано получить отказ. Один набор для трёх мест: установщик (у него все ключи
//   в admin\staging), проба службы под zavod-kernel (ci/service_probe.mjs, только ключи keys\kernel) и проверка
//   Claude без ключей (ci/install_check.mjs: только попытки без сертификата, паролем и сертификатом чужого CA).
// ОГРАНИЧЕНИЯ: в итог пишутся только имена проверок, ожидание, итог и код ошибки PostgreSQL/TLS — ключей и путей к ним нет.

import pg from 'pg';
import tls from 'node:tls';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

// tryConnect — одна попытка; sql — запросы после входа (по порядку). Итог: { ok, user?, rows?, code? }.
export async function tryConnect({ port, user, database = 'bem', ssl = true, caFile, certDir, certRole, password, sql = [] }) {
  const cfg = { host: '127.0.0.1', port, user, database, connectionTimeoutMillis: 10000, application_name: 'zavod_pg_probe' };
  if (password !== undefined) cfg.password = password;
  if (ssl) {
    cfg.ssl = { rejectUnauthorized: true, ca: readFileSync(caFile), checkServerIdentity: (_h, cert) => tls.checkServerIdentity('127.0.0.1', cert) };
    if (certDir) Object.assign(cfg.ssl, { cert: readFileSync(join(certDir, `${certRole}.crt.pem`)), key: readFileSync(join(certDir, `${certRole}.key.pem`)) });
  } else cfg.ssl = false;
  const c = new pg.Client(cfg);
  c.on('error', () => {});
  try {
    await c.connect();
    const r = await c.query('SELECT current_user AS u');
    const rows = [];
    for (const q of sql) rows.push((await c.query(q)).rows);
    return { ok: true, user: r.rows[0].u, rows };
  } catch (e) {
    return { ok: false, code: e.code || String(e.message).split('\n')[0].slice(0, 80) };
  } finally {
    await c.end().catch(() => {});
  }
}

// Одна строка итога: name, expect ('ok' | 'refused'), got, pass. Отказ засчитывается только с ожидаемым кодом:
// отказ по чужой причине (например, клиент сам не принял сертификат сервера) — не доказательство и даёт FAIL.
export const AUTH_REFUSED = Object.freeze(['28000']);
export const UNKNOWN_CA = Object.freeze(['ERR_SSL_TLSV1_ALERT_UNKNOWN_CA']);
export const SERVER_UNTRUSTED = Object.freeze(['SELF_SIGNED_CERT_IN_CHAIN', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE', 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY']);
const row = (name, expect, r, extra = true, codes = AUTH_REFUSED) => ({ name, expect, got: r.ok ? 'ok' : 'refused', code: r.code ?? null,
  pass: expect === 'ok' ? r.ok && extra : !r.ok && codes.includes(r.code) });

// keyless — проверки без закрытых ключей ядра: их может выполнить кто угодно с открытым ca.crt.pem.
export async function keylessChecks({ port, caFile, foreignDir }) {
  const out = [];
  out.push(row('no_ssl_refused', 'refused', await tryConnect({ port, user: 'bem_kernel_rw', ssl: false })));
  out.push(row('ssl_no_client_cert_refused', 'refused', await tryConnect({ port, user: 'bem_kernel_rw', caFile })));
  out.push(row('password_zavod_dba_refused', 'refused', await tryConnect({ port, user: 'zavod_dba', database: 'postgres', caFile, password: 'zavod-probe-not-a-secret' })));
  for (const r of ['bem_kernel_rw', 'zavod_dba']) {
    out.push(row(`foreign_ca_${r}_refused`, 'refused', await tryConnect({ port, user: r, database: r === 'zavod_dba' ? 'postgres' : 'bem', caFile, certDir: foreignDir, certRole: r }), true, UNKNOWN_CA));
  }
  // Сервер под чужим CA: клиент доверяет только чужому CA — сервер обязан не пройти проверку.
  out.push(row('server_vs_foreign_ca_refused', 'refused', await tryConnect({ port, user: 'bem_kernel_rw', caFile: join(foreignDir, 'ca.crt.pem'), certDir: foreignDir, certRole: 'bem_kernel_rw' }), true, SERVER_UNTRUSTED));
  return out;
}

// kernelChecks — ключи keys\kernel (служба zavod-kernel или установщик): свои входы проходят, чужие имена и роли — нет.
export async function kernelChecks({ port, caFile, certDir }) {
  const out = [];
  const own = await tryConnect({ port, user: 'bem_kernel_rw', caFile, certDir, certRole: 'bem_kernel_rw',
    sql: ['SELECT count(*)::int AS n FROM bem_control.rules_activation', 'SELECT count(*)::int AS n FROM bem_control.chat_lease'] });
  out.push(row('kernel_rw_login_ok', 'ok', own, own.user === 'bem_kernel_rw'));
  if (own.ok) out.push({ name: 'mode_not_active', expect: 'ok', got: `rules_activation=${own.rows[0][0].n} chat_lease=${own.rows[1][0].n}`,
    code: null, pass: own.rows[0][0].n === 0 && own.rows[1][0].n === 0 });
  const gate = await tryConnect({ port, user: 'bem_rules_gate', caFile, certDir, certRole: 'bem_rules_gate' });
  out.push(row('rules_gate_login_ok', 'ok', gate, gate.user === 'bem_rules_gate'));
  out.push(row('kernel_cert_as_rules_gate_refused', 'refused', await tryConnect({ port, user: 'bem_rules_gate', caFile, certDir, certRole: 'bem_kernel_rw' })));
  out.push(row('kernel_cert_as_zavod_dba_refused', 'refused', await tryConnect({ port, user: 'zavod_dba', database: 'postgres', caFile, certDir, certRole: 'bem_kernel_rw' })));
  out.push(row('kernel_cert_as_schema_migrator_refused', 'refused', await tryConnect({ port, user: 'schema_migrator', caFile, certDir, certRole: 'bem_kernel_rw' })));
  out.push(row('rules_gate_cert_as_kernel_refused', 'refused', await tryConnect({ port, user: 'bem_kernel_rw', caFile, certDir, certRole: 'bem_rules_gate' })));
  for (const target of ['zavod_dba', 'bem_rules_gate', 'schema_migrator']) {
    const r = await tryConnect({ port, user: 'bem_kernel_rw', caFile, certDir, certRole: 'bem_kernel_rw', sql: [`SET ROLE ${target}`] });
    out.push({ name: `kernel_set_role_${target}_refused`, expect: 'refused', got: r.ok ? 'ok' : 'refused', code: r.code ?? null, pass: !r.ok && r.code === '42501' });
  }
  return out;
}

// adminChecks — только установщик (сертификат zavod_dba в admin\staging): вход суперпользователя есть, окно миграции закрыто.
export async function adminChecks({ port, caFile, certDir }) {
  const out = [];
  const dba = await tryConnect({ port, user: 'zavod_dba', database: 'postgres', caFile, certDir, certRole: 'zavod_dba',
    sql: ["SELECT count(*)::int AS n FROM pg_hba_file_rules WHERE error IS NOT NULL OR type <> 'hostssl' OR auth_method <> 'cert' OR address <> '127.0.0.1'",
      "SELECT count(*)::int AS n FROM pg_hba_file_rules WHERE 'schema_migrator' = ANY(user_name)",
      "SELECT rolcanlogin FROM pg_roles WHERE rolname = 'schema_migrator'", "SHOW ssl_min_protocol_version", "SHOW listen_addresses"] });
  out.push(row('zavod_dba_login_ok', 'ok', dba, dba.user === 'zavod_dba'));
  if (dba.ok) {
    const [bad, migr, login, tlsv, listen] = dba.rows;
    out.push({ name: 'hba_only_hostssl_cert_localhost', expect: 'ok', got: `other_rules=${bad[0].n}`, code: null, pass: bad[0].n === 0 });
    out.push({ name: 'migration_window_closed', expect: 'ok', got: `hba=${migr[0].n} login=${login[0]?.rolcanlogin}`, code: null,
      pass: migr[0].n === 0 && login[0]?.rolcanlogin === false });
    out.push({ name: 'tls13_localhost_only', expect: 'ok', got: `${tlsv[0].ssl_min_protocol_version} ${listen[0].listen_addresses}`, code: null,
      pass: tlsv[0].ssl_min_protocol_version === 'TLSv1.3' && listen[0].listen_addresses === '127.0.0.1' });
  }
  out.push(row('dba_cert_as_schema_migrator_refused', 'refused', await tryConnect({ port, user: 'schema_migrator', caFile, certDir, certRole: 'zavod_dba' })));
  return out;
}

export const allPass = (rows) => rows.length > 0 && rows.every((r) => r.pass);
export const haveKeys = (dir, role) => existsSync(join(dir, `${role}.key.pem`));

// Запуск установщиком (шаг database): node install/pg_probe.mjs <порт> <ca.crt.pem> <admin\certs> <чужой CA>
//   → одна строка JSON { ok, checks } (adminChecks + kernelChecks + keylessChecks); код 3, если хоть одна не прошла.
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const [port, caFile, certDir, foreignDir] = [Number(process.argv[2]), process.argv[3], process.argv[4], process.argv[5]];
  let res;
  try {
    const checks = [...await adminChecks({ port, caFile, certDir }), ...await kernelChecks({ port, caFile, certDir }),
      ...await keylessChecks({ port, caFile, foreignDir })];
    res = { ok: allPass(checks), checks };
  } catch (e) {
    // Только код ошибки: в тексте сообщения бывает путь к файлу ключа.
    res = { ok: false, checks: [], code: (e && e.code) || 'PROBE_ERROR' };
  }
  process.stdout.write(`${JSON.stringify(res)}\n`);
  process.exitCode = res.ok ? 0 : 3;
}
