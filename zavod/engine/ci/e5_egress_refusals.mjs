// ДОКУМЕНТ: zavod/engine/ci/e5_egress_refusals.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-12 08:16 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: шаг S7 плана пилота (критерий E5-7) на строках Kernel настоящего прогона пилота: три отказа до
//   внешнего действия — подмена байта артефакта, чужой репозиторий, чужой заказчик/заказ; точный выпуск
//   проходит сверку. Строки — loadReleaseRows по настоящей строке outbox выпуска (SENT); артефакт — git archive
//   принятого head_sha из клона продукта; адаптер — src/product_egress.mjs с целью пилота. Внешний вызов здесь —
//   счётчик: точный выпуск уже сделан прогоном один раз (тег в продукте), повторять его нельзя; любой отказ
//   обязан случиться до счётчика. Чужой заказчик — RLS: строка outbox под другим заказчиком (из другого прогона
//   на том же Kernel) не читается. Чужой заказ и согласованный чужой репозиторий — подмена полей манифеста с
//   новой печатью (как если бы строки Kernel их называли).
// ВЫЗОВ: из zavod/engine: PGPORT=5436 P1_RUN_DIR=<папка прогона> P1_FOREIGN_RUN_DIR=<папка другого прогона>
//   node ci/e5_egress_refusals.mjs. Результат: <P1_RUN_DIR>/out/e5_egress_refusals.{log,json}.
// ОГРАНИЧЕНИЯ: только чтение Kernel (роль bem_kernel_rw, SELECT) и git/gh на чтение; ничего не пишет в Kernel и
//   в продукт; секретов нет.

import { readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { withRole } from '../../kernel/tests/helpers.mjs';
import { loadReleaseRows, verifyRelease, sealManifest } from '../../kernel/src/release_manifest.mjs';
import { productEgress } from '../src/product_egress.mjs';

const RT = 'C:/AI/multiagent-runtime';
const DIR = process.env.P1_RUN_DIR;
const FOREIGN_DIR = process.env.P1_FOREIGN_RUN_DIR;
if (!DIR || !FOREIGN_DIR) { console.error('need P1_RUN_DIR and P1_FOREIGN_RUN_DIR'); process.exit(2); }
const CLONE = process.env.P1_PRODUCT_CLONE || `${RT}/state/zavod_20261007/stage5_pilot/zavod-p1-bot`;
const PRODUCT = 'bereznyi-aleksandr/zavod-p1-bot';
const PRODUCT_ID = 1412203481;
const TAG = process.env.P1_TAG || 'p1-v0.1.0';
const OUT = join(DIR, 'out');
const LOG = join(OUT, 'e5_egress_refusals.log');
const sha = (b) => createHash('sha256').update(b).digest('hex');
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };
const checks = [];
const check = (id, ok, detail) => { checks.push({ id, ok: !!ok, detail }); log(`${ok ? 'CHECK_PASS' : 'CHECK_FAIL'} ${id}:`, detail); };
const run = (cmd, args, encoding = 'utf8') => new Promise((resolve) => execFile(cmd, args,
  { maxBuffer: 256 << 20, encoding, windowsHide: true }, (err, stdout, stderr) => resolve({ code: err ? (err.code ?? 1) : 0, stdout, stderr: String(stderr || '') })));
const codeOf = async (fn) => { try { await fn(); return 'OK'; } catch (e) { return e?.code || String(e?.message || e).slice(0, 80); } };

log('=== E5 S7 egress refusals', new Date().toISOString(), 'run', DIR);
const exp = JSON.parse(readFileSync(join(OUT, 'e5_pilot_export.json'), 'utf8'));
const foreign = JSON.parse(readFileSync(join(FOREIGN_DIR, 'out', 'e5_pilot_export.json'), 'utf8'));
const ob = exp.outbox.find((o) => o.kind === 'zavod.product.release');
const foreignTenant = foreign.ids.tenant;
const foreignWi = foreign.work_item[0].id;
if (!ob || foreignTenant === ob.tenant_id) { log('BAD_INPUT'); process.exit(2); }

const rows = await withRole('bem_kernel_rw', (c) => loadReleaseRows(c, { tenant_id: ob.tenant_id, outbox_id: ob.id }));
const a = await run('git', ['-C', CLONE, 'archive', '--format=tar', rows.manifest.head_sha], 'buffer');
if (a.code !== 0) { log('ARTIFACT_FAILED', a.stderr.slice(0, 200)); process.exit(2); }
const artifact = a.stdout;
log(`ROWS outbox=${ob.id} status=${ob.status} head=${rows.manifest.head_sha} manifest=${rows.manifest.manifest_sha256} artifact_sha256=${sha(artifact)}`);

