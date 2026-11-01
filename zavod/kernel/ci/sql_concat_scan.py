#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_scan.py
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 01:15 +02:00 (v0.3: аудит M3310-R2-01 — проверка
#   по месту вызова: у каждого .query(…) в JavaScript текст запроса — постоянный, иначе находка; массив с текстом
#   запроса и .join(); в Python — текст, который возвращает функция этого файла; v0.2: аудит M3310-R1B-02 — текст
#   запроса отслеживается и через переменные: «q = 'SELECT …'; q += v», промежуточная переменная, куски
#   «'SEL' + 'ECT …'»; то же для JavaScript)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: проверка сборки (карта 3.3.10.2, протокол И.7а п.2): запрос к базе — только заранее написанный текст,
#   значения — только параметрами. Находит склейку запросов (текст запроса, собранный из кусков во время работы)
#   и роняет сборку (код выхода 1, строки SQL_CONCAT ...).
#   Python (службы ячейки): f-строка с подстановкой, «+», «+=», «%», .format(), .join(), .replace() — если
#   сложенный текст всех известных кусков похож на запрос. Кусок известен, если он записан в коде прямо, лежит в
#   переменной, которой в этом файле присвоен такой текст, или его возвращает функция этого файла (по всем
#   присваиваниям и return, до неподвижной точки).
#   JavaScript (ядро, движок): у каждого вызова .query(…) первый аргумент — постоянный текст: строка, шаблон без
#   ${}, цепочка таких строк через «+» или имя, объявленное const с таким текстом и больше не присваиваемое; иначе
#   находка — текст из функции, параметра, .join() и любой другой склейки сюда попадает. Сверх того: шаблон
#   `...${...}...` с текстом запроса; «+», «+=», .concat(), .join() рядом с текстом запроса или с переменной, которой
#   присвоен текст запроса (в том числе массив); цепочка строк через «+», вместе похожая на запрос.
#   Исключения — только из файла разрешений: строка «путь<TAB>точный текст строки кода», для каждой — причина.
# ВЫЗОВ: python3 -I sql_concat_scan.py [--allow файл] путь…   (папки обходятся целиком: *.py, *.mjs, *.js и файлы
#   без расширения с первой строкой «#!…python3»)
# ОГРАНИЧЕНИЯ: проверка по тексту и дереву разбора, а не по смыслу программы. В Python текст, пришедший из другого
#   файла или извне, сканер не видит; поэтому запросы пишутся постоянными в том же файле, где выполняются (службы
#   ячейки шлют запросы только через psql с постоянным текстом). В JavaScript это закрывает проверка по месту вызова.
#   Неиспользованная строка разрешений — тоже отказ: разрешения не копятся.
import ast
import os
import re
import sys

SQL = re.compile(r'\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|GRANT\s|REVOKE\s|TRUNCATE\s'
                 r'|COPY\s|EXECUTE\s|SET\s+(LOCAL\s+)?ROLE|WHERE\s|VALUES\s*\()')
JS_TEMPLATE = re.compile(r'`[^`]*`', re.S)
JS_LIT = r'''(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`[^`]*`)'''
JS_PLUS = re.compile(r'''(['"])((?:(?!\1)[^\\\n]|\\.)*)\1\s*\+|\+=?\s*(['"])((?:(?!\3)[^\\\n]|\\.)*)\3''')
JS_CHAIN = re.compile(JS_LIT + r'(?:\s*\+\s*' + JS_LIT + r')+', re.S)
JS_ASSIGN = re.compile(r'([A-Za-z_$][\w$.]*)\s*(\+?=)(?![=>])\s*(' + JS_LIT + r'(?:\s*\+\s*' + JS_LIT + r')*)', re.S)
JS_ARRAY = re.compile(r'([A-Za-z_$][\w$.]*)\s*=(?![=>])\s*\[([^\[\]]*)\]', re.S)
JS_INLINE_JOIN = re.compile(r'\[([^\[\]]*)\]\s*\.\s*join\s*\(', re.S)
JS_ALIAS = re.compile(r'([A-Za-z_$][\w$.]*)\s*=(?![=>])\s*([A-Za-z_$][\w$.]*)\s*[;\n]')
JS_QUERY_CALL = re.compile(r'\.\s*query\s*\(')
# Постоянный кусок текста: строка в кавычках или шаблон без ${…}.
JS_FIXED_LIT = r'''(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`$\\]|\\.|\$(?!\{))*`)'''
JS_FIXED = JS_FIXED_LIT + r'(?:\s*\+\s*' + JS_FIXED_LIT + r')*'
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


def js_unquote(chain):
    """Текст цепочки строк «'a' + "b" + `c`» без кавычек; ${...} шаблона заменяется пробелом."""
    return ''.join(re.sub(r'\$\{[^}]*\}', ' ', m.group(0)[1:-1]) for m in re.finditer(JS_LIT, chain, re.S))


def js_blank(text):
    """Код, где содержимое строк, шаблонов (кроме ${…}) и комментариев заменено пробелами: скобки и запятые внутри
    строк не мешают искать границы аргумента. Переводы строк сохраняются — номера строк те же."""
    out = list(text)
    n = len(text)
    i = depth = 0
    stack = []  # глубина фигурных скобок, на которой открыт каждый ${

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != '\n':
                out[k] = ' '

    while i < n:
        c = text[i]
        if text.startswith('//', i):
            j = text.find('\n', i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue
        if c in '\'"':
            j = i + 1
            while j < n and text[j] != c and text[j] != '\n':
                j += 2 if text[j] == '\\' else 1
            blank(i + 1, j)
            i = j + 1
            continue
        if c == '`' or (c == '}' and stack and stack[-1] == depth):
            if c == '}':
                stack.pop()
            j = i + 1
            while j < n and text[j] != '`' and not text.startswith('${', j):
                j += 2 if text[j] == '\\' else 1
            blank(i + 1, j)
            if j >= n or text[j] == '`':
                i = j + 1
                continue
            stack.append(depth)
            i = j + 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return ''.join(out)


def js_fixed_consts(text):
    """Имена «const ИМЯ = постоянный текст», которым больше нигде ничего не присваивается."""
    names = set()
    for m in re.finditer(r'\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(' + JS_FIXED + r')\s*[;\n]', text, re.S):
        n = re.escape(m.group(1))
        if len(re.findall(r'(?<![\w$.])' + n + r'\s*(?:[-+*/%&|^]|\?\?|\|\||&&)?=(?![=>])', text)) == 1:
            names.add(m.group(1))
    return names


def js_findings(path, text):
    out = []
    lines = text.splitlines()

    def line_of(pos):
        return text.count('\n', 0, pos) + 1

    def add(pos, why):
        ln = line_of(pos)
        item = (ln, why, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
        if item not in out:
            out.append(item)

    for m in JS_TEMPLATE.finditer(text):
        body = m.group(0)
        if '${' in body and sqlish(body):
            add(m.start() + body.index('${'), 'template literal with SQL text and ${}')
    for m in JS_PLUS.finditer(text):
        s = m.group(2) if m.group(2) is not None else m.group(4)
        if sqlish(s or ''):
            add(m.start(), 'SQL text joined with +')
    for m in JS_CHAIN.finditer(text):
        if sqlish(js_unquote(m.group(0))):
            add(m.start(), 'SQL text pieces joined with +')
    for m in JS_INLINE_JOIN.finditer(text):
        if sqlish(js_unquote(m.group(1))):
            add(m.start(), 'SQL text array joined with .join()')
    # Имена, которым в файле присвоен текст запроса (в том числе кусками, массивом и через другое имя).
    env = {}
    for m in JS_ASSIGN.finditer(text):
        env[m.group(1)] = env.get(m.group(1), '') + '\n' + js_unquote(m.group(3))
    for m in JS_ARRAY.finditer(text):
        env[m.group(1)] = env.get(m.group(1), '') + '\n' + js_unquote(m.group(2))
    for _ in range(5):
        for m in JS_ALIAS.finditer(text):
            if m.group(2) in env and env[m.group(2)] not in env.get(m.group(1), ''):
                env[m.group(1)] = env.get(m.group(1), '') + '\n' + env[m.group(2)]
    for name in sorted(n for n, v in env.items() if sqlish(v)):
        q = re.escape(name)
        for pat, why in ((r'(?<![\w$.])' + q + r'\s*\+=', 'SQL text variable appended with +='),
                         (r'(?<![\w$.])' + q + r'\s*\+(?![+=])', 'SQL text variable joined with +'),
                         (r'(?<!\+)\+\s*' + q + r'(?![\w$])', 'SQL text variable joined with +'),
                         (r'\$\{\s*' + q + r'\s*\}', 'SQL text variable inside a template'),
                         (r'(?<![\w$.])' + q + r'\s*\.\s*(?:concat|replace|replaceAll|join)\s*\(',
                          'SQL text variable built with a string method')):
            for m in re.finditer(pat, text):
                add(m.start(), why)
    # Проверка по месту вызова (аудит M3310-R2-01): текст каждого .query(…) — постоянный. Если текст — первый
    # параметр функции этого файла (обёртка вроде «const one = (sql) => c.query(sql)»), то постоянным обязан быть
    # первый аргумент у каждого вызова этой обёртки; и так далее по цепочке обёрток.
    code = js_blank(text)
    fixed_names = js_fixed_consts(text)
    defs = js_defs(code)
    def_pos = {d[1] for d in defs}
    wrappers = {}
    todo = [(m.start(), m.end()) for m in JS_QUERY_CALL.finditer(code)]
    while todo:
        at, start = todo.pop()
        arg = text[start:js_arg_end(code, start)].strip()
        if re.fullmatch(JS_FIXED, arg, re.S) or arg in fixed_names:
            continue
        owner = min((d for d in defs if d[2] == arg and d[3] < at < d[4]), key=lambda d: d[4] - d[3], default=None)
        if owner is None:
            add(at, 'query text is not a fixed string')
            continue
        name = owner[0]
        if name in wrappers:
            continue
        wrappers[name] = True
        for m in re.finditer(r'(?<![\w$])' + re.escape(name) + r'\s*\(', code):
            if m.start() not in def_pos:
                todo.append((m.start(), m.end()))
    return out


JS_DEFS = (
    re.compile(r'\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(\s*([A-Za-z_$][\w$]*)'),
    re.compile(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(\s*([A-Za-z_$][\w$]*)[^()]*\)\s*=>'),
    re.compile(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*=>'),
    re.compile(r'^[ \t]*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\(\s*([A-Za-z_$][\w$]*)[^()]*\)\s*\{', re.M),
)
JS_KEYWORDS = {'if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'with'}


def js_arg_end(code, start):
    """Конец первого аргумента вызова: запятая или закрывающая скобка на том же уровне вложенности."""
    k = start
    depth = 0
    while k < len(code):
        ch = code[k]
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            if depth == 0:
                break
            depth -= 1
        elif ch == ',' and depth == 0:
            break
        k += 1
    return k


def js_close(code, i):
    """Позиция за парной скобкой к code[i]."""
    depth = 0
    for k in range(i, len(code)):
        if code[k] in '([{':
            depth += 1
        elif code[k] in ')]}':
            depth -= 1
            if depth == 0:
                return k + 1
    return len(code)


def js_defs(code):
    """Функции файла: (имя, позиция имени, первый параметр, начало тела, конец тела)."""
    defs = []
    for kind, rx in enumerate(JS_DEFS):
        for m in rx.finditer(code):
            if m.group(1) in JS_KEYWORDS:
                continue
            if kind == 0:  # function ИМЯ(параметры) { … }
                body = code.find('{', js_close(code, code.index('(', m.start(1))))
                end = js_close(code, body) if body >= 0 else len(code)
            elif kind == 3:  # метод ИМЯ(параметры) { … }
                body = m.end() - 1
                end = js_close(code, body)
            else:  # стрелка: тело в {…} или выражение до конца оператора
                body = m.end()
                while body < len(code) and code[body] in ' \t\r\n':
                    body += 1
                if body < len(code) and code[body] == '{':
                    end = js_close(code, body)
                else:
                    end = body
                    depth = 0
                    while end < len(code):
                        ch = code[end]
                        if ch in '([{':
                            depth += 1
                        elif ch in ')]}':
                            if depth == 0:
                                break
                            depth -= 1
                        elif depth == 0 and ch in ';,\n':
                            break
                        end += 1
            defs.append((m.group(1), m.start(1), m.group(2), body, end))
    return defs


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
    for path in files(argv):
        norm = path.replace('\\', '/')
        if norm.endswith(('.mjs', '.js')):
            kind = 'js'
        elif is_python(path):
            kind = 'py'
        else:
            continue
        with open(path, encoding='utf-8') as f:
            text = f.read()
        scanned += 1
        for ln, why, code in (js_findings if kind == 'js' else py_findings)(norm, text):
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
