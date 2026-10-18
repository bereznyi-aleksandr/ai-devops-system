// ДОКУМЕНТ: tests/rules_registry_repo.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 08:59 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 08:59 +03:00 (v0.1: реестр правил репозитория в формате ядра)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: настоящий реестр zavod/rules/RULES_REGISTRY.json разбирается тем же parseRegistry, что и включение
//   правил; каждый файл из него есть в репозитории; роли иерархии = папки roles/ с ROLE.md; MEMORY.md и HANDOFF.md
//   правилами не являются (протокол v2.5 Д.7, Л.8; AGENTS.md «Где живут эти файлы»).
// ОГРАНИЧЕНИЯ: только чтение файлов репозитория; база, сеть и секреты не нужны.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseRegistry, REGISTRY_PATH } from '../src/rules_gate.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

test('реестр правил репозитория: формат ядра, файлы на месте, роли = папки roles/', () => {
  const reg = parseRegistry(readFileSync(join(ROOT, REGISTRY_PATH)));
  for (const f of reg.files) assert.ok(existsSync(join(ROOT, f)), `нет файла ${f}`);
  assert.ok(!reg.files.some((f) => /(^|\/)(MEMORY|HANDOFF)\.md$/.test(f)), 'MEMORY.md и HANDOFF.md не правила');
  const folders = readdirSync(join(ROOT, 'roles')).filter((d) => statSync(join(ROOT, 'roles', d)).isDirectory()).sort();
  assert.deepEqual(Object.keys(reg.role_parents), folders);
  for (const d of folders) assert.ok(reg.files.includes(`roles/${d}/ROLE.md`), `ROLE.md роли ${d} не в реестре`);
  assert.deepEqual(Object.entries(reg.role_parents).filter(([, p]) => p === 'OPERATOR').map(([k]) => k), ['01_Куратор_ГД']);
});
