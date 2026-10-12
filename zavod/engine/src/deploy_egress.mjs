// ДОКУМЕНТ: zavod/engine/src/deploy_egress.mjs
// ВЕРСИЯ: v0.5  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 10:14 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 13:39 +03:00 (v0.5: аудит ChatGPT S6-prep R4,
//   M-S6-R4-01 — operatorSigner больше не берёт путь к allowed_signers и не зовёт ssh-keygen: открытый ключ выпуска
//   передаётся строкой при создании (закреплённый источник — у вызывающего), разбирается один раз и держится в
//   памяти; подпись проверяется в памяти (sshsig.mjs, формат SSHSIG) по байтам билета из памяти кода. Файл
//   SIGN_COMMAND.txt убран: оператор не исполняет команду из общей папки, у него одна постоянная функция
//   Sign-ZavodTicket (zavod/ops/operator/sign_ticket.ps1.txt), которая читает билет один раз и подписывает те же
//   байты, что показала. v0.4: аудит ChatGPT S6-prep R3,
//   M-S6-R3-01 — sshSigner убран: у агентов больше нет функции, которая подписывает произвольные байты ключом
//   выпуска. Подпись билета — только явное действие оператора: operatorSigner кладёт билет в папку запроса, пишет
//   точную команду для оператора и ждёт файл подписи; подпись принимается только после ssh-keygen -Y verify
//   открытым ключом выпуска по байтам, которые держит сам код. Ключ выпуска у оператора под паролем. Срок билета
//   по умолчанию 3600 с (оператору нужно время), запас до конца срока 600 с — на прогон workflow.
//   v0.3: аудит ChatGPT S6-prep R2.
//   M-S6-R2-02 — после verifyRelease адаптер выпускает билет выпуска (v=1, ticket_id = outbox_id, head_sha,
//   artifact_sha256, manifest_sha256, repo_id, repo_full_name, tenant_id, work_item_id, issued_at, expires_at
//   не больше часа) и подписывает его функцией sign (sshSigner: ssh-keygen -Y sign, пространство имён
//   zavod-release-ticket@v1, ключ выпуска Завода — путь к файлу, сам ключ код не читает). Без подписи сервер и
//   workflow ничего не ставят. L-S6-R2-01 — ghDeployInstall берёт только прогоны workflow_dispatch, созданные
//   после запуска, с точным именем «p1-deploy <outbox_id>»; два таких прогона — отказ DEPLOY_RUN_AMBIGUOUS; строка
//   результата обязана нести тот же outbox_id и быть ровно одна; INSTALL_OK при неуспешном прогоне — отказ
//   DEPLOY_RUN_FAILED; не нашли прогон или не дождались — DEPLOY_RUN_TIMEOUT.
//   v0.2: M-S6-05/L-S6-01 — sshInstall убран; транспорт сервера — workflow продукта с ключом из секрета GitHub)
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: этап 6, E6-2 — адаптер Egress деплоя продукта на сервер. Одна строка outbox выпуска → одна
//   установка. Порядок: цель сервера (repo_id, repo_full_name, tenant_id — сервер принадлежит одному
//   заказчику; чужой tenant — DEPLOY_TENANT_MISMATCH до всего остального) → productEgress (цель репозитория,
//   verifyRelease: печать, байты артефакта, предмет, заказ, outbox, решение оператора) → билет и подпись →
//   install(...) — передача манифеста, архива, билета и подписи на сервер, где install_release.sh сверяет их
//   второй раз. Ответ сервера разбирается строго: INSTALL_OK state=installed|already_present head=<head_sha>.
// ОГРАНИЧЕНИЯ: адаптер сам сеть не открывает: install — функция вызывающего (ghDeployInstall для сервера,
//   localInstall для проверок). Ключей SSH сервера нет ни у адаптера, ни у агента: ключ живёт только в секрете
//   окружения GitHub. Ключа подписи билетов у кода нет совсем: он под паролем у оператора, подписывает оператор.
//   Временные файлы остаются в tmpdir ОС (ничего не удаляется).
import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { ReleaseRefused } from '../../kernel/src/release_manifest.mjs';
import { productEgress } from './product_egress.mjs';
import { fingerprint, parseEd25519PublicKey, verifySshSig } from './sshsig.mjs';

