# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_scan.py
# ВЕРСИЯ: v0.13  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 08:40 +02:00 (v0.13: аудит M3310-R12-01..03 —
#   getattr/setattr/delattr/eval/exec/compile только прямым вызовом, attrgetter/methodcaller в любом виде, правка
#   sys.path/meta_path/path_hooks и addsitedir — PY_RUN; архивы (.zip, .egg, .whl …) и .pyd — находка FORMAT);
#   прежняя дата: 2026-11-02 07:26 +02:00 (v0.12: аудит M3310-R11-01..03 —
#   специальные имена и атрибуты (__dict__, __globals__, __getattribute__ …), .modules, кадры стека, getattr с именем
#   не ПОСТОЯННОЙ, .system/.popen/.exec*/.spawn* у любого объекта — PY_RUN; *.cjs проверяется; исполняемые форматы,
#   которые проверка не разбирает (.ts, .node, .pyc …, в том числе в __pycache__), — находка FORMAT); прежняя дата: 2026-11-02 07:05 +02:00 (v0.11: аудит M3310-R10-05..07 —
#   любой не постоянный аргумент запуска — находка PY_RUN; параметр затеняет внешнее имя; модули запуска (subprocess,
#   importlib, builtins, ctypes …), .eval/.exec, getattr(…, 'exec'), globals/vars, import_module/exec_module — находка
#   PY_RUN; файл с разрешённым запуском (CHILD, CHILD_IMPORT, PY_RUN) обязан быть закреплён суммой (строка PIN); v0.10: аудит M3310-R9-02..04 —
#   метод запроса, взятый как значение (send = cur.execute), — находка; цикл доказательства (функция передаёт параметр
#   сама себе) — не постоянно; запуск программ из Python — только subprocess.run/Popen/call/check_* по имени модуля,
#   без shell, программа — постоянное имя, не оболочка и не исполнитель кода, список — литерал без изменений методами;
#   os.system/popen/exec*/spawn*, pty.spawn, asyncio.create_subprocess_*, импорт «from subprocess» и «as» — находка; v0.9: аудит M3310-R8-03 — SQL узнаётся в любом регистре;
#   у мест выполнения запроса в Python (.execute и родня, psql через subprocess с текстом на входе) текст обязан
#   быть постоянным, параметр своей функции — только если все её вызовы в файле дают постоянный текст; eval, exec,
#   compile, getattr с не постоянным именем — находка; v0.8: аудит M3310-R7-03 — проверяются и сценарии оболочки (*.sh и файлы с #!…sh): запрос к базе только
#   постоянным текстом (psql -c, помощник запроса, труба и heredoc в psql), eval, source, программа из подстановки,
#   код из строки (python -c, node -e) — находка; v0.7: аудит M3310-R6-04 —
#   разрешение снимает только находку своего кода правила: строка «путь<TAB>КОД<TAB>точный текст»; строка разрешения,
#   где есть объект базы (pg., Pool, Client, pool, client, db, .query), — отказ; v0.6: аудит M3310-R5-01, -02, -03 —
#   JavaScript проверяется не по тексту, а полным разбором кода: sql_concat_js.cjs (разборщик acorn из Node, имена
#   связываются с объявлениями по областям видимости, правила разрешающие — что не доказано постоянным, то находка);
#   прежняя проверка JavaScript по регулярным выражениям (v0.2–v0.5) удалена; v0.5: аудит M3310-R4-01; v0.4: аудит
#   M3310-R3-01; v0.3: аудит M3310-R2-01 — проверка по месту вызова; v0.2: аудит M3310-R1B-02 — текст запроса
#   через переменные)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: проверка сборки (карта 3.3.10.2, протокол И.7а п.2): запрос к базе — только заранее написанный текст,
#   значения — только параметрами. Находит склейку запросов (текст запроса, собранный из кусков во время работы)
#   и роняет сборку (код выхода 1, строки SQL_CONCAT ...).
#   Python (службы ячейки): f-строка с подстановкой, «+», «+=», «%», .format(), .join(), .replace() — если
#   сложенный текст всех известных кусков похож на запрос. Кусок известен, если он записан в коде прямо, лежит в
#   переменной, которой в этом файле присвоен такой текст, или его возвращает функция этого файла (по всем
#   присваиваниям и return, до неподвижной точки).
#   JavaScript (ядро, движок): все файлы *.mjs и *.js одним вызовом передаются в sql_concat_js.cjs (правила — в его
#   шапке): у каждого .query(…) текст доказан постоянным по дереву разбора; имя query, вычисляемое имя свойства,
#   код из строки, отражение (reflection — доступ к свойствам и прототипу в обход имени) и нижний слой драйвера —
#   находка. Разборщик печатается строкой SQL_CONCAT_JS_PARSER=…; сбой разборщика — отказ.
#   Исключения — только из файла разрешений: строка «путь<TAB>КОД<TAB>точный текст строки кода», для каждой — причина;
#   КОД — код правила находки (QUERY_TEXT, COMPUTED, CHILD …, у Python — PY_SQL), снимается только он.
# ВЫЗОВ: python3 -I sql_concat_scan.py [--allow файл] путь…   (папки обходятся целиком: *.py, *.mjs, *.js и файлы
#   без расширения с первой строкой «#!…python3»). Node — из переменной ZAVOD_NODE, иначе node из PATH.
# ОГРАНИЧЕНИЯ: в Python текст, пришедший из другого файла или извне, сканер не видит; поэтому запросы пишутся
#   постоянными в том же файле, где выполняются (службы ячейки шлют запросы только через psql с постоянным
#   текстом). Неиспользованная строка разрешений — тоже отказ: разрешения не копятся.
import ast
import hashlib
import json
import os
import re
import subprocess
import sys

SQL = re.compile(r'\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|GRANT\s|REVOKE\s|TRUNCATE\s'
                 r'|COPY\s|EXECUTE\s|SET\s+(LOCAL\s+)?ROLE|WHERE\s|VALUES\s*\()', re.IGNORECASE)
# Аудит M3310-R8-03: SQL узнаётся в любом регистре (select … where — тоже SQL). Кроме того, у мест выполнения
# запроса (.execute и родня, psql через subprocess с текстом на входе) текст обязан быть постоянным — не «похожим
# на SQL», а известным целиком: неизвестная форма — находка.
EXEC_METHODS = {'execute', 'executemany', 'executescript', 'mogrify', 'copy_expert', 'callproc'}
CODE_BUILTINS = {'eval', 'exec', 'compile', '__import__'}
# Запуск программ из Python (аудит M3310-R9-04): только subprocess.run/Popen/call/check_call/check_output по имени
# модуля, без shell; программа — постоянное имя, не оболочка и не исполнитель кода. Остальные пути запуска — находка.
PY_RUN = {'run', 'Popen', 'call', 'check_call', 'check_output'}
PY_SUBPROCESS_OK = PY_RUN | {'TimeoutExpired', 'CalledProcessError', 'SubprocessError', 'PIPE', 'DEVNULL', 'STDOUT',
                             'CompletedProcess'}
PY_OS_RUN = re.compile(r'^(system|popen|exec\w*|spawn\w*|posix_spawn\w*|startfile)$')
PY_RUNNERS = re.compile(r'^(sh|bash|dash|zsh|ash|ksh|mksh|csh|tcsh|fish|busybox|toybox|python[0-9.]*|pypy[0-9.]*'
                        r'|perl[0-9.]*|ruby|php|lua[0-9.]*|tclsh|wish|expect|awk|gawk|mawk|nawk|node|nodejs|deno|bun'
                        r'|osascript|pwsh|powershell|sqlite3|R|Rscript|julia|guile|racket|scheme)$')
