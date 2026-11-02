# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_scan.py
# ВЕРСИЯ: v0.8  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 03:47 +02:00 (v0.8: аудит M3310-R7-03 — проверяются и сценарии оболочки (*.sh и файлы с #!…sh): запрос к базе только
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
                dirs[:] = sorted(d for d in dirs if d not in ('node_modules', '__pycache__', '.git'))
                for n in sorted(names):
                    yield os.path.join(root, n)
        else:
            yield p


# Строка разрешения не должна касаться объекта базы: пул, клиент, вызов запроса (аудит M3310-R6-04).
ALLOW_DB = re.compile(r'\bpg\.|\b(Pool|Client|pool|client|db|rulesPool)\b|\.query\b')
ALLOW_CODE = re.compile(r'^[A-Z_]+$')


def main(argv):
    allow_path = None
    if len(argv) >= 2 and argv[0] == '--allow':
        allow_path, argv = argv[1], argv[2:]
    if not argv:
        print('usage: sql_concat_scan.py [--allow file] path...', file=sys.stderr)
        return 2
    allow = {}
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
                allow[(parts[0].replace('\\', '/'), parts[1], parts[2].strip())] = False
    found = 0
    scanned = 0
    todo = []
    for path in files(argv):
        norm = path.replace('\\', '/')
        if norm.endswith(('.mjs', '.js')):
            todo.append((norm, 'js'))
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
            items = [(ln, why, 'PY_SQL', code) for ln, why, code in py_findings(norm, text)]
        for ln, why, rule, code in items:
            key = (norm, rule, code)
            if key in allow:
                allow[key] = True
                continue
            found += 1
            print(f'SQL_CONCAT {norm}:{ln}: {rule}: {why}: {code[:160]}')
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
