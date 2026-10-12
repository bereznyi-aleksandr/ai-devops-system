// ДОКУМЕНТ: zavod/engine/src/deploy_egress.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 10:14 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 10:39 +03:00 (v0.2: аудит ChatGPT S6-prep
//   M-S6-05/L-S6-01 — sshInstall (ssh с агентом ключей оператора) убран; транспорт сервера — ghDeployInstall:
//   workflow выкладки репозитория продукта с ключом из секрета GitHub; localInstall передаёт INCOMING)
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: этап 6, E6-2 — адаптер Egress деплоя продукта на сервер. Одна строка outbox выпуска → одна
//   установка. Порядок: цель сервера (repo_id, repo_full_name, tenant_id — сервер принадлежит одному
//   заказчику; чужой tenant — DEPLOY_TENANT_MISMATCH до всего остального) → productEgress (цель репозитория,
//   verifyRelease: печать, байты артефакта, предмет, заказ, outbox, решение оператора) → install(...) — передача
//   манифеста и архива на сервер, где install_release.sh сверяет их второй раз. Ответ сервера разбирается
//   строго: INSTALL_OK state=installed|already_present head=<head_sha манифеста>; иначе — отказ.
// ОГРАНИЧЕНИЯ: адаптер сам сеть не открывает: install — функция вызывающего (ghDeployInstall для сервера,
//   localInstall для проверок). Ключей SSH нет ни у адаптера, ни у агента: ключ живёт только в секрете GitHub.
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

// Сервер (v0.2, аудит ChatGPT S6-prep M-S6-05, L-S6-01): Завод не держит ключ сервера и не ходит на сервер сам.
// Он запускает workflow выкладки в репозитории продукта (gh workflow run): workflow сам собирает архив git archive
// на head_sha, сверяет его SHA-256 с манифестом и передаёт на сервер ключом из секрета GitHub (deploy_push.sh).
// Ответ сервера workflow печатает строкой ZAVOD_RESULT <строка сервера>; адаптер находит прогон по request_id
// (= outbox_id, конец имени прогона), ждёт завершения и возвращает только эти строки — разбор строгий, как раньше.
const RESULT = /ZAVOD_RESULT (INSTALL_(?:OK|REFUSED) [^\r\n]*)/g;
export function ghDeployInstall({ repo_full_name, workflow = 'p1-deploy.yml', ref = 'main', exec = run,
  wait = (ms) => new Promise((r) => setTimeout(r, ms)), pollMs = 10000, maxPolls = 90 }) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo_full_name || '')) throw new TypeError('ghDeployInstall: bad repo');
  const R = ['-R', repo_full_name];
  return async ({ manifest, outbox_id }) => {
    if (!UUID.test(outbox_id || '')) throw new TypeError('ghDeployInstall: bad outbox_id');
    const b64 = Buffer.from(JSON.stringify({ manifest })).toString('base64');
    await exec('gh', ['workflow', 'run', workflow, ...R, '--ref', ref, '-f', `head_sha=${manifest.head_sha}`,
      '-f', `manifest_b64=${b64}`, '-f', `request_id=${outbox_id}`]);
    let id = null;
    for (let i = 0; i < maxPolls; i += 1) {
      if (id === null) {
        const { stdout } = await exec('gh', ['run', 'list', ...R, '-w', workflow, '-L', '20', '--json', 'databaseId,displayTitle']);
        const hit = JSON.parse(stdout || '[]').find((x) => String(x.displayTitle).endsWith(` ${outbox_id}`));
        if (hit) id = String(hit.databaseId);
      }
      if (id !== null) {
        const { stdout } = await exec('gh', ['run', 'view', id, ...R, '--json', 'status,conclusion']);
        if (JSON.parse(stdout).status === 'completed') {
          const log = await exec('gh', ['run', 'view', id, ...R, '--log']).catch((e) => ({ stdout: e.stdout || '' }));
          return [...String(log.stdout).matchAll(RESULT)].map((m) => m[1].trim()).join('\n') + '\n';
        }
      }
      await wait(pollMs);
    }
    return '';
  };
}

// Проверки: тот же install_release.sh локально (Linux), с переменными ROOT/TARGET_ENV/JOURNAL/RESTART.
export function localInstall({ script, env }) {
  return async (job) => {
    const { dir, m, a } = stage(job);
    const r = await run('bash', [script, m, a], { env: { ...process.env, ...env, INCOMING: dir } }).catch((e) => ({ stdout: e.stdout || '' }));
    return r.stdout;
  };
}