# Программы, которые запускают другую программу из своих аргументов: у них все аргументы — постоянные слова.
PY_WRAPPERS = {'sudo', 'doas', 'env', 'exec', 'timeout', 'nohup', 'setsid', 'nice', 'runuser', 'su', 'setpriv',
               'stdbuf', 'ionice', 'chroot', 'unshare', 'nsenter', 'systemd-run', 'docker', 'podman', 'ssh', 'xargs',
               'find', 'flock', 'watch', 'strace', 'gdb', 'script', 'busybox'}
PSQL_DANGER = {'-c', '--command', '-f', '--file'}
# Модули, через которые Python запускает программы или код (аудит M3310-R10-07): их импорт — находка PY_RUN; файл,
# где она разрешена, обязан быть закреплён суммой (PIN в файле разрешений).
PY_RUN_MODULES = {'subprocess', 'pty', 'importlib', 'builtins', 'runpy', 'ctypes', 'code', 'codeop', 'multiprocessing',
                  'pickle', 'marshal', 'shelve', 'imp', 'zipimport', 'cffi', '_posixsubprocess', 'posix', 'nt'}
PY_LOAD_ATTRS = {'import_module', 'exec_module', 'load_module', 'run_path', 'run_module', 'spec_from_file_location'}
# Рефлексия (аудит M3310-R11-01, -02): специальные атрибуты (__dict__, __globals__, __getattribute__ …), таблица
# загруженных модулей и кадры стека дают метод базы или запуска по строке-ключу, мимо проверки вызовов. Разрешены
# только безвредные имена; остальное — находка PY_RUN.
PY_SAFE_DUNDER = {'__name__', '__qualname__', '__doc__', '__module__', '__file__', '__main__', '__init__'}
PY_REFLECT_ATTRS = {'modules', 'f_globals', 'f_locals', 'f_builtins', 'f_back', 'f_code', 'gi_frame', 'cr_frame',
                    'ag_frame', 'tb_frame', '_getframe', 'attrgetter', 'methodcaller', 'get_referrers', 'get_objects'}
PY_GETATTR_OK = re.compile(r'^[A-Z][A-Z0-9_]*$')  # getattr(модуль, 'ИМЯ_ПОСТОЯННОЙ', запасное) — только постоянные
PY_CODE_NAMES = {'__builtins__', 'globals', 'vars', 'locals', '__loader__', '__spec__'}
# Встроенные функции рефлексии и кода — только прямым вызовом; имя как значение (pick = getattr; fn = eval) прячет
# вызов под другим именем (аудит M3310-R12-01, -02). attrgetter/methodcaller — в любом виде.
PY_CALL_ONLY = {'getattr', 'setattr', 'delattr'} | CODE_BUILTINS
PY_NEVER_NAMES = {'attrgetter', 'methodcaller', 'addsitedir'}
# Пути поиска модулей: правка sys.path и др. подключает код мимо проверки, например из архива (аудит M3310-R12-03).
PY_IMPORT_PATH_ATTRS = {'meta_path', 'path_hooks', 'path_importer_cache', 'addsitedir'}
MAX_TEXT = 20000
STR_METHODS = ('format', 'format_map', 'join', 'replace', 'strip', 'lstrip', 'rstrip', 'lower', 'upper',
               'casefold', 'encode', 'decode', 'removeprefix', 'removesuffix', '__add__', '__mod__')


def sqlish(s):
    return isinstance(s, str) and SQL.search(s) is not None


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + '.' + node.attr if base else None
    return None


