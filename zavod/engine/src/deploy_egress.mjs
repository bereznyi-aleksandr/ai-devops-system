// ДОКУМЕНТ: zavod/engine/src/deploy_egress.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 10:14 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: этап 6, E6-2 — адаптер Egress деплоя продукта на сервер. Одна строка outbox выпуска → одна
//   установка. Порядок: цель сервера (repo_id, repo_full_name, tenant_id — сервер принадлежит одному
//   заказчику; чужой tenant — DEPLOY_TENANT_MISMATCH до всего остального) → productEgress (цель репозитория,
//   verifyRelease: печать, байты артефакта, предмет, заказ, outbox, решение оператора) → install(...) — передача
//   манифеста и архива на сервер, где install_release.sh сверяет их второй раз. Ответ сервера разбирается
//   строго: INSTALL_OK state=installed|already_present head=<head_sha манифеста>; иначе — отказ.
// ОГРАНИЧЕНИЯ: адаптер сам сеть не открывает: install — функция вызывающего (sshInstall для сервера,
//   localInstall для проверок). Ключ SSH адаптер не читает: ssh берёт его из агента SSH оператора. Секретов нет.
import { execFile } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { ReleaseRefused } from '../../kernel/src/release_manifest.mjs';
import { productEgress } from './product_egress.mjs';

const run = promisify(execFile);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const OK_LINE = /^INSTALL_OK state=(installed|already_present) head=([0-9a-f]{40})$/m;
const REFUSED_LINE = /^INSTALL_REFUSED code=([A-Z_]+)$/m;

export function deployEgress({ repo_id, repo_full_name, tenant_id }, install) {
  if (typeof tenant_id !== 'string' || !UUID.test(tenant_id) || typeof install !== 'function') {
    throw new TypeError('deployEgress: bad target');
  }
  const repo = productEgress({ repo_id, repo_full_name });
  const target = Object.freeze({ ...repo.target, tenant_id });
  return {
    target,
    async deploy(rows) {
      if (rows?.manifest?.tenant_id !== tenant_id) {
        throw new ReleaseRefused('DEPLOY_TENANT_MISMATCH', 'manifest names another tenant than this server');
      }
      return repo.release(rows, async ({ manifest_sha256, outbox_id }) => {
        const out = await install({ manifest: rows.manifest, artifact: rows.artifact, manifest_sha256, outbox_id });
        const refused = REFUSED_LINE.exec(out || '');
        if (refused) throw new ReleaseRefused(`SERVER_${refused[1]}`, 'server refused the release');
        const ok = OK_LINE.exec(out || '');
        if (!ok || ok[2] !== rows.manifest.head_sha) throw new ReleaseRefused('SERVER_NO_CONFIRMATION', 'no INSTALL_OK for this head');
        return { state: ok[1], head_sha: ok[2], manifest_sha256, outbox_id };
      });
    },
  };
}

function stage({ manifest, artifact }) {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-deploy-'));
  const m = join(dir, `manifest_${manifest.head_sha.slice(0, 8)}.json`);
  const a = join(dir, `artifact_${manifest.head_sha.slice(0, 8)}.tar`);
  writeFileSync(m, JSON.stringify({ manifest }, null, 2));
  writeFileSync(a, artifact);
  return { dir, m, a };
}

// Сервер: scp манифеста и архива во входящую папку, затем install_release.sh. BatchMode — без паролей.
export function sshInstall({ host, user = 'zavod', script = '/opt/zavod-ops/install_release.sh',
  inbox = '/var/lib/zavod-p1/incoming', exec = run }) {
  if (!/^[A-Za-z0-9.:-]+$/.test(host)) throw new TypeError('sshInstall: bad host');
  const base = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes'];
  return async (job) => {
    const { m, a } = stage(job);
    const h = job.manifest.head_sha.slice(0, 8);
    await exec('scp', [...base, m, a, `${user}@${host}:${inbox}/`]);
    const r = await exec('ssh', [...base, `${user}@${host}`, 'sudo', script,
      `${inbox}/manifest_${h}.json`, `${inbox}/artifact_${h}.tar`]).catch((e) => ({ stdout: e.stdout || '' }));
    return r.stdout;
  };
}

// Проверки: тот же install_release.sh локально (Linux), с переменными ROOT/TARGET_ENV/JOURNAL/RESTART.
export function localInstall({ script, env }) {
  return async (job) => {
    const { m, a } = stage(job);
    const r = await run('bash', [script, m, a], { env: { ...process.env, ...env } }).catch((e) => ({ stdout: e.stdout || '' }));
    return r.stdout;
  };
}
