// ДОКУМЕНТ: zavod/engine/src/graph_check.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 05:50 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 05:50 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверщик графа процесса Завода по H1.31 §12 (критерий E4-3 протокола Z1 v1.9).
//   Развёртывание модели в движок — только после успеха этой проверки (H1.31 §12.1 п.6, R47 §22.2:
//   валидатор Flowable принял все испорченные копии). Сверяется точная таблица узлов §12.2 и потоков
//   §12.3 (id, откуда, куда, условие), машинные инварианты §12.3 и запреты §12.1 (сигнал, досрочное
//   завершение, старт без сообщения bemIntake). Всё неизвестное — отказ (закрыто по умолчанию).
// ОТСТУПЛЕНИЕ DEV-E43-01: узел 4 по §12.2 — Business Rule Task; в Flowable он требует движка правил,
//   которого в поставке нет, поэтому узел 4 — Service Task внешнего исполнителя Kernel (как в пробе R47).
//   Проверщик принимает для узла 4 только serviceTask и только эту замену.
// ВЫЗОВ: node src/graph_check.mjs <файл.bpmn20.xml>  → JSON в stdout; код 0 — PASS, 1 — FAIL, 2 — ошибка вызова.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const GRAPH_CHECK_VERSION = '0.1.0';
export const PROCESS_ID = 'bem_work';
export const SUBPROCESS_ID = 'bem_subtask';

// §12.2: узел → допустимый тип элемента BPMN.
export const NODES = Object.freeze({
  n1: 'startEvent', n2: 'serviceTask', n3: 'serviceTask', n4: 'serviceTask', n5: 'exclusiveGateway',
  n6: 'serviceTask', n7: 'callActivity', n8: 'serviceTask', n9: 'serviceTask', n10: 'parallelGateway',
  n11: 'serviceTask', n12: 'serviceTask', n13: 'parallelGateway', n14: 'serviceTask', n15: 'receiveTask',
  n16: 'exclusiveGateway', n17: 'serviceTask', n18: 'serviceTask', n19: 'userTask', n20: 'endEvent',
});

// §12.3: id → [откуда, куда, условие или null]. Условие сравнивается после удаления пробелов.
export const FLOWS = Object.freeze({
  f01: ['n1', 'n2', null], f02: ['n2', 'n3', null], f03: ['n3', 'n4', null], f04: ['n4', 'n5', null],
  f05: ['n5', 'n6', "${criticality == 'NORMAL'}"], f06: ['n5', 'n6', "${criticality == 'CRITICAL'}"],
  f07: ['n6', 'n7', null], f08: ['n7', 'n8', null], f09: ['n8', 'n9', null], f10: ['n9', 'n10', null],
  f11: ['n10', 'n11', null], f12: ['n10', 'n12', null], f13: ['n11', 'n13', null], f14: ['n12', 'n13', null],
  f15: ['n13', 'n14', null], f16: ['n14', 'n15', null], f17: ['n15', 'n16', null],
  f18: ['n16', 'n17', "${verdict == 'ACCEPT'}"],
  f19: ['n16', 'n6', "${verdict == 'REVISE' || verdict == 'REJECT'}"],
  f20: ['n16', 'n19', "${verdict == 'BLOCKED'}"],
  f21: ['n17', 'n18', null], f22: ['n18', 'n20', null],
  f23: ['n19', 'n20', "${operatorChoice == 'CANCEL'}"], f24: ['n19', 'n6', "${operatorChoice == 'CONTINUE'}"],
});

// Внешние исполнители: тема задания для каждого Service Task (кто исполняет по §12.2).
export const TOPICS = Object.freeze({
  n2: 'kernel', n3: 'kernel', n4: 'kernel', n6: 'kernel', n8: 'kernel', n9: 'kernel', n11: 'kernel-check',
  n12: 'kernel-publish', n14: 'kernel-assign', n17: 'kernel', n18: 'egress',
});

const SUB_NODES = Object.freeze({ s1: 'startEvent', s2: 'serviceTask', s3: 'intermediateCatchEvent', s4: 'endEvent' });
const SUB_FLOWS = Object.freeze({ g1: ['s1', 's2'], g2: ['s2', 's3'], g3: ['s3', 's4'] });