def py_findings(path, text):
    try:
        tree = ast.parse(text, path)
    except SyntaxError as e:
        return [(e.lineno or 0, f'syntax error: {e.msg}', '')]
    out = []
    lines = text.splitlines()
    env = {}  # имя (или a.b) → сложенный текст всех кусков, когда-либо присвоенных в этом файле
    funcs = {}  # имя функции этого файла → сложенный текст всего, что она возвращает

    def fold(node):
        """Текст всех строковых кусков выражения по порядку; имя — его известный текст."""
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else ''
        if isinstance(node, (ast.Name, ast.Attribute)):
            d = dotted(node)
            if d in env:
                return env[d]
            return fold(node.value) if isinstance(node, ast.Attribute) else ''
        if isinstance(node, ast.JoinedStr):
            return ''.join(fold(v) for v in node.values)
        if isinstance(node, ast.FormattedValue):
            return fold(node.value)
        if isinstance(node, ast.BinOp):
            return fold(node.left) + fold(node.right)
        if isinstance(node, ast.Call):
            # Текст несут строковые методы, str() и функции этого файла, которые возвращают текст.
            if isinstance(node.func, ast.Attribute) and node.func.attr in STR_METHODS:
                return ''.join(fold(a) for a in [node.func.value] + list(node.args))
            if isinstance(node.func, ast.Name) and node.func.id == 'str':
                return ''.join(fold(a) for a in node.args)
            fname = node.func.id if isinstance(node.func, ast.Name) else \
                node.func.attr if isinstance(node.func, ast.Attribute) else None
            return funcs.get(fname, '')
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return ''.join(fold(e) for e in node.elts)
        if isinstance(node, ast.IfExp):
            return fold(node.body) + '\n' + fold(node.orelse)
        if isinstance(node, (ast.Subscript, ast.Starred)):
            return fold(node.value)
        return ''

    def sqlv(node):
        return sqlish(fold(node))

    # Неподвижная точка: присваивания и return читаются, пока известные тексты имён и функций меняются.
    assigns = []
    returns = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assigns += [(t, node.value) for t in node.targets]
            if isinstance(node.value, ast.Lambda):
                returns += [(t.id, node.value.body) for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None:
            assigns.append((node.target, node.value))
        elif isinstance(node, (ast.For, ast.comprehension)):
            assigns.append((node.target, node.iter))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            returns += [(node.name, r.value) for r in ast.walk(node) if isinstance(r, ast.Return) and r.value]
    for _ in range(20):
        changed = False
        for target, value in assigns:
            v = fold(value)
            if not v:
                continue
            for t in (target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]):
                d = dotted(t)
                if d is None:
                    continue
                old = env.get(d, '')
                if v not in old.split('\n'):
                    env[d] = (old + '\n' + v if old else v)[:MAX_TEXT]
                    changed = changed or env[d] != old
        for name, value in returns:
            v = fold(value)
            old = funcs.get(name, '')
            if v and v not in old.split('\n'):
                funcs[name] = (old + '\n' + v if old else v)[:MAX_TEXT]
                changed = changed or funcs[name] != old
        if not changed:
            break

    def listy(node):
        return isinstance(node, (ast.List, ast.Tuple, ast.ListComp, ast.Set, ast.Dict))

    for node in ast.walk(tree):
        bad = None
        if isinstance(node, ast.JoinedStr) and any(isinstance(v, ast.FormattedValue) for v in node.values) \
                and sqlv(node):
            bad = 'f-string with SQL text'
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)) \
                and not (listy(node.left) or listy(node.right)) and sqlv(node):
            bad = 'SQL text joined with + or %'
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, (ast.Add, ast.Mod)) \
                and not listy(node.value) and (sqlv(node.value) or sqlish(env.get(dotted(node.target), ''))):
            bad = 'SQL text appended with +='
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ('format', 'join', 'replace', 'format_map', '__add__', '__mod__'):
            if sqlv(node.func.value) or any(sqlv(a) for a in node.args):
                bad = f'SQL text built with .{node.func.attr}()'
        if bad:
            ln = getattr(node, 'lineno', 0)
            item = (ln, bad, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
            if item not in out:  # «a + b + c» — два узла сложения на одной строке, находка одна
                out.append(item)
    for ln, bad in py_exec_findings(tree):
        item = (ln, bad, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
        if item not in out:
            out.append(item)
    return out


def py_exec_findings(tree):
    """Места выполнения запроса (аудит M3310-R8-03): текст — постоянный. Постоянно: строка, сумма строк, f-строка без
    подстановок, имя, которому в файле присваивают только постоянное, параметр своей функции, которую вызывают только
    напрямую и всегда с постоянным текстом на этом месте. Остальное — находка."""
    out = []
    parents = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n

    def enclosing(n):
        while n in parents:
            n = parents[n]
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return n
        return None

    # (функция или None для модуля, имя) → значения всех присваиваний в этой области (None — присваивание, которое
    # не прочитать: цикл, +=, распаковка, with)
    values = {}

    def put(n, name, v):
        values.setdefault((enclosing(n), name), []).append(v)

    def var_insert(tg, v):
        # args[1:1] = ['-v', f'{k}={v}']: вставка после программы; вставляют постоянные ключи (не -c/-f) и значения
        # только после -v (переменная psql). Такое присваивание программу и запрос не меняет.
        if not (isinstance(tg, ast.Subscript) and isinstance(tg.value, ast.Name) and isinstance(tg.slice, ast.Slice)):
            return False
        lo = tg.slice.lower
        if not (isinstance(lo, ast.Constant) and isinstance(lo.value, int) and lo.value >= 1 and tg.slice.step is None
                and isinstance(tg.slice.upper, ast.Constant) and tg.slice.upper.value == lo.value):
            return False
        if not isinstance(v, ast.List):
            return False
        prev = None
        for x in v.elts:
            c = x.value if isinstance(x, ast.Constant) and isinstance(x.value, str) else None
            if prev != '-v' and (c is None or c in PSQL_DANGER):
                return False
            prev = c
        return True

    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    put(n, tg.id, n.value)
                elif len(n.targets) == 1 and var_insert(tg, n.value):
                    pass
                else:
                    for e in ast.walk(tg):
                        if isinstance(e, ast.Name):
                            put(n, e.id, None)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)) and isinstance(n.target, ast.Name):
            put(n, n.target.id, n.value if isinstance(n, ast.AnnAssign) else None)
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            for e in ast.walk(n.target):
                if isinstance(e, ast.Name):
                    put(n, e.id, None)
        elif isinstance(n, ast.withitem) and n.optional_vars is not None:
            for e in ast.walk(n.optional_vars):
                if isinstance(e, ast.Name):
                    put(n, e.id, None)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            for name in n.names:
                put(n, name, None)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                and n.func.attr in ('append', 'extend', 'insert', 'pop', 'remove', 'clear', 'reverse', 'sort',
                                    '__setitem__', '__iadd__'):
            put(n, n.func.value.id, None)  # список меняют методом — его состав не прочитать
        elif isinstance(n, ast.Delete):
            for tg in n.targets:
                for e in ast.walk(tg):
                    if isinstance(e, ast.Name):
                        put(n, e.id, None)

    def fixed(e, at, depth=0, seen=None):
        seen = seen or set()
        if e is None or depth > 6:
            return False
        if isinstance(e, ast.Constant):
            return isinstance(e.value, str)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
            return fixed(e.left, at, depth, seen) and fixed(e.right, at, depth, seen)
        if isinstance(e, ast.JoinedStr):
            return all(isinstance(v, ast.Constant) for v in e.values)
        if isinstance(e, ast.Name):
            f = enclosing(at)
            if isinstance(f, ast.Lambda):
                return False
            if f is not None:
                a = f.args
                pos = [x.arg for x in a.posonlyargs + a.args]
                if e.id in pos + [x.arg for x in a.kwonlyargs]:
                    if (f, e.id) in values:
                        return False  # параметр, которому в функции присваивают ещё что-то
                    if (f, e.id) in seen:
                        return False  # цикл (функция передаёт параметр сама себе) — постоянный текст не доказан
                    return param_fixed(f, e.id, pos.index(e.id) if e.id in pos else None, depth, seen | {(f, e.id)})
                if (f, e.id) in values:
                    vs = values[(f, e.id)]
                    return all(v is not None and fixed(v, v, depth + 1, seen) for v in vs)
                vs = lookup(e)
                return bool(vs) and all(v is not None and fixed(v, v, depth + 1, seen) for v in vs)
            vs = values.get((None, e.id))
            return bool(vs) and all(v is not None and fixed(v, v, depth + 1, seen) for v in vs)
        return False

    def param_fixed(f, name, index, depth, seen):
        calls = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id == f.name and isinstance(n.ctx, ast.Load):
                c = parents.get(n)
                if not (isinstance(c, ast.Call) and c.func is n):
                    return False  # функция передаётся дальше — вызовы не прочитать
                calls.append(c)
            elif isinstance(n, ast.Attribute) and n.attr == f.name:
                return False
        if sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == f.name) != 1:
            return False
        if not calls:
            return False  # функцию никто в файле не вызывает — её могут вызвать извне с любым текстом
        for c in calls:
            if any(isinstance(a, ast.Starred) for a in c.args) or any(k.arg is None for k in c.keywords):
                return False
            arg = next((k.value for k in c.keywords if k.arg == name), None)
            if arg is None and index is not None and index < len(c.args):
                arg = c.args[index]
            if arg is None or not fixed(arg, c, depth + 1, seen):
                return False
        return True

    def params(f):
        a = f.args
        names = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
        names += [x.arg for x in (a.vararg, a.kwarg) if x is not None]
        return names

    def lookup(e):
        """Значения имени по областям изнутри наружу; параметр или лямбда на пути — None (значение неизвестно)."""
        f = enclosing(e)
        while f is not None:
            if isinstance(f, ast.Lambda) or e.id in params(f):
                return None
            if (f, e.id) in values:
                return values[(f, e.id)]
            f = enclosing(f)
        return values.get((None, e.id))

    def strs(e, depth=0):
        """Все возможные постоянные строки выражения или None, если значение не прочитать."""
        if depth > 6 or e is None:
            return None
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            return {e.value}
        if isinstance(e, ast.Name):
            vs = lookup(e)
            if not vs or any(v is None for v in vs):
                return None
            out = set()
            for v in vs:
                s = strs(v, depth + 1)
                if s is None:
                    return None
                out |= s
            return out
        return None

    def argv_lists(e, depth=0):
        """Списки-литералы, которые могут прийти на место списка программы, или None, если происхождение не прочитать
        (собран сложением, изменён методом, пришёл параметром)."""
        if depth > 6 or e is None:
            return None
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in ('list', 'tuple') \
                and len(e.args) == 1 and not e.keywords:
            return argv_lists(e.args[0], depth + 1)
        if isinstance(e, (ast.List, ast.Tuple)):
            return [e]
        if isinstance(e, ast.Name):
            vs = lookup(e)
            if not vs or any(v is None for v in vs):
                return None
            out = []
            for v in vs:
                ls = argv_lists(v, depth + 1)
                if ls is None:
                    return None
                out += ls
            return out
        return None

    def check_run(n, ln):
        for k in n.keywords:
            if k.arg == 'shell' and not (isinstance(k.value, ast.Constant) and k.value.value is False):
                out.append((ln, 'RUN: subprocess started through a shell'))
            if k.arg == 'executable':
                out.append((ln, 'RUN: subprocess with executable= (the real program differs from the list)'))
            if k.arg is None:
                out.append((ln, 'RUN: subprocess with **keywords'))
        if any(isinstance(a, ast.Starred) for a in n.args):
            out.append((ln, 'RUN: subprocess call with *arguments'))
            return
        argv = n.args[0] if n.args else next((k.value for k in n.keywords if k.arg == 'args'), None)
        ls = argv_lists(argv)
        if not ls:
            out.append((ln, 'RUN: subprocess: argument list is not a list literal of fixed origin'))
            return
        for lst in ls:
            el = lst.elts
            prog = strs(el[0]) if el and not isinstance(el[0], ast.Starred) else None
            if not prog:
                out.append((ln, 'RUN: subprocess: program is not a fixed name'))
                continue
            names = {os.path.basename(s) for s in prog}
            if any(PY_RUNNERS.match(s) for s in names):
                out.append((ln, 'RUN: subprocess: program is a shell or a code interpreter'))
            words = []
            for x in el[1:]:
                s = strs(x) if not isinstance(x, ast.Starred) else None
                if s is None:
                    out.append((ln, 'RUN: subprocess: argument is not a fixed string'))
                words.append(s)
                for w in s or ():
                    if PY_RUNNERS.match(os.path.basename(w)) or os.path.basename(w) == 'psql' and 'psql' not in names:
                        out.append((ln, f'RUN: subprocess: {w} inside the argument list'))
            if 'psql' in names:
                for j, s in enumerate(words):
                    if s and s & PSQL_DANGER:
                        nx = words[j + 1] if j + 1 < len(words) else None
                        if not (s & {'-f', '--file'} and nx == {'-'}) and not (s & {'-c', '--command'} and nx):
                            out.append((ln, 'RUN: psql: -c or -f with text or a file that is not fixed'))
                for k in n.keywords:
                    if k.arg == 'input' and not fixed(k.value, n):
                        out.append((ln, 'RUN: psql gets text on input that is not fixed'))

    def psql_list(e):
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == 'list' and e.args:
            e = e.args[0]
        if isinstance(e, ast.Name):
            vs = lookup(e) or []
            return any(v is not None and psql_list(v) for v in vs)
        if isinstance(e, (ast.List, ast.Tuple)):
            return any(isinstance(x, ast.Constant) and isinstance(x.value, str) and os.path.basename(x.value) == 'psql'
                       for x in e.elts)
        return False

    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        ln = getattr(n, 'lineno', 0)
        fn = n.func
        if isinstance(fn, ast.Name) and fn.id in CODE_BUILTINS:
            out.append((ln, f'RUN: {fn.id}() runs code from a string'))
        if isinstance(fn, ast.Name) and fn.id in ('getattr', 'setattr', 'delattr') and len(n.args) >= 2:
            k = n.args[1]
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)) or k.value in EXEC_METHODS:
                out.append((ln, f'{fn.id}() with a name that is not fixed or is a query method'))
        if isinstance(fn, ast.Attribute) and fn.attr in EXEC_METHODS:
            if not n.args or not fixed(n.args[0], n):
                out.append((ln, f'.{fn.attr}() gets query text that is not fixed'))
        if dotted(fn) in {'subprocess.' + x for x in PY_RUN}:
            check_run(n, ln)
    # Метод запроса или запуска, взятый как значение (send = cur.execute; run = subprocess.run): вызов под другим
    # именем проверка не видит (аудит M3310-R9-02). Модули запуска — только по своему имени, без «as» и «from».
    for n in ast.walk(tree):
        ln = getattr(n, 'lineno', 0)
        p = parents.get(n)
        is_callee = isinstance(p, ast.Call) and p.func is n
        if isinstance(n, ast.Attribute) and n.attr in EXEC_METHODS and not is_callee:
            out.append((ln, f'query method .{n.attr} used other than by a direct call'))
        d = dotted(n) if isinstance(n, ast.Attribute) else None
        if d and d.startswith('subprocess.') and d.count('.') == 1:
            if n.attr not in PY_SUBPROCESS_OK or n.attr in PY_RUN and not is_callee:
                out.append((ln, f'RUN: {d} used other than as a direct run call'))
        if d and (d.count('.') == 1 and d.split('.')[0] == 'os' and PY_OS_RUN.match(n.attr)
                  or d in ('pty.spawn', 'asyncio.create_subprocess_shell', 'asyncio.create_subprocess_exec')):
            out.append((ln, f'RUN: {d} starts a program'))
        if isinstance(n, ast.Name) and n.id == 'subprocess' and not (isinstance(p, ast.Attribute) and p.value is n):
            out.append((ln, 'RUN: subprocess module used other than as subprocess.name'))
        # код из строки через другой объект (builtins.eval, getattr(x, 'exec')) и словари областей (globals()['eval'])
        if isinstance(n, ast.Attribute) and n.attr in CODE_BUILTINS and                 not (n.attr == 'compile' and isinstance(n.value, ast.Name) and n.value.id == 're'):
            out.append((ln, f'RUN: .{n.attr} runs code from a string'))
        if isinstance(n, ast.Attribute) and n.attr in PY_LOAD_ATTRS:
            out.append((ln, f'RUN: .{n.attr} loads or runs a module by name'))
        if isinstance(n, ast.Name) and n.id in PY_CALL_ONLY and not is_callee:
            out.append((ln, f'RUN: {n.id} used other than by a direct call'))
        if isinstance(n, ast.Name) and n.id in PY_NEVER_NAMES:
            out.append((ln, f'RUN: {n.id} calls a method or loads code by name'))
        if isinstance(n, ast.Attribute) and (n.attr in PY_IMPORT_PATH_ATTRS or
                                             n.attr == 'path' and isinstance(n.value, ast.Name) and n.value.id == 'sys'):
            out.append((ln, f'RUN: .{n.attr} changes where modules are loaded from'))
        if isinstance(n, ast.Name) and n.id in PY_CODE_NAMES:
            out.append((ln, f'RUN: {n.id} gives access to code and names of the program'))
        elif isinstance(n, ast.Name) and n.id.startswith('__') and n.id not in PY_SAFE_DUNDER:
            out.append((ln, f'RUN: special name {n.id} (reflection)'))
        if isinstance(n, ast.Attribute) and n.attr.startswith('__') and n.attr not in PY_SAFE_DUNDER:
            out.append((ln, f'RUN: special attribute .{n.attr} (reflection)'))
        if isinstance(n, ast.Attribute) and n.attr in PY_REFLECT_ATTRS:
            out.append((ln, f'RUN: .{n.attr} gives access to modules or stack frames'))
        if isinstance(n, ast.Attribute) and PY_OS_RUN.match(n.attr) and n.attr not in EXEC_METHODS and                 not (d and d.count('.') == 1 and d.split('.')[0] == 'os'):
            out.append((ln, f'RUN: .{n.attr} starts a program (any object)'))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('getattr', 'setattr', 'delattr') \
                and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)                 and not PY_GETATTR_OK.match(n.args[1].value):
            out.append((ln, f'RUN: {n.func.id}() with name {n.args[1].value}'))
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name in ('subprocess', 'pty', 'os', 'asyncio', 'importlib', 'sys', 'operator', 'site') and a.asname:
                    out.append((ln, f'RUN: import {a.name} as {a.asname}'))
                if a.name.split('.')[0] in PY_RUN_MODULES:
                    out.append((ln, f'RUN: module {a.name} starts programs or code (file must be pinned)'))
        if isinstance(n, ast.ImportFrom):
            mod = n.module or ''
            if mod in ('subprocess', 'pty', 'asyncio.subprocess') or mod.startswith('_posixsubprocess') or \
                    mod == 'os' and any(a.name == '*' or PY_OS_RUN.match(a.name) for a in n.names) or \
                    mod == 'asyncio' and any(a.name == '*' or a.name.startswith('create_subprocess') for a in n.names):
                out.append((ln, f'RUN: from {mod} import … (run calls must use the module name)'))
            elif mod in ('sys', 'operator', 'site') and any(a.name == '*' or a.name in PY_IMPORT_PATH_ATTRS | PY_NEVER_NAMES
                                                            | {'path', 'modules'} for a in n.names):
                out.append((ln, f'RUN: from {mod} import … (module paths or call by name)'))
            elif mod.split('.')[0] in PY_RUN_MODULES:
                out.append((ln, f'RUN: module {mod} starts programs or code (file must be pinned)'))
    return out


