'use strict';
// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_js.cjs
// ВЕРСИЯ: v0.10  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-11-02 02:21 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c; v0.8 — сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// ДАТА ОБНОВЛЕНИЯ: 2026-11-02 15:12 +02:00 (v0.10: аудит M3310-R15B-01 и -07 — относительный импорт только к файлу из набора прогона; у запуска программ cwd и среда загрузки кода — находка CHILD_OPTS; прежняя 2026-11-02 10:42 +02:00 — v0.9: самопроверка R15 — импорт по пути к node_modules или по абсолютному пути — находка MODULE; v0.8: аудит M3310-R14-03, -06, -07 — импорт модуля вне закрытого
//   списка JS_MODULES (сторонний пакет: postgres.js, execa …) — находка MODULE; копия «...x.map/flatMap(…)» в списке
//   запуска — только у настоящего массива (литерал, const-список, Object.entries/keys/values)); прежняя дата: 2026-11-02 07:26 +02:00 (v0.7: аудит M3310-R11-03 — *.cjs разбирается как script; импорт своего
//   файла не формата .mjs/.js/.cjs и «#имя» — находка MODULE); прежняя дата: 2026-11-02 07:05 +02:00 (v0.6: аудит M3310-R10-01..04 — список запуска строго: литерал в
//   вызове или параметр своей функции, упомянутый один раз; любой не постоянный элемент — находка (разрешается
//   точной строкой, файл закрепляется суммой PIN); раннего выхода после «node --» нет; v0.5: аудит M3310-R9-01 — список запуска из переменной только
//   доказанного происхождения: const со списком-литералом или параметр своей функции / закрытого метода, без push,
//   другого имени и передачи дальше; копии «...x» в списке — того же происхождения или map/flatMap со списком-литералом;
//   v0.4: аудит M3310-R8-01 — встроенные объекты (Object, Array, globalThis …) только как
//   X.член или вызов, запись в любую цепочку от них — находка; запись в элемент замороженного литерала — не таблица;
//   M3310-R8-02 — имя оболочки в любом списке — только «-c сценарий из SHELL_SCRIPTS», имя исполнителя кода
//   (python, perl, node …) в списке — находка; v0.3: аудит M3310-R7-01 — обратный вызов map/forEach/… только стрелкой без
//   третьего параметра и thisArg, вызов метода таблицы с this — не чтение, цепочка от свойства (push.call) — не чтение;
//   M3310-R7-02 — сценарий после -c в любом списке файла: исполняющий аргументы — только из SHELL_SCRIPTS; своя
//   обёртка запуска (run(file, args)) проверяется по каждому вызову; v0.2: аудит M3310-R6-01..04 — таблица и список ключей только для
//   чтения; process.getBuiltinModule и другие пути к встроенным модулям запрещены; запуск программ — только spawn,
//   spawnSync, execFile, execFileSync прямым вызовом, программа — постоянное имя из списка, без оболочки; у каждой
//   находки есть код правила, разрешение снимает только находку своего кода)
// НАЗНАЧЕНИЕ: часть JavaScript проверки сборки (карта 3.3.10.2, протокол И.7а п.2) — аудит M3310-R5-01, -02, -03.
//   Код разбирается полностью (дерево разбора acorn, тот же разборщик, что внутри Node), имена связываются с
//   объявлениями по областям видимости. Правила — разрешающие: принимается только то, что доказано постоянным;
//   всё остальное — находка (отказ сборки).
//   1) Текст запроса. У каждого вызова x.query(…) первый аргумент — постоянный текст: строка, шаблон без ${},
//      сумма таких через «+» или имя const (по области видимости, не по совпадению имени), чьё значение такое же.
//      Параметр функции принимается, только если функция — своя функция файла (function f или const f = …), не
//      выставлена наружу, используется только прямым вызовом f(…), сам параметр не переприсваивается, и в КАЖДОМ
//      вызове на этом месте снова постоянный текст (по цепочке).
//   2) Имя query. Любое имя или ключ, где есть «query» (без учёта регистра: Query, queryQueue, activeQuery), —
//      находка, кроме прямого вызова .query(…). Разборщик сам раскрывает экранирования (query = query).
//   3) Вычисляемое имя X[k] (k — не постоянная строка и не число) — находка, кроме X — имя const с объектом-литералом
//      этого файла (без «...», get/set и вычисляемых ключей), или k — элемент постоянного списка строк файла (for…of,
//      .map/.filter… по списку, Object.keys таблицы). Таблица и список — только для чтения: каждое упоминание имени —
//      чтение свойства, вызов не меняющего метода (map, filter, forEach, some, every, find, findIndex, flatMap,
//      includes, indexOf, slice, join, at, hasOwnProperty), for…of, Object.keys/entries/values или «in»; запись
//      в элемент (names[0] = …), push/splice/fill, передача имени в функцию, присваивание другому имени, выставление
//      наружу — и это уже не таблица (аудит M3310-R6-01). Вычисляемый ключ { [k]: … } в объекте, разборе и классе —
//      находка.
//   4) Код из строки и доступ в обход: eval, Function, constructor, prototype, __proto__, Reflect, Proxy,
//      getPrototypeOf/setPrototypeOf, getOwnPropertyDescriptor(s)/Names, defineProperty(ies), create, assign, values,
//      entries, call/apply/bind, require, createRequire, binding, _linkedBinding, dlopen, getBuiltinModule (встроенный
//      модуль по имени-строке, аудит M3310-R6-02), execve, mainModule, NODE_OPTIONS — находка как имя, свойство
//      или ключ разбора (ключ, который только определяет свойство в объекте-литерале или классе, не читает — для
//      него только query и __proto__; constructor класса допустим). Object.entries/values у таблицы этого файла —
//      допустимы. Чтение свойства connection (нижний слой драйвера pg: x.connection, x['connection'],
//      { connection } = x) — находка. import(…), with, модули vm, module, repl, inspector, worker_threads, cluster,
//      sqlite, test, источники data:/http(s): — находка; постоянная строка (и сумма постоянных строк), где словом стоит
//      psql, -e, --eval, -p, --print, -r, --require, --import, --loader (в том числе «node -e …», «--eval=…»), —
//      находка (запуск кода или psql из строки).
//   5) Склейка, похожая на запрос: «+», «+=», шаблон с ${}, .join/.concat/.replace(All), где известный текст
//      (строки, значения имён по всем присваиваниям, массивы) похож на запрос. Сумма, где ВСЕ части постоянны
//      (строки и const), — не склейка: её текст известен при проверке целиком.
//   6) Запуск программ (аудит M3310-R6-03). Импорт child_process — находка CHILD_IMPORT в любом файле, кроме файлов,
//      чья строка импорта есть в файле разрешений: иначе файл мог бы записать код во временный файл и запустить его
//      node. Из child_process можно взять только по имени spawn, spawnSync, execFile,
//      execFileSync (не exec, execSync, fork, не весь модуль) и вызывать только прямо (без promisify и без передачи
//      функции дальше). Программа — постоянное имя из списка PROGRAMS или process.execPath (сам node: первый
//      аргумент — не флаг, постоянный); после «-c» — только постоянный текст сценария; параметры — объект-литерал
//      без «...» и без shell (кроме shell: false); у node, sudo и оболочек аргументы — массив-литерал.
//   Каждая находка несёт код правила (поле code): разрешение в sql_concat_allow.txt снимает только находку этого кода
//   на этой строке (аудит M3310-R6-04).
// ВЫЗОВ: node --expose-internals sql_concat_js.cjs файл…  (вызывает sql_concat_scan.py). Печать: первая строка
//   {"parser": …}, далее по строке JSON на находку {"path", "line", "code", "why"}. Код выхода 0 — проверка прошла до конца
//   (находки решает sql_concat_scan.py), 2 — сбой самой проверки.
// ОГРАНИЧЕНИЯ: разборщик берётся из Node (internal/deps/acorn, флаг --expose-internals; версия печатается; в CI Node
//   закреплён setup-node). Правила строгие, поэтому ложные находки ожидаемы: проверенные строки с причиной идут в
//   sql_concat_allow.txt и видны аудиту. Вне проверки: (а) драйвер базы, написанный заново поверх сети (net) с
//   ручным протоколом — это не склейка, а свой драйвер; (б) что делает запущенная программа из списка PROGRAMS с
//   файлом из хранилища (node, docker, gh), решают ограждение (fencer) и песочница работника, а файлы node проверяет
//   этот же сканер; запуск кода прямо из строки (оболочка, -e, getBuiltinModule('vm')) — находка.
const fs = require('node:fs');
const nodePath = require('node:path');
// Аудит M3310-R15B-01: свой модуль (import './x.mjs', '../y.js') разрешён, только если это один из файлов этого же
// прогона (после realpath): иначе import '../../unscanned/run.mjs' ведёт к коду, которого проверка не видела.
const real = (f) => { try { return fs.realpathSync(f); } catch { return null; } };
const SCANNED = new Set(process.argv.slice(2).map(real).filter(Boolean));
const acorn = require('internal/deps/acorn/acorn/dist/acorn');