// ---------- минимальный разбор XML (без внешних зависимостей) ----------
// Поддерживает элементы, атрибуты в двойных/одинарных кавычках, текст, комментарии, CDATA, пролог.
// DOCTYPE и сущности кроме пяти стандартных — отказ (закрыто по умолчанию).
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };
function decode(s) {
  return s.replace(/&(#x[0-9a-f]+|#[0-9]+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') return String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
    if (!(e in ENT)) throw new Error(`XML_ENTITY_UNKNOWN ${e}`);
    return ENT[e];
  });
}
export function parseXml(xml) {
  const root = { name: '#root', attrs: {}, children: [], text: '' };
  const stack = [root];
  let i = 0;
  const n = xml.length;
  while (i < n) {
    const lt = xml.indexOf('<', i);
    if (lt < 0) { stack.at(-1).text += decode(xml.slice(i)); break; }
    if (lt > i) stack.at(-1).text += decode(xml.slice(i, lt));
    if (xml.startsWith('<!--', lt)) { const e = xml.indexOf('-->', lt + 4); if (e < 0) throw new Error('XML_COMMENT_OPEN'); i = e + 3; continue; }
    if (xml.startsWith('<![CDATA[', lt)) { const e = xml.indexOf(']]>', lt); if (e < 0) throw new Error('XML_CDATA_OPEN'); stack.at(-1).text += xml.slice(lt + 9, e); i = e + 3; continue; }
    if (xml.startsWith('<?', lt)) { const e = xml.indexOf('?>', lt); if (e < 0) throw new Error('XML_PI_OPEN'); i = e + 2; continue; }
    if (xml.startsWith('<!', lt)) throw new Error('XML_DOCTYPE_FORBIDDEN');
    if (xml[lt + 1] === '/') {
      const e = xml.indexOf('>', lt);
      const name = xml.slice(lt + 2, e).trim();
      const top = stack.pop();
      if (!top || top.name !== name || stack.length === 0) throw new Error(`XML_MISMATCH ${name}`);
      i = e + 1; continue;
    }
    const m = /^<([A-Za-z_][\w.:-]*)((?:\s+[A-Za-z_][\w.:-]*\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>/.exec(xml.slice(lt));
    if (!m) throw new Error(`XML_BAD_TAG at ${lt}`);
    const attrs = {};
    for (const a of m[2].matchAll(/([A-Za-z_][\w.:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)) {
      if (a[1] in attrs) throw new Error(`XML_DUP_ATTR ${a[1]}`);
      attrs[a[1]] = decode(a[2] ?? a[3]);
    }
    const node = { name: m[1], attrs, children: [], text: '' };
    stack.at(-1).children.push(node);
    if (!m[3]) stack.push(node);
    i = lt + m[0].length;
  }
  if (stack.length !== 1) throw new Error('XML_UNCLOSED');
  return root;
}
const local = (name) => name.split(':').pop();
const kids = (el, nm) => el.children.filter((c) => local(c.name) === nm);
function descendants(el, out = []) { for (const c of el.children) { out.push(c); descendants(c, out); } return out; }
const norm = (s) => (s ?? '').replace(/\s+/g, '');

// ---------- проверка ----------
export function checkGraph(xml) {
  const errs = [];
  let doc;
  try { doc = parseXml(xml); } catch (e) { return { ok: false, errs: [`PARSE ${e.message}`] }; }
  const defs = doc.children.filter((c) => local(c.name) === 'definitions');
  if (defs.length !== 1 || doc.children.length !== 1) return { ok: false, errs: ['ROOT must be one <definitions>'] };
  const d = defs[0];
  const all = descendants(d);

  // §12.1 п.4: сигнал как средство синхронизации запрещён; п.3: досрочного завершения нет.
  for (const el of all) {
    const nm = local(el.name);
    if (/^signal/i.test(nm)) errs.push(`FORBIDDEN ${nm} (signal, §12.1 п.4)`);
    if (nm === 'completionCondition') errs.push('FORBIDDEN completionCondition (§12.1 п.3)');
    if (nm === 'boundaryEvent' || nm === 'subProcess' || nm === 'eventBasedGateway' || nm === 'inclusiveGateway' || nm === 'complexGateway')
      errs.push(`FORBIDDEN ${nm} (нет в §12.2)`);
  }
  // Сообщения: ровно bemIntake (старт) и subtaskAck (подтверждение подзадачи).
  const messages = Object.fromEntries(kids(d, 'message').map((m) => [m.attrs.id, m.attrs.name]));
  const msgNames = Object.values(messages).sort().join(',');
  if (msgNames !== 'bemIntake,subtaskAck') errs.push(`MESSAGES ${msgNames} (надо bemIntake,subtaskAck)`);

  const procs = kids(d, 'process');
  const ids = procs.map((p) => p.attrs.id).sort().join(',');
  if (ids !== [PROCESS_ID, SUBPROCESS_ID].sort().join(',')) errs.push(`PROCESSES ${ids}`);
  const main = procs.find((p) => p.attrs.id === PROCESS_ID);
  const sub = procs.find((p) => p.attrs.id === SUBPROCESS_ID);
  if (main) checkProcess(main, NODES, FLOWS, true, messages, errs);
  if (sub) checkProcess(sub, SUB_NODES, Object.fromEntries(Object.entries(SUB_FLOWS).map(([k, v]) => [k, [...v, null]])), false, messages, errs);
  return { ok: errs.length === 0, errs, flows: main ? kids(main, 'sequenceFlow').length : 0 };
}

function checkProcess(p, wantNodes, wantFlows, isMain, messages, errs) {
  const tag = p.attrs.id;
  if (p.attrs.isExecutable !== 'true') errs.push(`${tag} isExecutable != true`);
  const nodes = {};
  const flows = {};
  for (const c of p.children) {
    const nm = local(c.name);
    if (nm === 'sequenceFlow') {
      if (c.attrs.id in flows) errs.push(`${tag} DUP flow ${c.attrs.id}`);
      const cond = kids(c, 'conditionExpression');
      if (cond.length > 1) errs.push(`${tag} ${c.attrs.id} несколько условий`);
      flows[c.attrs.id] = { s: c.attrs.sourceRef, t: c.attrs.targetRef, cond: cond.length ? cond[0].text.trim() : null, el: c };
    } else if (nm === 'documentation' || nm === 'extensionElements') {
      continue;
    } else {
      if (c.attrs.id in nodes) errs.push(`${tag} DUP node ${c.attrs.id}`);
      nodes[c.attrs.id] = { type: nm, el: c };
    }
  }
  // Точный состав узлов и типов.
  for (const [id, type] of Object.entries(wantNodes)) {
    if (!nodes[id]) errs.push(`${tag} нет узла ${id}`);
    else if (nodes[id].type !== type) errs.push(`${tag} ${id} тип ${nodes[id].type} (надо ${type})`);
  }
  for (const id of Object.keys(nodes)) if (!(id in wantNodes)) errs.push(`${tag} лишний узел ${id} (${nodes[id].type})`);
  // Точная таблица потоков.
  for (const [id, [s, t, cond]] of Object.entries(wantFlows)) {
    const f = flows[id];
    if (!f) { errs.push(`${tag} нет потока ${id}`); continue; }
    if (f.s !== s || f.t !== t) errs.push(`${tag} ${id} ${f.s}->${f.t} (надо ${s}->${t})`);
    if (norm(f.cond) !== norm(cond)) errs.push(`${tag} ${id} условие «${f.cond ?? '—'}» (надо «${cond ?? '—'}»)`);
  }
  for (const id of Object.keys(flows)) if (!(id in wantFlows)) errs.push(`${tag} лишний поток ${id}`);
  // Обработчик по умолчанию у развилок не допускается: путь выбирают только условия таблицы.
  for (const [id, n] of Object.entries(nodes)) if (n.el.attrs.default) errs.push(`${tag} ${id} default-поток запрещён`);

  const list = Object.values(flows);
  const inn = (n) => list.filter((f) => f.t === n).length;
  const out = (n) => list.filter((f) => f.s === n).length;
  const reach = (from) => {
    const seen = new Set([from]); const st = [from];
    while (st.length) { const x = st.pop(); for (const f of list) if (f.s === x && !seen.has(f.t)) { seen.add(f.t); st.push(f.t); } }
    return seen;
  };
  const first = isMain ? 'n1' : 's1';
  const r = reach(first);
  for (const id of Object.keys(nodes)) if (!r.has(id)) errs.push(`${tag} ${id} недостижим из ${first}`);
  for (const [id, n] of Object.entries(nodes)) {
    if (n.type === 'endEvent' && (out(id) !== 0 || inn(id) === 0)) errs.push(`${tag} ${id} End Event: вход ${inn(id)}, выход ${out(id)}`);
    if (n.type === 'startEvent' && inn(id) !== 0) errs.push(`${tag} ${id} Start Event с входящим потоком`);
  }
  if (!isMain) {
    const s3 = nodes.s3?.el;
    const md = s3 ? kids(s3, 'messageEventDefinition') : [];
    if (md.length !== 1 || messages[md[0].attrs.messageRef] !== 'subtaskAck') errs.push(`${tag} s3 ждёт не subtaskAck`);
    if (nodes.s1 && nodes.s1.el.children.length) errs.push(`${tag} s1 должен быть простым стартом`);
    return;
  }
  // Машинные инварианты §12.3.
  if (!(inn('n10') === 1 && out('n10') === 2)) errs.push(`n10 вход/выход ${inn('n10')}/${out('n10')} (надо 1/2)`);
  if (!(inn('n13') === 2 && out('n13') === 1)) errs.push(`n13 вход/выход ${inn('n13')}/${out('n13')} (надо 2/1)`);
  const n7out = list.filter((f) => f.s === 'n7');
  if (!(n7out.length === 1 && n7out[0].t === 'n8')) errs.push(`n7 -> ${n7out.map((f) => f.t).join(',')} (надо ровно один поток прямо в n8)`);
  const n7 = nodes.n7?.el;
  if (n7) {
    const mi = kids(n7, 'multiInstanceLoopCharacteristics');
    if (mi.length !== 1 || mi[0].attrs.isSequential !== 'false') errs.push('n7 не объявлен isSequential="false"');
    if (n7.attrs.calledElement !== SUBPROCESS_ID) errs.push(`n7 calledElement ${n7.attrs.calledElement} (надо ${SUBPROCESS_ID})`);
  }
  for (const [a, ts] of [['n17', ['n18', 'n20']], ['n16', ['n17', 'n19', 'n6']]]) {
    const ra = reach(a); for (const t of ts) if (!ra.has(t)) errs.push(`из ${a} недостижим ${t}`);
  }
  // §12.1 п.5: старт только сообщением bemIntake.
  const n1 = nodes.n1?.el;
  const md = n1 ? kids(n1, 'messageEventDefinition') : [];
  if (md.length !== 1 || messages[md[0].attrs.messageRef] !== 'bemIntake') errs.push('n1 стартует не сообщением bemIntake');
  // Исполнители: внешние задания Kernel/Egress со своей темой; ни одного скрипта или класса в процессе.
  for (const [id, topic] of Object.entries(TOPICS)) {
    const el = nodes[id]?.el;
    if (!el) continue;
    if (el.attrs['flowable:type'] !== 'external-worker' || el.attrs['flowable:topic'] !== topic)
      errs.push(`${id} исполнитель ${el.attrs['flowable:type']}/${el.attrs['flowable:topic']} (надо external-worker/${topic})`);
  }
  for (const el of descendants(p)) {
    const nm = local(el.name);
    if (nm === 'scriptTask' || el.attrs['flowable:class'] || el.attrs['flowable:expression'] || el.attrs['flowable:delegateExpression'])
      errs.push(`${tag} исполняемый код в модели запрещён (${nm} ${el.attrs.id ?? ''})`);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const f = process.argv[2];
  if (!f) { console.error('usage: node graph_check.mjs <file.bpmn20.xml>'); process.exit(2); }
  const r = checkGraph(readFileSync(f, 'utf8'));
  console.log(JSON.stringify({ check: 'zavod-graph', version: GRAPH_CHECK_VERSION, file: f, ...r }));
  process.exit(r.ok ? 0 : 1);
}