# --- Оболочка (аудит M3310-R7-03): *.sh и файлы с первой строкой «#!…sh». Правила разрешающие, как у JavaScript:
#   слово, где есть подстановка ($x, $(…), `…`), — не постоянный текст. Запрос к базе — только psql с постоянным
#   текстом: -c с постоянным словом, вход из heredoc в кавычках (<<'X'), первый аргумент своей функции-обёртки psql —
#   постоянный; значения — только переменными psql (-v имя=значение, в тексте :'имя'). Находка:
#   SH_SQL_TEXT — слово или heredoc с подстановкой, похожие на запрос; SH_DYN_C — после -c / --command не постоянный
#   текст (у любой программы: psql, sh, bash, su …); SH_CMD — имя программы не постоянное ("$@", $p, $(…));
#   SH_EVAL — eval, source, «.», xargs; SH_PSQL — psql читает запрос из трубы, файла (-f, <), here-строки, heredoc с
#   подстановкой или получает параметр из переменной на месте ключа; SH_SQL_ARG — в обёртку psql первым аргументом
#   передан не постоянный текст; SH_PSQL_VAR — в тексте для psql переменная без кавычек (:имя) или команда psql
#   с обратной косой (\gexec, \i, \! …); SH_INLINE — код другого языка из переменной или трубы (python -c "$x",
#   node -e, perl -e …); код python из постоянного текста проверяется правилами Python; SH_PARSE — не разобрано.
SH_SQL = re.compile(r'\b(SELECT|INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|GRANT|REVOKE|TRUNCATE|COPY|EXECUTE'
                    r'|CALL|VALUES|FROM|WHERE|SET)\b')
