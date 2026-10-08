// ДОКУМЕНТ: tests/scan.test.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 23:10 +03:00 (v0.2: аудит E3-5 —
//   M-E35-04: исключений целых файлов нет, поддельный ключ в бывших файлах-исключениях и в workflow
//   ловится; L-E35-01: закрепления workflow проверяются, мутация любой ссылки ломает проверку)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: SR-02 и SR-08 — сканер ловит поддельный ключ и платный маршрут, не печатая значение;
//   зависимости и внешние части CI закреплены неизменяемо. База не нужна.
// ОГРАНИЧЕНИЯ: поддельные ключи и признаки платных маршрутов собираются во время теста из частей,
//   чтобы сам этот файл не совпадал с образцами сканера (исключений для него нет).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, appendFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { scan, parseAllow, lineHash } from '../ci/leak_scan.mjs';
import { workflowPinErrors } from '../ci/workflow_pins.mjs';
import { findSecret } from '../src/guards.mjs';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SCANNER = fileURLToPath(new URL('../ci/leak_scan.mjs', import.meta.url));
const WORKFLOW = join(ROOT, '..', '..', '.github', 'workflows', 'zavod-kernel.yml');
const ALLOW = join(ROOT, 'ci', 'leak_scan_allow.txt');

// Поддельные значения, собранные из частей (в исходном тексте целиком их нет).
const FAKE = {
  github: 'ghp' + '_' + 'Z'.repeat(36),
  openai: 'sk-' + 'proj-' + 'Q'.repeat(40),
  anthropic: 'sk-' + 'ant-' + 'W'.repeat(40),
  paidHost: 'https://api.' + 'openai.com/v1/chat',
  paidEnv: 'OPENAI' + '_API_KEY',
};

test('SR-02 сканер находит поддельные ключ и платный маршрут, значение не печатает', () => {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-scan-'));
  writeFileSync(join(dir, 'a.js'), `const t = "${FAKE.github}";\n`);
  writeFileSync(join(dir, 'b.yml'), `env:\n  K: \${{ secrets.${FAKE.paidEnv} }}\n`);
  writeFileSync(join(dir, 'c.md'), 'clean text\n');
  const hits = scan([dir], new Set(), dir);
  assert.deepEqual(hits.map((h) => `${h.file}|${h.pattern}`).sort(), ['a.js|github_token', 'b.yml|openai_key_env']);
  const r = spawnSync(process.execPath, [SCANNER, dir, '--base', dir], { encoding: 'utf8' });
  assert.equal(r.status, 1);
  assert.ok(!r.stdout.includes(FAKE.github), 'value must not be printed');
  assert.match(r.stdout, /LEAK_SCAN=FAIL/);
});

test('SR-02 сам репозиторий Kernel и его workflow чисты, исключений нет', () => {
  const r = spawnSync(process.execPath, [SCANNER, '.', WORKFLOW, '--allow', ALLOW, '--strict-allow'],
    { encoding: 'utf8', cwd: ROOT });
  assert.equal(r.status, 0, r.stdout);
  assert.deepEqual([...parseAllow(readFileSync(ALLOW, 'utf8'))], []);
});

test('M-E35-04 исключение целого файла и неполная запись отклоняются (код 2)', () => {
  for (const bad of ['src/guards.mjs|*', 'src/guards.mjs|github_token', `src/guards.mjs|*|${'a'.repeat(64)}`,
    `*|github_token|${'a'.repeat(64)}`]) {
    assert.throws(() => parseAllow(bad), /ALLOW_ENTRY_INVALID/, bad);
    const dir = mkdtempSync(join(tmpdir(), 'zavod-allow-'));
    writeFileSync(join(dir, 'allow.txt'), `${bad}\n`);
    const r = spawnSync(process.execPath, [SCANNER, dir, '--allow', join(dir, 'allow.txt')], { encoding: 'utf8' });
    assert.equal(r.status, 2, `${bad}: ${r.stdout}`);
  }
});

test('M-E35-04 исключение покрывает только точную строку; лишнее исключение при --strict-allow — отказ', () => {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-exact-'));
  const line = `const k = "${FAKE.github}";`;
  writeFileSync(join(dir, 'x.js'), `${line}\n`);
  const allow = new Set([`x.js|github_token|${lineHash(line)}`]);
  assert.deepEqual([...scan([dir], allow, dir)], []);
  appendFileSync(join(dir, 'x.js'), `${line} // copy\n`);                      // та же находка в другой строке
  assert.deepEqual(scan([dir], allow, dir).map((h) => h.line), [2]);
  writeFileSync(join(dir, 'allow.txt'), `x.js|github_token|${lineHash(line)}\nx.js|openai_key|${'b'.repeat(64)}\n`);
  writeFileSync(join(dir, 'x.js'), `${line}\n`);
  const r = spawnSync(process.execPath, [SCANNER, dir, '--base', dir, '--allow', join(dir, 'allow.txt'), '--strict-allow'],
    { encoding: 'utf8' });
  assert.equal(r.status, 1, r.stdout);
  assert.match(r.stdout, /ALLOW_UNUSED x\.js\|openai_key/);
});