const run = promisify(execFile);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const OK_LINE = /^INSTALL_OK state=(installed|already_present) head=([0-9a-f]{40})$/m;
const REFUSED_LINE = /^INSTALL_REFUSED code=([A-Z_]+)$/m;
export const TICKET_NAMESPACE = 'zavod-release-ticket@v1';
const TICKET_FIELDS = ['head_sha', 'artifact_sha256', 'manifest_sha256', 'repo_id', 'repo_full_name', 'tenant_id', 'work_item_id'];

// Билет выпуска: что именно разрешено поставить, кем (подпись) и до какого времени.
export function releaseTicket({ manifest, outbox_id, now = Date.now(), ttlSec = 3600 }) {
  if (!UUID.test(outbox_id || '')) throw new TypeError('releaseTicket: bad outbox_id');
  if (!Number.isInteger(ttlSec) || ttlSec <= 0 || ttlSec > 3600) throw new TypeError('releaseTicket: bad ttl');
  const issued_at = Math.floor(now / 1000);
  const t = { v: 1, ticket_id: outbox_id, issued_at, expires_at: issued_at + ttlSec };
  for (const k of TICKET_FIELDS) {
    if (manifest?.[k] === undefined) throw new TypeError(`releaseTicket: manifest has no ${k}`);
    t[k] = manifest[k];
  }
  return Buffer.from(JSON.stringify(t), 'utf8');
}

export function deployEgress({ repo_id, repo_full_name, tenant_id }, install, { sign, now = () => Date.now(), ttlSec = 3600 } = {}) {
  if (typeof tenant_id !== 'string' || !UUID.test(tenant_id) || typeof install !== 'function') {
    throw new TypeError('deployEgress: bad target');
  }
  if (typeof sign !== 'function') throw new TypeError('deployEgress: no ticket signer');
  const repo = productEgress({ repo_id, repo_full_name });
  const target = Object.freeze({ ...repo.target, tenant_id });
  return {
    target,
    async deploy(rows) {
      if (rows?.manifest?.tenant_id !== tenant_id) {
        throw new ReleaseRefused('DEPLOY_TENANT_MISMATCH', 'manifest names another tenant than this server');
      }
      return repo.release(rows, async ({ manifest_sha256, outbox_id }) => {
        const ticket = releaseTicket({ manifest: rows.manifest, outbox_id, now: now(), ttlSec });
        const ticket_sig = Buffer.from(await sign(ticket));
        if (ticket_sig.length === 0) throw new ReleaseRefused('TICKET_NOT_SIGNED', 'signer returned nothing');
        const out = await install({ manifest: rows.manifest, artifact: rows.artifact, manifest_sha256, outbox_id, ticket, ticket_sig });
        const refused = REFUSED_LINE.exec(out || '');
        if (refused) throw new ReleaseRefused(`SERVER_${refused[1]}`, 'server refused the release');
        const ok = OK_LINE.exec(out || '');
        if (!ok || ok[2] !== rows.manifest.head_sha) throw new ReleaseRefused('SERVER_NO_CONFIRMATION', 'no INSTALL_OK for this head');
        return { state: ok[1], head_sha: ok[2], manifest_sha256, outbox_id, ticket_id: outbox_id };
      });
    },
  };
}