SH_RAW_VAR = re.compile(r"(?<![:\w]):(?!:)[A-Za-z_]\w*")
SH_META = re.compile(r'(^|[\s;])\\[A-Za-z!]')
SH_KEYS = {'if', 'then', 'else', 'elif', 'fi', 'while', 'until', 'do', 'done', '!', 'time', 'esac'}
SH_WRAP = {'sudo', 'env', 'exec', 'timeout', 'nohup', 'setsid', 'nice', 'command', 'builtin', 'runuser',
           'setpriv', 'stdbuf', 'ionice', 'chroot', 'unshare', 'nsenter', 'systemd-run', 'doas'}
SH_SHELLS = {'sh', 'bash', 'dash', 'ash', 'zsh', 'ksh', 'busybox'}
SH_CODE = {'node', 'nodejs', 'perl', 'ruby', 'php', 'deno', 'bun', 'lua', 'tclsh', 'osascript'}
SH_OPS = ('<<<', '<<-', '&&', '||', ';;', '>>', '<<', '<&', '>&', '&>', '>|', '<>', '|&', '|', '&', ';',
          '<', '>', '(', ')', '\n')
SH_ASSIGN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=')
X = '\x00'


class ShError(Exception):
    pass


class ShLex:
    """Разбор оболочки: простые команды (слова, трубы, перенаправления, heredoc) с функцией, в которой стоят."""

    def __init__(self, text, line=1, fn=None):
        self.t, self.i, self.line = text, 0, line
        self.cmds = []
        self.fdefs = {}
        self.fn = [(fn, -1)] if fn else []
        self.depth = 0

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else ''

    def adv(self, n=1):
        for _ in range(n):
            if self.i < len(self.t) and self.t[self.i] == '\n':
                self.line += 1
            self.i += 1

    def blanks(self):
        while True:
            c = self.peek()
            if c in (' ', '\t'):
                self.adv()
            elif c == '\\' and self.peek(1) == '\n':
                self.adv(2)
            else:
                return

    def new_cmd(self):
        return {'words': [], 'line': self.line, 'pin': False, 'pout': False, 'redir': [], 'here': [], 'hstr': [],
                'fn': self.fn[-1][0] if self.fn else None}

    def word(self):
        """Слово до разделителя: {'val' (подстановка = X), 'lit', 'quoted', 'line', 'raw'}."""
        start, line, val, lit, quoted = self.i, self.line, [], True, False
        while True:
            c = self.peek()
            if c == '' or c in ' \t\n;&|()<>':
                if c in '<>' and self.peek(1) == '(' and not val:
                    self.adv(2)
                    self.seq(')')
                    val.append(X)
                    lit = False
                    continue
                break
            if c == '\\':
                if self.peek(1) == '\n':
                    self.adv(2)
                    continue
                quoted = True
                val.append(self.peek(1))
                self.adv(2)
            elif c == "'":
                quoted = True
                self.adv()
                j = self.t.find("'", self.i)
                if j < 0:
                    raise ShError('unterminated single quote')
                val.append(self.t[self.i:j])
                self.adv(j - self.i + 1)
            elif c == '"':
                quoted = True
                self.adv()
                v, ok = self.dq('"')
                val.append(v)
                lit = lit and ok
            elif c == '$' and self.peek(1) == "'":
                quoted = True
                self.adv(2)
                buf = []
                while self.peek() not in ("'", ''):
                    if self.peek() == '\\':
                        buf.append(self.peek(1))
                        self.adv(2)
                    else:
                        buf.append(self.peek())
                        self.adv()
                self.adv()
                val.append(''.join(buf))
            elif c in '$`':
                if self.expansion():
                    val.append(X)
                    lit = False
                else:
                    val.append(c)
                    self.adv()
            else:
                val.append(c)
                self.adv()
        return {'val': ''.join(val), 'lit': lit, 'quoted': quoted, 'line': line, 'raw': self.t[start:self.i]}

    def dq(self, end):
        """Текст в двойных кавычках (или тело heredoc без кавычек при end=None): (текст, постоянный ли)."""
        val, ok = [], True
        while True:
            c = self.peek()
            if c == '':
                if end is None:
                    break
                raise ShError('unterminated double quote')
            if end is not None and c == end:
                self.adv()
                break
            if c == '\\' and self.peek(1) in ('$', '`', '"', '\\', '\n'):
                if self.peek(1) != '\n':
                    val.append(self.peek(1))
                self.adv(2)
            elif c in '$`':
                if self.expansion():
                    val.append(X)
                    ok = False
                else:
                    val.append(c)
                    self.adv()
            else:
                val.append(c)
                self.adv()
        return ''.join(val), ok

    def expansion(self):
        """$…/`…` на месте: разбирает подстановку команды как команды; True, если это подстановка."""
        c, n = self.peek(), self.peek(1)
        if c == '`':
            self.adv()
            buf, line = [], self.line
            while self.peek() not in ('`', ''):
                if self.peek() == '\\' and self.peek(1) in ('`', '\\', '$'):
                    buf.append(self.peek(1))
                    self.adv(2)
                else:
                    buf.append(self.peek())
                    self.adv()
            if self.peek() != '`':
                raise ShError('unterminated backquote')
            self.adv()
            self.sub(''.join(buf), line)
            return True
        if n == '(' and self.peek(2) == '(':
            self.adv(3)
            depth = 2
            while depth:
                ch = self.peek()
                if ch == '':
                    raise ShError('unterminated arithmetic')
                if ch == '$' and self.peek(1) == '(' and self.peek(2) != '(':
                    self.adv(2)
                    self.seq(')')
                    continue
                depth += (ch == '(') - (ch == ')')
                self.adv()
            return True
        if n == '(':
            self.adv(2)
            self.seq(')')
            return True
        if n == '{':
            self.adv(2)
            depth = 1
            while depth:
                ch = self.peek()
                if ch == '':
                    raise ShError('unterminated ${')
                if ch == '$' and self.peek(1) == '(':
                    self.expansion()
                    continue
                depth += (ch == '{') - (ch == '}')
                self.adv()
            return True
        if n and (n.isalnum() or n in '_@*#?$!-'):
            self.adv(2)
            if n.isalpha() or n == '_':
                while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
                    self.adv()
            return True
        return False

    def sub(self, text, line):
        lx = ShLex(text, line, self.fn[-1][0] if self.fn else None)
        lx.seq(None)
        self.cmds.extend(lx.cmds)
        self.fdefs.update(lx.fdefs)

    def heredocs(self, pending):
        for cmd, delim, quoted, strip in pending:
            body, line = [], self.line
            while True:
                if self.i >= len(self.t):
                    raise ShError('unterminated heredoc ' + delim)
                j = self.t.find('\n', self.i)
                j = len(self.t) if j < 0 else j
                row = self.t[self.i:j]
                self.adv(j - self.i + (1 if j < len(self.t) else 0))
                if (row.lstrip('\t') if strip else row) == delim:
                    break
                body.append(row.lstrip('\t') if strip else row)
            text = '\n'.join(body)
            ok = True
            if not quoted:
                lx = ShLex(text, line, cmd['fn'])
                text, ok = lx.dq(None)
                self.cmds.extend(lx.cmds)
            cmd['here'].append({'val': text, 'lit': ok, 'quoted': quoted, 'line': line})

    def seq(self, stop):
        cur, pending, fname, case = self.new_cmd(), [], None, 0

        def done(pout=False):
            nonlocal cur
            if cur['words'] or cur['here'] or cur['redir'] or cur['hstr']:
                cur['pout'] = pout
                self.cmds.append(cur)
            pin = pout
            cur = self.new_cmd()
            cur['pin'] = pin

        while True:
            self.blanks()
            c = self.peek()
            if c == '':
                if stop:
                    raise ShError('unterminated ' + stop)
                done()
                return
            if case == 2:  # образец ветви case: до «)»
                if c == '\n' or c == ';':
                    self.adv()
                    continue
                w = self.word()
                if w['val'] == 'esac':
                    case = 0
                    continue
                if w['val'] == '' and self.peek() == '(':
                    self.adv()
                    continue
                while self.peek() not in (')', ''):
                    self.adv()
                self.adv()
                case = 0
                continue
            if c == '#' and not cur['words']:
                while self.peek() not in ('\n', ''):
                    self.adv()
                continue
            if stop and c == stop:
                self.adv()
                done()
                return
            op = next((o for o in SH_OPS if self.t.startswith(o, self.i)), None)
            if op:
                self.adv(len(op))
                if op in ('|', '|&'):
                    done(True)
                elif op in ('&&', '||', ';', '&', ';;', '\n'):
                    done()
                    if op == ';;':
                        case = 2
                    if op == '\n' and pending:
                        self.heredocs(pending)
                        pending = []
                elif op == '(':
                    self.blanks()
                    if len(cur['words']) == 1 and self.peek() == ')':
                        self.adv()
                        fname = cur['words'][0]['val']
                        cur = self.new_cmd()
                    else:
                        done()
                elif op == ')':
                    done()
                else:
                    self.blanks()
                    w = self.word()
                    if op in ('<<', '<<-'):
                        pending.append((cur, w['val'], w['quoted'], op == '<<-'))
                    elif op == '<<<':
                        cur['hstr'].append(w)
                    else:
                        cur['redir'].append((op, w))
                continue
            w = self.word()
            if w['lit'] and w['val'].isdigit() and self.peek() in ('<', '>'):
                continue
            if not cur['words'] and w['lit'] and not w['quoted']:
                v = w['val']
                if v == '{':
                    self.depth += 1
                    if fname:
                        self.fn.append((fname, self.depth))
                        self.fdefs[fname] = w['line']
                        fname = None
                        cur['fn'] = self.fn[-1][0]
                    continue
                if v == '}':
                    if self.fn and self.fn[-1][1] == self.depth:
                        self.fn.pop()
                    self.depth -= 1
                    cur['fn'] = self.fn[-1][0] if self.fn else None
                    continue
                if v in SH_KEYS:
                    continue
                if v == 'function':
                    self.blanks()
                    fname = self.word()['val']
                    continue
            if not cur['words']:
                cur['line'] = w['line']
            cur['words'].append(w)
            if cur['words'][0]['val'] == 'case' and w['val'] == 'in' and len(cur['words']) > 1:
                done()
                case = 2
            if cur['words'] and cur['words'][0]['val'] in ('for', 'select') and w['val'] == 'do':
                cur['words'].pop()
                done()