test('M-E35-04 поддельный ключ в бывших файлах-исключениях и в workflow ловится; без него — PASS', () => {
  // Копия дерева с теми же относительными путями: zavod/kernel/{ci,src,tests} и .github/workflows.
  const top = mkdtempSync(join(tmpdir(), 'zavod-inject-'));
  const base = join(top, 'zavod', 'kernel');
  const files = { 'ci/leak_scan.mjs': join(ROOT, 'ci', 'leak_scan.mjs'), 'src/guards.mjs': join(ROOT, 'src', 'guards.mjs'),
    'tests/scan.test.mjs': join(ROOT, 'tests', 'scan.test.mjs'), '../../.github/workflows/zavod-kernel.yml': WORKFLOW };
  const copy = () => {
    for (const [rel, src] of Object.entries(files)) {
      const dst = join(base, rel);
      mkdirSync(dirname(dst), { recursive: true });
      writeFileSync(dst, readFileSync(src));
    }
  };
  const allow = parseAllow(readFileSync(ALLOW, 'utf8'));
  const targets = [join(base, 'ci'), join(base, 'src'), join(base, 'tests'), join(top, '.github')];
  copy();
  assert.deepEqual([...scan(targets, allow, base)], [], 'clean copies must pass');
  const injections = [
    ['github_token', `// ${FAKE.github}`], ['openai_key', `// ${FAKE.openai}`],
    ['anthropic_key', `// ${FAKE.anthropic}`], ['openai_api_host', `// ${FAKE.paidHost}`],
  ];
  for (const rel of Object.keys(files)) {
    for (const [pattern, text] of injections) {
      copy();
      const marker = rel.endsWith('.yml') ? text.replace('//', '#') : text;
      appendFileSync(join(base, rel), `\n${marker}\n`);
      const hits = scan(targets, allow, base);
      assert.ok(hits.some((h) => h.file === rel && h.pattern === pattern), `${rel} ${pattern}: ${JSON.stringify(hits)}`);
    }
  }
});

test('findSecret ловит образцы и пропускает обычный текст', () => {
  assert.equal(findSecret({ a: 'hello world', n: 12345 }), null);
  assert.equal(findSecret('-----BEGIN OPENSSH ' + 'PRIVATE KEY-----'), 'private_key');
  assert.equal(findSecret({ x: '123456789:' + 'a'.repeat(35) }), 'telegram_token');
});

test('SR-08 зависимости закреплены точной версией и есть файл блокировки', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  for (const [name, ver] of Object.entries({ ...pkg.dependencies, ...pkg.devDependencies })) {
    assert.match(ver, /^\d+\.\d+\.\d+$/, `${name} must be pinned exactly, got ${ver}`);
  }
  const lock = JSON.parse(readFileSync(join(ROOT, 'package-lock.json'), 'utf8'));
  assert.equal(lock.lockfileVersion >= 2, true);
  for (const [p, meta] of Object.entries(lock.packages)) {
    if (p) assert.ok(meta.integrity, `${p} must have integrity hash`);
  }
});

test('L-E35-01 внешние части CI закреплены; плавающая ссылка любой части — отказ', () => {
  const wf = readFileSync(WORKFLOW, 'utf8');
  assert.deepEqual(workflowPinErrors(wf), []);
  const sha = (s) => new RegExp(`(${s}@)[0-9a-f]{40}`);
  const mutations = [
    ['checkout major', (t) => t.replace(sha('actions/checkout'), '$1v4')],
    ['setup-node latest', (t) => t.replace(sha('actions/setup-node'), '$1main')],
    ['upload-artifact tag', (t) => t.replace(sha('actions/upload-artifact'), '$1v4.6.2')],
    ['service image tag', (t) => t.replace(/(image: postgres:16)@sha256:[0-9a-f]{64}/, '$1')],
    ['client image tag', (t) => t.replace(/(ZAVOD_PG_IMAGE: postgres:16)@sha256:[0-9a-f]{64}/, '$1')],
    ['client image differs', (t) => t.replace(/(ZAVOD_PG_IMAGE: postgres:16@sha256:)[0-9a-f]{64}/, `$1${'0'.repeat(64)}`)],
    ['node major', (t) => t.replace(/node-version: '22\.\d+\.\d+'/, "node-version: '22'")],
    ['apt psql', (t) => t.replace('steps:', 'steps:\n      - run: sudo apt-get install -y postgresql-client')],
  ];
  for (const [name, mutate] of mutations) {
    const m = mutate(wf);
    assert.notEqual(m, wf, `${name}: mutation must change the file`);
    assert.ok(workflowPinErrors(m).length > 0, `${name} must be refused`);
  }
});
