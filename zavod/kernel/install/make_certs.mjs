// ДОКУМЕНТ: install/make_certs.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 14:11 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 14:11 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 v0.4 §4.C — выпуск ключей установки средствами node:crypto (без openssl):
//   свой центр сертификации (CA), сертификат сервера базы (адрес 127.0.0.1 в subjectAltName), клиентские сертификаты
//   ролей bem_kernel_rw, bem_rules_gate и суперпользователя zavod_dba (CN = имя роли — по нему PostgreSQL сверяет
//   вход «cert»), ключ привратника Ed25519. Ключи ECDSA P-256, подпись ecdsa-with-SHA256, X.509 v3.
// ЗАПУСК: node install/make_certs.mjs <пустой каталог>   (установщик запускает его в admin\staging\certs и сам
//   раскладывает файлы по каталогам с правами §2; certs.json — отпечатки и сроки, без секретов).
// ОГРАНИЧЕНИЯ: закрытые ключи пишутся только в указанный каталог; в stdout и certs.json — только отпечатки.

import { generateKeyPairSync, createHash, randomBytes, sign as cSign, createPublicKey, X509Certificate } from 'node:crypto';
import { writeFileSync, readdirSync, existsSync } from 'node:fs';
import { join, isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';

// --- DER (минимум для X.509) ---
const len = (n) => {
  if (n < 0x80) return Buffer.from([n]);
  const b = [];
  for (let x = n; x > 0; x >>= 8) b.unshift(x & 0xff);
  return Buffer.from([0x80 | b.length, ...b]);
};
const tlv = (tag, ...parts) => { const body = Buffer.concat(parts); return Buffer.concat([Buffer.from([tag]), len(body.length), body]); };
const seq = (...p) => tlv(0x30, ...p);
const set = (...p) => tlv(0x31, ...p);
const ctx = (n, ...p) => tlv(0xa0 | n, ...p);
const bool = (v) => tlv(0x01, Buffer.from([v ? 0xff : 0x00]));
const octet = (b) => tlv(0x04, b);
const bitString = (b, unused = 0) => tlv(0x03, Buffer.from([unused]), b);
const utf8 = (s) => tlv(0x0c, Buffer.from(s, 'utf8'));
const uint = (b) => tlv(0x02, b[0] & 0x80 ? Buffer.concat([Buffer.from([0]), b]) : b);
const intSmall = (n) => tlv(0x02, Buffer.from([n]));
export function oid(s) {
  const p = s.split('.').map(Number);
  const out = [40 * p[0] + p[1]];
  for (const v of p.slice(2)) {
    const b = [v & 0x7f];
    for (let x = Math.floor(v / 128); x > 0; x = Math.floor(x / 128)) b.unshift(0x80 | (x & 0x7f));
    out.push(...b);
  }
  return tlv(0x06, Buffer.from(out));
}
const utcTime = (d) => {
  if (d.getUTCFullYear() >= 2050) throw new Error('UTCTime only before 2050');
  const z = (n) => String(n).padStart(2, '0');
  return tlv(0x17, Buffer.from(`${z(d.getUTCFullYear() % 100)}${z(d.getUTCMonth() + 1)}${z(d.getUTCDate())}`
    + `${z(d.getUTCHours())}${z(d.getUTCMinutes())}${z(d.getUTCSeconds())}Z`, 'ascii'));
};
const name = (cn) => seq(set(seq(oid('2.5.4.3'), utf8(cn))));
const ECDSA_SHA256 = seq(oid('1.2.840.10045.4.3.2'));
const ext = (id, critical, valueDer) => seq(oid(id), ...(critical ? [bool(true)] : []), octet(valueDer));

const pem = (label, der) => `-----BEGIN ${label}-----\n${der.toString('base64').match(/.{1,64}/g).join('\n')}\n-----END ${label}-----\n`;
const keyId = (pub) => createHash('sha1').update(pub.export({ type: 'spki', format: 'der' })).digest();

// buildCertificate: kind 'ca' | 'server' | 'client'. Возвращает DER.
export function buildCertificate({ kind, subjectCN, issuerCN, publicKey, issuerPublicKey, signKey, days, now = new Date() }) {
  const serial = randomBytes(16);
  serial[0] &= 0x7f;
  if (serial[0] === 0) serial[0] = 1;
  const notBefore = new Date(now.getTime() - 5 * 60_000);
  const notAfter = new Date(now.getTime() + days * 86_400_000);
  const exts = [];
  if (kind === 'ca') {
    exts.push(ext('2.5.29.19', true, seq(bool(true), intSmall(0))));
    exts.push(ext('2.5.29.15', true, bitString(Buffer.from([0x06]), 1))); // keyCertSign, cRLSign
  } else {
    exts.push(ext('2.5.29.19', true, seq()));
    exts.push(ext('2.5.29.15', true, bitString(Buffer.from([0x80]), 7))); // digitalSignature
    exts.push(ext('2.5.29.37', false, seq(oid(kind === 'server' ? '1.3.6.1.5.5.7.3.1' : '1.3.6.1.5.5.7.3.2'))));
    if (kind === 'server') exts.push(ext('2.5.29.17', false, seq(tlv(0x87, Buffer.from([127, 0, 0, 1])))));
  }
  exts.push(ext('2.5.29.14', false, octet(keyId(publicKey))));
  exts.push(ext('2.5.29.35', false, seq(tlv(0x80, keyId(issuerPublicKey)))));
  const tbs = seq(ctx(0, intSmall(2)), uint(serial), ECDSA_SHA256, name(issuerCN),
    seq(utcTime(notBefore), utcTime(notAfter)), name(subjectCN),
    publicKey.export({ type: 'spki', format: 'der' }), ctx(3, seq(...exts)));
  const sig = cSign('sha256', tbs, { key: signKey, dsaEncoding: 'der' });
  return seq(tbs, ECDSA_SHA256, bitString(sig));
}

export const CLIENT_ROLES = Object.freeze(['bem_kernel_rw', 'bem_rules_gate', 'zavod_dba']);
const ec = () => generateKeyPairSync('ec', { namedCurve: 'P-256' });

// makeAll(dir) — все файлы установки в пустой каталог; возвращает сведения без секретов.
export function makeAll(dir, { now = new Date() } = {}) {
  if (!isAbsolute(dir) || !existsSync(dir) || readdirSync(dir).length !== 0) throw new Error('CERTS_DIR_NOT_EMPTY_OR_MISSING');
  const info = { created_at: now.toISOString(), algorithm: 'ECDSA P-256 / SHA-256', files: {} };
  const put = (file, text, fp) => { writeFileSync(join(dir, file), text, { flag: 'wx' }); if (fp) info.files[file] = fp; };
  const fpOf = (der) => {
    const x = new X509Certificate(der);
    return { subject: x.subject, issuer: x.issuer, serial: x.serialNumber, valid_to: x.validTo,
      sha256: createHash('sha256').update(der).digest('hex') };
  };
  const ca = ec();
  const caDer = buildCertificate({ kind: 'ca', subjectCN: 'Zavod Kernel Local CA', issuerCN: 'Zavod Kernel Local CA',
    publicKey: ca.publicKey, issuerPublicKey: ca.publicKey, signKey: ca.privateKey, days: 7300, now });
  put('ca.key.pem', ca.privateKey.export({ type: 'pkcs8', format: 'pem' }));
  put('ca.crt.pem', pem('CERTIFICATE', caDer), fpOf(caDer));
  const issue = (kind, cn, file) => {
    const k = ec();
    const der = buildCertificate({ kind, subjectCN: cn, issuerCN: 'Zavod Kernel Local CA', publicKey: k.publicKey,
      issuerPublicKey: ca.publicKey, signKey: ca.privateKey, days: 3650, now });
    put(`${file}.key.pem`, k.privateKey.export({ type: 'pkcs8', format: 'pem' }));
    put(`${file}.crt.pem`, pem('CERTIFICATE', der), fpOf(der));
  };
  issue('server', '127.0.0.1', 'server');
  for (const r of CLIENT_ROLES) issue('client', r, r);
  const g = generateKeyPairSync('ed25519');
  put('gate_ed25519.key.pem', g.privateKey.export({ type: 'pkcs8', format: 'pem' }));
  const pubPem = g.publicKey.export({ type: 'spki', format: 'pem' });
  put('gate_ed25519.pub.pem', pubPem, { sha256_spki: createHash('sha256')
    .update(createPublicKey(pubPem).export({ type: 'spki', format: 'der' })).digest('hex') });
  writeFileSync(join(dir, 'certs.json'), JSON.stringify(info, null, 2) + '\n', { flag: 'wx' });
  return info;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try {
    const info = makeAll(process.argv[2] || '');
    process.stdout.write(JSON.stringify({ ok: true, files: Object.keys(info.files) }) + '\n');
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, code: String(e.message).slice(0, 80) }) + '\n');
    process.exit(3);
  }
}