def sh_prog(words, k):
    """Пропускает присваивания и обёртки (sudo, env, timeout …): (индекс программы или None, причина отказа)."""
    n = len(words)
    while k < n and SH_ASSIGN.match(words[k]['val']):
        k += 1
    while k < n:
        w = words[k]
        if not w['lit']:
            return k, 'program name is not fixed text'
        p = os.path.basename(w['val'])
        if p not in SH_WRAP:
            return k, None
        k += 1
        if p == 'timeout':
            while k < n and words[k]['lit'] and words[k]['val'].startswith('-'):
                k += 1 + (words[k]['val'] in ('-s', '-k', '--signal', '--kill-after'))
            k += 1
            continue
        while k < n and ((words[k]['lit'] and words[k]['val'].startswith('-')) or SH_ASSIGN.match(words[k]['val'])):
            v = words[k]['val']
            k += 1
            if v == '--':
                break
            if (p in ('sudo', 'doas', 'runuser') and v in ('-u', '-g', '-C', '-D', '-h', '-p', '-r', '-t', '-U', '-T'))\
                    or (p == 'env' and v in ('-u', '-C', '-S')) or (p == 'exec' and v == '-a') \
                    or (p in ('nice', 'ionice') and v in ('-n', '-c')) or (p == 'stdbuf' and v in ('-i', '-o', '-e')):
                k += 1
        if p == 'chroot':
            k += 1
    return None, None