const SQL = /\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|GRANT\s|REVOKE\s|TRUNCATE\s|COPY\s|EXECUTE\s|SET\s+(LOCAL\s+)?ROLE|WHERE\s|VALUES\s*\()/;
const QUERY = /query/i;
const BANNED = new Set(['eval', 'Function', 'constructor', 'prototype', '__proto__', '__defineGetter__',
  '__defineSetter__', '__lookupGetter__', '__lookupSetter__', 'Reflect', 'Proxy', 'getPrototypeOf', 'setPrototypeOf',
  'getOwnPropertyDescriptor', 'getOwnPropertyDescriptors', 'getOwnPropertyNames', 'defineProperty',
  'defineProperties', 'assign', 'values', 'entries', 'call', 'apply', 'bind', 'require',
  'createRequire', 'create', 'binding', '_linkedBinding', 'dlopen', 'getBuiltinModule', 'execve', 'mainModule',
  'NODE_OPTIONS']);
// Внутренности драйвера pg: опасно только ЧТЕНИЕ свойства (x.connection, { connection } = x), не имя переменной.
const DRIVER = new Set(['connection']);
const BANNED_MODULES = new Set(['vm', 'module', 'repl', 'inspector', 'worker_threads', 'cluster', 'sqlite', 'test']);
// Модули, которые можно импортировать (аудит M3310-R14-03, -06): встроенные Node, которыми пользуются ядро и
// движок, и драйвер pg (его запросы — только .query с постоянным текстом). Новый модуль — правкой этого списка с аудитом.
const JS_MODULES = new Set(['node:child_process', 'node:crypto', 'node:events', 'node:fs', 'node:http', 'node:net',
  'node:os', 'node:path', 'node:url', 'pg']);
const BANNED_STRINGS = new Set(['psql', '-e', '--eval', '-p', '--print', '-r', '--require', '--import', '--loader']);
// Запуск программ: что можно взять из child_process, какие программы запускать и у каких аргументы — только данные.
const CHILD_FUNCS = new Set(['spawn', 'spawnSync', 'execFile', 'execFileSync']);
// Имена среды, которые загружают код до запускаемой программы (аудит M3310-R15B-07).
const CHILD_ENV_BAD = /^(NODE_OPTIONS|NODE_PATH|PYTHONPATH|PYTHONHOME|PYTHONSTARTUP|BASH_ENV|ENV|LD_[A-Z_]+|DYLD_[A-Z_]+|PERL5OPT|PERL5LIB|RUBYOPT|JAVA_TOOL_OPTIONS|_JAVA_OPTIONS|JDK_JAVA_OPTIONS)$/;
const PROGRAMS = new Set(['gh', 'git', 'docker', 'podman', 'sudo', 'sh', 'bash']);
const DATA_PROGRAMS = new Set(['gh', 'git', 'docker', 'podman']);
// Сценарии после «-c» (аудит M3310-R7-02): постоянный сценарий может исполнить свои аргументы (eval "$1", "$@").
// Поэтому сценарий с $, `, eval, source, exec или «.» принимается, только если он — один из этих (ограждение fencer.mjs:
// вход в группу cgroup и запуск argv исполнителя под setpriv; остановка группы; проверка и остановка процесса в
// контейнере). Любой другой такой сценарий — находка.
const SHELL_SCRIPTS = new Set([
  'L=$1; U=$2; G=$3; shift 3; mkdir "$L" && echo $$ > "$L/cgroup.procs" && ' +
    'exec setpriv --reuid="$U" --regid="$G" --clear-groups --no-new-privs -- "$@"',
  'echo 1 > "$1/cgroup.kill"', 'kill -0 "$1"', 'kill -9 "$1"']);
