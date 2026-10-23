// ДОКУМЕНТ: tests/make_certs.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:11 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 14:11 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки v0.4 §4.C — ключи установки: цепочка до своего CA, назначение сертификатов, адрес сервера,
//   взаимная проверка TLS (сервер по CA и адресу, клиент по CA), отказ сертификату чужого CA; каталог должен быть пуст.

import test from 'node:test';
import assert from 'node:assert/strict';
import tls from 'node:tls';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { X509Certificate } from 'node:crypto';
import { makeAll, CLIENT_ROLES, oid } from '../install/make_certs.mjs';

const dir = mkdtempSync(join(tmpdir(), 'zavod-certs-'));
const info = makeAll(dir);
const other = mkdtempSync(join(tmpdir(), 'zavod-certs-other-'));
makeAll(other);
const R = (d, f) => readFileSync(join(d, f));

test('кодирование OID', () => {
  assert.equal(oid('1.2.840.10045.4.3.2').toString('hex'), '06082a8648ce3d040302');
  assert.equal(oid('2.5.29.19').toString('hex'), '0603551d13');
});

test('цепочка: CA самоподписан и помечен CA; остальные выданы им и не CA; сервер — 127.0.0.1', () => {
  const ca = new X509Certificate(R(dir, 'ca.crt.pem'));
  assert.equal(ca.ca, true);
  assert.ok(ca.verify(ca.publicKey));
  for (const f of ['server', ...CLIENT_ROLES]) {
    const x = new X509Certificate(R(dir, `${f}.crt.pem`));
    assert.equal(x.ca, false, f);
    assert.ok(x.checkIssued(ca), f);
    assert.ok(x.verify(ca.publicKey), f);
    assert.equal(x.subject, `CN=${f === 'server' ? '127.0.0.1' : f}`);
  }
  const s = new X509Certificate(R(dir, 'server.crt.pem'));
  assert.equal(s.checkIP('127.0.0.1'), '127.0.0.1');
  assert.equal(s.checkIP('10.0.0.1'), undefined);
  assert.deepEqual(s.keyUsage, ['1.3.6.1.5.5.7.3.1']);
  assert.deepEqual(new X509Certificate(R(dir, 'bem_kernel_rw.crt.pem')).keyUsage, ['1.3.6.1.5.5.7.3.2']);
  const foreign = new X509Certificate(R(other, 'bem_kernel_rw.crt.pem'));
  assert.equal(foreign.verify(ca.publicKey), false);
});

test('certs.json — отпечатки без закрытых ключей; повторный выпуск в непустой каталог — отказ', () => {
  const text = readFileSync(join(dir, 'certs.json'), 'utf8');
  assert.equal(/PRIVATE KEY/.test(text), false);
  assert.ok(info.files['ca.crt.pem'].sha256.match(/^[0-9a-f]{64}$/));
  assert.equal(Object.keys(info.files).some((f) => f.includes('.key.')), false);
  assert.throws(() => makeAll(dir), /CERTS_DIR_NOT_EMPTY_OR_MISSING/);
  assert.throws(() => makeAll('relative'), /CERTS_DIR_NOT_EMPTY_OR_MISSING/);
});

function handshake({ clientCertDir, clientRole, caForClient = dir, servername }) {
  return new Promise((resolve) => {
    const server = tls.createServer({ key: R(dir, 'server.key.pem'), cert: R(dir, 'server.crt.pem'), ca: R(dir, 'ca.crt.pem'),
      requestCert: true, rejectUnauthorized: true, minVersion: 'TLSv1.2' }, (sock) => {
      const peer = sock.getPeerCertificate();
      sock.end(peer.subject?.CN || '');
    });
    server.on('tlsClientError', () => {});
    server.listen(0, '127.0.0.1', () => {
      const c = tls.connect({ host: '127.0.0.1', port: server.address().port, ca: R(caForClient, 'ca.crt.pem'),
        cert: R(clientCertDir, `${clientRole}.crt.pem`), key: R(clientCertDir, `${clientRole}.key.pem`),
        rejectUnauthorized: true, ...(servername ? { servername } : {}) }, () => {});
      let data = '';
      c.on('data', (d) => { data += d; });
      c.on('end', () => { server.close(); resolve(data ? { ok: true, cn: data } : { ok: false, code: 'NO_DATA' }); });
      c.on('error', (e) => { server.close(); resolve({ ok: false, code: e.code || e.message }); });
    });
  });
}

test('TLS: взаимная проверка проходит; клиент чужого CA и сервер под чужим CA — отказ', async () => {
  const good = await handshake({ clientCertDir: dir, clientRole: 'bem_kernel_rw' });
  assert.deepEqual(good, { ok: true, cn: 'bem_kernel_rw' });
  const foreignClient = await handshake({ clientCertDir: other, clientRole: 'bem_kernel_rw' });
  assert.equal(foreignClient.ok, false);
  const foreignServer = await handshake({ clientCertDir: dir, clientRole: 'bem_rules_gate', caForClient: other });
  assert.equal(foreignServer.ok, false);
});

test('ключ привратника: Ed25519, открытая часть отдельным файлом', () => {
  const pub = readFileSync(join(dir, 'gate_ed25519.pub.pem'), 'utf8');
  assert.match(pub, /BEGIN PUBLIC KEY/);
  assert.match(info.files['gate_ed25519.pub.pem'].sha256_spki, /^[0-9a-f]{64}$/);
});