def sh_findings(path, text, line=1, depth=0):
    out = []

    def add(ln, why, code):
        out.append((ln, why, code))

    try:
        lx = ShLex(text, line)
        lx.seq(None)
    except Exception as e:  # неразобранное — находка, не пропуск
        return [(line, f'shell text not parsed: {e}', 'SH_PARSE')]
    cmds = lx.cmds
    # Постоянные переменные: присвоены один раз постоянным текстом (X='…' или local X='…') и нигде больше не
    # меняются (read, for, printf -v, ${X:=}, (( )), let, unset, повторное присваивание). "$X" такой переменной —
    # постоянный текст (так код python в PY_TCP='…' проверяется правилами Python).
    assigned = {}
    for c in cmds:
        ws = c['words']
        i0 = 1 if ws and ws[0]['lit'] and ws[0]['val'] in ('local', 'export', 'readonly', 'declare', 'typeset') else 0
        for w in ws[i0:] if i0 else ws:
            m = SH_ASSIGN.match(w['val'])
            if not m:
                if i0:
                    continue
                break
            name = w['val'][:m.end()].rstrip('=+')
            assigned.setdefault(name, []).append(w)
    consts = {}
    for name, ws_ in assigned.items():
        w = ws_[0]
        if len(ws_) != 1 or not w['lit'] or '[' in name:
            continue
        n = re.escape(name)
        if len(re.findall(r'(?<![\w$])' + n + r'\+?=', text)) != 1 or re.search(
                r'\b(read|mapfile|readarray|getopts|unset|let)\b[^\n;|&]*\b' + n + r'\b|\bfor\s+' + n + r'\b'
                r'|printf\s+-v\s*' + n + r'\b|\$\{' + n + r':?[=?]|\(\([^)]*\b' + n + r'\b', text):
            continue
        consts[name] = w['val'][len(name) + 1:]
    one_var = re.compile(r'^"?\$(\{)?([A-Za-z_]\w*)(?(1)\})"?$')
    for c in cmds:
        for w in c['words'] + c['hstr'] + [r[1] for r in c['redir']]:
            m = one_var.match(w['raw'])
            if m and m.group(2) in consts:
                w['lit'], w['val'] = True, consts[m.group(2)]
    # Обёртки psql: функции, где psql читает трубу или берёт аргумент из переменной (как pgv); их вызовы
    # проверяются: первый аргумент — постоянный текст. Обёртка над обёрткой не нужна: внутри неё вызов pgv "$1" —
    # уже находка. Функции-запускатели (wait_for, probe): выполняют "$@" после shift — их вызов проверяется как
    # команда из оставшихся слов.
    psqlf, runners = set(), {}
    for c in cmds:
        k, _ = sh_prog(c['words'], 0)
        if not c['fn'] or k is None:
            continue
        w = c['words'][k]
        if os.path.basename(w['val']) == 'psql' and (c['pin'] or not all(x['lit'] for x in c['words'][k + 1:])):
            psqlf.add(c['fn'])
        if w['raw'] == '"$@"':
            runners[c['fn']] = 0
    for c in cmds:
        ws = c['words']
        if c['fn'] in runners and ws and ws[0]['val'] == 'shift':
            runners[c['fn']] += int(ws[1]['val']) if len(ws) > 1 and ws[1]['val'].isdigit() else 1

    def sql_text(s, ln, stdin):
        if stdin and SH_RAW_VAR.search(s):
            add(ln, 'psql variable without quotes (:name) in SQL text', 'SH_PSQL_VAR')
        if SH_META.search(s):
            add(ln, 'psql backslash command in SQL text', 'SH_PSQL_VAR')

    def stdin_ok(c, what, code):
        if c['pin']:
            add(c['line'], f'{what} reads text from a pipe', code)
        for op, w in c['redir']:
            if op in ('<', '<>'):
                add(w['line'], f'{what} reads text from a file', code)
        for w in c['hstr']:
            add(w['line'], f'{what} reads text from a here-string', code)
        bodies = []
        for h in c['here']:
            if not h['lit']:
                add(h['line'], f'{what} reads a heredoc with substitutions', code)
            else:
                bodies.append(h)
        return bodies

    def one(c, ws):
        for w in ws + c['hstr'] + [h for h in c['here']] + [r[1] for r in c['redir']]:
            if not w['lit'] and SH_SQL.search(w['val'].replace(X, ' ')):
                add(w['line'], 'SQL-like text built with shell substitutions', 'SH_SQL_TEXT')
        for j, w in enumerate(ws):
            v = w['val']
            if w['lit'] and v in ('-c', '--command') and j + 1 < len(ws) and not ws[j + 1]['lit']:
                add(ws[j + 1]['line'], f'text after {v} is not fixed', 'SH_DYN_C')
            if v.startswith('--command=') and not w['lit']:
                add(w['line'], 'text after --command= is not fixed', 'SH_DYN_C')
        if ws and ws[0]['lit'] and ws[0]['val'] in ('for', 'select', 'case', 'local', 'export', 'declare',
                                                    'readonly', 'typeset'):
            return
        k, why = sh_prog(ws, 0)
        if k is None:
            return
        if why and ws[k]['raw'] == '"$@"' and c['fn'] in runners:
            return
        if why:
            add(ws[k]['line'], why, 'SH_CMD')
            return
        p = os.path.basename(ws[k]['val'])
        rest = ws[k + 1:]
        if ws[k]['val'] in runners:
            one(c, ws[k + 1 + runners[ws[k]['val']]:])
            return
        if ws[k]['val'] in lx.fdefs and ws[k]['val'] not in psqlf:
            return  # своя функция: её тело проверено как команды
        if p in ('eval', 'source', '.', 'xargs', 'parallel'):
            add(ws[k]['line'], f'{p} runs text as commands', 'SH_EVAL')
        elif p == 'psql':
            for h in stdin_ok(c, 'psql', 'SH_PSQL'):
                sql_text(h['val'], h['line'], True)
            j = 0
            while j < len(rest):
                w = rest[j]
                v = w['val']
                if not w['lit']:
                    if j == 0 or not (rest[j - 1]['lit'] and rest[j - 1]['val'] in ('-v', '--set', '--variable', '-d',
                                                                                  '-U', '-h', '-p', '-o', '-L')):
                        if not SH_ASSIGN.match(v) and not v.startswith('--set=') and not v.startswith('--variable='):
                            add(w['line'], 'psql argument from a variable in option position', 'SH_PSQL')
                    j += 1
                    continue
                if v in ('-f', '--file') or v.startswith('--file='):
                    add(w['line'], 'psql reads SQL from a file', 'SH_PSQL')
                elif v in ('-c', '--command') and j + 1 < len(rest):
                    if rest[j + 1]['lit']:
                        sql_text(rest[j + 1]['val'], rest[j + 1]['line'], False)
                    j += 1
                elif v.startswith('--command='):
                    sql_text(v[10:], w['line'], False)
                elif v.startswith('-') and not v.startswith('--'):
                    for q, ch in enumerate(v[1:]):
                        if ch == 'f':
                            add(w['line'], 'psql reads SQL from a file', 'SH_PSQL')
                            break
                        if ch == 'c':
                            tail = v[q + 2:]
                            if tail:
                                sql_text(tail, w['line'], False)
                            elif j + 1 < len(rest):
                                if rest[j + 1]['lit']:
                                    sql_text(rest[j + 1]['val'], rest[j + 1]['line'], False)
                                else:
                                    add(rest[j + 1]['line'], 'text after -c is not fixed', 'SH_DYN_C')
                                j += 1
                            break
                        if ch in 'dhpUvoLPTFRW' and ch != 'W':
                            if not v[q + 2:]:
                                j += 1
                            break
                j += 1
        elif ws[k]['val'] in psqlf:
            stdin_ok(c, f'psql wrapper {ws[k]["val"]}', 'SH_PSQL')
            if rest:
                if not rest[0]['lit']:
                    add(rest[0]['line'], f'psql wrapper {ws[k]["val"]} gets SQL text that is not fixed', 'SH_SQL_ARG')
                else:
                    sql_text(rest[0]['val'], rest[0]['line'], True)
        elif p in SH_SHELLS:
            opts = [w for w in rest if w['lit'] and w['val'].startswith('-')]
            if any(w['val'] == '-c' or (w['val'].startswith('-') and not w['val'].startswith('--') and 'c' in w['val'][1:])
                   for w in opts):
                at = next(j for j, w in enumerate(rest) if w['lit'] and w['val'].startswith('-') and
                          not w['val'].startswith('--') and 'c' in w['val'][1:])
                if at + 1 < len(rest) and rest[at + 1]['lit'] and depth < 4:
                    out.extend(sh_findings(path, rest[at + 1]['val'], rest[at + 1]['line'], depth + 1))
                elif at + 1 < len(rest) and not rest[at + 1]['lit']:
                    add(rest[at + 1]['line'], f'{p} -c with text that is not fixed', 'SH_DYN_C')
            else:
                files_ = [w for w in rest if not (w['lit'] and w['val'].startswith('-'))]
                if not files_ or any(w['val'] == '-s' for w in opts):
                    for h in stdin_ok(c, p, 'SH_INLINE'):
                        if depth < 4:
                            out.extend(sh_findings(path, h['val'], h['line'], depth + 1))
        elif p.startswith('python'):
            j, code_text, script = 0, None, False
            while j < len(rest):
                v = rest[j]['val']
                if rest[j]['lit'] and v in ('-c',):
                    if j + 1 < len(rest) and rest[j + 1]['lit']:
                        code_text = (rest[j + 1]['val'], rest[j + 1]['line'])
                    else:
                        add(rest[j]['line'], 'python -c with code that is not fixed', 'SH_INLINE')
                    script = True
                    break
                if rest[j]['lit'] and v in ('-W', '-X'):
                    j += 2
                    continue
                if rest[j]['lit'] and v.startswith('-') and v != '-':
                    j += 1
                    continue
                script = v != '-'
                break
            if code_text is None and not script:
                for h in stdin_ok(c, 'python', 'SH_INLINE'):
                    code_text = (h['val'], h['line'])
            if code_text:
                for ln, why, _ in py_findings(path, code_text[0]):
                    if why.startswith('RUN: '):
                        add(code_text[1] + ln - 1, why[5:], 'PY_RUN')
                    else:
                        add(code_text[1] + ln - 1, why, 'PY_SQL')
        elif p in SH_CODE:
            if any(w['lit'] and w['val'] in ('-e', '-E', '-p', '-r', '--eval', '--print', '-', '-x') or
                   w['val'].startswith(('--eval=', '--print=')) for w in rest) or not rest:
                add(ws[k]['line'], f'{p} runs inline code', 'SH_INLINE')

    for c in cmds:
        one(c, c['words'])
    return list(dict.fromkeys(out))


