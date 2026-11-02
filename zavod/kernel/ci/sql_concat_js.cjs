'use strict';
// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_js.cjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-11-02 02:21 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
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
//      этого файла (без «...», get/set и вычисляемых ключей), в который ничего не записывается. Вычисляемый ключ
//      { [k]: … } в объекте, разборе и классе — находка.
//   4) Код из строки и доступ в обход: eval, Function, constructor, prototype, __proto__, Reflect, Proxy,
//      getPrototypeOf/setPrototypeOf, getOwnPropertyDescriptor(s)/Names, defineProperty(ies), create, assign, values,
//      entries, call/apply/bind, require, createRequire, binding, _linkedBinding, dlopen — находка как имя, свойство
//      или ключ разбора (ключ, который только определяет свойство в объекте-литерале или классе, не читает — для
//      него только query и __proto__; constructor класса допустим). Object.entries/values у таблицы этого файла —
//      допустимы. Чтение свойства connection (нижний слой драйвера pg: x.connection, x['connection'],
//      { connection } = x) — находка. import(…), with, модули vm, module, repl, inspector, worker_threads,
//      источники data:/http(s): — находка; строки psql, -e, --eval, -p, --print, -r, --require, --import,
//      --loader (запуск кода или psql из строки) — находка.
//   5) Склейка, похожая на запрос: «+», «+=», шаблон с ${}, .join/.concat/.replace(All), где известный текст
//      (строки, значения имён по всем присваиваниям, массивы) похож на запрос.
// ВЫЗОВ: node --expose-internals sql_concat_js.cjs файл…  (вызывает sql_concat_scan.py). Печать: первая строка
//   {"parser": …}, далее по строке JSON на находку {"path", "line", "why"}. Код выхода 0 — проверка прошла до конца
//   (находки решает sql_concat_scan.py), 2 — сбой самой проверки.
// ОГРАНИЧЕНИЯ: разборщик берётся из Node (internal/deps/acorn, флаг --expose-internals; версия печатается; в CI Node
//   закреплён setup-node). Правила строгие, поэтому ложные находки ожидаемы: проверенные строки с причиной идут в
//   sql_concat_allow.txt и видны аудиту. Вне проверки: (а) драйвер базы, написанный заново поверх сети (net) с
//   ручным протоколом — это не склейка, а свой драйвер; (б) запуск другой программы (child_process): проект законно
//   запускает node, podman, docker, gh с файлами из хранилища — что делает запущенная программа, решают ограждение
//   (fencer) и песочница работника, а их файлы проверяет этот же сканер; запрещён только запуск кода прямо из строки.
const fs = require('node:fs');
const acorn = require('internal/deps/acorn/acorn/dist/acorn');

const SQL = /\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|GRANT\s|REVOKE\s|TRUNCATE\s|COPY\s|EXECUTE\s|SET\s+(LOCAL\s+)?ROLE|WHERE\s|VALUES\s*\()/;
const QUERY = /query/i;
const BANNED = new Set(['eval', 'Function', 'constructor', 'prototype', '__proto__', '__defineGetter__',
  '__defineSetter__', '__lookupGetter__', '__lookupSetter__', 'Reflect', 'Proxy', 'getPrototypeOf', 'setPrototypeOf',
  'getOwnPropertyDescriptor', 'getOwnPropertyDescriptors', 'getOwnPropertyNames', 'defineProperty',
  'defineProperties', 'assign', 'values', 'entries', 'call', 'apply', 'bind', 'require',
  'createRequire', 'create', 'binding', '_linkedBinding', 'dlopen']);
// Внутренности драйвера pg: опасно только ЧТЕНИЕ свойства (x.connection, { connection } = x), не имя переменной.
const DRIVER = new Set(['connection']);
const BANNED_MODULES = new Set(['vm', 'module', 'repl', 'inspector', 'worker_threads']);
const BANNED_STRINGS = new Set(['psql', '-e', '--eval', '-p', '--print', '-r', '--require', '--import', '--loader']);
const SKIP_KEYS = new Set(['type', 'start', 'end', 'loc', 'range']);

const sqlish = (s) => typeof s === 'string' && SQL.test(s);

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
  const add = (node, why) => found.push({ path, line: node.loc.start.line, why });
  let tree;
  try {
    tree = acorn.parse(text, { ecmaVersion: 'latest', sourceType: 'module', locations: true, allowHashBang: true });
  } catch (e) {
    found.push({ path, line: (e.loc && e.loc.line) || 1, why: 'file cannot be parsed as a JavaScript module' });
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
  function isTable(b) {
    if (!literalInit(b)) return false;
    for (const r of b.refs) {
      const m = parent.get(r);
      if (!m || m.type !== 'MemberExpression' || m.object !== r) continue;
      const up = parent.get(m);
      const target = up && ((up.type === 'AssignmentExpression' && up.left === m) || up.type === 'UpdateExpression' ||
        (up.type === 'UnaryExpression' && up.operator === 'delete') || up.type === 'ObjectPattern' ||
        up.type === 'ArrayPattern' || (up.type === 'Property' && up.value === m && parent.get(up) && parent.get(up).type === 'ObjectPattern') ||
        up.type === 'RestElement' || up.type === 'AssignmentPattern' ||
        ((up.type === 'ForOfStatement' || up.type === 'ForInStatement') && up.left === m));
      if (target && m.computed) return false;
    }
    return true;
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
      if (!constBinding(b) || seen.has(b)) return null;
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
  };
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
          if (BANNED_STRINGS.has(n.value)) add(n, `string ${n.value} starts code or psql from a string`);
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
        if (n.operator === '+' && !(p && p.type === 'BinaryExpression' && p.operator === '+') && sqlish(textOf(n))) {
          add(n, 'SQL text joined with +');
        }
        break;
      case 'AssignmentExpression':
        if (n.operator === '+=' && sqlish(textOf(n.left) + textOf(n.right))) add(n, 'SQL text appended with +=');
        break;
      case 'ImportExpression': add(n, 'module loaded at run time (import())'); break;
      case 'WithStatement': add(n, 'with statement'); break;
      case 'ImportDeclaration': case 'ExportNamedDeclaration': case 'ExportAllDeclaration':
        if (n.source && typeof n.source.value === 'string') {
          const m = n.source.value.replace(/^node:/, '');
          if (BANNED_MODULES.has(m) || /^(data|https?):/i.test(n.source.value)) add(n, `module ${n.source.value} runs code from a string`);
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
