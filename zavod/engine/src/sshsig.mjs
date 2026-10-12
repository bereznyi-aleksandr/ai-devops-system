// ДОКУМЕНТ: zavod/engine/src/sshsig.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 13:37 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: аудит ChatGPT S6-prep R4, M-S6-R4-01 — проверка подписи билета выпуска без файлов: формат SSHSIG
//   (OpenSSH PROTOCOL.sshsig, тот же, что пишет ssh-keygen -Y sign), только ключ ssh-ed25519. Открытый ключ выпуска
//   разбирается один раз и держится в памяти; путь к изменяемому файлу allowed_signers больше не нужен.
// ОГРАНИЧЕНИЯ: только ssh-ed25519 и hash sha512/sha256; любое отклонение формата — отказ (false), не исключение.
import { createHash, createPublicKey, verify } from 'node:crypto';

const MAGIC = Buffer.from('SSHSIG');

function reader(buf) {
  let off = 0;
  const need = (n) => { if (off + n > buf.length) throw new Error('short'); };
  return {
    u32() { need(4); const v = buf.readUInt32BE(off); off += 4; return v; },
    str() { const n = this.u32(); need(n); const v = buf.subarray(off, off + n); off += n; return v; },
    raw(n) { need(n); const v = buf.subarray(off, off + n); off += n; return v; },
    done() { return off === buf.length; },
  };
}
const sshString = (b) => { const n = Buffer.alloc(4); n.writeUInt32BE(b.length); return Buffer.concat([n, b]); };

// «ssh-ed25519 AAAA… комментарий» → 32 байта ключа. Иной тип или битый блок — TypeError.
export function parseEd25519PublicKey(line) {
  const parts = String(line || '').trim().split(/\s+/);
  if (parts[0] !== 'ssh-ed25519' || !/^[A-Za-z0-9+/]+={0,2}$/.test(parts[1] || '')) throw new TypeError('sshsig: not an ssh-ed25519 key');
  let type, key, done;
  try {
    const r = reader(Buffer.from(parts[1], 'base64'));
    type = r.str().toString('latin1');
    key = r.str();
    done = r.done();
  } catch {
    throw new TypeError('sshsig: bad ed25519 key');
  }
  if (type !== 'ssh-ed25519') throw new TypeError('sshsig: key type mismatch');
  if (key.length !== 32 || !done) throw new TypeError('sshsig: bad ed25519 key');
  return Buffer.from(key);
}

export function fingerprint(rawKey) {
  const blob = Buffer.concat([sshString(Buffer.from('ssh-ed25519')), sshString(rawKey)]);
  return `SHA256:${createHash('sha256').update(blob).digest('base64').replace(/=+$/, '')}`;
}

// true — подпись сделана этим ключом, в этом пространстве имён, над этими байтами.
export function verifySshSig({ armored, message, namespace, rawKey }) {
  try {
    const text = Buffer.from(armored).toString('latin1');
    const m = /^-----BEGIN SSH SIGNATURE-----\r?\n([A-Za-z0-9+/=\r\n]+)-----END SSH SIGNATURE-----\r?\n?$/.exec(text);
    if (!m) return false;
    const r = reader(Buffer.from(m[1].replace(/[\r\n]/g, ''), 'base64'));
    if (!r.raw(6).equals(MAGIC) || r.u32() !== 1) return false;
    const pk = reader(r.str());
    if (pk.str().toString('latin1') !== 'ssh-ed25519' || !pk.str().equals(rawKey) || !pk.done()) return false;
    const ns = r.str();
    if (ns.toString('utf8') !== namespace) return false;
    const reserved = r.str();
    const alg = r.str().toString('latin1');
    if (alg !== 'sha512' && alg !== 'sha256') return false;
    const sig = reader(r.str());
    if (!r.done()) return false;
    if (sig.str().toString('latin1') !== 'ssh-ed25519') return false;
    const s = sig.str();
    if (s.length !== 64 || !sig.done()) return false;
    const signed = Buffer.concat([MAGIC, sshString(ns), sshString(reserved), sshString(Buffer.from(alg)),
      sshString(createHash(alg).update(Buffer.from(message)).digest())]);
    const key = createPublicKey({ key: { kty: 'OKP', crv: 'Ed25519', x: rawKey.toString('base64url') }, format: 'jwk' });
    return verify(null, signed, key, s);
  } catch {
    return false;
  }
}
