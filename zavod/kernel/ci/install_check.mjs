// ДОКУМЕНТ: ci/install_check.mjs
// ВЕРСИЯ: v0.2  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 15:00 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 21:31 +03:00 (v0.2: каталог engine — права как у app, суммы, запись запрещена)
// ИСПОЛНИТЕЛЬ: Claude (сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.4 §4.D — проверка готовой установки из ОБЫЧНОЙ учётки оператора (без
//   повышения прав, без ключей и без пароля zavod-kernel). Шесть групп: 1) права каталогов ровно как §2 (читаемые —
//   по факту, нечитаемые — по снимку квитанции) и настоящие попытки чтения и записи; итог пробы службы
//   logs\service_probe.json (владелец zavod-kernel, сумма = квитанции); 2) база: входы без ключей ядра — отказ, проверки
//   с ключами ядра — из пробы службы; 3) служба базы под NT SERVICE\ZavodKernelPg, привратник под zavod-kernel, порты
//   не занять повторно; 4) вход привратника: подпись /hello ключом из public, отказы Origin, без X-Zavod-Gate, не POST,
//   большое тело; 5) квитанция: суммы bin/app совпадают с файлами, закреплённые суммы = суммам в установщике;
//   6) ci/leak_scan.mjs по logs и public — пусто.
// ЗАПУСК: node ci/install_check.mjs [корень, по умолчанию C:\ZavodKernel] [--out <файл итога>]
// ОГРАНИЧЕНИЯ: ничего в установке не меняет: проба записи — открытие существующего файла (r+) или создание нового
//   с флагом wx; неожиданный успех оставляет файл как улику. Чужой CA для отрицательных проверок создаётся во временной
//   папке ОС и не удаляется (закрытые ключи чужого CA ни к чему не дают доступа). Пробная выдача пропуска (RG21-02)
//   в v0.1 не проверяется — отдельный пункт.

import { closeSync, existsSync, mkdtempSync, openSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash, createPublicKey, randomBytes, verify } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';
import http from 'node:http';
import net from 'node:net';
import { helloMessage, HELLO_NAMESPACE, MAX_BODY } from '../src/gate_server.mjs';
import { keylessChecks, allPass } from '../install/pg_probe.mjs';
import { makeAll } from '../install/make_certs.mjs';
import { scan } from './leak_scan.mjs';

export const VERSION = 'v0.1';
export const DIRS = Object.freeze(['.', 'admin', 'admin\\certs', 'admin\\staging', 'app', 'bin', 'data', 'engine', 'keys', 'keys\\kernel', 'logs', 'public', 'rules', 'run']);
const A = 'S-1-5-32-544', S = 'S-1-5-18', U = 'S-1-5-32-545';
const F = 'FullControl', RX = 'ReadAndExecute, Synchronize', M = 'Modify, Synchronize';
const OICI = 'ContainerInherit, ObjectInherit', NONE = 'None';
// Каталоги, права которых оператор прочитать не может (у Users там нет записи; администраторы в обычном сеансе — «только запрет»).
export const UNREADABLE = Object.freeze(['admin', 'admin\\certs', 'admin\\staging', 'data', 'keys', 'keys\\kernel']);

// Ожидаемые права §2: владелец и точный набор записей [SID, права, наследование]; K — SID zavod-kernel, PG — SID службы базы.
export function expectedAcl({ K, PG }) {
  const base = [[A, F, OICI], [S, F, OICI]];
  const pub = { owner: A, protected: true, rules: [...base, [U, RX, OICI]] };
  const kw = { owner: A, protected: true, rules: [...base, [K, M, OICI], [U, RX, OICI]] };
  return {
    '.': { owner: A, protected: true, rules: [[A, F, NONE], [S, F, NONE], [U, RX, NONE]] },
    admin: { owner: A, protected: true, rules: base },
    'admin\\certs': { owner: A, protected: false, rules: base },
    'admin\\staging': { owner: A, protected: false, rules: base },
    bin: pub, app: pub, engine: pub, public: pub,
    keys: { owner: A, protected: true, rules: [...base, [K, RX, NONE]] },
    'keys\\kernel': { owner: A, protected: true, rules: [...base, [K, RX, OICI]] },
    rules: { ...kw, owner: K }, run: kw, logs: kw,
    data: { owner: A, protected: true, rules: [[S, F, OICI], [PG, F, OICI]] },
  };
}

