// ДОКУМЕНТ: zavod/engine/src/product_egress.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 08:16 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: адаптер Egress выпуска продукта (этап 5, шаг S7, критерий E5-7). До v0.1 адаптер жил внутри
//   ci/e5_pilot_run.mjs и сверял только строки Kernel между собой (release_manifest.verifyRelease): манифест и
//   строка outbox, согласованно назвавшие ДРУГОЙ репозиторий, проходили сверку, а внешний вызов уходил в
//   репозиторий, на который настроен адаптер. Теперь адаптер знает свою цель (repo_id, repo_full_name) и
//   отказывает TARGET_MISMATCH до внешнего вызова, если манифест называет не её. Порядок: цель адаптера →
//   verifyRelease (печать, байты артефакта, предмет, заказчик, заказ, outbox, решение оператора) → send.
// ОГРАНИЧЕНИЯ: адаптер сам ничего не публикует: внешний вызов — функция send вызывающего. Секретов нет.

import { releaseViaEgress, ReleaseRefused } from '../../kernel/src/release_manifest.mjs';

const REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

// target — неизменяемая цель адаптера, задаётся при создании, а не строками Kernel.
export function productEgress({ repo_id, repo_full_name }) {
  if (!(Number.isSafeInteger(repo_id) && repo_id > 0) || typeof repo_full_name !== 'string' || !REPO_RE.test(repo_full_name)) {
    throw new TypeError('productEgress: bad target');
  }
  const target = Object.freeze({ repo_id, repo_full_name });
  return {
    target,
    // rows — строки Kernel (loadReleaseRows) и байты артефакта; send — единственный внешний вызов.
    async release(rows, send) {
      const m = rows?.manifest || {};
      if (m.repo_id !== target.repo_id || m.repo_full_name !== target.repo_full_name) {
        throw new ReleaseRefused('TARGET_MISMATCH', 'manifest names another repository than this adapter');
      }
      return releaseViaEgress(rows, send);
    },
  };
}