let calls = 0;
const counter = async ({ manifest_sha256 }) => { calls += 1; return { reached: true, manifest_sha256 }; };
const EG = productEgress({ repo_id: PRODUCT_ID, repo_full_name: PRODUCT });
async function refusedBefore(id, expect, fn, what) {
  const before = calls;
  const code = await codeOf(fn);
  check(id, code === expect && calls === before, `${what}: ${code}; внешних вызовов до отказа ${calls - before}`);
}
const reseal = (over) => { const { manifest_sha256: _, ...f } = rows.manifest; return sealManifest({ ...f, ...over }); };

// Точный выпуск: адаптер с целью пилота пропускает настоящие строки и байты до внешнего вызова.
const before = calls;
const ok = await EG.release({ ...rows, artifact }, counter);
check('s7_exact_passes', ok.reached && calls === before + 1 && ok.manifest_sha256 === rows.manifest.manifest_sha256
  && verifyRelease({ ...rows, artifact }) === rows.manifest.manifest_sha256, `печать ${ok.manifest_sha256}, вызов достигнут один раз (счётчик, не GitHub)`);

// 1. Подмена одного байта артефакта.
const bad = Buffer.from(artifact); bad[bad.length >> 1] ^= 0x01;
await refusedBefore('s7_tampered_byte', 'ARTIFACT_MISMATCH', () => EG.release({ ...rows, artifact: bad }, counter), 'байт артефакта изменён');

// 2. Чужой репозиторий: (а) адаптер другого продукта получает строки пилота; (б) строки согласованно называют чужой.
const other = productEgress({ repo_id: 900000001, repo_full_name: 'other-org/other-bot' });
await refusedBefore('s7_foreign_repo_adapter', 'TARGET_MISMATCH', () => other.release({ ...rows, artifact }, counter), 'адаптер чужого репозитория');
const fm = reseal({ repo_id: 900000001, repo_full_name: 'other-org/other-bot' });
const fRows = { ...rows, artifact, manifest: fm,
  outbox: { ...rows.outbox, payload: { ...rows.outbox.payload, repo_id: fm.repo_id, repo_full_name: fm.repo_full_name, manifest_sha256: fm.manifest_sha256 } } };
check('s7_foreign_repo_rows_consistent', verifyRelease(fRows) === fm.manifest_sha256, 'строки между собой согласованы: без цели адаптера сверка прошла бы');
await refusedBefore('s7_foreign_repo_rows', 'TARGET_MISMATCH', () => EG.release(fRows, counter), 'манифест и outbox называют чужой репозиторий');

// 3. Чужой заказчик и чужой заказ.
await refusedBefore('s7_foreign_tenant_rls', 'OUTBOX_MISMATCH', () => withRole('bem_kernel_rw',
  (c) => loadReleaseRows(c, { tenant_id: foreignTenant, outbox_id: ob.id })), `строка outbox под заказчиком ${foreignTenant}`);
await refusedBefore('s7_foreign_tenant_manifest', 'TENANT_MISMATCH', () => EG.release({ ...rows, artifact, manifest: reseal({ tenant_id: foreignTenant }) }, counter),
  'манифест назван на другого заказчика');
await refusedBefore('s7_foreign_order', 'ORDER_MISMATCH', () => EG.release({ ...rows, artifact, manifest: reseal({ work_item_id: foreignWi }) }, counter),
  `манифест назван на заказ ${foreignWi}`);

// Внешнее действие прогона было одно: тег на принятом head_sha.
const tags = await run('git', ['ls-remote', `https://github.com/${PRODUCT}`, 'refs/tags/*']);
const tagLines = tags.stdout.trim().split('\n').filter(Boolean);
check('s7_single_real_release', tags.code === 0 && ob.status === 'SENT' && tagLines.length === 1
  && tagLines[0] === `${rows.manifest.head_sha}\trefs/tags/${TAG}`, `outbox ${ob.status}; теги продукта: ${tagLines.join(' | ')}`);

const FAIL = checks.some((c) => !c.ok);
const res = { result: FAIL ? 'FAIL' : 'PASS', outbox_id: ob.id, head_sha: rows.manifest.head_sha, manifest_sha256: rows.manifest.manifest_sha256,
  artifact_sha256: sha(artifact), foreign_tenant: foreignTenant, foreign_work_item: foreignWi, checks, id: randomUUID() };
const t = JSON.stringify(res, null, 1);
writeFileSync(join(OUT, 'e5_egress_refusals.json'), t);
log(`=== E5_S7_RESULT=${FAIL ? 'FAIL' : 'PASS'} (${checks.filter((c) => c.ok).length}/${checks.length}) json_sha256=${sha(t)}`);
process.exit(FAIL ? 1 : 0);