const ruleKey = (r) => r.join('|');
// sameAcl — сравнение без учёта порядка записей и признака «унаследовано»; запрет (Deny) — всегда расхождение.
export function sameAcl(got, want) {
  if (!got || got.owner !== want.owner || got.protected !== want.protected) return false;
  if (got.rules.some((r) => r.type !== 'Allow')) return false;
  const g = got.rules.map((r) => ruleKey([r.sid, r.rights, r.inh])).sort();
  const w = want.rules.map(ruleKey).sort();
  return g.length === w.length && g.every((x, i) => x === w[i]);
}

// Права через PowerShell (Get-Acl) — для каждого каталога: факт (если читается) и разбор снимка SDDL из квитанции.
const PS_ACL = String.raw`
$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'
$root = $env:ZAVOD_IC_ROOT; $receipt = Get-Content -Raw -Encoding UTF8 -LiteralPath $env:ZAVOD_IC_RECEIPT | ConvertFrom-Json
$sidT = [Security.Principal.SecurityIdentifier]
function Norm($sec) { [ordered]@{ owner = $sec.GetOwner($sidT).Value; protected = $sec.AreAccessRulesProtected
  rules = @($sec.GetAccessRules($true, $true, $sidT) | ForEach-Object { [ordered]@{ sid = $_.IdentityReference.Value
    rights = [string]$_.FileSystemRights; inh = [string]$_.InheritanceFlags; prop = [string]$_.PropagationFlags; type = [string]$_.AccessControlType } }) } }
function Sid($name) { try { (New-Object Security.Principal.NTAccount $name).Translate($sidT).Value } catch { $null } }
$out = [ordered]@{ K = (Sid 'zavod-kernel'); PG = (Sid 'NT SERVICE\ZavodKernelPg'); dirs = [ordered]@{} }
foreach ($d in $env:ZAVOD_IC_DIRS.Split('|')) {
  $p = if ($d -eq '.') { $root } else { Join-Path $root $d }
  $e = [ordered]@{}
  try { $a = Get-Acl -LiteralPath $p; $e.actual = Norm $a; $e.actual.readable = $true; $e.sddl = $a.Sddl }
  catch { $e.actual = [ordered]@{ readable = $false; error = $_.Exception.GetType().Name } }
  $snap = $null; if ($receipt.acl) { $snap = $receipt.acl.PSObject.Properties[$d] }
  if ($snap) { $ds = New-Object Security.AccessControl.DirectorySecurity; $ds.SetSecurityDescriptorSddlForm($snap.Value.sddl)
    $e.receipt = Norm $ds; $e.receipt_sddl = $snap.Value.sddl }
  $out.dirs[$d] = $e
}
$pf = Join-Path $root 'logs\service_probe.json'
$out.probe_owner = if (Test-Path -LiteralPath $pf) { (Get-Acl -LiteralPath $pf).GetOwner($sidT).Value } else { $null }
$svc = Get-CimInstance Win32_Service -Filter "Name='ZavodKernelPg'"
$out.pg_service = if ($svc) { [ordered]@{ start_name = $svc.StartName; state = $svc.State } } else { $null }
$out | ConvertTo-Json -Depth 8 -Compress
`;

export function readAclState(root, receiptFile) {
  const enc = Buffer.from(PS_ACL, 'utf16le').toString('base64');
  const outText = execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-EncodedCommand', enc], {
    env: { ...process.env, ZAVOD_IC_ROOT: root, ZAVOD_IC_RECEIPT: receiptFile, ZAVOD_IC_DIRS: DIRS.join('|') },
    encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 16 * 1024 * 1024 });
  return JSON.parse(outText.replace(/^\uFEFF/, ''));
}

