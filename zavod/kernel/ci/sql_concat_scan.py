# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_scan.py
# ВЕРСИЯ: v0.6  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 02:26 +02:00 (v0.6: аудит M3310-R5-01, -02, -03 —
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
#   Исключения — только из файла разрешений: строка «путь<TAB>точный текст строки кода», для каждой — причина.
# ВЫЗОВ: python3 -I sql_concat_scan.py [--allow файл] путь…   (папки обходятся целиком: *.py, *.mjs, *.js и файлы
#   без расширения с первой строкой «#!…python3»). Node — из переменной ZAVOD_NODE, иначе node из PATH.
# ОГРАНИЧЕНИЯ: в Python текст, пришедший из другого файла или извне, сканер не видит; поэтому запросы пишутся
#   постоянными в том же файле, где выполняются (службы ячейки шлют запросы только через psql с постоянным
#   текстом). Неиспользованная строка разрешений — тоже отказ: разрешения не копятся.
import ast
import json
import os
import re
import subprocess
import sys

SQL = re.compile(r'\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|GRANT\s|REVOKE\s|TRUNCATE\s'
                 r'|COPY\s|EXECUTE\s|SET\s+(LOCAL\s+)?ROLE|WHERE\s|VALUES\s*\()')
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
    return out


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
        out.setdefault(f['path'], []).append((int(f['line']), f['why']))
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


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in ('node_modules', '__pycache__', '.git'))
                for n in sorted(names):
                    yield os.path.join(root, n)
        else:
            yield p


def main(argv):
    allow_path = None
    if len(argv) >= 2 and argv[0] == '--allow':
        allow_path, argv = argv[1], argv[2:]
    if not argv:
        print('usage: sql_concat_scan.py [--allow file] path...', file=sys.stderr)
        return 2
    allow = {}
    if allow_path:
        with open(allow_path, encoding='utf-8') as f:
            for raw in f:
                if not raw.strip() or raw.startswith('#'):
                    continue
                p, _, code = raw.rstrip('\n').partition('\t')
                allow[(p.replace('\\', '/'), code.strip())] = False
    found = 0
    scanned = 0
    todo = []
    for path in files(argv):
        norm = path.replace('\\', '/')
        if norm.endswith(('.mjs', '.js')):
            todo.append((norm, 'js'))
        elif is_python(path):
            todo.append((norm, 'py'))
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
            items = [(ln, why, lines[ln - 1].strip() if 0 < ln <= len(lines) else '') for ln, why in js_found.get(norm, [])]
        else:
            items = py_findings(norm, text)
        for ln, why, code in items:
            key = (norm, code)
            if key in allow:
                allow[key] = True
                continue
            found += 1
            print(f'SQL_CONCAT {norm}:{ln}: {why}: {code[:160]}')
    for (p, code), used in allow.items():
        if not used:
            found += 1
            print(f'SQL_CONCAT_ALLOW_UNUSED {p}: {code[:160]}')
    print(f'SQL_CONCAT_SCAN files={scanned} findings={found}')
    print('SQL_CONCAT_SCAN=' + ('FAIL' if found or not scanned else 'PASS'))
    return 1 if found or not scanned else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
