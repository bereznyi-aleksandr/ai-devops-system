// ДОКУМЕНТ: zavod/engine/tests/graph_check.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 06:00 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 06:00 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E4-3 — проверщик графа H1.31 §12 принимает эталон и отклоняет каждую испорченную копию,
//   в том числе три копии теста K-R5-11 (R47: валидатор Flowable принял все пять) и копии K-R5-12, K-R3-07.
// ОГРАНИЧЕНИЯ: движок не нужен; только чтение файла модели.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { checkGraph } from '../src/graph_check.mjs';

const XML = readFileSync(new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url), 'utf8');

function mutate(from, to) {
  assert.ok(XML.includes(from), `образец не найден: ${from.slice(0, 60)}`);
  return XML.replace(from, to);
}

test('эталонный граф §12 проходит проверку', () => {
  const r = checkGraph(XML);
  assert.deepEqual(r.errs, []);
  assert.equal(r.ok, true);
  assert.equal(r.flows, 24);
});

const F08 = '<sequenceFlow id="f08" sourceRef="n7" targetRef="n8"/>';
const MUTATIONS = [
  // K-R5-11: три копии с лишним слиянием после узла 7 (R47 §22.2 — Flowable их принял).
  ['K-R5-11a лишнее слияние между n7 и n8', F08,
    '<parallelGateway id="nX"/><sequenceFlow id="f08" sourceRef="n7" targetRef="nX"/><sequenceFlow id="fX" sourceRef="nX" targetRef="n8"/>'],
  ['K-R5-11b второй выход из n7', F08, `${F08}<sequenceFlow id="fX" sourceRef="n7" targetRef="n9"/>`],
  ['K-R5-11c n7 ведёт не в n8', F08, '<sequenceFlow id="f08" sourceRef="n7" targetRef="n9"/>'],
  // K-R5-12: развилка и слияние качества.
  ['K-R5-12a у n13 один вход', '<sequenceFlow id="f14" sourceRef="n12" targetRef="n13"/>',
    '<sequenceFlow id="f14" sourceRef="n12" targetRef="n14"/>'],
  ['K-R5-12b n10 — исключающая развилка', '<parallelGateway id="n10" name="10 Развилка качества"/>',
    '<exclusiveGateway id="n10" name="10 Развилка качества"/>'],
  // K-R3-07: завершение и досрочное окончание подзадач.
  ['K-R3-07a End Event с исходящим', '<sequenceFlow id="f24"', '<sequenceFlow id="fX" sourceRef="n20" targetRef="n6"/><sequenceFlow id="f24"'],
  ['K-R3-07b n7 последовательный', 'isSequential="false"', 'isSequential="true"'],
  ['K-R3-07c completionCondition у n7', '</loopCardinality>', '</loopCardinality><completionCondition>${nrOfCompletedInstances > 0}</completionCondition>'],
  // Таблица потоков и запреты §12.1.
  ['возврат REVISE на n1, а не n6', '<sequenceFlow id="f19" sourceRef="n16" targetRef="n6">', '<sequenceFlow id="f19" sourceRef="n16" targetRef="n1">'],
  ['условие ACCEPT ослаблено', "${verdict == 'ACCEPT'}", "${verdict != 'BLOCKED'}"],
  ['поток f22 пропал', '<sequenceFlow id="f22" sourceRef="n18" targetRef="n20"/>', ''],
  ['старт без сообщения', '<messageEventDefinition messageRef="msgIntake"/>', ''],
  ['сигнал вместо сообщения', '<message id="msgIntake" name="bemIntake"/>', '<message id="msgIntake" name="bemIntake"/><signal id="sg" name="sync"/>'],
  ['скрипт в модели', '<serviceTask id="n9" name="9 Слияние изменений" flowable:type="external-worker" flowable:topic="kernel"/>',
    '<scriptTask id="n9" name="9" scriptFormat="groovy"><script>1</script></scriptTask>'],
  ['исполнитель n18 не Egress', 'flowable:topic="egress"', 'flowable:topic="kernel"'],
  ['default-поток у развилки вердикта', '<exclusiveGateway id="n16" name="16 Развилка по вердикту"/>',
    '<exclusiveGateway id="n16" name="16 Развилка по вердикту" default="f18"/>'],
  ['лишний узел-таймер', '<endEvent id="n20" name="20 Завершение"/>',
    '<endEvent id="n20" name="20 Завершение"/><boundaryEvent id="b1" attachedToRef="n15"><timerEventDefinition/></boundaryEvent>'],
  ['DOCTYPE с сущностью', '<?xml version="1.0" encoding="UTF-8"?>', '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE x [<!ENTITY e "n6">]>'],
  ['подзадача не ждёт subtaskAck', '<messageEventDefinition messageRef="msgSubAck"/>', ''],
];

for (const [name, from, to] of MUTATIONS) {
  test(`испорченная копия отклонена: ${name}`, () => {
    const r = checkGraph(mutate(from, to));
    assert.equal(r.ok, false, `копия «${name}» прошла проверку`);
    assert.ok(r.errs.length > 0);
  });
}

test('CLI: код 0 на эталоне, 1 на испорченной копии', async () => {
  const { spawnSync } = await import('node:child_process');
  const { mkdtempSync, writeFileSync } = await import('node:fs');
  const { tmpdir } = await import('node:os');
  const { join } = await import('node:path');
  const cli = new URL('../src/graph_check.mjs', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
  const good = spawnSync(process.execPath, [cli, new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')]);
  assert.equal(good.status, 0, good.stdout.toString());
  const bad = join(mkdtempSync(join(tmpdir(), 'zavod-graph-')), 'bad.bpmn20.xml');   // файл остаётся, не удаляется (P4.702)
  writeFileSync(bad, mutate(F08, '<sequenceFlow id="f08" sourceRef="n7" targetRef="n9"/>'));
  const r = spawnSync(process.execPath, [cli, bad]);
  assert.equal(r.status, 1, r.stdout.toString());
});