const row = (group, name, pass, got = null) => ({ group, name, pass: Boolean(pass), got });

// 1. Права: снимок квитанции = §2 для всех каталогов; читаемые сейчас = снимку; нечитаемые — ровно ожидаемые.
export function aclChecks(state) {
  const want = expectedAcl({ K: state.K, PG: state.PG });
  const out = [row('acl', 'kernel_user_sid_known', /^S-1-5-21-/.test(state.K || ''), state.K),
    row('acl', 'pg_service_sid_known', /^S-1-5-80-/.test(state.PG || ''), state.PG)];
  for (const d of DIRS) {
    const e = state.dirs[d] || {};
    out.push(row('acl', `receipt_acl_${d}_as_plan`, sameAcl(e.receipt, want[d])));
    if (UNREADABLE.includes(d)) out.push(row('acl', `operator_cannot_read_acl_${d}`, e.actual && e.actual.readable === false, e.actual?.error ?? 'readable'));
    else {
      out.push(row('acl', `acl_${d}_as_plan`, sameAcl(e.actual, want[d])));
      out.push(row('acl', `acl_${d}_unchanged_since_receipt`, e.sddl && e.sddl === e.receipt_sddl));
    }
  }
  return out;
}

const attempt = (fn) => { try { fn(); return { ok: true }; } catch (e) { return { ok: false, code: e.code || 'ERR' }; } };
const DENIED = new Set(['EPERM', 'EACCES']);
const refused = (r) => !r.ok && DENIED.has(r.code);
const openRw = (p) => () => closeSync(openSync(p, 'r+'));
const create = (p) => () => closeSync(openSync(p, 'wx'));

// 1. Настоящие попытки из сеанса оператора: закрытое не читается, программы, правила и файл остановки не пишутся.
export function operatorFsChecks(root) {
  const P = (...a) => join(root, ...a);
  const no = (name, r) => row('fs', name, refused(r), r.ok ? 'ok' : r.code);
  const yes = (name, r) => row('fs', name, r.ok, r.ok ? 'ok' : r.code);
  return [
    no('read_admin_refused', attempt(() => readdirSync(P('admin')))),
    no('read_ca_key_refused', attempt(() => readFileSync(P('admin', 'certs', 'ca.key.pem')))),
    no('read_keys_refused', attempt(() => readdirSync(P('keys')))),
    no('read_kernel_key_refused', attempt(() => readFileSync(P('keys', 'kernel', 'bem_kernel_rw.key.pem')))),
    no('read_gate_key_refused', attempt(() => readFileSync(P('keys', 'kernel', 'gate_ed25519.key.pem')))),
    no('read_data_refused', attempt(() => readdirSync(P('data')))),
    no('write_bin_refused', attempt(openRw(P('bin', 'node.exe')))),
    no('create_in_bin_refused', attempt(create(P('bin', 'install_check_must_fail.txt')))),
    no('write_app_refused', attempt(openRw(P('app', 'gate.json')))),
    no('create_in_app_refused', attempt(create(P('app', 'install_check_must_fail.txt')))),
    no('write_engine_refused', attempt(openRw(P('engine', 'src', 'sshsig.mjs')))),
    no('create_in_engine_refused', attempt(create(P('engine', 'src', 'install_check_must_fail.txt')))),
    no('write_rules_refused', attempt(openRw(P('rules', '.git', 'HEAD')))),
    no('create_in_rules_refused', attempt(create(P('rules', 'install_check_must_fail.txt')))),
    no('write_run_stop_refused', attempt(openRw(P('run', 'STOP')))),
    no('create_in_run_refused', attempt(create(P('run', 'install_check_must_fail.txt')))),
    no('write_logs_refused', attempt(openRw(P('logs', 'service_probe.json')))),
    no('write_public_refused', attempt(openRw(P('public', 'install_receipt.json')))),
    yes('read_public_ca_ok', attempt(() => readFileSync(P('public', 'ca.crt.pem')))),
    yes('read_app_config_ok', attempt(() => readFileSync(P('app', 'gate.json')))),
  ];
}

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');
const readJson = (file) => JSON.parse(readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));