// Подпись билета (v0.5, аудит ChatGPT S6-prep R4, M-S6-R4-01; v0.4 — R3, M-S6-R3-01) — только явное действие
// оператора. У кода нет ни закрытого ключа выпуска, ни вызова ssh-keygen. Открытый ключ выпуска (строка
// «ssh-ed25519 …») передаётся при создании и держится в памяти: подменить его файлом нельзя. Код кладёт билет в
// новую папку запроса <requestsDir>/<ticket_id>_<sha256[:12]>/ticket.json (другие байты под тем же именем —
// TICKET_REQUEST_CONFLICT, те же байты — повтор того же запроса), сообщает notify(...) путь, SHA-256 билета и
// отпечаток ключа и ждёт ticket.json.sig до конца срока билета минус SIGN_MARGIN_S. Подпись проверяется в памяти по
// байтам билета из памяти кода: не тот ключ, не тот билет, не то пространство имён — TICKET_BAD_OPERATOR_SIGNATURE.
// Оператор подписывает постоянной функцией Sign-ZavodTicket: она читает файл один раз, показывает поля и SHA-256 и
// подписывает те же байты из памяти. Подмена ticket.json до чтения видна оператору (другие поля и SHA-256), а
// подпись подменённых байтов код не примет: они не совпадут с билетом в памяти.
const SIGN_MARGIN_S = 600;
const sha256 = (b) => createHash('sha256').update(b).digest('hex');
// expectFingerprint (необязательно) — отпечаток ключа из второго, независимого источника (решение оператора OD-5):
// ключ с другим отпечатком не принимается при создании.
export function operatorSigner({ requestsDir, releasePublicKey, expectFingerprint, notify = async () => {},
  namespace = TICKET_NAMESPACE, now = () => Date.now(), wait = (ms) => new Promise((r) => setTimeout(r, ms)), pollMs = 5000 }) {
  if (typeof requestsDir !== 'string' || requestsDir.length === 0 || /['"`$\r\n]/.test(requestsDir)) {
    throw new TypeError('operatorSigner: bad requests dir');
  }
  const rawKey = parseEd25519PublicKey(releasePublicKey);
  const key_fingerprint = fingerprint(rawKey);
  if (expectFingerprint !== undefined && expectFingerprint !== key_fingerprint) {
    throw new TypeError('operatorSigner: release key fingerprint mismatch');
  }
  return async (bytes) => {
    const ticket = Buffer.from(bytes);
    const t = JSON.parse(ticket.toString('utf8'));
    if (!UUID.test(t.ticket_id || '') || !Number.isInteger(t.expires_at)) throw new TypeError('operatorSigner: bad ticket');
    const ticket_sha256 = sha256(ticket);
    const dir = join(requestsDir, `${t.ticket_id}_${ticket_sha256.slice(0, 12)}`);
    const f = join(dir, 'ticket.json');
    mkdirSync(dir, { recursive: true });
    try {
      writeFileSync(f, ticket, { flag: 'wx' });
    } catch (e) {
      if (e.code !== 'EEXIST' || !readFileSync(f).equals(ticket)) {
        throw new ReleaseRefused('TICKET_REQUEST_CONFLICT', 'request folder holds other bytes');
      }
    }
    await notify({ ticket_id: t.ticket_id, path: f, ticket_sha256, key_fingerprint, ticket: t });
    const sigPath = `${f}.sig`;
    const deadline = (t.expires_at - SIGN_MARGIN_S) * 1000;
    while (now() < deadline) {
      if (existsSync(sigPath)) {
        const sig = readFileSync(sigPath);
        if (verifySshSig({ armored: sig, message: ticket, namespace, rawKey })) return sig;
        // файл подписи мог быть дописан в момент чтения — тогда ждём; тот же файл и не проходит — отказ
        if (readFileSync(sigPath).equals(sig)) {
          throw new ReleaseRefused('TICKET_BAD_OPERATOR_SIGNATURE', 'signature does not verify for this ticket and key');
        }
      }
      await wait(pollMs);
    }
    throw new ReleaseRefused('TICKET_NOT_SIGNED_IN_TIME', 'operator did not sign before the ticket deadline');
  };
}

function stage({ manifest, artifact, ticket, ticket_sig }) {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-deploy-'));
  const h8 = manifest.head_sha.slice(0, 8);
  const m = join(dir, `manifest_${h8}.json`);
  const a = join(dir, `artifact_${h8}.tar`);
  const t = join(dir, `ticket_${h8}.json`);
  const s = join(dir, `ticket_${h8}.sig`);
  writeFileSync(m, JSON.stringify({ manifest }, null, 2));
  writeFileSync(a, artifact);
  writeFileSync(t, ticket);
  writeFileSync(s, ticket_sig);
  return { dir, m, a, t, s };
}

// Сервер (v0.2, аудит ChatGPT S6-prep M-S6-05, L-S6-01): Завод не держит ключ сервера и не ходит на сервер сам.
// Он запускает workflow выкладки в репозитории продукта (gh workflow run): workflow проверяет подпись билета, сам
// собирает архив git archive на head_sha, сверяет его SHA-256 с манифестом и передаёт на сервер ключом из секрета
// окружения GitHub (deploy_push.sh). Ответ сервера workflow печатает строкой ZAVOD_RESULT <outbox_id> <строка>.
// v0.3 (L-S6-R2-01): свой прогон — ровно один прогон workflow_dispatch, созданный после запуска, с точным именем;
// строка результата — ровно одна и с тем же outbox_id; успех сервера при неуспешном прогоне — отказ.
const RESULT = /ZAVOD_RESULT ([0-9a-f-]{36}) (INSTALL_OK state=(?:installed|already_present) head=[0-9a-f]{40}|INSTALL_REFUSED code=[A-Z_]+)\r?$/gm;
const SKEW_MS = 60000;
export function ghDeployInstall({ repo_full_name, workflow = 'p1-deploy.yml', ref = 'main', exec = run,
  wait = (ms) => new Promise((r) => setTimeout(r, ms)), now = () => Date.now(), pollMs = 10000, maxPolls = 90 }) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo_full_name || '')) throw new TypeError('ghDeployInstall: bad repo');
  const R = ['-R', repo_full_name];
  const mine = async (title, since) => {
    const { stdout } = await exec('gh', ['run', 'list', ...R, '-w', workflow, '-e', 'workflow_dispatch', '-L', '50',
      '--json', 'databaseId,displayTitle,createdAt,event']);
    return JSON.parse(stdout || '[]').filter((x) => x.displayTitle === title && x.event === 'workflow_dispatch'
      && Date.parse(x.createdAt) >= since - SKEW_MS);
  };
  return async ({ manifest, outbox_id, ticket, ticket_sig }) => {
    if (!UUID.test(outbox_id || '')) throw new TypeError('ghDeployInstall: bad outbox_id');
    if (!ticket?.length || !ticket_sig?.length) throw new TypeError('ghDeployInstall: no signed ticket');
    const b64 = (x) => Buffer.from(x).toString('base64');
    const title = `p1-deploy ${outbox_id}`;
    const since = now();
    await exec('gh', ['workflow', 'run', workflow, ...R, '--ref', ref, '-f', `head_sha=${manifest.head_sha}`,
      '-f', `manifest_b64=${b64(JSON.stringify({ manifest }))}`, '-f', `request_id=${outbox_id}`,
      '-f', `ticket_b64=${b64(ticket)}`, '-f', `sig_b64=${b64(ticket_sig)}`]);
    let id = null;
    for (let i = 0; i < maxPolls; i += 1) {
      const hits = await mine(title, since);
      if (hits.length > 1) throw new ReleaseRefused('DEPLOY_RUN_AMBIGUOUS', `${hits.length} runs named ${title}`);
      if (id !== null && (hits.length === 0 || String(hits[0].databaseId) !== id)) {
        throw new ReleaseRefused('DEPLOY_RUN_AMBIGUOUS', 'run list changed under us');
      }
      if (hits.length === 1) id = String(hits[0].databaseId);
      if (id !== null) {
        const { stdout } = await exec('gh', ['run', 'view', id, ...R, '--json', 'status,conclusion,event,displayTitle']);
        const v = JSON.parse(stdout);
        if (v.event !== 'workflow_dispatch' || v.displayTitle !== title) throw new ReleaseRefused('DEPLOY_RUN_AMBIGUOUS', 'run changed');
        if (v.status === 'completed') {
          const log = await exec('gh', ['run', 'view', id, ...R, '--log']).catch((e) => ({ stdout: e.stdout || '' }));
          const lines = [...String(log.stdout).matchAll(RESULT)].filter((m) => m[1] === outbox_id).map((m) => m[2]);
          if (lines.length !== 1) throw new ReleaseRefused('DEPLOY_RUN_NO_RESULT', `${lines.length} result lines`);
          if (lines[0].startsWith('INSTALL_OK') && v.conclusion !== 'success') {
            throw new ReleaseRefused('DEPLOY_RUN_FAILED', `run ${v.conclusion} but server line is INSTALL_OK`);
          }
          return `${lines[0]}\n`;
        }
      }
      await wait(pollMs);
    }
    throw new ReleaseRefused('DEPLOY_RUN_TIMEOUT', id === null ? 'run not found' : 'run did not complete');
  };
}

// Проверки: тот же install_release.sh локально (Linux), с переменными ROOT/TARGET_ENV/JOURNAL/RESTART/
// RELEASE_SIGNERS/TICKETS.
export function localInstall({ script, env }) {
  return async (job) => {
    const { dir, m, a, t, s } = stage(job);
    const r = await run('bash', [script, m, a, t, s], { env: { ...process.env, ...env, INCOMING: dir } }).catch((e) => ({ stdout: e.stdout || '' }));
    return r.stdout;
  };
}
