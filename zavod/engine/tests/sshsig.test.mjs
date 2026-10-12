// ДОКУМЕНТ: zavod/engine/tests/sshsig.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 13:39 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: проверки src/sshsig.mjs (аудит ChatGPT S6-prep R4, M-S6-R4-01): подпись ssh-keygen -Y sign (sha512 и
//   sha256) принимается; другие байты, другой ключ, другое пространство имён, изменённый байт подписи, обрезанная
//   и мусорная подпись — false; отпечаток совпадает с ssh-keygen -lf; не-ed25519 и битый ключ — TypeError.
// ОГРАНИЧЕНИЯ: нужен ssh-keygen (иначе пропуск); пароль ключей тестовый; папки остаются в tmpdir ОС.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fingerprint, parseEd25519PublicKey, verifySshSig } from '../src/sshsig.mjs';

const NS = 'zavod-release-ticket@v1';
function hasKeygen() {
  try { execFileSync('ssh-keygen', ['-V'], { stdio: 'ignore' }); return true; } catch (e) { return e.code !== 'ENOENT'; }
}
function key(d, name) {
  const f = join(d, name);
  execFileSync('ssh-keygen', ['-q', '-t', 'ed25519', '-N', '', '-C', name, '-f', f]);
  const pub = readFileSync(`${f}.pub`, 'utf8').trim();
  const sign = (bytes, ns = NS, extra = []) => {
    const m = join(d, `m_${Math.random().toString(16).slice(2)}`);
    writeFileSync(m, bytes);
    execFileSync('ssh-keygen', ['-Y', 'sign', '-q', '-n', ns, ...extra, '-f', f, m], { stdio: ['ignore', 'ignore', 'pipe'] });
    return readFileSync(`${m}.sig`);
  };
  return { f, pub, raw: parseEd25519PublicKey(pub), sign };
}

test('sshsig: подпись ssh-keygen принимается, любые отклонения — false', { skip: !hasKeygen() }, () => {
  const d = mkdtempSync(join(tmpdir(), 'zavod-sshsig-'));
  const a = key(d, 'a');
  const b = key(d, 'b');
  const msg = Buffer.from('{"v":1,"ticket":"x"}');
  const ok = (armored, o = {}) => verifySshSig({ armored, message: msg, namespace: NS, rawKey: a.raw, ...o });
  const sig = a.sign(msg);
  assert.equal(ok(sig), true);
  assert.equal(ok(a.sign(msg, NS, ['-O', 'hashalg=sha256'])), true);
  assert.equal(ok(sig, { message: Buffer.from('{"v":1,"ticket":"y"}') }), false);
  assert.equal(ok(sig, { rawKey: b.raw }), false);
  assert.equal(ok(b.sign(msg)), false);
  assert.equal(ok(a.sign(msg, 'zavod-other@v1')), false);
  assert.equal(ok(sig, { namespace: 'zavod-other@v1' }), false);
  const lines = sig.toString('latin1').split('\n');
  const body = Buffer.from(lines.slice(1, -2).join(''), 'base64');
  body[body.length - 5] ^= 1;
  const flipped = `${lines[0]}\n${body.toString('base64').match(/.{1,70}/g).join('\n')}\n${lines.at(-2)}\n`;
  assert.equal(ok(Buffer.from(flipped)), false);
  assert.equal(ok(sig.subarray(0, sig.length - 40)), false);
  assert.equal(ok(Buffer.from('not a signature')), false);
  assert.equal(ok(Buffer.concat([Buffer.from('x'), sig])), false);
  assert.equal(fingerprint(a.raw), execFileSync('ssh-keygen', ['-lf', `${a.f}.pub`], { encoding: 'utf8' }).split(' ')[1]);
});

test('sshsig: разбор открытого ключа', { skip: !hasKeygen() }, () => {
  const d = mkdtempSync(join(tmpdir(), 'zavod-sshsig-k-'));
  const a = key(d, 'a');
  assert.equal(parseEd25519PublicKey(a.pub).length, 32);
  assert.throws(() => parseEd25519PublicKey(a.pub.replace('ssh-ed25519', 'ssh-rsa')), TypeError);
  assert.throws(() => parseEd25519PublicKey(''), TypeError);
  assert.throws(() => parseEd25519PublicKey('ssh-ed25519 AAAA'), TypeError);
  assert.throws(() => parseEd25519PublicKey(`ssh-ed25519 ${Buffer.from('garbage').toString('base64')}`), TypeError);
});