// Проверки с ключами ядра делает только проба службы (у оператора ключей нет) — здесь требуется их наличие и успех.
export const PROBE_REQUIRED = Object.freeze(['os_user_is_zavod_kernel', 'read_admin_dir_refused', 'read_ca_key_refused',
  'read_data_dir_refused', 'write_bin_file_refused', 'write_app_file_refused', 'write_rules_ok', 'write_run_stop_ok',
  'kernel_rw_login_ok', 'mode_not_active', 'rules_gate_login_ok', 'kernel_cert_as_rules_gate_refused',
  'kernel_cert_as_zavod_dba_refused', 'kernel_cert_as_schema_migrator_refused', 'rules_gate_cert_as_kernel_refused',
  'kernel_set_role_zavod_dba_refused', 'kernel_set_role_bem_rules_gate_refused', 'kernel_set_role_schema_migrator_refused']);

export function probeChecks(root, receipt, state) {
  const file = join(root, 'logs', 'service_probe.json');
  if (!existsSync(file)) return [row('probe', 'service_probe_exists', false)];
  const buf = readFileSync(file);
  let res = null;
  try { res = JSON.parse(buf.toString('utf8').replace(/^\uFEFF/, '')); } catch { /* разбор ниже даст FAIL */ }
  const byName = new Map((res?.checks || []).map((c) => [c.name, c]));
  return [
    row('probe', 'service_probe_exists', true),
    row('probe', 'service_probe_owner_is_kernel', state.probe_owner && state.probe_owner === state.K, state.probe_owner),
    row('probe', 'service_probe_sha_matches_receipt', receipt.service_probe?.sha256 === sha256(buf)),
    row('probe', 'service_probe_all_pass', res?.ok === true && res.checks.every((c) => c.pass)),
    ...PROBE_REQUIRED.map((n) => row('probe', `probe_${n}`, byName.get(n)?.pass === true, byName.get(n)?.got ?? 'missing')),
  ];
}

export async function dbChecks(root, port) {
  const foreignDir = mkdtempSync(join(tmpdir(), 'zavod-install-check-foreign-'));
  makeAll(foreignDir);
  const rows = await keylessChecks({ port, caFile: join(root, 'public', 'ca.crt.pem'), foreignDir });
  return rows.map((r) => row('db', r.name, r.pass, r.got + (r.code ? ` ${r.code}` : '')));
}

export function tryListen(host, port) {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.once('error', (e) => resolve({ ok: false, code: e.code }));
    s.listen({ host, port, exclusive: true }, () => s.close(() => resolve({ ok: true })));
  });
}

function getJson(port, path) {
  return new Promise((resolve) => {
    const req = http.get({ host: '127.0.0.1', port, path, timeout: 5000 }, (res) => {
      const parts = []; res.on('data', (c) => parts.push(c));
      res.on('end', () => { try { resolve(JSON.parse(Buffer.concat(parts).toString('utf8'))); } catch { resolve(null); } });
    });
    req.on('timeout', () => req.destroy()); req.on('error', () => resolve(null));
  });
}

// 3. Учётные записи процессов и порты.
export async function serviceChecks(state, ports) {
  const h = await getJson(ports.health, '/internal/health');
  const out = [
    row('service', 'pg_service_runs_as_virtual_account', state.pg_service?.start_name === 'NT SERVICE\\ZavodKernelPg', state.pg_service?.start_name ?? null),
    row('service', 'pg_service_running', state.pg_service?.state === 'Running', state.pg_service?.state ?? null),
    row('service', 'gate_health_os_user_kernel', h?.os_user === 'zavod-kernel', h?.os_user ?? null),
    row('service', 'gate_health_port', h?.gate_port === ports.gate, h?.gate_port ?? null),
  ];
  for (const [name, port] of [['gate', ports.gate], ['db', ports.db], ['health', ports.health]]) {
    const r = await tryListen('127.0.0.1', port);
    out.push(row('service', `rebind_${name}_port_refused`, !r.ok && (r.code === 'EADDRINUSE' || r.code === 'EACCES'), r.ok ? 'ok' : r.code));
  }
  return out;
}

