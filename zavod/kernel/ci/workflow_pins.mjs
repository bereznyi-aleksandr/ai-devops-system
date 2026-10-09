// ДОКУМЕНТ: ci/workflow_pins.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-08 23:05 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 23:05 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: SR-08 для CI (аудит E3-5 L-E35-01): внешние части workflow закреплены неизменяемо —
//   действия GitHub по SHA коммита (40 знаков), образ PostgreSQL по digest sha256, Node — точная
//   версия x.y.z; клиент psql берётся из того же образа (ZAVOD_PG_IMAGE = образ сервиса), установка
//   клиента из apt без версии запрещена. Плавающая ссылка (тег, major, latest) — отказ.
// ВЫЗОВ: node ci/workflow_pins.mjs <файл workflow> -> WORKFLOW_PINS=PASS|FAIL, код 0|1.
// ОГРАНИЧЕНИЯ: разбор построчный, под формат этого workflow; YAML целиком не разбирается.

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const strip = (v) => v.replace(/\s+#.*$/, '').trim().replace(/^['"]|['"]$/g, '');
const ACTION = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_./-]+)?@[0-9a-f]{40}$/;
const IMAGE = /^[A-Za-z0-9_./-]+(?::[A-Za-z0-9_.-]+)?@sha256:[0-9a-f]{64}$/;
const VERSION = /^\d+\.\d+\.\d+$/;

export function workflowPinErrors(text) {
  const errors = [];
  const found = { uses: 0, image: 0, node: 0 };
  let serviceImage = null;
  let pgImage = null;
  for (const raw of text.split(/\r?\n/)) {
    if (/^\s*#/.test(raw)) continue;
    let m;
    if ((m = /^\s*(?:-\s*)?uses:\s*(.+)$/.exec(raw))) {
      found.uses += 1;
      const v = strip(m[1]);
      if (!ACTION.test(v)) errors.push(`action not pinned to commit sha: ${v}`);
    } else if ((m = /^\s*image:\s*(.+)$/.exec(raw))) {
      found.image += 1;
      serviceImage = strip(m[1]);
      if (!IMAGE.test(serviceImage)) errors.push(`image not pinned to digest: ${serviceImage}`);
    } else if ((m = /^\s*node-version:\s*(.+)$/.exec(raw))) {
      found.node += 1;
      const v = strip(m[1]);
      if (!VERSION.test(v)) errors.push(`node-version not exact: ${v}`);
    } else if ((m = /^\s*ZAVOD_PG_IMAGE:\s*(.+)$/.exec(raw))) {
      pgImage = strip(m[1]);
      if (!IMAGE.test(pgImage)) errors.push(`ZAVOD_PG_IMAGE not pinned to digest: ${pgImage}`);
    }
    if (/apt-get\s+install[^\n]*postgresql-client/.test(raw)) errors.push('psql client installed from apt without pinned version');
  }
  if (!found.uses) errors.push('no actions found');
  if (!found.image) errors.push('no service image found');
  if (!found.node) errors.push('no node-version found');
  if (!pgImage) errors.push('ZAVOD_PG_IMAGE missing: psql client image not pinned');
  else if (serviceImage && pgImage !== serviceImage) errors.push('psql client image differs from service image');
  return errors;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const errors = workflowPinErrors(readFileSync(process.argv[2], 'utf8'));
  for (const e of errors) console.log(`PIN ${e}`);
  console.log(errors.length ? `WORKFLOW_PINS=FAIL (${errors.length})` : 'WORKFLOW_PINS=PASS');
  process.exit(errors.length ? 1 : 0);
}
