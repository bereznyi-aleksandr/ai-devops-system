// ДОКУМЕНТ: ci/service_probe.mjs
// ВЕРСИЯ: v0.2  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:27 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 21:31 +03:00 (v0.2: запись в engine запрещена)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.4 §4.C (RG28-02) — проба прав службы: запускается установщиком ОТ ИМЕНИ
//   zavod-kernel (Start-Process -Credential) и делает настоящие попытки. Обязано дать отказ: чтение admin, data, ключа CA
//   и ключа zavod_dba; запись в bin, app, public; вход в базу как zavod_dba, schema_migrator, чужим именем; SET ROLE
//   zavod_dba. Обязано пройти: запись в rules, run, logs; вход bem_kernel_rw и bem_rules_gate. Итог — logs\service_probe.json
//   (пишет U1, установщик сверяет владельца файла и копирует итог в install_receipt.json).
// ЗАПУСК: <bin>\node.exe <app>\ci\service_probe.mjs <корень, по умолчанию C:\ZavodKernel> <порт базы, по умолчанию 54390>
// ОГРАНИЧЕНИЯ: файлы не создаются и не меняются, кроме logs\service_probe.json: проверка записи — открытие существующего
//   файла на запись без изменения (r+). Неожиданный успех создания файла в bin/app/public оставляет файл как улику.

import { openSync, closeSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { userInfo } from 'node:os';
import { pathToFileURL } from 'node:url';
import { kernelChecks, allPass } from '../install/pg_probe.mjs';

const attempt = (fn) => { try { fn(); return { ok: true }; } catch (e) { return { ok: false, code: e.code || 'ERR' }; } };
const DENIED = new Set(['EPERM', 'EACCES']);
const fsRow = (name, expect, r) => ({ name, expect, got: r.ok ? 'ok' : 'refused', code: r.code ?? null,
  pass: expect === 'ok' ? r.ok : !r.ok && DENIED.has(r.code) });
const openRw = (p) => () => closeSync(openSync(p, 'r+'));

export function fsChecks(root) {
  const P = (...a) => join(root, ...a);
  return [
    fsRow('read_admin_dir_refused', 'refused', attempt(() => readdirSync(P('admin')))),
    fsRow('read_ca_key_refused', 'refused', attempt(() => readFileSync(P('admin', 'certs', 'ca.key.pem')))),
    fsRow('read_zavod_dba_key_refused', 'refused', attempt(() => readFileSync(P('admin', 'certs', 'zavod_dba.key.pem')))),
    fsRow('read_data_dir_refused', 'refused', attempt(() => readdirSync(P('data')))),
    fsRow('read_server_key_refused', 'refused', attempt(() => readFileSync(P('data', 'server.key.pem')))),
    fsRow('write_bin_file_refused', 'refused', attempt(openRw(P('bin', 'node.exe')))),
    fsRow('create_in_bin_refused', 'refused', attempt(() => closeSync(openSync(P('bin', 'service_probe_must_fail.txt'), 'wx')))),
    fsRow('write_app_file_refused', 'refused', attempt(openRw(P('app', 'gate.json')))),
    fsRow('write_engine_file_refused', 'refused', attempt(openRw(P('engine', 'src', 'sshsig.mjs')))),
    fsRow('create_in_engine_refused', 'refused', attempt(() => closeSync(openSync(P('engine', 'src', 'service_probe_must_fail.txt'), 'wx')))),
    fsRow('create_in_app_refused', 'refused', attempt(() => closeSync(openSync(P('app', 'service_probe_must_fail.txt'), 'wx')))),
    fsRow('write_public_file_refused', 'refused', attempt(openRw(P('public', 'ca.crt.pem')))),
    fsRow('create_in_public_refused', 'refused', attempt(() => closeSync(openSync(P('public', 'service_probe_must_fail.txt'), 'wx')))),
    fsRow('write_rules_ok', 'ok', attempt(openRw(P('rules', '.git', 'HEAD')))),
    fsRow('write_run_stop_ok', 'ok', attempt(openRw(P('run', 'STOP')))),
    fsRow('read_kernel_keys_ok', 'ok', attempt(() => readFileSync(P('keys', 'kernel', 'bem_kernel_rw.key.pem')))),
  ];
}

export async function probe(root, port) {
  const user = userInfo().username;
  const checks = [{ name: 'os_user_is_zavod_kernel', expect: 'ok', got: user, code: null, pass: user.toLowerCase() === 'zavod-kernel' },
    ...fsChecks(root),
    ...await kernelChecks({ port, caFile: join(root, 'public', 'ca.crt.pem'), certDir: join(root, 'keys', 'kernel') })];
  return { probe: 'zavod_service_probe', version: 'v0.1', user, at: new Date().toISOString(), port, checks, ok: allPass(checks) };
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const root = process.argv[2] || 'C:\\ZavodKernel';
  const port = Number(process.argv[3] || 54390);
  const res = await probe(root, port);
  // Запись итога — тоже проба: logs обязан быть доступен U1 на запись.
  const w = attempt(() => writeFileSync(join(root, 'logs', 'service_probe.json'), `${JSON.stringify(res, null, 2)}\n`));
  process.stdout.write(`${JSON.stringify({ ok: res.ok && w.ok, written: w.ok, failed: res.checks.filter((c) => !c.pass).map((c) => c.name) })}\n`);
  process.exit(res.ok && w.ok ? 0 : 3);
}