// Сырой запрос к привратнику; ответ засчитывается, даже если сервер потом оборвал соединение (большое тело).
export function gateRequest(port, { method = 'POST', path = '/hello', headers = {}, body = '' } = {}) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    const req = http.request({ host: '127.0.0.1', port, method, path, headers, timeout: 10000 }, (res) => {
      const parts = []; res.on('data', (c) => parts.push(c));
      res.on('end', () => { let json = null; try { json = JSON.parse(Buffer.concat(parts).toString('utf8')); } catch { /* не JSON */ }
        finish({ status: res.statusCode, json }); });
      res.on('error', () => finish({ status: res.statusCode, json: null }));
    });
    req.on('timeout', () => req.destroy());
    req.on('error', (e) => finish({ status: null, error: e.code }));
    req.end(body);
  });
}

// 4. Вход привратника: подпись /hello открытым ключом из public; чужой ключ подпись не принимает; отказы входа.
export async function gateChecks({ port, publicKeyPem, foreignPublicKeyPem }) {
  const H = { 'x-zavod-gate': '1', 'content-type': 'application/json' };
  const nonce = randomBytes(32).toString('hex');
  const hello = await gateRequest(port, { headers: H, body: JSON.stringify({ nonce }) });
  const sig = hello.json && typeof hello.json.signature === 'string' ? Buffer.from(hello.json.signature, 'base64') : Buffer.alloc(0);
  const msg = helloMessage(port, nonce);
  const check = (pem) => { try { return verify(null, msg, createPublicKey(pem), sig); } catch { return false; } };
  const st = (r) => `${r.status ?? r.error}${r.json?.code ? ` ${r.json.code}` : ''}`;
  const big = Buffer.alloc(MAX_BODY + 1, 0x20);
  const origin = await gateRequest(port, { headers: { ...H, origin: 'http://example.invalid' }, body: JSON.stringify({ nonce }) });
  const noHdr = await gateRequest(port, { headers: { 'content-type': 'application/json' }, body: JSON.stringify({ nonce }) });
  const get = await gateRequest(port, { method: 'GET', headers: { 'x-zavod-gate': '1' } });
  const large = await gateRequest(port, { path: '/command', headers: H, body: big });
  return [
    row('gate', 'hello_ok', hello.status === 200 && hello.json?.namespace === HELLO_NAMESPACE && hello.json?.port === port, st(hello)),
    row('gate', 'hello_signed_by_public_key', check(publicKeyPem)),
    row('gate', 'hello_not_signed_by_foreign_key', !check(foreignPublicKeyPem)),
    row('gate', 'origin_refused_403', origin.status === 403 && origin.json?.code === 'GATE_ORIGIN_FORBIDDEN', st(origin)),
    row('gate', 'no_gate_header_refused_403', noHdr.status === 403 && noHdr.json?.code === 'GATE_HEADER_REQUIRED', st(noHdr)),
    row('gate', 'get_refused_405', get.status === 405, st(get)),
    row('gate', 'large_body_refused_413', large.status === 413, st(large)),
  ];
}

function* walkFiles(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* walkFiles(p); else if (e.isFile()) yield p;
  }
}

