// chk_round_facts.mjs — сверка фактов раунда R50 между документом и двумя отчётами.
// PASSPORT: ACTIVE vR50.1, раунд R50, H1.30.
// AUTHOR: ChatGPT, DEVELOPER R38; Claude, DEVELOPER R42–R50 (РАУНД-R50-ПЕРЕНОС-ИМЁН: H1.30; логика программ в R47–R50 не менялась, последняя правка логики — D1 и D2 проб R46; базовая пара — в build_package, verify_package, chk_round_facts); UPDATED: 2026-10-05.
// SUPERSEDES: версия из H1.29/R49; LIVE_POSTGRESQL_16: PG16_D05=EXECUTED_PASS, пробы R46 — раздел 22.1, пробы движка R47, R49 и R50 — раздел 22.2, остальное — раздел 15.43.
// Читает только строки вида ROUND_FACT[key]=value; затем сверяет их с измеренными полями.
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';

const positional = [];
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] === '--pg16-evidence') { i += 1; continue; }
  if (!process.argv[i].startsWith('--')) positional.push(process.argv[i]);
}
const [docPath, tamperPath, packagePath] = positional;
const argAfter = (flag) => { const i = process.argv.indexOf(flag); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : null; };
const pg16EvidencePath = argAfter('--pg16-evidence');
const sha = (buf) => createHash('sha256').update(buf).digest('hex');
if (!docPath || !tamperPath || !packagePath) {
  console.error('нужны: <document> <tamper_report.json> <package_report.json>');
  process.exit(2);
}
const LINE = /^ROUND_FACT\[([A-Z0-9_]+)\]=([^\r\n]+)$/;
const REQUIRED = ['BASELINE_EDITION','EXPECTED_EDITION','PG16_D05','TAMPER_CASES_RANGE','TAMPER_CASES_TOTAL'];
function loadJson(path, label, problems) {
  try { return JSON.parse(readFileSync(path, 'utf8')); }
  catch (e) { problems.push(label + ': JSON не читается'); return {}; }
}
function fromDocument(path) {
  return readFileSync(path, 'utf8').split(/\r?\n/).filter((x) => LINE.test(x));
}
function fromReport(obj) {
  return Array.isArray(obj.round_facts) ? obj.round_facts.filter((x) => typeof x === 'string' && LINE.test(x)) : [];
}
function parse(lines, label) {
  const m = new Map(), problems = [];
  for (const line of lines) {
    const x = line.match(LINE); if (!x) continue;
    if (m.has(x[1])) problems.push(label + ': duplicate ROUND_FACT[' + x[1] + ']');
    else m.set(x[1], x[2]);
  }
  return {m, problems};
}
const problems = [];
const tamperObj = loadJson(tamperPath, 'tamper_report', problems);
const packageObj = loadJson(packagePath, 'package_report', problems);
const sources = [
  ['document', parse(fromDocument(docPath), 'document')],
  ['tamper_report', parse(fromReport(tamperObj), 'tamper_report')],
  ['package_report', parse(fromReport(packageObj), 'package_report')],
];
problems.push(...sources.flatMap(([,x]) => x.problems));
const keys = new Set(sources.flatMap(([,x]) => [...x.m.keys()]));
for (const need of REQUIRED) if (!keys.has(need)) problems.push('нет обязательного ROUND_FACT[' + need + ']');
for (const key of [...keys].sort()) {
  if (!REQUIRED.includes(key)) problems.push('неизвестный ROUND_FACT[' + key + ']');
  const vals = sources.map(([name,x]) => [name, x.m.get(key)]);
  for (const [name,val] of vals) if (val === undefined) problems.push(name + ': missing ROUND_FACT[' + key + ']');
  const present = vals.filter(([,v]) => v !== undefined).map(([,v]) => v);
  if (new Set(present).size > 1) problems.push('stale/mismatch ROUND_FACT[' + key + ']: ' + vals.map(([n,v]) => n + '=' + (v ?? '<missing>')).join(', '));
}
const fact = (key) => sources[0][1].m.get(key);
// FIX-02: факт должен совпадать не только между тремя источниками, но и с измерением.
if (String(tamperObj.tampers_total) !== String(fact('TAMPER_CASES_TOTAL'))) {
  problems.push('measurement mismatch TAMPER_CASES_TOTAL: fact=' + fact('TAMPER_CASES_TOTAL') + ', tampers_total=' + tamperObj.tampers_total);
}
if (String(tamperObj.tamper_cases_range) !== String(fact('TAMPER_CASES_RANGE'))) {
  problems.push('measurement mismatch TAMPER_CASES_RANGE: fact=' + fact('TAMPER_CASES_RANGE') + ', tamper_cases_range=' + tamperObj.tamper_cases_range);
}
for (const [label,obj] of [['tamper_report',tamperObj],['package_report',packageObj]]) {
  if (String(obj.expected_edition) !== String(fact('EXPECTED_EDITION'))) {
    problems.push('measurement mismatch EXPECTED_EDITION in ' + label + ': fact=' + fact('EXPECTED_EDITION') + ', expected_edition=' + obj.expected_edition);
  }
}
if (String(packageObj.live_postgres_tests) !== String(fact('PG16_D05'))) {
  problems.push('measurement mismatch PG16_D05: fact=' + fact('PG16_D05') + ', live_postgres_tests=' + packageObj.live_postgres_tests);
}
if (fact('PG16_D05') !== 'DESIGNED_NOT_EXECUTED') {
  if (!pg16EvidencePath || !existsSync(pg16EvidencePath)) {
    problems.push('PG16_D05 требует --pg16-evidence с существующим файлом доказательства');
  } else {
    const evidence = readFileSync(pg16EvidencePath);
    const gotSha = sha(evidence);
    if (!/^[0-9a-f]{64}$/.test(String(packageObj.pg16_evidence_sha256 || ''))) problems.push('package_report: нет pg16_evidence_sha256');
    else if (gotSha !== packageObj.pg16_evidence_sha256) problems.push('PG16 evidence SHA-256 mismatch: report=' + packageObj.pg16_evidence_sha256 + ', actual=' + gotSha);
    const t = evidence.toString('utf8');
    const required = ['EVIDENCE_ID=','STATUS=','POSTGRESQL_VERSION=','EXECUTED_AT_UTC=','SOURCE_DOCUMENT_SHA256=','SQL_FILE_SHA256=','POSITIVE_TEST_EXIT_CODE=','NEGATIVE_TEST_EXIT_CODE=','POSITIVE_RESULT=','NEGATIVE_RESULT=','FINAL_RESULT=','SECRETS_INCLUDED=NO'];
    for (const marker of required) if (!t.includes(marker)) problems.push('PG16 evidence не соответствует EVIDENCE_PG16_D05_FORMAT_v1_0.md: нет ' + marker);
    // H1.24: улика обязана говорить о файле 01 этого пакета и о документе
    // этого пакета, а её итог — совпадать с фактом документа.
    const field = (k) => { const m = t.match(new RegExp('^' + k + '=(.*)$', 'm')); return m ? m[1].trim() : null; };
    const sql01 = join(dirname(packagePath), '01_database_migration.sql');
    if (!existsSync(sql01)) problems.push('PG16 evidence: рядом с package_report нет 01_database_migration.sql');
    else if (field('SQL_FILE_SHA256') !== sha(readFileSync(sql01))) problems.push('PG16 evidence: SQL_FILE_SHA256 не равен сумме 01 пакета');
    if (field('SOURCE_DOCUMENT_SHA256') !== packageObj.document_sha256) problems.push('PG16 evidence: SOURCE_DOCUMENT_SHA256 не равен document_sha256 отчёта');
    if (field('STATUS') !== fact('PG16_D05')) problems.push('PG16 evidence: STATUS не равен ROUND_FACT[PG16_D05]');
    if (field('FINAL_RESULT') !== 'PASS' || field('POSITIVE_RESULT') !== 'PASS' || field('NEGATIVE_RESULT') !== 'PASS'
        || field('SECRETS_INCLUDED') !== 'NO') problems.push('PG16 evidence: итог не PASS/PASS/PASS/NO');
  }
}
if (fact('BASELINE_EDITION') !== 'H1.29') problems.push('BASELINE_EDITION должен быть H1.29 для R50');
for (const p of problems) console.error(p);
console.log('ROUND_FACT keys: ' + keys.size + '; problems: ' + problems.length);
process.exit(problems.length ? 1 : 0);