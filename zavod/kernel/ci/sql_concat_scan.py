#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_scan.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 22:56 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: проверка сборки (карта 3.3.10.2, протокол И.7а п.2): запрос к базе — только заранее написанный текст,
#   значения — только параметрами. Находит склейку запросов (текст запроса, собранный из кусков во время работы)
#   и роняет сборку (код выхода 1, строки SQL_CONCAT ...).
#   Python (службы ячейки): f-строка, «+», «%», .format() или .join() с текстом, похожим на запрос.
#   JavaScript (ядро, движок): шаблон `...${...}...` или «+» рядом с текстом запроса.
#   Исключения — только из файла разрешений: строка «путь<TAB>точный текст строки кода», для каждой — причина.
# ВЫЗОВ: python3 -I sql_concat_scan.py [--allow файл] путь…   (папки обходятся целиком: *.py, *.mjs, *.js и файлы
#   без расширения с первой строкой «#!…python3»)
# ОГРАНИЧЕНИЯ: проверка по тексту и дереву разбора, а не по смыслу программы; ловит склейку там, где кусок запроса
#   записан прямо в коде. Неиспользованная строка разрешений — тоже отказ: разрешения не копятся.
import ast
import os
import re
import sys

SQL = re.compile(r'\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|GRANT\s|REVOKE\s|TRUNCATE\s'
                 r'|COPY\s|EXECUTE\s|SET\s+(LOCAL\s+)?ROLE|WHERE\s|VALUES\s*\()')
JS_TEMPLATE = re.compile(r'`[^`]*`', re.S)
JS_PLUS = re.compile(r'''(['"])((?:(?!\1)[^\\\n]|\\.)*)\1\s*\+|\+\s*(['"])((?:(?!\3)[^\\\n]|\\.)*)\3''')


def sqlish(s):
    return isinstance(s, str) and SQL.search(s) is not None


def py_findings(path, text):
    try:
        tree = ast.parse(text, path)
    except SyntaxError as e:
        return [(e.lineno or 0, f'syntax error: {e.msg}')]
    out = []
    lines = text.splitlines()

    def const_sql(node):
        return isinstance(node, ast.Constant) and sqlish(node.value)

    def has_sql(node):
        return any(const_sql(n) for n in ast.walk(node))

    for node in ast.walk(tree):
        bad = None
        if isinstance(node, ast.JoinedStr) and any(const_sql(v) for v in node.values):
            bad = 'f-string with SQL text'
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)) and (has_sql(node.left)
                                                                                         or has_sql(node.right)):
            bad = 'SQL text joined with + or %'
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add) and has_sql(node.value):
            bad = 'SQL text appended with +='
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('format', 'join'):
            if const_sql(node.func.value) or any(has_sql(a) for a in node.args):
                bad = f'SQL text built with .{node.func.attr}()'
        if bad:
            ln = getattr(node, 'lineno', 0)
            item = (ln, bad, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
            if item not in out:  # «a + b + c» — два узла сложения на одной строке, находка одна
                out.append(item)
    return out


def js_findings(path, text):
    out = []
    lines = text.splitlines()

    def line_of(pos):
        return text.count('\n', 0, pos) + 1
    for m in JS_TEMPLATE.finditer(text):
        body = m.group(0)
        if '${' in body and sqlish(body):
            ln = line_of(m.start() + body.index('${'))
            out.append((ln, 'template literal with SQL text and ${}', lines[ln - 1].strip()))
    for m in JS_PLUS.finditer(text):
        s = m.group(2) if m.group(2) is not None else m.group(4)
        if sqlish(s or ''):
            ln = line_of(m.start())
            out.append((ln, 'SQL text joined with +', lines[ln - 1].strip()))
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