// Закреплённые суммы установщика: строки вида  key = @{ url = '...'; sha = '<64 hex>' ... }.
export function installerPins(text) {
  const pins = {};
  for (const m of text.matchAll(/^\s*(\w+)\s*=\s*@\{[^\n]*?\bsha\s*=\s*'([^']*)'/gm)) pins[m[1]] = m[2];
  return pins;
}

// 5. Квитанция: статус, MODE, суммы bin/app ровно по файлам (ни лишних, ни недостающих), закреплённые суммы.
export function receiptChecks(root, receipt) {
  const out = [row('receipt', 'status_ok', receipt.status === 'OK', receipt.status),
    row('receipt', 'mode_not_active', receipt.mode_active === false),
    row('receipt', 'commit_pinned', /^[0-9a-f]{40}$/.test(receipt.commit || ''), receipt.commit ?? null)];
  const want = receipt.file_sums || {};
  const got = {};
  for (const base of ['bin', 'app', 'engine']) {
    for (const f of walkFiles(join(root, base))) got[relative(root, f).replace(/\\/g, '/')] = sha256(readFileSync(f));
  }
  const wantKeys = Object.keys(want).sort(), gotKeys = Object.keys(got).sort();
  const extra = gotKeys.filter((k) => !(k in want)), missing = wantKeys.filter((k) => !(k in got));
  const changed = gotKeys.filter((k) => k in want && want[k] !== got[k]);
  out.push(row('receipt', 'file_sums_match', wantKeys.length > 0 && !extra.length && !missing.length && !changed.length,
    `files=${gotKeys.length} extra=${extra.length} missing=${missing.length} changed=${changed.length}`));
  const ps1 = join(root, 'app', 'install', 'install_zavod_kernel.ps1');
  const pins = existsSync(ps1) ? installerPins(readFileSync(ps1, 'utf8')) : {};
  for (const key of ['node', 'mingit', 'pgsetup', 'pgzip']) {
    const pin = pins[key];
    out.push(row('receipt', `source_${key}_matches_pin`, /^[0-9a-f]{64}$/.test(pin || '') && receipt.sources?.[key]?.sha256 === pin));
  }
  return out;
}

// 6. Поиск секретов в logs и public.
export function leakChecks(root) {
  const hits = scan([join(root, 'logs'), join(root, 'public')], new Set(), root);
  return [row('leak', 'no_secrets_in_logs_public', hits.length === 0, hits.map((h) => `${h.kind} ${h.pattern} ${h.file}:${h.line}`).slice(0, 10))];
}

export async function installCheck(root) {
  const receiptFile = join(root, 'public', 'install_receipt.json');
  const receipt = readJson(receiptFile);
  const ports = { db: receipt.ports?.db, gate: receipt.ports?.gate, health: receipt.ports?.health };
  const state = readAclState(root, receiptFile);
  const foreignGate = mkdtempSync(join(tmpdir(), 'zavod-install-check-gate-'));
  makeAll(foreignGate);
  const checks = [
    ...aclChecks(state),
    ...operatorFsChecks(root),
    ...probeChecks(root, receipt, state),
    ...await dbChecks(root, ports.db),
    ...await serviceChecks(state, ports),
    ...await gateChecks({ port: ports.gate, publicKeyPem: readFileSync(join(root, 'public', 'gate_ed25519.pub.pem')),
      foreignPublicKeyPem: readFileSync(join(foreignGate, 'gate_ed25519.pub.pem')) }),
    ...receiptChecks(root, receipt),
    ...leakChecks(root),
  ];
  return { check: 'zavod_install_check', version: VERSION, at: new Date().toISOString(), root, ports,
    receipt_sha256: sha256(readFileSync(receiptFile)), checks, ok: allPass(checks) };
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const args = process.argv.slice(2);
  const i = args.indexOf('--out');
  const outFile = i >= 0 ? args.splice(i, 2)[1] : null;
  const root = args[0] || 'C:\\ZavodKernel';
  let res;
  try { res = await installCheck(root); } catch (e) {
    res = { check: 'zavod_install_check', version: VERSION, root, ok: false, error: String(e.message).split('\n')[0].slice(0, 200), checks: [] };
  }
  if (outFile) writeFileSync(outFile, `${JSON.stringify(res, null, 2)}\n`, { flag: 'wx' });
  for (const c of res.checks.filter((x) => !x.pass)) console.log(`FAIL ${c.group} ${c.name} ${JSON.stringify(c.got)}`);
  console.log(`INSTALL_CHECK=${res.ok ? 'PASS' : 'FAIL'} checks=${res.checks.length} failed=${res.checks.filter((x) => !x.pass).length}${res.error ? ` error=${res.error}` : ''}`);
  process.exit(res.ok ? 0 : 3);
}