def js_findings(paths):
    """Находки JavaScript от sql_concat_js.cjs: {путь: [(строка, причина)]}; сбой разборщика — None (отказ)."""
    if not paths:
        return {}
    here = os.path.dirname(os.path.abspath(__file__))
    node = os.environ.get('ZAVOD_NODE') or 'node'
    try:
        run = subprocess.run([node, '--expose-internals', os.path.join(here, 'sql_concat_js.cjs')] + paths,
                             capture_output=True, encoding='utf-8', timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f'SQL_CONCAT_JS_ERROR {e}')
        return None
    rows = run.stdout.splitlines()
    try:
        head = json.loads(rows[0]) if rows else {}
        found = [json.loads(r) for r in rows[1:]]
    except ValueError:
        head, found = {}, None
    if run.returncode != 0 or 'parser' not in head or found is None:
        print(f'SQL_CONCAT_JS_ERROR exit={run.returncode} {run.stderr.strip()[:300]}')
        return None
    print(f"SQL_CONCAT_JS_PARSER={head['parser']} node {head['node']}")
    out = {}
    for f in found:
        out.setdefault(f['path'], []).append((int(f['line']), f['why'], f['code']))
    return out


def is_python(path):
    if path.endswith('.py'):
        return True
    if os.path.splitext(path)[1]:
        return False
    try:
        with open(path, 'rb') as f:
            first = f.readline(200)
    except OSError:
        return False
    return first.startswith(b'#!') and b'python3' in first


def is_shell(path):
    if path.endswith('.sh'):
        return True
    if os.path.splitext(path)[1]:
        return False
    try:
        with open(path, 'rb') as f:
            first = f.readline(200)
    except OSError:
        return False
    return first.startswith(b'#!') and re.search(rb'[/ ](ba|da|z|k)?sh(\s|$)', first) is not None and b'python' not in first


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                # __pycache__ не пропускается: скомпилированный *.pyc — непроверяемый формат (аудит M3310-R11-03)
                dirs[:] = sorted(d for d in dirs if d not in ('node_modules', '.git'))
                for n in sorted(names):
                    yield os.path.join(root, n)
        else:
            yield p


# Строка разрешения не должна касаться объекта базы: пул, клиент, вызов запроса (аудит M3310-R6-04).
ALLOW_DB = re.compile(r'\bpg\.|\b(Pool|Client|pool|client|db|rulesPool)\b|\.query\b')
ALLOW_CODE = re.compile(r'^[A-Z_]+$')
# Находки, разрешение которых требует закрепить файл суммой (PIN): запуск программ и кода.
PIN_RULES = {'CHILD', 'CHILD_IMPORT', 'PY_RUN'}
UNCHECKED_EXT = ('.ts', '.mts', '.cts', '.tsx', '.jsx', '.node', '.wasm', '.so', '.dll', '.dylib', '.pyc', '.pyo',
                 '.pyw', '.pyz', '.pth', '.cmd', '.bat', '.ps1', '.exe', '.pyd', '.zip', '.egg', '.whl', '.jar',
                 '.tar', '.gz', '.tgz', '.bz2', '.xz', '.7z')


def main(argv):
    allow_path = None
    if len(argv) >= 2 and argv[0] == '--allow':
        allow_path, argv = argv[1], argv[2:]
    if not argv:
        print('usage: sql_concat_scan.py [--allow file] path...', file=sys.stderr)
        return 2
    allow = {}
    pins = {}  # путь → [sha256, файл проверен]
    bad_allow = False
    if allow_path:
        with open(allow_path, encoding='utf-8') as f:
            for raw in f:
                if not raw.strip() or raw.startswith('#'):
                    continue
                parts = raw.rstrip('\n').split('\t', 2)
                if len(parts) != 3 or not ALLOW_CODE.match(parts[1]) or ALLOW_DB.search(parts[2]):
                    print(f'SQL_CONCAT_ALLOW_BAD {raw.strip()[:160]}')
                    bad_allow = True
                    continue
                if parts[1] == 'PIN':
                    pins[parts[0].replace('\\', '/')] = [parts[2].strip(), False]
                    continue
                allow[(parts[0].replace('\\', '/'), parts[1], parts[2].strip())] = False
    found = 0
    scanned = 0
    todo = []
    for path in files(argv):
        norm = path.replace('\\', '/')
        if norm.endswith(('.mjs', '.js', '.cjs')):
            todo.append((norm, 'js'))
        elif norm.endswith(UNCHECKED_EXT):
            # исполняемый формат, который проверка не разбирает (аудит M3310-R11-03), — отказ
            found += 1
            print(f'SQL_CONCAT {norm}:0: FORMAT: executable file format the scan does not check')
        elif is_python(path):
            todo.append((norm, 'py'))
        elif is_shell(path):
            todo.append((norm, 'sh'))
    js_found = js_findings([p for p, k in todo if k == 'js'])
    if js_found is None:
        print('SQL_CONCAT_SCAN=FAIL')
        return 1
    for norm, kind in todo:
        with open(norm, encoding='utf-8') as f:
            text = f.read()
        scanned += 1
        lines = text.splitlines()
        if kind == 'js':
            items = [(ln, why, rule, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
                     for ln, why, rule in js_found.get(norm, [])]
        elif kind == 'sh':
            items = [(ln, why, rule, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
                     for ln, why, rule in sh_findings(norm, text)]
        else:
            items = [(ln, why[5:], 'PY_RUN', code) if why.startswith('RUN: ') else (ln, why, 'PY_SQL', code)
                     for ln, why, code in py_findings(norm, text)]
        launch = False
        for ln, why, rule, code in items:
            key = (norm, rule, code)
            if key in allow:
                allow[key] = True
                launch = launch or rule in PIN_RULES
                continue
            found += 1
            print(f'SQL_CONCAT {norm}:{ln}: {rule}: {why}: {code[:160]}')
        # Закрепление (аудит M3310-R10): файл, которому разрешено запускать программы или код, закреплён суммой SHA-256
        # всего файла. Любая правка такого файла — находка, пока сумма в файле разрешений не обновлена (это видно
        # в изменениях и проверяется аудитом). Так код, который проверка не разбирает до конца, не меняется молча.
        if launch or norm in pins:
            with open(norm, 'rb') as f:
                got = hashlib.sha256(f.read()).hexdigest()
            want = pins.get(norm)
            if want:
                want[1] = True
            if not want or want[0] != got:
                found += 1
                print(f'SQL_CONCAT {norm}:0: PIN: file that starts programs is {"not pinned" if not want else "changed"}: sha256 {got}')
    for p, (want, used) in pins.items():
        if not used:
            found += 1
            print(f'SQL_CONCAT_ALLOW_UNUSED {p}: PIN: {want}')
    for (p, rule, code), used in allow.items():
        if not used:
            found += 1
            print(f'SQL_CONCAT_ALLOW_UNUSED {p}: {rule}: {code[:160]}')
    found += bad_allow
    print(f'SQL_CONCAT_SCAN files={scanned} findings={found}')
    print('SQL_CONCAT_SCAN=' + ('FAIL' if found or not scanned else 'PASS'))
    return 1 if found or not scanned else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