const SHELLS = /^(sh|bash|dash|zsh|ash|ksh|mksh|csh|tcsh|fish|busybox|toybox)$/;
const INTERPRETERS = /^(python[0-9.]*|pypy[0-9.]*|perl[0-9.]*|ruby|php|lua[0-9.]*|tclsh|wish|expect|awk|gawk|mawk|nawk|node|nodejs|deno|bun|osascript|pwsh|powershell|psql|sqlite3|R|Rscript|julia|guile|racket|scheme)$/;
const SHELL_RUNS = /[$`]|\b(eval|source|exec)\b|(^|[\s;&|(])\.\s/;
const SKIP_KEYS = new Set(['type', 'start', 'end', 'loc', 'range']);
// Код правила у каждой находки: разрешение снимает только находку своего кода.
const CODES = [[/^(query text|function passing query text)/, 'QUERY_TEXT'], [/^name containing query/, 'QUERY_NAME'],
  [/^string with the word query/, 'QUERY_STRING'], [/^name .* is not allowed/, 'BANNED_NAME'],
  [/^property .* \(driver internals\)/, 'DRIVER'], [/^string .* starts code/, 'CODE_STRING'],
  [/^property accessed by a computed name/, 'COMPUTED'], [/^computed property name/, 'COMPUTED_KEY'],
  [/SQL text|template literal with SQL/, 'SQL_CONCAT'], [/^(module|with statement)/, 'MODULE'],
  [/^child process: (cwd option|environment that loads code)/, 'CHILD_OPTS'], [/^child process module imported/, 'CHILD_IMPORT'], [/^child process/, 'CHILD'], [/^global object changed/, 'GLOBAL_WRITE'],
  [/^(file cannot be parsed|template text cannot)/, 'PARSE']];
const GLOBALS = new Set(['Object', 'Array', 'Function', 'String', 'Number', 'Boolean', 'Symbol', 'JSON', 'Math',
  'Promise', 'Map', 'Set', 'globalThis', 'global']);
const codeOf = (why) => (CODES.find(([re]) => re.test(why)) || [null, 'OTHER'])[1];

const sqlish = (s) => typeof s === 'string' && SQL.test(s);
// Строка запускает код или psql: целиком или словом (node -e …, --eval=…).
const codeString = (s) => typeof s === 'string' &&
  (BANNED_STRINGS.has(s) || s.split(/[\s=]+/).some((w) => BANNED_STRINGS.has(w)));

function children(node) {
  const out = [];
  for (const k of Object.keys(node)) {
    if (SKIP_KEYS.has(k)) continue;
    const v = node[k];
    if (Array.isArray(v)) {
      for (const x of v) if (x && typeof x.type === 'string') out.push(x);
    } else if (v && typeof v.type === 'string') out.push(v);
  }
  return out;
}

const isFunc = (n) => n.type === 'FunctionDeclaration' || n.type === 'FunctionExpression' ||
  n.type === 'ArrowFunctionExpression';

function check(path, text) {
  const found = [];
  const add = (node, why) => found.push({ path, line: node.loc.start.line, code: codeOf(why), why });
  let tree;
  try {
    // *.cjs — сценарий CommonJS (аудит M3310-R11-03): разбирается как script и проверяется теми же правилами.
    tree = acorn.parse(text, { ecmaVersion: 'latest', sourceType: path.endsWith('.cjs') ? 'script' : 'module', locations: true, allowHashBang: true });
  } catch (e) {
    found.push({ path, line: (e.loc && e.loc.line) || 1, code: 'PARSE', why: 'file cannot be parsed as a JavaScript module' });
    return found;
  }

  // --- Области видимости: объявления (с подъёмом var и function), затем ссылки. ---
  const parent = new Map();
  const identScope = new Map(); // Identifier → область, где он стоит
  const declIds = new Set(); // Identifier, который объявляет имя
  const writeIds = new Set(); // Identifier, которому присваивают
  const nameIds = new Set(); // Identifier — не ссылка (ключ, свойство, метка)
  const newScope = (up, fn) => ({ up, fn, vars: new Map() });

  function declare(scope, id, b) {
    declIds.add(id);
    identScope.set(id, scope);
    const target = b.kind === 'var' ? funcScope(scope) : scope;
    const binding = { name: id.name, refs: [], writes: [], id, ...b };
    target.vars.set(id.name, binding);
    return binding;
  }
  const funcScope = (s) => { while (!s.fn) s = s.up; return s; };

  function declarePattern(p, scope, b) {
    if (!p) return;
    switch (p.type) {
      case 'Identifier': declare(scope, p, b); break;
      case 'ObjectPattern':
        for (const pr of p.properties) {
          if (pr.type === 'RestElement') declarePattern(pr.argument, scope, b);
          else {
            parent.set(pr, p);
            if (pr.computed) walk(pr.key, scope, pr); else if (pr.key !== pr.value) markName(pr.key, scope, pr);
            declarePattern(pr.value, scope, b);
          }
        }
        break;
      case 'ArrayPattern': for (const e of p.elements) declarePattern(e, scope, b); break;
      case 'RestElement': declarePattern(p.argument, scope, b); break;
      case 'AssignmentPattern': declarePattern(p.left, scope, b); walk(p.right, scope, p); break;
      default: walk(p, scope, null);
    }
  }
  function assignPattern(p, scope, from) {
    if (!p) return;
    parent.set(p, from);
    switch (p.type) {
      case 'Identifier': identScope.set(p, scope); writeIds.add(p); break;
      case 'ObjectPattern':
        for (const pr of p.properties) {
          parent.set(pr, p);
          if (pr.type === 'RestElement') { assignPattern(pr.argument, scope, pr); continue; }
          if (pr.computed) walk(pr.key, scope, pr); else if (pr.key !== pr.value) markName(pr.key, scope, pr);
          assignPattern(pr.value, scope, pr);
        }
        break;
      case 'ArrayPattern': for (const e of p.elements) assignPattern(e, scope, p); break;
      case 'RestElement': assignPattern(p.argument, scope, p); break;
      case 'AssignmentPattern': assignPattern(p.left, scope, p); walk(p.right, scope, p); break;
      default: walk(p, scope, from);
    }
  }
  function markName(id, scope, from) {
    parent.set(id, from);
    if (id.type === 'Identifier') { nameIds.add(id); identScope.set(id, scope); } else walk(id, scope, from);
  }

  function walk(node, scope, from) {
    if (!node) return;
    parent.set(node, from);
    switch (node.type) {
      case 'Identifier': identScope.set(node, scope); return;
      case 'FunctionDeclaration': case 'FunctionExpression': case 'ArrowFunctionExpression': {
        if (node.type === 'FunctionDeclaration' && node.id) declare(scope, node.id, { kind: 'function', decl: node });
        const fs_ = newScope(scope, true);
        if (node.type === 'FunctionExpression' && node.id) declare(fs_, node.id, { kind: 'fname', decl: node });
        node.params.forEach((p, i) => {
          parent.set(p, node);
          declarePattern(p, fs_, { kind: 'param', fn: node, index: p.type === 'Identifier' ? i : -1 });
        });
        if (node.body.type === 'BlockStatement') {
          parent.set(node.body, node);
          for (const s of node.body.body) walk(s, fs_, node.body);
        } else walk(node.body, fs_, node);
        return;
      }
      case 'ClassDeclaration': case 'ClassExpression': {
        if (node.type === 'ClassDeclaration' && node.id) declare(scope, node.id, { kind: 'class', decl: node });
        const cs = newScope(scope, false);
        if (node.type === 'ClassExpression' && node.id) declare(cs, node.id, { kind: 'class', decl: node });
        if (node.superClass) walk(node.superClass, cs, node);
        parent.set(node.body, node);
        for (const m of node.body.body) {
          parent.set(m, node.body);
          if (m.key) { if (m.computed) walk(m.key, cs, m); else markName(m.key, cs, m); }
          if (m.type === 'StaticBlock') { const ss = newScope(cs, true); for (const s of m.body) walk(s, ss, m); }
          else if (m.value) walk(m.value, cs, m);
        }
        return;
      }
      case 'BlockStatement': case 'StaticBlock': {
        const bs = newScope(scope, false);
        for (const s of node.body) walk(s, bs, node);
        return;
      }
      case 'ForStatement': case 'ForInStatement': case 'ForOfStatement': case 'SwitchStatement': {
        const ls = newScope(scope, false);
        for (const c of children(node)) {
          if ((node.type === 'ForInStatement' || node.type === 'ForOfStatement') && c === node.left &&
              c.type !== 'VariableDeclaration') assignPattern(c, ls, node);
          else walk(c, ls, node);
        }
        return;
      }
      case 'CatchClause': {
        const cs = newScope(scope, false);
        if (node.param) { parent.set(node.param, node); declarePattern(node.param, cs, { kind: 'catch' }); }
        walk(node.body, cs, node);
        return;
      }
      case 'VariableDeclaration':
        for (const d of node.declarations) {
          parent.set(d, node);
          parent.set(d.id, d);
          declarePattern(d.id, scope, { kind: node.kind, decl: d });
          if (d.init) walk(d.init, scope, d);
        }
        return;
      case 'ImportDeclaration':
        for (const s of node.specifiers) {
          parent.set(s, node);
          if (s.imported) markName(s.imported, scope, s);
          declare(scope, s.local, { kind: 'import', decl: s });
        }
        walk(node.source, scope, node);
        return;
      case 'ExportSpecifier': walk(node.local, scope, node); if (node.exported !== node.local) markName(node.exported, scope, node); return;
      case 'ExportAllDeclaration': if (node.exported) markName(node.exported, scope, node); walk(node.source, scope, node); return;
      case 'MemberExpression':
        walk(node.object, scope, node);
        if (node.computed) walk(node.property, scope, node); else markName(node.property, scope, node);
        return;
      case 'Property':
        if (node.computed) walk(node.key, scope, node); else if (node.key !== node.value) markName(node.key, scope, node);
        walk(node.value, scope, node);
        return;
      case 'LabeledStatement': case 'BreakStatement': case 'ContinueStatement':
        if (node.label) markName(node.label, scope, node);
        if (node.body) walk(node.body, scope, node);
        return;
      case 'MetaProperty': markName(node.meta, scope, node); markName(node.property, scope, node); return;
      case 'AssignmentExpression': assignPattern(node.left, scope, node); walk(node.right, scope, node); return;
      case 'UpdateExpression':
        if (node.argument.type === 'Identifier') { parent.set(node.argument, node); identScope.set(node.argument, scope); writeIds.add(node.argument); }
        else walk(node.argument, scope, node);
        return;
      default:
        for (const c of children(node)) walk(c, scope, node);
    }
  }
  const top = newScope(null, true);
  parent.set(tree, null);
  for (const s of tree.body) walk(s, top, tree);

  // Связать каждую ссылку и запись с объявлением.
  const bindingOf = new Map();
  const resolve = (id) => {
    for (let s = identScope.get(id); s; s = s.up) if (s.vars.has(id.name)) return s.vars.get(id.name);
    return null;
  };
  for (const [id] of identScope) {
    if (nameIds.has(id) || id.type !== 'Identifier') continue;
    const b = declIds.has(id) ? null : resolve(id);
    if (!b) continue;
    bindingOf.set(id, b);
    if (writeIds.has(id)) b.writes.push(id); else b.refs.push(id);
  }
  // Записи через разбор в объявлении var/let (повторное объявление var) тоже записи.
  const all = [];
  (function collect(n) { all.push(n); for (const c of children(n)) collect(c); })(tree);

  // --- Постоянный текст и известный текст. ---
  function constBinding(b) {
    return b && b.kind === 'const' && b.decl && b.decl.type === 'VariableDeclarator' && b.decl.id === b.id &&
      b.writes.length === 0;
  }
  function isConst(e, seen = new Set()) {
    if (!e) return false;
    switch (e.type) {
      case 'Literal': return typeof e.value === 'string';
      // Шаблон с ${…} постоянным не считается даже при постоянной подстановке (аудит M3310-R1B-02).
      case 'TemplateLiteral': return e.expressions.length === 0 && e.quasis.every((q) => q.value.cooked != null);
      case 'BinaryExpression': return e.operator === '+' && isConst(e.left, seen) && isConst(e.right, seen);
      case 'Identifier': {
        const b = bindingOf.get(e);
        if (!constBinding(b) || seen.has(b)) return false;
        // seen — путь по цепочке имён (защита от цикла), не общий список: A + A — постоянно.
        return isConst(b.decl.init, new Set([...seen, b]));
      }
      default: return false;
    }
  }
  // Значение постоянного текста (isConst) — строка, иначе null.
  function constValue(e, seen = new Set()) {
    if (!isConst(e)) return null;
    switch (e.type) {
      case 'Literal': return e.value;
      case 'TemplateLiteral': return e.quasis[0].value.cooked;
      case 'BinaryExpression': return constValue(e.left, seen) + constValue(e.right, seen);
      case 'Identifier': {
        const b = bindingOf.get(e);
        if (seen.has(b)) return null;
        return constValue(b.decl.init, new Set([...seen, b]));
      }
      default: return null;
    }
  }
  function textOf(e, seen = new Set()) {
    if (!e) return '';
    switch (e.type) {
      case 'Literal': return typeof e.value === 'string' ? e.value : '';
      case 'TemplateLiteral':
        return e.quasis.map((q, i) => (q.value.cooked || '') + (i < e.expressions.length ? textOf(e.expressions[i], seen) || ' ' : '')).join('');
      case 'BinaryExpression': return e.operator === '+' ? textOf(e.left, seen) + textOf(e.right, seen) : '';
      case 'ArrayExpression': return e.elements.map((x) => textOf(x, seen)).join(' ');
      case 'ConditionalExpression': return textOf(e.consequent, seen) + '\n' + textOf(e.alternate, seen);
      case 'LogicalExpression': return textOf(e.left, seen) + '\n' + textOf(e.right, seen);
      case 'CallExpression':
        if (e.callee.type === 'MemberExpression') return textOf(e.callee.object, seen) + ' ' + e.arguments.map((a) => textOf(a, seen)).join(' ');
        return '';
      case 'Identifier': {
        const b = bindingOf.get(e);
        if (!b || seen.has(b)) return '';
        seen.add(b);
        const parts = [];
        if (b.decl && b.decl.type === 'VariableDeclarator' && b.decl.id === b.id) parts.push(textOf(b.decl.init, seen));
        for (const w of b.writes) {
          const a = parent.get(w);
          if (a && a.type === 'AssignmentExpression' && a.left === w) parts.push(textOf(a.right, seen));
        }
        return parts.join('\n');
      }
      default: return '';
    }
  }

  // --- Таблица: const с объектом- или массивом-литералом этого файла (без «...», get/set и вычисляемых ключей),
  // в который ничего не пишут по вычисляемому имени (иначе ключ __proto__ сменил бы прототип), не разбирают в цели.
  function literalInit(b) {
    if (!constBinding(b)) return null;
    let init = b.decl.init;
    if (init && init.type === 'CallExpression' && init.callee.type === 'MemberExpression' && !init.callee.computed &&
        init.callee.object.type === 'Identifier' && init.callee.object.name === 'Object' && !bindingOf.get(init.callee.object) &&
        init.callee.property.name === 'freeze' && init.arguments.length === 1) init = init.arguments[0];
    return plainLiteral(init) ? init : null;
  }
  function plainLiteral(e) {
    return !!e && ((e.type === 'ObjectExpression' &&
      e.properties.every((p) => p.type === 'Property' && p.kind === 'init' && !p.computed)) ||
      (e.type === 'ArrayExpression' && e.elements.every((x) => x && x.type !== 'SpreadElement')));
  }
  // Только для чтения (аудит M3310-R6-01): const не даёт переназначить имя, но не мешает менять элементы. Поэтому
  // каждое упоминание имени должно быть чтением: x.a / x[k] не в цели записи, вызов не меняющего метода, for…of,
  // Object.keys/entries/values(x), «k in x». Всё иное (names[0] = …, push, передача в функцию, другое имя, экспорт) —
  // не таблица и не список.
  const READ_METHODS = new Set(['map', 'filter', 'forEach', 'some', 'every', 'find', 'findIndex', 'flatMap',
    'includes', 'indexOf', 'slice', 'join', 'at', 'hasOwnProperty']);
  // Аудит M3310-R7-01: обратный вызов этих методов получает сам массив третьим аргументом (и как this у function).
  // Поэтому принимается только стрелка (у неё нет своих this и arguments) с одним-двумя простыми параметрами,
  // без второго аргумента метода (thisArg). Иначе массив можно изменить под другим именем: names.forEach((_, i, a) =>
  // { a[0] = 'qu' + 'ery'; }).
  const CALLBACK_METHODS = new Set(['map', 'filter', 'forEach', 'some', 'every', 'find', 'findIndex', 'flatMap']);
  const safeCallback = (c) => c.arguments.length === 1 && c.arguments[0].type === 'ArrowFunctionExpression' &&
    c.arguments[0].params.length <= 2 && c.arguments[0].params.every((x) => x.type !== 'RestElement');
  // Метод объекта-литерала, написанный как function или f() {}, получает сам объект как this и может его изменить
  // (this.a = 'query', super.a = …). Вызов метода такой таблицы разрешён, только если ни один её метод не берёт
  // this или super (стрелки внутри метода берут this метода — тоже считается).
  const thisUsers = new Set();
  for (const n of all) {
    if (n.type !== 'ThisExpression' && n.type !== 'Super') continue;
    let f = parent.get(n);
    while (f && (f.type !== 'FunctionExpression' && f.type !== 'FunctionDeclaration')) f = parent.get(f);
    if (f) thisUsers.add(f);
  }
  const thisMethods = (lit) => lit.type === 'ObjectExpression' && lit.properties.some((pr) => thisUsers.has(pr.value));
  const writeTarget = (m) => {
    const up = parent.get(m);
    return !up || (up.type === 'AssignmentExpression' && up.left === m) || up.type === 'UpdateExpression' ||
      (up.type === 'UnaryExpression' && up.operator === 'delete') || up.type === 'ObjectPattern' ||
      up.type === 'ArrayPattern' || (up.type === 'Property' && up.value === m && parent.get(up) && parent.get(up).type === 'ObjectPattern') ||
      up.type === 'RestElement' || up.type === 'AssignmentPattern' ||
      ((up.type === 'ForOfStatement' || up.type === 'ForInStatement') && up.left === m);
  };
  const objectCall = (c, names) => c && c.type === 'CallExpression' && c.callee.type === 'MemberExpression' &&
    !c.callee.computed && c.callee.object.type === 'Identifier' && c.callee.object.name === 'Object' &&
    !bindingOf.get(c.callee.object) && names.includes(c.callee.property.name) && c.arguments.length === 1;
  // Литерал под Object.freeze (глобальный Object, не своё имя): его можно выставить наружу и передавать дальше —
  // настоящий Object.freeze не даёт менять элементы. Подменить Object.freeze проверка не даёт: встроенный объект —
  // только как Object.член, запись в Object.… — находка (аудит M3310-R8-01: const A = Object; A.freeze = (x) => x).
  // Запись в элемент замороженного литерала в этом файле — всё равно не таблица (аудит M3310-R8-01).
  function readOnly(b) {
    if (!constBinding(b)) return false;
    const lit = unfreeze(b.decl.init);
    if (lit !== b.decl.init) {
      return b.refs.every((r) => {
        let m = parent.get(r);
        if (!m || m.type !== 'MemberExpression' || m.object !== r) return true;
        while (m.type === 'MemberExpression' && parent.get(m) && parent.get(m).type === 'MemberExpression' && parent.get(m).object === m) m = parent.get(m);
        return !writeTarget(m);
      });
    }
    if (exported(b)) return false;
    return b.refs.every((r) => {
      const p = parent.get(r);
      if (!p) return false;
      if (p.type === 'MemberExpression' && p.object === r) {
        if (writeTarget(p)) return false;
        const c = parent.get(p);
        // Вызов из объекта-литерала (T.f(…), T[k](…)) — своя функция таблицы: у Object.prototype меняющих методов,
        // кроме запрещённых имён, нет. У массива — только не меняющие методы.
        if (c && c.type === 'CallExpression' && c.callee === p) {
          if (lit && lit.type === 'ObjectExpression') return !thisMethods(lit);
          if (p.computed || !READ_METHODS.has(p.property.name)) return false;
          return !CALLBACK_METHODS.has(p.property.name) || safeCallback(c);
        }
        // Цепочка от свойства (names.push.call(…), T.list[0] = …) — уже не чтение самого имени.
        if (c && c.type === 'MemberExpression' && c.object === p) return false;
        return true;
      }
      if (p.type === 'ForOfStatement' && p.right === r) return true;
      if (p.type === 'BinaryExpression' && p.operator === 'in' && p.right === r) return true;
      return objectCall(p, ['keys', 'entries', 'values']) && p.arguments[0] === r;
    });
  }
  function isTable(b) {
    return !!literalInit(b) && readOnly(b);
  }
  // Ключ из постоянного списка: for (const k of СПИСОК) или параметр стрелки в СПИСОК.map/filter/…((k) => …).
  // СПИСОК — массив строк этого файла, Object.keys(ТАБЛИЦА) (ключи литерала), то же через .sort() или имя const
  // с таким значением. Каждое имя списка проходит проверку имён (не query, не запрещённое имя).
  const unfreeze = (e) => (e && e.type === 'CallExpression' && e.callee.type === 'MemberExpression' && !e.callee.computed &&
    e.callee.object.type === 'Identifier' && e.callee.object.name === 'Object' && !bindingOf.get(e.callee.object) &&
    e.callee.property.name === 'freeze' && e.arguments.length === 1 ? e.arguments[0] : e);
  function listNames(e, seen = new Set()) {
    e = unfreeze(e);
    if (!e) return null;
    if (e.type === 'ArrayExpression') {
      return e.elements.every((x) => x && x.type === 'Literal' && typeof x.value === 'string') ? e.elements.map((x) => x.value) : null;
    }
    if (e.type === 'Identifier') {
      const b = bindingOf.get(e);
      if (!constBinding(b) || seen.has(b) || !readOnly(b)) return null;
      seen.add(b);
      return listNames(b.decl.init, seen);
    }
    if (e.type === 'CallExpression' && e.callee.type === 'MemberExpression' && !e.callee.computed) {
      const m = e.callee.property.name;
      if ((m === 'sort' || m === 'slice') && e.arguments.length === 0) return listNames(e.callee.object, seen);
      if (m === 'filter' && safeCallback(e)) return listNames(e.callee.object, seen);
      if (m === 'keys' && e.callee.object.type === 'Identifier' && e.callee.object.name === 'Object' &&
          !bindingOf.get(e.callee.object) && e.arguments.length === 1 && e.arguments[0].type === 'Identifier') {
        const tb = bindingOf.get(e.arguments[0]);
        const lit = isTable(tb) ? literalInit(tb) : null;
        if (!lit || lit.type !== 'ObjectExpression') return null;
        return lit.properties.map((pr) => (pr.key.type === 'Identifier' ? pr.key.name : String(pr.key.value)));
      }
    }
    return null;
  }
  const safeNames = (names) => !!names && names.every((v) => !QUERY.test(v) && !BANNED.has(v) && !DRIVER.has(v) && v !== '__proto__');
  function listKey(k) {
    if (k.type !== 'Identifier') return false;
    const b = bindingOf.get(k);
    if (!b || b.writes.length || b.id === undefined) return false;
    if (b.kind === 'const' && b.decl && b.decl.id === b.id) {
      const vd = parent.get(b.decl);
      const loop = vd && parent.get(vd);
      return !!loop && loop.type === 'ForOfStatement' && loop.left === vd && safeNames(listNames(loop.right));
    }
    if (b.kind === 'param' && b.index === 0 && b.fn.type === 'ArrowFunctionExpression') {
      const call = parent.get(b.fn);
      return !!call && call.type === 'CallExpression' && call.arguments[0] === b.fn &&
        call.callee.type === 'MemberExpression' && !call.callee.computed &&
        ['map', 'filter', 'forEach', 'some', 'every', 'find', 'flatMap'].includes(call.callee.property.name) &&
        safeNames(listNames(call.callee.object));
    }
    return false;
  }

  // --- Обёртки: параметр своей функции, каждый вызов которой передаёт постоянный текст. ---
  const wrapperDone = new Map();
  function wrapperBinding(fn) {
    if (fn.type === 'FunctionDeclaration') return fn.id ? resolveDecl(fn.id) : null;
    const p = parent.get(fn);
    if (p && p.type === 'VariableDeclarator' && p.init === fn && p.id.type === 'Identifier') {
      const b = resolveDecl(p.id);
      return constBinding(b) ? b : null;
    }
    return null;
  }
  function resolveDecl(id) {
    for (let s = identScope.get(id); s; s = s.up) if (s.vars.has(id.name) && s.vars.get(id.name).id === id) return s.vars.get(id.name);
    return null;
  }
  function exported(b) {
    let n = b.decl;
    if (b.kind === 'function') n = parent.get(n); else if (b.decl) n = parent.get(parent.get(b.decl));
    if (n && (n.type === 'ExportNamedDeclaration' || n.type === 'ExportDefaultDeclaration')) return true;
    return b.refs.some((r) => { const p = parent.get(r); return p && (p.type === 'ExportSpecifier' || p.type === 'ExportDefaultDeclaration'); });
  }
  function checkText(arg, call) {
    if (!arg || arg.type === 'SpreadElement') { add(call, 'query text is missing or spread'); return; }
    if (isConst(arg)) return;
    if (arg.type === 'Identifier') {
      const b = bindingOf.get(arg);
      if (b && b.kind === 'param' && b.index >= 0 && b.writes.length === 0) {
        const key = b.fn.start + ':' + b.index;
        if (wrapperDone.has(key)) { if (!wrapperDone.get(key)) add(call, 'query text comes from a parameter that is not always fixed'); return; }
        wrapperDone.set(key, true);
        const fb = wrapperBinding(b.fn);
        if (!fb || exported(fb)) {
          wrapperDone.set(key, false);
          add(call, 'query text is a parameter of a function that is not a local named function (or is exported)');
          return;
        }
        for (const r of fb.refs) {
          const c = parent.get(r);
          if (!c || c.type !== 'CallExpression' || c.callee !== r) { add(r, 'function passing query text is used other than by a direct call'); continue; }
          if (c.arguments.slice(0, b.index + 1).some((a) => a.type === 'SpreadElement')) { add(c, 'query text is missing or spread'); continue; }
          checkText(c.arguments[b.index], c);
        }
        return;
      }
    }
    add(call, 'query text is not a fixed string');
  }

  // --- Правила. ---
  const nameRule = (node, name) => {
    if (typeof name !== 'string') return;
    if (QUERY.test(name)) add(node, 'name containing query used other than as a direct call .query(…)');
    if (BANNED.has(name)) add(node, `name ${name} is not allowed (code from a string, reflection, prototype or driver internals)`);
  };
  // Ключ, который ОПРЕДЕЛЯЕТ свойство (объект-литерал, метод класса), ничего не читает: для него — только query и
  // __proto__ (смена прототипа). Ключ в разборе { a } = x и имя свойства x.a — чтение: полная проверка.
  const defines = (n, p) => p && ((p.type === 'Property' && p.key === n && !p.computed && parent.get(p) &&
    parent.get(p).type === 'ObjectExpression') || ((p.type === 'MethodDefinition' || p.type === 'PropertyDefinition') &&
    p.key === n && !p.computed));
  const reads = (n, p) => p && ((p.type === 'MemberExpression' && p.property === n) ||
    (p.type === 'Property' && p.key === n && parent.get(p) && parent.get(p).type === 'ObjectPattern'));
  const keyRule = (n, name, p) => {
    if (DRIVER.has(name) && reads(n, p)) add(n, `property ${name} is not allowed (driver internals)`);
    if (!defines(n, p)) return nameRule(n, name);
    if (QUERY.test(name)) add(n, 'name containing query used other than as a direct call .query(…)');
    if (name === '__proto__') add(n, 'name __proto__ is not allowed (prototype change)');
    if (name === 'NODE_OPTIONS') add(n, 'name NODE_OPTIONS is not allowed (code loaded into a started node)');
  };

  // --- Запуск программ (аудит M3310-R6-03). ---
  const isExecPath = (e) => e && e.type === 'MemberExpression' && !e.computed && e.object.type === 'Identifier' &&
    e.object.name === 'process' && !bindingOf.get(e.object) && e.property.name === 'execPath';
  function childImport(decl) {
    if (decl.type !== 'ImportDeclaration') { add(decl, 'child process module re-exported'); return; }
    for (const s of decl.specifiers) {
      if (s.type !== 'ImportSpecifier' || s.imported.type !== 'Identifier' || !CHILD_FUNCS.has(s.imported.name)) {
        add(s, 'child process: only spawn, spawnSync, execFile, execFileSync may be imported, by name');
        const nb = resolveDecl(s.local);
        for (const r of nb ? nb.refs : []) add(r, 'child process: function that is not allowed (exec, execSync, fork, whole module)');
        continue;
      }
      const b = resolveDecl(s.local);
      if (!b || b.writes.length) { add(s, 'child process function is reassigned'); continue; }
      for (const r of b.refs) {
        const c = parent.get(r);
        if (!c || c.type !== 'CallExpression' || c.callee !== r) add(r, 'child process function used other than by a direct call');
        else checkChild(c);
      }
    }
  }
  // Обёртка запуска (функция run(file, args) над execFile): программа или аргументы — параметры своей функции. Тогда
  // функция — своя функция файла, не выставлена наружу, используется только прямым вызовом, и КАЖДЫЙ вызов
  // проверяется как запуск программы с теми аргументами, что пришли на место параметров.
  function wrapperChild(call, depth) {
    const pos = new Map();
    let fn = null;
    call.arguments.forEach((a, i) => {
      const b = a.type === 'Identifier' ? bindingOf.get(a) : null;
      if (b && b.kind === 'param' && b.index >= 0 && !b.writes.length && (!fn || fn === b.fn)) { fn = b.fn; pos.set(i, b.index); }
    });
    if (!fn || !pos.has(0) || depth > 4) return;
    const fb = wrapperBinding(fn);
    if (!fb) return;
    if (exported(fb)) add(call, 'child process: wrapper function that starts programs is exported');
    for (const r of fb.refs) {
      const cs = parent.get(r);
      if (!cs || cs.type !== 'CallExpression' || cs.callee !== r) { add(r, 'child process: wrapper function used other than by a direct call'); continue; }
      if (cs.arguments.some((a) => a.type === 'SpreadElement')) { add(cs, 'child process call with spread arguments'); continue; }
      const none = { type: 'Identifier', name: 'undefined', start: cs.start, end: cs.end, loc: cs.loc };
      const pseudo = call.arguments.map((a, i) => (pos.has(i) ? cs.arguments[pos.get(i)] || none : a));
      checkChild({ type: 'CallExpression', arguments: pseudo, start: cs.start, end: cs.end, loc: cs.loc }, depth + 1);
    }
  }
  function checkChild(call, depth = 0) {
    const args = call.arguments;
    if (args.some((a) => a.type === 'SpreadElement')) { add(call, 'child process call with spread arguments'); return; }
    wrapperChild(call, depth);
    const prog = isExecPath(args[0]) ? 'node' : constValue(args[0]);
    if (prog !== 'node' && !PROGRAMS.has(prog)) add(call, 'child process: program is not a fixed allowed name');
    if (prog !== null && !DATA_PROGRAMS.has(prog) && !(args[1] && args[1].type === 'ArrayExpression')) {
      add(call, 'child process: node, sudo or a shell started without a literal argument list');
    }
    args.slice(1).forEach((a, i) => {
      if (a.type === 'ArrayExpression') {
        if (i === 0) { checkArgv(prog, a.elements, 0, a); argvArray(a, depth); }
      } else if (a.type === 'ObjectExpression') {
        for (const pr of a.properties) {
          if (pr.type !== 'Property' || pr.computed) { add(pr, 'child process options with spread or computed key'); continue; }
          const k = pr.key.type === 'Identifier' ? pr.key.name : pr.key.value;
          if (k === 'shell' && !(pr.value.type === 'Literal' && pr.value.value === false)) add(pr, 'child process started through a shell');
          // Аудит M3310-R15B-07: cwd меняет, какой файл запустит постоянное имя ('known.mjs' из /tmp); переменные
          // среды NODE_OPTIONS, LD_PRELOAD и подобные загружают код до проверенной программы. Среда, собранная
          // функцией (env: workerEnv()), проверяется при обязательной ревизии файла с PIN.
          if (k === 'cwd') add(pr, 'child process: cwd option changes which file a fixed name starts');
          if (k === 'env' && pr.value.type === 'ObjectExpression') {
            for (const ep of pr.value.properties) {
              const ek = ep.type === 'Property' && !ep.computed ? (ep.key.type === 'Identifier' ? ep.key.name : ep.key.value) : null;
              if (ek === null || CHILD_ENV_BAD.test(String(ek))) add(ep, 'child process: environment that loads code before the program');
            }
          }
        }
      } else if (i === 0 && a.type === 'Identifier' && (prog !== null || depth > 0)) {
        argvSource(a, depth); // список из параметра своей функции — по каждому вызову
      } else if (!(i >= 1 && isFunc(a))) {
        add(a, 'child process: arguments or options are not a literal');
      }
    });
  }
  // Список запуска (аудиты M3310-R9-01, R10-01..04). Строго: список — литерал в самом вызове или параметр своей
  // функции файла (не выставленной наружу) либо закрытого метода (#имя), который упомянут ОДИН раз — местом списка в
  // этом вызове; у параметра проверяется каждый вызов функции. Переменная со списком (const argv = [...]) — находка:
  // её можно изменить по ссылке. Копия «...x» — только из такого же параметра или из const-списка, который упомянут
  // лишь копиями, или map/flatMap со стрелкой, возвращающей список-литерал (он проверяется так же). Любой элемент, не
  // являющийся постоянной строкой, — находка: данные в списке запуска разрешаются только точной строкой файла
  // разрешений, а такой файл закреплён суммой (PIN).
  const ARGV_BAD = 'child process: argument list is not a list literal or a single-use parameter';
  function bindingCalls(fb, at, depth) {
    const sites = [];
    for (const r of fb.refs) {
      const cs = parent.get(r);
      if (cs && cs.type === 'CallExpression' && cs.callee === r) { sites.push(cs); continue; }
      // значение параметра по умолчанию (exec = ghRun): вызовы этого параметра
      if (cs && cs.type === 'AssignmentPattern' && cs.right === r && cs.left.type === 'Identifier' && depth < 3) {
        const pb = resolveDecl(cs.left);
        const more = pb && !pb.writes.length ? bindingCalls(pb, at, depth + 1) : null;
        if (more) { sites.push(...more); continue; }
      }
      add(r, 'child process: function that gets the argument list used other than by a direct call');
      return null;
    }
    return sites;
  }
  function callSites(fn, at) {
    const m = parent.get(fn);
    if (m && m.type === 'MethodDefinition') {
      if (m.computed || m.key.type !== 'PrivateIdentifier') { add(at, `${ARGV_BAD} (parameter of a public method)`); return null; }
      const sites = [];
      for (const n of all) {
        if (n.type !== 'MemberExpression' || n.property.type !== 'PrivateIdentifier' || n.property.name !== m.key.name) continue;
        const cs = parent.get(n);
        if (!cs || cs.type !== 'CallExpression' || cs.callee !== n) { add(n, 'child process: private method that starts programs used other than by a direct call'); return null; }
        sites.push(cs);
      }
      return sites;
    }
    const fb = wrapperBinding(fn);
    if (!fb || exported(fb)) { add(at, `${ARGV_BAD} (parameter of a function that is not a local one)`); return null; }
    return bindingCalls(fb, at, 0);
  }
  // Параметр, упомянутый ровно один раз — здесь (at): по ссылке его не изменить. Каждый вызов функции даёт на этом
  // месте список-литерал или такой же параметр.
  function paramSource(id, at, depth, asSpread) {
    const b = id.type === 'Identifier' ? bindingOf.get(id) : null;
    if (!b || b.kind !== 'param' || b.index < 0 || b.writes.length || b.refs.length !== 1 || b.refs[0] !== id || depth > 6) return false;
    for (const cs of callSites(b.fn, at) || []) {
      if (cs.arguments.some((a) => a.type === 'SpreadElement')) { add(cs, 'child process call with spread arguments'); continue; }
      const a = cs.arguments[b.index];
      if (!a) continue;
      if (a.type === 'ArrayExpression') { checkDashC(a); argvArray(a, depth + 1); } else if (!paramSource(a, a, depth + 1, asSpread)) add(a, ARGV_BAD);
    }
    return true;
  }
  function argvSource(id, depth) {
    if (!paramSource(id, id, depth, false)) add(id, ARGV_BAD);
  }
  // У x.flatMap(() => [...]) результат задаёт сам x (аудит M3310-R14-07): свой объект с методом flatMap вернёт любой
  // список. Принимается только настоящий массив: литерал, const со списком-литералом, который читают лишь как
  // x.map/x.flatMap, или Object.entries/keys/values(…) (Object защищён от подмены правилом встроенных объектов).
  function realArray(o) {
    if (o.type === 'ArrayExpression') return true;
    if (o.type === 'CallExpression' && o.callee.type === 'MemberExpression' && !o.callee.computed &&
      o.callee.object.type === 'Identifier' && o.callee.object.name === 'Object' && !bindingOf.get(o.callee.object) &&
      ['entries', 'keys', 'values'].includes(o.callee.property.name)) return true;
    if (o.type !== 'Identifier') return false;
    const b = bindingOf.get(o);
    return Boolean(constBinding(b) && b.decl.init && b.decl.init.type === 'ArrayExpression' && b.refs.every((r) => {
      const m = parent.get(r);
      const c = m && parent.get(m);
      return m && m.type === 'MemberExpression' && m.object === r && !m.computed && ['map', 'flatMap'].includes(m.property.name) &&
        c && c.type === 'CallExpression' && c.callee === m;
    }));
  }
  function argvArray(arr, depth) {
    for (const x of arr.elements) {
      if (!x) continue;
      if (x.type !== 'SpreadElement') {
        if (!isConst(x) || typeof constValue(x) !== 'string') add(x, 'child process: argument is not a fixed string');
        continue;
      }
      const s = x.argument;
      if (s.type === 'Identifier') {
        const b = bindingOf.get(s);
        if (constBinding(b) && b.decl.init && b.decl.init.type === 'ArrayExpression' &&
          b.refs.every((r) => parent.get(r) && parent.get(r).type === 'SpreadElement')) { argvArray(b.decl.init, depth + 1); continue; }
        if (paramSource(s, s, depth, true)) continue;
        add(x, 'child process: argument list copies (...) a value of unknown origin');
        continue;
      }
      if (s.type === 'CallExpression' && s.callee.type === 'MemberExpression' && !s.callee.computed &&
        ['map', 'flatMap'].includes(s.callee.property.name) && s.arguments.length === 1 &&
        s.arguments[0].type === 'ArrowFunctionExpression' && s.arguments[0].body.type === 'ArrayExpression' &&
        realArray(s.callee.object)) {
        argvArray(s.arguments[0].body, depth + 1);
        continue;
      }
      add(x, 'child process: argument list copies (...) a value of unknown origin');
    }
  }
  // Любой список файла (прямой вызов, своя обёртка this.docker([...]), список в переменной; аудит M3310-R8-02):
  // имя оболочки — только «оболочка -c сценарий из SHELL_SCRIPTS» (любой другой сценарий может запустить
  // python3 -c, eval и т. п.; слитые флаги -ec — тоже находка); имя другого исполнителя кода (python, perl, node …) —
  // находка; после «-c» у любой программы — постоянный текст, исполняющий аргументы — только из SHELL_SCRIPTS.
  const word = (x) => (x && x.type !== 'SpreadElement' && isConst(x) ? constValue(x) : null);
  const base = (s) => (typeof s === 'string' ? s.split('/').pop() : null);
  function checkDashC(a) {
    const el = a.elements;
    for (let j = 0; j < el.length; j++) {
      const x = el[j];
      const v = word(x);
      if (typeof v !== 'string') continue;
      if (SHELLS.test(base(v))) {
        if (word(el[j + 1]) !== '-c' || !SHELL_SCRIPTS.has(word(el[j + 2]))) {
          add(x, 'child process: shell in an argument list without -c and a script from SHELL_SCRIPTS');
          continue;
        }
        // «sh -c сценарий sh …»: слово после сценария — имя $0, не запуск.
        j += SHELLS.test(base(word(el[j + 3]))) ? 3 : 2;
        continue;
      }
      if (INTERPRETERS.test(base(v))) { add(x, `child process: interpreter ${v} in an argument list`); continue; }
      if (v !== '-c') continue;
      const s = word(el[j + 1]);
      if (typeof s !== 'string') add(x, 'child process: shell script after -c is not a fixed string');
      else if (SHELL_RUNS.test(s) && !SHELL_SCRIPTS.has(s)) {
        add(el[j + 1], 'child process: script after -c runs its arguments or variables and is not one of SHELL_SCRIPTS');
      }
    }
  }
  // Что именно запускают: node — с постоянным файлом первым (не флагом: -e, -, --eval=…), оболочка — только
  // «-c постоянный сценарий» (не чтение со входа), sudo — программу из списка, её аргументы — по тем же правилам.
  function checkArgv(prog, el, from, at) {
    const v = (j) => (el[j] && el[j].type !== 'SpreadElement' ? constValue(el[j]) : null);
    if (prog === 'node') {
      if (v(from) === null || v(from).startsWith('-')) add(at, 'child process: node is started with a first argument that is not a fixed file name');
    } else if (prog === 'sh' || prog === 'bash') {
      if (v(from) !== '-c' || !SHELL_SCRIPTS.has(v(from + 1))) add(at, 'child process: shell started without -c and a script from SHELL_SCRIPTS');
    } else if (prog === 'sudo') {
      let j = from;
      while (v(j) !== null && v(j).startsWith('-')) j++;
      const next = v(j);
      if (next === null || next === 'sudo' || !PROGRAMS.has(next)) add(at, 'child process: sudo runs a program that is not a fixed allowed name');
      else checkArgv(next, el, j + 1, at);
    }
  }
  for (const n of all) {
    const p = parent.get(n);
    switch (n.type) {
      case 'Identifier': {
        // Встроенный объект (Object, Array, JSON, globalThis …) — только как X.член, вызов X(…), new X(…), x instanceof
        // X, typeof X; другое имя для него (const A = Object), запись в само имя или передача дальше — находка: так
        // встроенный меняют в обход проверки записи (аудит M3310-R8-01). Boolean, String, Number можно передать
        // функцией (filter(Boolean)).
        if (identScope.has(n) && !bindingOf.get(n) && GLOBALS.has(n.name) && !(p && (
          (p.type === 'MemberExpression' && p.object === n) || ((p.type === 'CallExpression' || p.type === 'NewExpression') && p.callee === n) ||
          (p.type === 'BinaryExpression' && p.operator === 'instanceof' && p.right === n) ||
          (p.type === 'UnaryExpression' && p.operator === 'typeof') ||
          (p.type === 'CallExpression' && p.arguments.includes(n) && ['Boolean', 'String', 'Number'].includes(n.name))))) {
          add(n, `global object changed: ${n.name} used other than as ${n.name}.member or a call`);
        }
        const directCall = n.name === 'query' && p && p.type === 'MemberExpression' && p.property === n && !p.computed &&
          parent.get(p) && parent.get(p).type === 'CallExpression' && parent.get(p).callee === p;
        // Object.entries(T) и Object.values(T) у таблицы этого файла отдают только то, что записано в литерале.
        const tableWalk = (n.name === 'entries' || n.name === 'values') && p && p.type === 'MemberExpression' &&
          p.property === n && !p.computed && p.object.type === 'Identifier' && p.object.name === 'Object' &&
          !bindingOf.get(p.object) && parent.get(p) && parent.get(p).type === 'CallExpression' &&
          parent.get(p).callee === p && parent.get(p).arguments.length === 1 &&
          parent.get(p).arguments[0].type === 'Identifier' && isTable(bindingOf.get(parent.get(p).arguments[0]));
        if (!directCall && !tableWalk) keyRule(n, n.name, p);
        break;
      }
      case 'PrivateIdentifier': nameRule(n, n.name); break;
      case 'Literal':
        if (typeof n.value === 'string') {
          if (/(^|[^A-Za-z0-9_$])query($|[^A-Za-z0-9_$])/i.test(n.value) || n.value.trim().toLowerCase() === 'query') add(n, 'string with the word query');
          if (codeString(n.value)) add(n, `string ${JSON.stringify(n.value.slice(0, 40))} starts code or psql from a string`);
          if (n.value === 'NODE_OPTIONS') nameRule(n, n.value);
          if (p && ((p.type === 'Property' && p.key === n) || (p.type === 'MemberExpression' && p.property === n) ||
              p.type === 'ImportSpecifier' || p.type === 'ExportSpecifier' || p.type === 'MethodDefinition' ||
              p.type === 'PropertyDefinition')) keyRule(n, n.value, p);
        }
        break;
      case 'TemplateLiteral':
        for (const q of n.quasis) {
          if (q.value.cooked == null) add(n, 'template text cannot be read');
          else if (/(^|[^A-Za-z0-9_$])query($|[^A-Za-z0-9_$])/i.test(q.value.cooked)) add(n, 'string with the word query');
        }
        // Куски шаблона проверяются вместе: подстановка ${…} — часть слова, не разделитель («-p${pass}» — не флаг -p).
        if (n.quasis.every((q) => q.value.cooked != null) && codeString(n.quasis.map((q) => q.value.cooked).join('X'))) {
          add(n, 'string in a template starts code or psql from a string');
        }
        if (p && p.type === 'MemberExpression' && p.property === n && n.expressions.length === 0) keyRule(n, n.quasis[0].value.cooked, p);
        if (n.expressions.length && sqlish(textOf(n))) add(n, 'template literal with SQL text and ${}');
        break;
      case 'MemberExpression':
        // Подмена встроенного (Object.freeze = …, разбор в Object.x, delete, ++): на нём держатся правила таблиц
        // и списков. Корень цепочки — глобальное имя (не своё).
        if (writeTarget(n)) {
          let root = n.object;
          while (root.type === 'MemberExpression') root = root.object;
          if (root.type === 'Identifier' && !bindingOf.get(root) && GLOBALS.has(root.name)) add(n, `global object changed: ${root.name}`);
        }
        if (n.computed) {
          const k = n.property;
          const fixedKey = (k.type === 'Literal' && (typeof k.value === 'string' || typeof k.value === 'number')) ||
            (k.type === 'TemplateLiteral' && k.expressions.length === 0);
          if (!fixedKey && !listKey(k) && !plainLiteral(n.object) &&
              !(n.object.type === 'Identifier' && isTable(bindingOf.get(n.object)))) {
            add(n, 'property accessed by a computed name (allowed: constant table of this file or key from a constant list)');
          }
        }
        break;
      case 'Property': case 'MethodDefinition': case 'PropertyDefinition':
        if (n.computed && !(n.key.type === 'Literal' || (n.key.type === 'TemplateLiteral' && n.key.expressions.length === 0))) {
          add(n, 'computed property name');
        } else if (n.computed && n.key.type === 'TemplateLiteral') nameRule(n.key, n.key.quasis[0].value.cooked);
        if (n.type === 'Property' && (n.kind === 'get' || n.kind === 'set') && p && p.type === 'ObjectExpression') { /* get/set: таблицей не считается */ }
        break;
      case 'CallExpression':
        if (n.callee.type === 'MemberExpression' && !n.callee.computed && n.callee.property.type === 'Identifier' &&
            n.callee.property.name === 'query') checkText(n.arguments[0], n);
        if (n.callee.type === 'MemberExpression' && !n.callee.computed && n.callee.property.type === 'Identifier' &&
            ['join', 'concat', 'replace', 'replaceAll'].includes(n.callee.property.name) && sqlish(textOf(n))) {
          add(n, 'SQL text built with a string method');
        }
        break;
      case 'BinaryExpression':
        if (n.operator === '+' && !(p && p.type === 'BinaryExpression' && p.operator === '+')) {
          // Сумма только постоянных частей — известный целиком текст: проверяется как строка, не как склейка.
          if (isConst(n)) { if (codeString(constValue(n))) add(n, 'string built from fixed parts starts code or psql from a string'); }
          else if (sqlish(textOf(n))) add(n, 'SQL text joined with +');
        }
        break;
      case 'AssignmentExpression': {
        if (n.operator === '+=' && sqlish(textOf(n.left) + textOf(n.right))) add(n, 'SQL text appended with +=');
        break;
      }
      case 'ArrayExpression': checkDashC(n); break;
      case 'ImportExpression': add(n, 'module loaded at run time (import())'); break;
      case 'WithStatement': add(n, 'with statement'); break;
      case 'ImportDeclaration': case 'ExportNamedDeclaration': case 'ExportAllDeclaration':
        if (n.source && typeof n.source.value === 'string') {
          const m = n.source.value.replace(/^node:/, '');
          if (BANNED_MODULES.has(m) || /^(data|https?):/i.test(n.source.value)) add(n, `module ${n.source.value} runs code from a string`);
          // Закрытый список модулей (аудит M3310-R14-03, -06): сторонний пакет (postgres.js sql.unsafe, execa …)
          // шлёт запрос или запускает программу мимо проверки .query и child_process. Разрешены только JS_MODULES.
          else if (!/^(\.|\/|file:|#)/i.test(n.source.value) && !JS_MODULES.has(n.source.value)) add(n, `module ${n.source.value} is not in the closed list of modules`);
          // Свой файл — только формата, который проверяет сканер (аудит M3310-R11-03); «#имя» (карта imports
          // package.json) ведёт к файлу, которого проверка не видит.
          if (/^(\.|\/|file:)/i.test(n.source.value) && !/\.(mjs|js|cjs)$/.test(n.source.value.split(/[?#]/)[0])) add(n, `module ${n.source.value} has a format the scan does not check`);
          if (n.source.value.startsWith('#')) add(n, `module ${n.source.value} is resolved through the imports map`);
          // Самопроверка R15: путь к пакету (../node_modules/postgres/…) или абсолютный путь обходит закрытый список.
          if (/(^|\/)node_modules(\/|$)/.test(n.source.value) || /^(\/|file:)/i.test(n.source.value)) add(n, `module ${n.source.value} is outside the scanned tree`);
          else if (n.source.value.startsWith('.') && /\.(mjs|js|cjs)$/.test(n.source.value.split(/[?#]/)[0]) && !SCANNED.has(real(nodePath.resolve(nodePath.dirname(path), n.source.value.split(/[?#]/)[0])))) add(n, `module ${n.source.value} is not one of the scanned files`);
          if (m === 'child_process') {
            // Запускать программы может только файл, чья строка импорта есть в файле разрешений (код CHILD_IMPORT):
            // иначе любой файл мог бы записать код во временный файл и запустить его node.
            add(n, 'child process module imported (only files listed in the allow file may start programs)');
            childImport(n);
          }
        }
        break;
      default: break;
    }
  }
  return found;
}

let failed = false;
console.log(JSON.stringify({ parser: `acorn ${acorn.version}`, node: process.version }));
for (const p of process.argv.slice(2)) {
  let text;
  try { text = fs.readFileSync(p, 'utf8'); } catch (e) { failed = true; console.error(`cannot read ${p}: ${e.message}`); continue; }
  const seen = new Set();
  for (const f of check(p, text)) {
    const key = f.line + '\0' + f.why;
    if (seen.has(key)) continue;
    seen.add(key);
    console.log(JSON.stringify(f));
  }
}
process.exit(failed ? 2 : 0);
