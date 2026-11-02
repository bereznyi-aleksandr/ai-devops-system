'use strict';
// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_js.cjs
// ВЕРСИЯ: v0.2  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-11-02 02:21 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
// ДАТА ОБНОВЛЕНИЯ: 2026-11-02 02:55 +02:00 (v0.2: аудит M3310-R6-01..04 — таблица и список ключей только для
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
//      sqlite, источники data:/http(s): — находка; постоянная строка (и сумма постоянных строк), где словом стоит
//      psql, -e, --eval, -p, --print, -r, --require, --import, --loader (в том числе «node -e …», «--eval=…»), —
//      находка (запуск кода или psql из строки).
//   5) Склейка, похожая на запрос: «+», «+=», шаблон с ${}, .join/.concat/.replace(All), где известный текст
//      (строки, значения имён по всем присваиваниям, массивы) похож на запрос. Сумма, где ВСЕ части постоянны
//      (строки и const), — не склейка: её текст известен при проверке целиком.
//   6) Запуск программ (аудит M3310-R6-03). Из child_process можно взять только по имени spawn, spawnSync, execFile,
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
const BANNED_MODULES = new Set(['vm', 'module', 'repl', 'inspector', 'worker_threads', 'cluster', 'sqlite']);
const BANNED_STRINGS = new Set(['psql', '-e', '--eval', '-p', '--print', '-r', '--require', '--import', '--loader']);
// Запуск программ: что можно взять из child_process, какие программы запускать и у каких аргументы — только данные.
const CHILD_FUNCS = new Set(['spawn', 'spawnSync', 'execFile', 'execFileSync']);
const PROGRAMS = new Set(['gh', 'git', 'docker', 'podman', 'sudo', 'sh', 'bash']);
const DATA_PROGRAMS = new Set(['gh', 'git', 'docker', 'podman']);
const SKIP_KEYS = new Set(['type', 'start', 'end', 'loc', 'range']);
// Код правила у каждой находки: разрешение снимает только находку своего кода.
const CODES = [[/^(query text|function passing query text)/, 'QUERY_TEXT'], [/^name containing query/, 'QUERY_NAME'],
  [/^string with the word query/, 'QUERY_STRING'], [/^name .* is not allowed/, 'BANNED_NAME'],
  [/^property .* \(driver internals\)/, 'DRIVER'], [/^string .* starts code/, 'CODE_STRING'],
  [/^property accessed by a computed name/, 'COMPUTED'], [/^computed property name/, 'COMPUTED_KEY'],
  [/SQL text|template literal with SQL/, 'SQL_CONCAT'], [/^(module|with statement)/, 'MODULE'],
  [/^child process/, 'CHILD'], [/^global object changed/, 'GLOBAL_WRITE'],
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
    tree = acorn.parse(text, { ecmaVersion: 'latest', sourceType: 'module', locations: true, allowHashBang: true });
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
  // Литерал под Object.freeze (глобальный Object, не своё имя) заморожен с самого объявления: его элементы и ключи
  // не меняются никем, поэтому упоминания имени не важны.
  function readOnly(b) {
    if (!constBinding(b)) return false;
    const lit = unfreeze(b.decl.init);
    if (lit !== b.decl.init) return true;
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
          return (lit && lit.type === 'ObjectExpression') || (!p.computed && READ_METHODS.has(p.property.name));
        }
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
      if (m === 'filter') return listNames(e.callee.object, seen);
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
  function checkChild(call) {
    const args = call.arguments;
    if (args.some((a) => a.type === 'SpreadElement')) { add(call, 'child process call with spread arguments'); return; }
    const prog = isExecPath(args[0]) ? 'node' : constValue(args[0]);
    if (prog !== 'node' && !PROGRAMS.has(prog)) add(call, 'child process: program is not a fixed allowed name');
    if (prog !== null && !DATA_PROGRAMS.has(prog) && !(args[1] && args[1].type === 'ArrayExpression')) {
      add(call, 'child process: node, sudo or a shell started without a literal argument list');
    }
    args.slice(1).forEach((a, i) => {
      if (a.type === 'ArrayExpression') {
        const el = a.elements;
        el.forEach((x, j) => {
          if (x && x.type !== 'SpreadElement' && constValue(x) === '-c' && !isConst(el[j + 1])) {
            add(x, 'child process: shell script after -c is not a fixed string');
          }
        });
        if (i === 0) checkArgv(prog, el, 0, a);
      } else if (a.type === 'ObjectExpression') {
        for (const pr of a.properties) {
          if (pr.type !== 'Property' || pr.computed) { add(pr, 'child process options with spread or computed key'); continue; }
          const k = pr.key.type === 'Identifier' ? pr.key.name : pr.key.value;
          if (k === 'shell' && !(pr.value.type === 'Literal' && pr.value.value === false)) add(pr, 'child process started through a shell');
        }
      } else if (i === 0 && DATA_PROGRAMS.has(prog)) {
        // аргументы программы-данных (gh, git, docker, podman) могут прийти списком из переменной
      } else if (!(i >= 1 && isFunc(a))) {
        add(a, 'child process: arguments or options are not a literal');
      }
    });
  }
  // Что именно запускают: node — с постоянным файлом первым (не флагом: -e, -, --eval=…), оболочка — только
  // «-c постоянный сценарий» (не чтение со входа), sudo — программу из списка, её аргументы — по тем же правилам.
  function checkArgv(prog, el, from, at) {
    const v = (j) => (el[j] && el[j].type !== 'SpreadElement' ? constValue(el[j]) : null);
    if (prog === 'node') {
      if (v(from) === null || v(from).startsWith('-')) add(at, 'child process: node is started with a first argument that is not a fixed file name');
    } else if (prog === 'sh' || prog === 'bash') {
      if (v(from) !== '-c' || !isConst(el[from + 1])) add(at, 'child process: shell started without a fixed script after -c');
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
        // Подмена встроенного (Object.freeze = …, Array.prototype…): на нём держатся правила таблиц и списков.
        let root = n.left;
        while (root.type === 'MemberExpression') root = root.object;
        if (n.left.type === 'MemberExpression' && root.type === 'Identifier' && !bindingOf.get(root) && GLOBALS.has(root.name)) {
          add(n, `global object changed: ${root.name}`);
        }
        break;
      }
      case 'ImportExpression': add(n, 'module loaded at run time (import())'); break;
      case 'WithStatement': add(n, 'with statement'); break;
      case 'ImportDeclaration': case 'ExportNamedDeclaration': case 'ExportAllDeclaration':
        if (n.source && typeof n.source.value === 'string') {
          const m = n.source.value.replace(/^node:/, '');
          if (BANNED_MODULES.has(m) || /^(data|https?):/i.test(n.source.value)) add(n, `module ${n.source.value} runs code from a string`);
          if (m === 'child_process') childImport(n);
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
