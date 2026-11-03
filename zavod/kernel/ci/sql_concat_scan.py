# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_scan.py
# ВЕРСИЯ: v0.23  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 22:56 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-03 02:19 +02:00 (v0.23: аудит M3310-R21-01 —
#   systemctl stop, disable --now и mask --now (в любом месте команды) проверяют юнит как запуск, в stop ещё
#   ИМЯ@*.service — экземпляры шаблона; M3310-R21-02 — sort и install только с закрытым списком опций (без
#   --compress-program, -s, --strip-program и сокращений длинных опций), у sort слово из подстановки с неизвестным
#   первым знаком — находка; systemd-analyze только verify и security с --man=no и --no-pager; pg_ctlcluster вне
#   списка программ (установщик останавливает базу через systemctl); все имена PSQL* (PSQL_PAGER …) — в SH_SPECIAL; v0.22 от 01:56: аудит M3310-R20-01 —
#   break/continue любым словом команды (builtin continue) снимает «выполняется всегда» с циклов; M3310-R20-02 —
#   помечается каждый путь записи (перенаправление и >&ФАЙЛ, tee, dd of=, опции SH_OUT_OPTS — sort -o, psql -o/-L,
#   blkid -c, useradd/usermod -d, в том числе в группе коротких опций, usermod -m — любой путь; truncate, fallocate,
#   mkfs.ext4, cp/install/mv, ln и cp -s/-l — любой путь): постоянный путь — сам путь и всё под ним; "…$ПОСТОЯННАЯ…" и
#   переменная for по постоянным именам — каждый вариант пути; иначе ИМЯ или ОКОНЧАНИЕ части пути по хвосту после
#   последней подстановки, без хвоста — любой путь; запись в любом месте сценария (два прохода) и во вложенном тексте
#   оболочки; touch не помечает (меняет только время); Claude, сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d; v0.21: аудит M3310-R19-01..03 —
#   systemctl start/restart/reload/enable — только юнит, который сценарий дерева ставит всегда из файла своей папки
#   в /etc/systemd/system/, или юнит ОС (SYSTEM_UNITS_OK), имя постоянное или "$ИМЯ" с одним присваиванием; установка
#   файла для systemd-tmpfiles и nft засчитывается, только если выполняется всегда (не в if/while/case/функции/&&/||/
#   трубе/фоне/$( ), только for по постоянному списку без break/continue) при set -e и из файла своей папки дерева;
#   любая иная запись в путь снимает разрешение; Claude, сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d; прежняя: 2026-11-02 21:20 +02:00 (v0.20: аудит M3310-R18-01, -02 — printf с %n в формате (с флагами, шириной, длиной) и кодами \0-7 \x \u — находка; for/select в имя оболочки — находка; systemd-tmpfiles --create — только файл, который этот же сценарий поставил install/cp из "$HERE/*.tmpfiles.conf" проверенного дерева; v0.19 от 20:53: аудит M3310-R17B-01..05 — trap вне списка программ; read, printf -v, wait -p, ${ИМЯ:=}, (( ИМЯ= )) для имён SH_SPECIAL — находка; путь записи с .. — находка, путь нормализуется; cd и ln в папку кода — SH_EXEC; правило polkit — закрытый мир имён и без вычисляемых свойств; nft и systemd-tmpfiles — только закрытые формы с файлом дерева; v0.18 от 15:58: аудит M3310-R16-01..06 и на опережение — закрытый мир оболочки и юнитов: программа только из списка SH_PROGRAMS_OK, обёртка только из WRAP_OPTS со своими опциями, среда программе не передаётся, имена PATH, BASH_ENV, LD_*, NODE_*, PYTHON* … не присваиваются, вложенность глубже предела — находка SH_PARSE, awk и sed — без запуска и записи, systemctl, find, flock, ip — закрытые подкоманды и опции, запись в папки кода — SH_EXEC; юнит: приставка | — UNIT_SHELL без разрешения, + и ! — UNIT_PRIV, закрытые разделы и ключи, без $ и ;, вставки *.conf, tmpfiles только d, polkit без запуска, nft без include; v0.17 от 15:12: аудит M3310-R15B-02..07 — файл дерева только полным путём папки установки; getattr только у модуля закрытого списка без вызова результата; $'…' с обратной чертой — имя не постоянное; опции ssh, которые запускают команды, и -F; среда службы — закрытый список имён, EnvironmentFile — находка; CHILD_OPTS не снимается разрешением; прежняя 2026-11-02 10:42 +02:00 — v0.16: самопроверка R15 — запись файла кода перенаправлением и tee, файл дерева из папки вне установки, службы только из /usr/local/lib/zavod, /etc/zavod, /usr/bin, /usr/sbin; v0.15: аудит M3310-R14-01, -02,
#   -04, -05 — закрытый мир: global/nonlocal делают имя во внешних областях не постоянным; импорт модуля Python вне
#   PY_MODULES и относительный импорт — находка PY_IMPORT; psql в любом месте команды и программа за docker/ssh/… —
#   по своим правилам, команда ssh одним словом разбирается, из подстановки — находка; python/bash/node запускают
#   только файл проверенного дерева своего вида (SH_EXEC); строки Exec…= служб *.service — только сценарии дерева
#   и nft -f (UNIT_EXEC); файл вне закрытого списка видов — FORMAT); прежняя: 2026-11-02 09:06 +02:00 (v0.14: аудит M3310-R13-01..03 —
#   в *.py параметр функции верхнего уровня или метода не постоянный (её вызывают из другого файла); .fetch, .fetchrow,
#   .fetchval, .copy, .copy_from, .copy_to, .prepare, .query, .stream — методы запроса; файл с #!, исполняемым или
#   архивным содержимым под чужим суффиксом — FORMAT, кроме правил сети *.nft); прежняя: 2026-11-02 08:40 +02:00 (v0.13: аудит M3310-R12-01..03 —
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
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c; v0.15 — сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
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
import posixpath
import re
import shlex
import subprocess
import sys

SQL = re.compile(r'\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|CREATE\s|ALTER\s|DROP\s|GRANT\s|REVOKE\s|TRUNCATE\s'
                 r'|COPY\s|EXECUTE\s|SET\s+(LOCAL\s+)?ROLE|WHERE\s|VALUES\s*\()', re.IGNORECASE)
# Аудит M3310-R8-03: SQL узнаётся в любом регистре (select … where — тоже SQL). Кроме того, у мест выполнения
# запроса (.execute и родня, psql через subprocess с текстом на входе) текст обязан быть постоянным — не «похожим
# на SQL», а известным целиком: неизвестная форма — находка.
EXEC_METHODS = {'execute', 'executemany', 'executescript', 'mogrify', 'copy_expert', 'callproc',
                # asyncpg и psycopg 3 тоже отправляют текст как запрос (аудит M3310-R13-02)
                'fetch', 'fetchrow', 'fetchval', 'copy', 'copy_from', 'copy_to', 'prepare', 'query', 'stream'}
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
# Закрытый список модулей Python (аудит M3310-R14-02): только стандартная библиотека, которой пользуются службы
# ячейки и их проверки. Модули запуска (subprocess, importlib, ctypes) здесь есть, но остаются находкой PY_RUN.
PY_MODULES = {'errno', 'fcntl', 'hashlib', 'io', 'ipaddress', 'json', 'os', 'pwd', 're', 'select', 'signal', 'socket',
              'stat', 'struct', 'sys', 'tarfile', 'tempfile', 'threading', 'time', 'unicodedata', 'unittest', 'urllib',
              'uuid', 'subprocess', 'importlib', 'ctypes'}
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


def py_rule(why):
    """Причина находки Python → (причина без приставки, код правила)."""
    for pre, rule in (('RUN: ', 'PY_RUN'), ('IMPORT: ', 'PY_IMPORT')):
        if why.startswith(pre):
            return why[len(pre):], rule
    return why, 'PY_SQL'


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
    for ln, bad in py_exec_findings(tree, path.endswith(".py")):
        item = (ln, bad, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
        if item not in out:
            out.append(item)
    return out


def py_exec_findings(tree, importable=True):
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
            # global/nonlocal (аудит M3310-R14-01): запись в функции меняет имя модуля или внешней функции — у этого
            # имени во всех внешних областях значение больше не прочитать.
            for name in n.names:
                put(n, name, None)
                g = enclosing(enclosing(n)) if enclosing(n) is not None else None
                while g is not None:
                    values.setdefault((g, name), []).append(None)
                    g = enclosing(g)
                values.setdefault((None, name), []).append(None)
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
        # Функцию верхнего уровня и метод класса можно импортировать из другого файла и вызвать с любым текстом
        # (аудит M3310-R13-01): в файле *.py постоянство параметра выводится только для функции, вложенной в другую.
        # Сценарий без суффикса .py обычным import не загрузить, а importlib, runpy и правка sys.path — находки.
        if importable and not isinstance(parents.get(f), (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
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
    # getattr с именем постоянной (аудит M3310-R15B-03) — только у модуля закрытого списка, подключённого «import
    # имя» и нигде не переназначенного, и без вызова результата: getattr(adapter, 'EXECUTE')(sql) — находка.
    mod_names = {a.name for x in ast.walk(tree) if isinstance(x, ast.Import) for a in x.names
                 if a.asname is None and a.name in PY_MODULES}
    rebound = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name) and not isinstance(x.ctx, ast.Load)} |         {x.arg for x in ast.walk(tree) if isinstance(x, ast.arg)} |         {x.name for x in ast.walk(tree) if isinstance(x, ast.ExceptHandler) and x.name} |         {(a.asname or a.name) for x in ast.walk(tree) if isinstance(x, ast.ImportFrom) for a in x.names} |         {a.asname for x in ast.walk(tree) if isinstance(x, ast.Import) for a in x.names if a.asname} |         {nm for x in ast.walk(tree) if isinstance(x, (ast.Global, ast.Nonlocal)) for nm in x.names}
    called = {id(x.func) for x in ast.walk(tree) if isinstance(x, ast.Call)}
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
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'getattr' and len(n.args) >= 2                 and not (isinstance(n.args[0], ast.Name) and n.args[0].id in mod_names - rebound and id(n) not in called):
            out.append((ln, 'RUN: getattr() from an object that is not a closed-list module, or its result is called'))
        # Закрытый список модулей (аудит M3310-R14-02): сторонний пакет (psycopg2.extras.execute_values,
        # pandas.read_sql, sqlalchemy …) отправляет запрос свободной функцией мимо проверки методов. Разрешены только
        # модули из PY_MODULES; новый модуль добавляется в список правкой сканера и проходит аудит.
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else \
            [n.module or ''] if isinstance(n, ast.ImportFrom) and not n.level else []
        for m in mods:
            if m.split('.')[0] not in PY_MODULES:
                out.append((ln, f'IMPORT: module {m} is not in the closed list of modules'))
        if isinstance(n, ast.ImportFrom) and n.level:
            out.append((ln, 'IMPORT: relative import (the scan checks one file at a time)'))
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
# Исполнители, которые запускают программу из своих аргументов на другом уровне (контейнер, другой узел, другое
# пространство имён): их список аргументов проверяется на psql, оболочку и интерпретатор (аудит M3310-R14-04).
SH_REMOTE = {'docker', 'podman', 'nerdctl', 'kubectl', 'oc', 'ssh', 'ip', 'lxc', 'lxc-attach', 'machinectl',
             'systemd-nspawn', 'flatpak', 'toolbox', 'distrobox', 'firejail', 'bwrap', 'proot', 'schroot', 'sg', 'su',
             'script', 'watch', 'flock', 'strace', 'ltrace', 'gdb', 'valgrind', 'xvfb-run', 'dbus-run-session',
             'unbuffer', 'faketime', 'torsocks', 'proxychains', 'proxychains4', 'find'}
# Опции ssh, значение которых — команда для запуска (аудит M3310-R15B-05); Match может нести «exec команда».
SSH_EXEC_OPTS = {'proxycommand', 'localcommand', 'permitlocalcommand', 'knownhostscommand', 'remotecommand', 'match'}
# Имена среды, которые служба может задать (аудит M3310-R15B-06): свои ZAVOD_* и адрес посредника. Ни одно не
# загружает код; NODE_OPTIONS, PYTHONPATH, BASH_ENV, LD_PRELOAD и прочие — вне списка.
UNIT_ENV_OK = re.compile(r'^(ZAVOD_[A-Z0-9_]+|HTTPS_PROXY|HTTP_PROXY|NO_PROXY)$')
# Аудит M3310-R16: закрытый мир оболочки. Программа — только из этого списка (то, что сценарии проекта вызывают на
# деле) или своя функция файла; любая другая (ed, git, tar, su, ssh …) — находка SH_CMD. Программа с путём — только
# из /usr/bin, /usr/sbin, /bin, /sbin.
SH_PROGRAMS_OK = {
    ':', '[', 'test', 'true', 'false', 'break', 'continue', 'exit', 'return', 'shift', 'wait', 'read', 'set', 'cd',
    'pwd', 'umask', 'local', 'echo', 'printf', 'sleep', 'awk', 'sed', 'grep', 'cut', 'tr', 'sort', 'uniq',
    'wc', 'head', 'tail', 'cat', 'tee', 'od', 'numfmt', 'seq', 'date', 'basename', 'dirname', 'stat', 'ls', 'du',
    'df', 'id', 'getent', 'uname', 'ps', 'ss', 'kill', 'pkill', 'mkdir', 'mktemp', 'touch', 'truncate', 'chmod',
    'chown', 'cp', 'mv', 'ln', 'install', 'dd', 'fallocate', 'find', 'flock', 'ip', 'nft', 'blkid', 'findmnt',
    'mountpoint', 'mkfs.ext4', 'tune2fs', 'useradd', 'usermod', 'passwd', 'journalctl', 'systemctl',
    'systemd-analyze', 'systemd-escape', 'systemd-tmpfiles', 'psql', 'python3', 'sh',
    'sudo', 'exec', 'timeout', 'command', 'systemd-run'}
SH_SYS_DIRS = ('/usr/bin/', '/usr/sbin/', '/bin/', '/sbin/')
# Опции программ SH_PROGRAMS_OK, значение которых — путь записи (аудит M3310-R20-02): путь помечается (taint).
# tune2fs не помечает: пишет только в файл с файловой системой ext4, файл настроек nft или tmpfiles он не меняет.
SH_OUT_OPTS = {'sort': ('-o', '--output'), 'psql': ('-o', '--output', '-L', '--log-file'), 'blkid': ('-c',),
               'useradd': ('-d', '--home-dir'), 'usermod': ('-d', '--home')}
# Обёртки (аудит M3310-R16-03): у каждой закрытый список опций; число — сколько слов опция берёт за собой.
# env -S/--split-string, sudo -E/-s/-i, runuser, setpriv, chroot, nsenter … — вне списка, находка.
WRAP_OPTS = {
    'sudo': {'-u': 1, '-g': 1, '-n': 0, '-l': 0, '-U': 1, '--': 0},
    'env': {'-i': 0, '--ignore-environment': 0, '-u': 1, '-': 0, '--': 0},
    'exec': {'-a': 1},
    'timeout': {'-s': 1, '-k': 1, '--signal': 1, '--kill-after': 1, '--preserve-status': 0, '--foreground': 0},
    'command': {'-v': 0, '-V': 0, '-p': 0},
    'nohup': {}, 'setsid': {}, 'builtin': {},
    'systemd-run': {'--quiet': 0, '-q': 0, '--wait': 0, '--pipe': 0, '-p': 1, '--property': 1},
}
RUN_PROPS = {'DynamicUser', 'Slice', 'User', 'IPAddressDeny', 'IPAddressAllow', 'RestrictSUIDSGID',
             'SystemCallFilter', 'SystemCallArchitectures'}
# Имена, которые читает сама оболочка или загрузчик программ (PATH, BASH_ENV, IFS, LD_PRELOAD, NODE_OPTIONS,
# PYTHONPATH, PSQLRC …): присваивать их в сценарии нельзя. Переменная из среды запуска остаётся в среде и после
# простого присваивания, поэтому список действует и без export.
SH_SPECIAL = re.compile(r'^(PATH|CDPATH|IFS|ENV|BASH\w*|SHELLOPTS|PS[0-4]|PROMPT_COMMAND|GLOBIGNORE|FPATH|HOME'
                        r'|EXECIGNORE|FUNCNEST|POSIXLY_CORRECT|INPUTRC|HIST\w*|TMPDIR|LANG|LC_\w*|LD_\w*|NODE_\w*'
                        r'|PYTHON\w*|PERL\w*|RUBY\w*|PSQL\w*|PG[A-Z]+|GIT_\w*|SYSTEMD_\w*|GCONV_PATH|LOCPATH|NLSPATH'
                        r'|MALLOC_\w*|OPENSSL_\w*|SSL_\w*|TERMINFO\w*|EDITOR|VISUAL|PAGER|LESS\w*|XDG_\w*)$')
# Аудит M3310-R17B-02: те же имена меняются и без слова «ИМЯ=»: ${ИМЯ:=…}, ${ИМЯ=…}, арифметика (( ИМЯ=… )),
# $(( ИМЯ+=… )); встроенные read и printf -v проверяются у самой команды. trap (аудит M3310-R17B-01) исполняет свой
# текст при выходе или сигнале — его нет в SH_PROGRAMS_OK.
SH_SPECIAL_SET = re.compile(r'\$\{' + SH_SPECIAL.pattern[1:-1] + r'(?!\w):?=|\(\([^)]*?(?<![\w$])'
                            + SH_SPECIAL.pattern[1:-1] + r'(?!\w)\s*(?:[-+*/%&|^]|<<|>>)?=(?!=)')
SH_NAME = re.compile(r'^[A-Za-z_]\w*$')


def norm_path(v):
    """Путь без //, /./ и /../ (аудит M3310-R17B-03); пустой — как есть."""
    return posixpath.normpath(re.sub(r'/+', '/', v)) if v else v

READ_OPTS = {'-r': 0}
WAIT_OPTS = {'-n': 0, '-f': 0}
SYSTEMCTL_CMDS = {'start', 'stop', 'restart', 'reload', 'is-active', 'is-enabled', 'is-failed', 'status', 'show',
                  'enable', 'disable', 'daemon-reload', 'mask', 'unmask', 'list-units', 'reset-failed'}
SYSTEMCTL_OPTS = {'--runtime': 0, '--now': 0, '--no-pager': 0, '--quiet': 0, '-q': 0, '-p': 1, '--property': 1,
                  '--value': 0, '--failed': 0, '--no-block': 0, '--no-legend': 0, '--plain': 0, '--all': 0,
                  '-a': 0, '--state': 1, '--type': 1, '--version': 0}
FIND_OPTS = {'-maxdepth': 1, '-mindepth': 1, '-name': 1, '-type': 1, '-path': 1, '-newer': 1, '-mmin': 1,
             '-size': 1, '-user': 1, '-group': 1, '-perm': 1, '-empty': 0, '-print': 0, '-print0': 0, '-quit': 0,
             '-o': 0, '-a': 0, '-not': 0, '-exec': 0, '-printf': 1, '-xdev': 0}
FLOCK_OPTS = {'-n': 0, '-x': 0, '-s': 0, '-o': 0, '-u': 0, '-E': 1, '-w': 1}
SED_SCRIPT = re.compile(r'^\s*(?:(?:\d+|\$|/(?:[^/\\\n]|\\.)*/)\s*[dpq=]|s(?P<d>[^\\\n\w\s])'
                        r'(?:(?!(?P=d))[^\\]|\\.)*(?P=d)(?:(?!(?P=d))[^\\]|\\.)*(?P=d)[gpI0-9]*)\s*$', re.S)
# Папки, откуда система берёт код или настройку запуска (на опережение аудита): запись туда из оболочки — находка
# SH_EXEC; установщик копирует туда только файлы проверенного дерева ("$HERE/…" командой install или cp).
CODE_DIRS = ('/usr/local/lib/zavod/', '/etc/zavod/', '/etc/systemd/', '/run/systemd/', '/usr/lib/systemd/',
             '/lib/systemd/', '/etc/tmpfiles.d/', '/usr/lib/tmpfiles.d/', '/run/tmpfiles.d/', '/etc/polkit-1/',
             '/usr/share/polkit-1/', '/etc/sudoers', '/etc/profile', '/etc/bash', '/etc/environment', '/etc/ld.so',
             '/etc/cron', '/var/spool/cron', '/usr/local/bin/', '/usr/local/sbin/', '/usr/bin/', '/usr/sbin/',
             '/bin/', '/sbin/', '/usr/lib/python3', '/usr/local/lib/python3', '/usr/lib/node_modules',
             '/usr/local/lib/node_modules', '/etc/apt/', '/root/', '/etc/postgresql/')
# Файлы проверенного дерева: имя → вид ('py', 'sh', 'js'). Заполняет main до проверки; интерпретатор и служба systemd
# запускают только такие файлы (аудит M3310-R14-05).
SCRIPTS = {}
# Имена файлов настроек дерева (DATA_EXT), строки которых проверяет data_findings (аудит M3310-R18-02).
DATA_FILES = set()
# Полные пути файлов проверенного дерева: "$HERE/имя" — файл папки самого сценария, а не любой файл с тем же
# именем (аудит M3310-R19-03).
TREE_PATHS = set()
# Аудит M3310-R19-01: systemctl start/restart/reload/enable — только юнит, который сценарий дерева ставит без
# условий из файла дерева в /etc/systemd/system/ (имя юнита или ('$', сценарий, ПЕРЕМЕННАЯ)), или юнит ОС из
# SYSTEM_UNITS_OK. Запуски сверяются с установками после разбора всех файлов (ставит install_cell.sh, запускают и
# проверки CI).
SD_DIR = '/etc/systemd/system/'
UNITS_INSTALLED = set()
UNITS_STARTED = []
SYSTEM_UNITS_OK = {'postgresql.service', 'postgresql@.service'}
SYSTEMCTL_START = {'start', 'restart', 'reload', 'enable'}
# Аудит M3310-R21-01: остановка исполняет ExecStop и ExecStopPost юнита — systemctl stop, а также disable и mask с
# --now проверяют имя юнита так же, как запуск. В stop имя может быть шаблоном экземпляров ИМЯ@*.service: под него
# подходят только экземпляры шаблона ИМЯ@.service.
SYSTEMCTL_STOP = {'stop'}
SYSTEMCTL_NOW = {'disable', 'mask'}
# Аудит M3310-R21-02: программы с опцией, которая запускает другую программу (sort --compress-program, install -s и
# --strip-program): опции — только из закрытого списка, длинные целиком (сокращения длинных опций — вне списка).
# Вид: (короткие без значения, короткие со значением, длинные без значения, длинные со значением).
CLOSED_OPTS = {
    'sort': ('unrVzbfhcm', 'okt', {'--unique', '--numeric-sort', '--reverse', '--version-sort', '--zero-terminated'},
             {'--output', '--key', '--field-separator'}),
    'install': ('dDpvCT', 'gmotS', {'--directory', '--preserve-timestamps', '--verbose', '--compare',
                                    '--no-target-directory'},
                {'--owner', '--group', '--mode', '--target-directory', '--suffix'}),
}
# systemd-analyze: только verify и security (ни одна не запускает команды юнита) с опциями --man=no и --no-pager.
ANALYZE_CMDS = {'verify', 'security'}
ANALYZE_OPTS = {'--man=no', '--no-pager'}
# Спецификатор %n формата printf с флагами, шириной, точностью и длиной (аудит M3310-R18-01).
PRINTF_N = re.compile(r"%[-+ #0'I]*(?:\d+|\*)?(?:\.(?:\d+|\*)?)?[hlLqjzt]*n")
SH_OPS = ('<<<', '<<-', '&&', '||', ';;', '>>', '<<', '<&', '>&', '&>', '>|', '<>', '|&', '|', '&', ';',
          '<', '>', '(', ')', '\n')
SH_ASSIGN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=')
X = '\x00'


class ShError(Exception):
    pass


class ShLex:
    """Разбор оболочки: простые команды (слова, трубы, перенаправления, heredoc) с функцией, в которой стоят."""

    def __init__(self, text, line=1, fn=None, inner=False):
        self.t, self.i, self.line = text, 0, line
        self.cmds = []
        self.fdefs = {}
        self.fn = [(fn, -1)] if fn else []
        self.depth = 0
        # Аудит M3310-R19-02: где стоит команда. nest — открытые составные команды: ('c',) — if/while/until/case,
        # { }, ( ); ('f', ИМЯ, значения) — for/select по постоянному списку. subst — внутри $( ), <( ); inner — текст
        # `…` или heredoc. Команда «на верхнем уровне» (top) — не там, не в функции, не в трубе, не рядом с &&, ||,
        # & и не после «!».
        self.nest = []
        self.subst = 0
        self.inner = inner
        self.loop = None  # слова for/select, у которых ещё не было do

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
                'fn': self.fn[-1][0] if self.fn else None, 'chain': False}

    def close(self):
        if self.nest:
            self.nest.pop()

    def word(self):
        """Слово до разделителя: {'val' (подстановка = X), 'lit', 'quoted', 'line', 'raw'}."""
        start, line, val, lit, quoted = self.i, self.line, [], True, False
        while True:
            c = self.peek()
            if c == '' or c in ' \t\n;&|()<>':
                if c in '<>' and self.peek(1) == '(' and not val:
                    self.adv(2)
                    self.subst += 1
                    self.seq(')')
                    self.subst -= 1
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
                esc = False
                while self.peek() not in ("'", ''):
                    if self.peek() == '\\':
                        esc = True
                        self.adv(2)
                    else:
                        buf.append(self.peek())
                        self.adv()
                self.adv()
                # Аудит M3310-R15B-04: Bash раскрывает \xHH, \NNN, \uHHHH, \cX — $'\x70sql' это psql. Значение с
                # любой обратной косой чертой сканер не угадывает: оно не постоянное (имя программы, флаг, путь).
                if esc:
                    val.append(X)
                    lit = False
                else:
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
                    self.subst += 1
                    self.seq(')')
                    self.subst -= 1
                    continue
                depth += (ch == '(') - (ch == ')')
                self.adv()
            return True
        if n == '(':
            self.adv(2)
            self.subst += 1
            self.seq(')')
            self.subst -= 1
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
        lx = ShLex(text, line, self.fn[-1][0] if self.fn else None, True)
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
                lx = ShLex(text, line, cmd['fn'], True)
                text, ok = lx.dq(None)
                self.cmds.extend(lx.cmds)
            cmd['here'].append({'val': text, 'lit': ok, 'quoted': quoted, 'line': line})

    def seq(self, stop):
        cur, pending, fname, case = self.new_cmd(), [], None, 0

        def done(pout=False):
            nonlocal cur
            if cur['words'] or cur['here'] or cur['redir'] or cur['hstr']:
                cur['pout'] = pout
                cur['top'] = not (self.inner or self.subst or cur['chain'] or cur['pin'] or pout or cur['fn'])
                cur['nest'] = tuple(self.nest)
                self.cmds.append(cur)
                if cur['words'] and cur['words'][0]['val'] in ('for', 'select'):
                    self.loop = cur['words']
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
                    self.close()
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
                    if op in ('&&', '||', '&'):
                        cur['chain'] = True
                    done()
                    if op in ('&&', '||'):
                        cur['chain'] = True
                    if op == ';;':
                        case = 2
                    if op == '\n' and pending:
                        self.heredocs(pending)
                        pending = []
                elif op == '(' and cur['words'] and cur['words'][-1]['val'].endswith('=') and \
                        SH_ASSIGN.match(cur['words'][-1]['val']):
                    # Массив X=(a b) — значения присваивания, а не команда (аудит M3310-R16, закрытый список программ)
                    a = cur['words'][-1]
                    while True:
                        self.blanks()
                        if self.peek() == ')':
                            self.adv()
                            break
                        if self.peek() == '\n':
                            self.adv()
                            continue
                        at = self.i
                        w = self.word()
                        if self.i == at or self.i >= len(self.t):
                            raise ShError('array value not parsed')
                        a['val'] += ' ' + w['val']
                        a['raw'] += ' ' + w['raw']
                        a['lit'] = a['lit'] and w['lit']
                elif op == '(':
                    self.blanks()
                    if len(cur['words']) == 1 and self.peek() == ')':
                        self.adv()
                        fname = cur['words'][0]['val']
                        cur = self.new_cmd()
                    else:
                        done()
                        self.nest.append(('c',))
                elif op == ')':
                    done()
                    self.close()
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
                    self.nest.append(('c',))
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
                    self.close()
                    cur['fn'] = self.fn[-1][0] if self.fn else None
                    continue
                if v in SH_KEYS:
                    if v in ('if', 'while', 'until'):
                        self.nest.append(('c',))
                    elif v == 'do' and self.loop:
                        self.push_loop()
                    elif v in ('fi', 'done', 'esac'):
                        self.close()
                    elif v == '!':
                        cur['chain'] = True
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
                self.nest.append(('c',))
                case = 2
            if cur['words'] and cur['words'][0]['val'] in ('for', 'select') and w['val'] == 'do':
                cur['words'].pop()
                done()
                self.push_loop()

    def push_loop(self):
        # for ИМЯ in постоянные имена без «/» — тело выполняется для каждого (если в тексте нет break/continue)
        fw, self.loop = self.loop, None
        self.nest.append(('f', fw[1]['val'], tuple(x['val'] for x in fw[3:])) if
                         fw and fw[0]['val'] == 'for' and len(fw) > 3 and fw[2]['val'] == 'in' and
                         all(x['lit'] and '/' not in x['val'] for x in fw[3:]) else ('c',))


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
        if p not in WRAP_OPTS:
            return k, f'wrapper {p} outside the closed list'
        opts = WRAP_OPTS[p]
        k += 1
        while k < n and words[k]['val'].startswith('-'):
            v = words[k]['val']
            if not words[k]['lit']:
                return k, f'wrapper {p} option is not fixed text'
            key, eq, val = v.partition('=') if v.startswith('--') else (v, '', '')
            if key not in opts or (eq and opts[key] != 1):
                return k, f'wrapper {p} option {v} outside the closed list'
            if p == 'systemd-run' and key in ('-p', '--property'):
                prop = val if eq else (words[k + 1]['val'] if k + 1 < n else X)
                if prop.split('=', 1)[0] not in RUN_PROPS:
                    return k, f'systemd-run property {prop.split("=", 1)[0].replace(X, "?")} outside the closed list'
            k += 1 + (0 if eq else opts[key])
            if v in ('--', '-'):
                break
        if k < n and SH_ASSIGN.match(words[k]['val']):
            return k, f'wrapper {p} passes environment to the program'
        if p == 'timeout':
            k += 1  # срок
    return None, None


def sh_findings(path, text, line=1, depth=0, shared=None):
    out = []

    def add(ln, why, code):
        out.append((ln, why, code))

    try:
        lx = ShLex(text, line)
        lx.seq(None)
    except Exception as e:  # неразобранное — находка, не пропуск
        return [(line, f'shell text not parsed: {e}', 'SH_PARSE')]
    cmds = lx.cmds
    for m in SH_SPECIAL_SET.finditer(text):
        add(line + text.count('\n', 0, m.start()), 'assignment to a name the shell or the program loader reads '
            '(${…:=}, (( … = )))', 'SH_CMD')
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
    def single(name):
        # имя присвоено ровно один раз и ничем больше не меняется
        if len(assigned.get(name, [])) != 1 or '[' in name:
            return False
        n = re.escape(name)
        return len(re.findall(r'(?<![\w$])' + n + r'\+?=', text)) == 1 and not re.search(
            r'\b(read|mapfile|readarray|getopts|unset|let)\b[^\n;|&]*\b' + n + r'\b|\bfor\s+' + n + r'\b'
            r'|printf\s+-v\s*' + n + r'\b|\$\{' + n + r':?[=?]|\(\([^)]*\b' + n + r'\b', text)

    consts = {}
    for name, ws_ in assigned.items():
        if single(name) and ws_[0]['lit']:
            consts[name] = ws_[0]['val'][len(name) + 1:]
    # Аудит M3310-R19-02: команда выполняется ровно один раз при каждом проходе сценария (once) — на верхнем уровне
    # или только в for по постоянному списку (и в тексте нет break/continue). Установку файла настроек засчитывает
    # только такая команда при включённом set -e (сбой установки останавливает сценарий).
    # Аудит M3310-R20-01: break/continue в любом месте команды (в том числе после обёртки builtin, command, exec) —
    # тело цикла может прерваться до установки.
    loopy = any(w['val'] in ('break', 'continue') for c in cmds for w in c['words'])
    for c in cmds:
        c['once'] = c['top'] and all(f[0] == 'f' for f in c['nest']) and not (loopy and c['nest'])
    state = {'errexit': False}
    # файлы /etc/tmpfiles.d/ и /etc/zavod/*.nft, поставленные из дерева; чужая запись: полные пути, ИМЕНА частей
    # пути, ОКОНЧАНИЯ частей пути. Вложенный текст оболочки (sh -c '…') делит их с внешним сценарием.
    if shared is None:
        shared = (set(), set(), set(), set())
    installed, tainted, names, suffixes = shared
    # Установщик: HERE — папка самого сценария, присвоена один раз; переменная цикла for — только по постоянным
    # именам файлов без «/» (так "$HERE/$u" — файл проверенного дерева).
    here_ok = len(re.findall(r'(?<![\w$])HERE\+?=', text)) == 1 and 'HERE=$(cd "$(dirname "$0")" && pwd)' in text
    forvars = set()
    for c in cmds:
        ws = c['words']
        if len(ws) > 3 and ws[0]['val'] == 'for' and ws[2]['val'] == 'in' and all(
                w['lit'] and '/' not in w['val'] and w['val'] not in ('.', '..') for w in ws[3:]):
            forvars.add(ws[1]['val'])
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
        # Запись кода во время работы (самопроверка R15): «> /tmp/kernel.mjs» создаёт файл с именем файла дерева
        # или с суффиксом кода, а запуск по имени его пропустит. Вывод в такой файл — находка.
        for op, w in c['redir']:
            b = w['val'].rsplit('/', 1)[-1]
            if op in ('>', '>>', '>|', '&>', '<>') and (b in SCRIPTS or b.endswith(CODE_EXT)):
                add(w['line'], f'shell writes code file {b.replace(X, "?")}', 'SH_EXEC')
        for j, w in enumerate(ws):
            if w['lit'] and w['val'].rsplit('/', 1)[-1] == 'tee':
                for t in ws[j + 1:]:
                    b = t['val'].rsplit('/', 1)[-1]
                    if b in SCRIPTS or b.endswith(CODE_EXT):
                        add(t['line'], f'tee writes code file {b.replace(X, "?")}', 'SH_EXEC')
        for j, w in enumerate(ws):
            v = w['val']
            if w['lit'] and v in ('-c', '--command') and j + 1 < len(ws) and not ws[j + 1]['lit']:
                add(ws[j + 1]['line'], f'text after {v} is not fixed', 'SH_DYN_C')
            if v.startswith('--command=') and not w['lit']:
                add(w['line'], 'text after --command= is not fixed', 'SH_DYN_C')
        # Аудит M3310-R16-03: среда программы. Присваивание перед программой (X=1 prog) — только IFS=… перед read;
        # export, declare, readonly, typeset — не используются и запрещены; имена, которые читает оболочка или
        # загрузчик (SH_SPECIAL), не присваиваются нигде.
        if ws and ws[0]['lit'] and ws[0]['val'] in ('export', 'declare', 'readonly', 'typeset'):
            add(ws[0]['line'], f'{ws[0]["val"]} changes the environment of programs', 'SH_CMD')
            return
        i0 = 1 if ws and ws[0]['lit'] and ws[0]['val'] == 'local' else 0
        na = i0
        while na < len(ws) and SH_ASSIGN.match(ws[na]['val']):
            name = ws[na]['val'].split('=', 1)[0].rstrip('+').split('[', 1)[0]
            if SH_SPECIAL.match(name) and not (name == 'IFS' and na + 1 < len(ws) and ws[na + 1]['val'] == 'read'):
                add(ws[na]['line'], f'assignment to {name}: the shell or the program loader reads it', 'SH_CMD')
            na += 1
        if i0:
            for w in ws[1:]:
                if not SH_ASSIGN.match(w['val']) and (not w['lit'] or SH_SPECIAL.match(w['val'])):
                    add(w['line'], 'local with a name that is not a plain fixed name', 'SH_CMD')
            return
        if 0 < na < len(ws) and not (ws[na]['val'] == 'read' and all(
                ws[q]['val'].startswith('IFS=') for q in range(na))):
            add(ws[0]['line'], 'program gets environment from an assignment before it', 'SH_CMD')
        if ws and ws[0]['lit'] and ws[0]['val'] in ('for', 'select', 'case'):
            # for/select ИМЯ in … присваивает ИМЯ (аудит M3310-R18-01, на опережение): имя — простое, не SH_SPECIAL
            if ws[0]['val'] != 'case' and len(ws) > 1 and (
                    not ws[1]['lit'] or not SH_NAME.match(ws[1]['val']) or SH_SPECIAL.match(ws[1]['val'])):
                add(ws[1]['line'], f'{ws[0]["val"]} loop writes {ws[1]["val"].replace(X, "?")}: not a plain name or '
                    'a name the shell reads', 'SH_CMD')
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
        if ws[k]['val'] not in psqlf:
            # Аудит M3310-R16: закрытый список программ; путь — только системные папки.
            if '/' in ws[k]['val'] and not unit_path(ws[k]['val'], SH_SYS_DIRS):
                add(ws[k]['line'], f'shell runs {ws[k]["val"]}: not from /usr/bin, /usr/sbin, /bin, /sbin', 'SH_CMD')
                return
            if p not in SH_PROGRAMS_OK and p not in ('eval', 'source', '.', 'xargs', 'parallel') and \
                    p not in SH_SHELLS and p not in SH_CODE and not p.startswith('python'):
                add(ws[k]['line'], f'shell runs {p}: program outside the closed list', 'SH_CMD')
                return
        writes(c, ws[k:])
        if p == 'set':
            for w in rest:
                if not (w['lit'] and (re.fullmatch(r'[-+][eux]+o?', w['val']) or w['val'] == 'pipefail')):
                    add(w['line'], f'set option {w["val"].replace(X, "?")} outside the closed list', 'SH_CMD')
            if any(w['lit'] and re.fullmatch(r'\+\w*e\w*', w['val']) for w in rest):
                state['errexit'] = False
            elif c['once'] and any(w['lit'] and re.fullmatch(r'-\w*e\w*', w['val']) for w in rest):
                state['errexit'] = True
            return
        # Аудит M3310-R17B-02: встроенные, которые записывают переменную по имени из своих слов (read ИМЯ,
        # printf -v ИМЯ, wait -p ИМЯ): опции — закрытый список, имя — постоянное и не из SH_SPECIAL.
        if p in ('wait', 'read', 'printf', 'cd', 'nft', 'systemd-tmpfiles') and ws[0]['val'] == 'command' and any(
                w['lit'] and w['val'] in ('-v', '-V') for w in ws[1:k]):
            return  # command -v nft только печатает путь программы
        if p == 'wait':  # номер процесса из переменной — только последним словом (иначе "$a" "$b" = -p ИМЯ)
            for j, w in enumerate(rest):
                if not (w['lit'] and (w['val'] in WAIT_OPTS or w['val'].isdigit()) or
                        not w['lit'] and j == len(rest) - 1):
                    add(w['line'], f'wait word {w["val"].replace(X, "?")} outside the closed list', 'SH_CMD')
            return
        if p == 'read':
            opts_ok, j = READ_OPTS, 0
            while j < len(rest) and (not rest[j]['lit'] or rest[j]['val'].startswith('-')):
                if not rest[j]['lit'] or rest[j]['val'] not in opts_ok:
                    add(rest[j]['line'], f'{p} option {rest[j]["val"].replace(X, "?")} outside the closed list', 'SH_CMD')
                    return
                j += 1
            for w in rest[j:] if p == 'read' else []:
                if not w['lit'] or not SH_NAME.match(w['val']) or SH_SPECIAL.match(w['val']):
                    add(w['line'], f'read into {w["val"].replace(X, "?")}: not a plain name or a name the shell '
                        'reads', 'SH_CMD')
            return
        if p == 'printf' and rest and (not rest[0]['lit'] or rest[0]['val'].startswith('-')):
            add(rest[0]['line'], 'printf option (-v writes a variable) or a format that is not fixed', 'SH_CMD')
            return
        # Аудит M3310-R18-01: %n в формате пишет число в переменную с именем из аргумента (printf '%n' PATH). Любое
        # «%…n» (с флагами, шириной, точностью, длиной) и коды \0-7, \x, \u, \U в формате — находка, без исключений.
        if p == 'printf' and rest and (PRINTF_N.search(rest[0]['val'].replace('%%', '')) or
                                       re.search(r'\\[0-7xuU]', rest[0]['val'])):
            add(rest[0]['line'], 'printf format with %n (writes a variable by name) or a coded character', 'SH_CMD')
            return
        # Аудит M3310-R17B-03: cd в папку кода — тогда запись по относительному пути попадёт туда.
        if p == 'cd':
            for w in rest:
                if code_dir(w):
                    add(w['line'], 'cd into a folder of code or start settings', 'SH_EXEC')
            return
        # Аудит M3310-R17B-05: nft и systemd-tmpfiles читают файл настроек. Разрешено: nft list …; nft [-c] -f файл
        # *.nft проверенного дерева в /etc/zavod/; systemd-tmpfiles --create один файл из /etc/tmpfiles.d/ (туда
        # оболочка пишет только файлы дерева, см. writes). Остальное (nft -f /tmp/…, nft flush, --prefix …) — находка.
        if p == 'nft':
            vals = [w['val'] if w['lit'] else X for w in rest]
            if vals[:1] == ['list'] and X not in vals:
                return
            fi = vals.index('-f') if '-f' in vals else None
            # Аудит M3310-R19-03: файл — только тот, что этот же сценарий раньше поставил ровно в этот путь из файла
            # своей папки дерева (как у systemd-tmpfiles ниже), а не любой файл дерева с тем же именем.
            if not (fi is not None and vals[:fi] in ([], ['-c']) and len(vals) == fi + 2 and
                    vals[-1].startswith('/etc/zavod/') and vals[-1].endswith('.nft') and from_tree_file(vals[-1])):
                add(ws[k]['line'], 'nft outside the closed forms (list …; -f a checked *.nft this script installed '
                    'into /etc/zavod/)', 'SH_EXEC')
            return
        if p == 'systemd-tmpfiles':
            vals = [w['val'] if w['lit'] else X for w in rest]
            # Аудит M3310-R18-02, M3310-R19-02: файл — только тот, что этот же сценарий раньше поставил командой
            # install/cp из "$HERE/*.tmpfiles.conf" своей папки дерева (его строки проверяет data_findings), причём
            # установка выполняется всегда (once, set -e), а других записей в этот путь нет; иначе — находка.
            if not (len(vals) == 2 and vals[0] == '--create' and from_tree_file(vals[1])):
                add(ws[k]['line'], 'systemd-tmpfiles outside the closed form (--create a checked tree file this '
                    'script installed into /etc/tmpfiles.d/)', 'SH_EXEC')
            return
        if p in CLOSED_OPTS:
            opts_closed(p, rest)
        if p == 'systemd-analyze':
            subs = [w for w in rest if not (w['lit'] and w['val'].startswith('-'))]
            if any(w['lit'] and w['val'].startswith('-') and w['val'] not in ANALYZE_OPTS for w in rest) or \
                    not subs or not subs[0]['lit'] or subs[0]['val'] not in ANALYZE_CMDS:
                add(ws[k]['line'], 'systemd-analyze outside the closed forms (verify, security; --man=no, '
                    '--no-pager)', 'SH_CMD')
            return
        if p == 'awk':
            awk_ok(c, rest)
            return
        if p == 'sed':
            sed_ok(rest)
            return
        if p == 'systemctl':
            sub, now, units = None, False, []
            j = 0
            while j < len(rest):
                v = rest[j]['val']
                if v.startswith('-'):
                    key, eq, _ = v.partition('=') if v.startswith('--') else (v, '', '')
                    if not rest[j]['lit'] or key not in SYSTEMCTL_OPTS:
                        add(rest[j]['line'], f'systemctl option {v.replace(X, "?")} outside the closed list', 'SH_CMD')
                    now = now or key == '--now'
                    j += 1 + (0 if eq else SYSTEMCTL_OPTS.get(key, 0))
                    continue
                if sub is None:
                    sub = v
                    if not rest[j]['lit'] or v not in SYSTEMCTL_CMDS:
                        add(rest[j]['line'], f'systemctl {v.replace(X, "?")}: command outside the closed list', 'SH_CMD')
                else:
                    units.append(rest[j])
                j += 1
            # --now может стоять и после имён юнитов, поэтому имена проверяются после разбора всей команды
            for w in units:
                if sub in SYSTEMCTL_START:
                    unit_use(w)
                elif sub in SYSTEMCTL_STOP or sub in SYSTEMCTL_NOW and now:
                    unit_use(w, 'stops')
            return
        if p == 'find':
            j = 0
            while j < len(rest):
                v = rest[j]['val']
                if v in ('-exec',) and rest[j]['lit']:
                    end = next((q for q in range(j + 1, len(rest)) if rest[q]['val'] in (';', '+')), len(rest))
                    one(c, rest[j + 1:end])
                    j = end + 1
                    continue
                if v.startswith('-') and len(v) > 1:
                    if not rest[j]['lit'] or v not in FIND_OPTS:
                        add(rest[j]['line'], f'find option {v.replace(X, "?")} outside the closed list', 'SH_CMD')
                    j += 1 + FIND_OPTS.get(v, 0)
                    continue
                j += 1
            return
        if p == 'flock':
            j = 0
            while j < len(rest) and rest[j]['val'].startswith('-'):
                v = rest[j]['val']
                if not rest[j]['lit'] or v not in FLOCK_OPTS:
                    add(rest[j]['line'], f'flock option {v.replace(X, "?")} outside the closed list', 'SH_CMD')
                j += 1 + FLOCK_OPTS.get(v, 0)
            if j + 1 < len(rest):
                one(c, rest[j + 1:])
            return
        if p == 'ip':
            if rest and (not rest[0]['lit'] or rest[0]['val'].startswith('-')):
                add(rest[0]['line'], 'ip option before the object (-batch, -netns …) outside the closed list', 'SH_CMD')
            elif len(rest) > 3 and rest[0]['val'] == 'netns' and rest[1]['val'] == 'exec':
                one(c, rest[3:])
            return
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
                if at + 1 < len(rest) and rest[at + 1]['lit']:
                    nested(rest[at + 1]['val'], rest[at + 1]['line'])
                elif at + 1 < len(rest) and not rest[at + 1]['lit']:
                    add(rest[at + 1]['line'], f'{p} -c with text that is not fixed', 'SH_DYN_C')
            else:
                files_ = [w for w in rest if not (w['lit'] and w['val'].startswith('-'))]
                if files_ and not any(w['val'] == '-s' for w in opts):
                    script_ok(files_[0], 'sh', p)
                if not files_ or any(w['val'] == '-s' for w in opts):
                    for h in stdin_ok(c, p, 'SH_INLINE'):
                        nested(h['val'], h['line'])
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
                if script:
                    script_ok(rest[j], 'py', p)
                break
            if code_text is None and not script:
                for h in stdin_ok(c, 'python', 'SH_INLINE'):
                    code_text = (h['val'], h['line'])
            if code_text:
                for ln, why, _ in py_findings(path, code_text[0]):
                    add(code_text[1] + ln - 1, *py_rule(why))
        elif p in SH_CODE:
            if any(w['lit'] and w['val'] in ('-e', '-E', '-p', '-r', '--eval', '--print', '-', '-x') or
                   w['val'].startswith(('--eval=', '--print=')) for w in rest) or not rest:
                add(ws[k]['line'], f'{p} runs inline code', 'SH_INLINE')
            elif p in ('node', 'nodejs'):
                first = next((w for w in rest if not (w['lit'] and w['val'].startswith('-'))), None)
                if first is not None:
                    script_ok(first, 'js', p)
        else:
            # Программа за ещё одним уровнем исполнения (аудит M3310-R14-04): docker/ssh/kubectl … запускают
            # программу из своих аргументов. psql в любом месте списка проверяется как psql; оболочка, python, node
            # у исполнителя из SH_REMOTE — по своим правилам; текст команды одним словом (ssh host 'psql -f x') —
            # разбирается как сценарий; не постоянное слово у ssh (вся команда — текст) — находка.
            remote = p in SH_REMOTE
            if p in ('ssh', 'scp', 'sftp'):
                # Аудит M3310-R15B-05: опция ssh сама бывает командой (-o ProxyCommand=psql -f …, LocalCommand,
                # KnownHostsCommand, Match exec); файл настроек -F может нести те же опции. Такие опции — находка.
                for j, w in enumerate(rest):
                    v = w['val'] if w['lit'] else X
                    opt = v[2:] if v.startswith('-o') and len(v) > 2 else \
                        ((rest[j + 1]['val'] if rest[j + 1]['lit'] else X) if v == '-o' and j + 1 < len(rest) else None)
                    if v.startswith('-F'):
                        add(w['line'], f'{p} reads options from a settings file (-F)', 'SH_CMD')
                    if opt is not None:
                        key = re.split(r'[=\s]', opt.strip(), maxsplit=1)[0].lower()
                        if X in opt or key in SSH_EXEC_OPTS:
                            add(w['line'], f'{p} option {key.replace(X, "?")} runs a command', 'SH_CMD')
            for j, w in enumerate(rest):
                if not w['lit']:
                    if p == 'ssh':
                        add(w['line'], 'ssh runs a remote command built from substitutions', 'SH_CMD')
                    continue
                b = os.path.basename(w['val'])
                if b == 'psql' or remote and (b in SH_SHELLS or b.startswith('python') or b in SH_CODE):
                    one(c, rest[j:])
                    break
                if remote and re.search(r'\s', w['val']):
                    nested(w['val'], w['line'])

    def nested(s, ln):
        # Аудит M3310-R16-04: вложенный текст оболочки глубже предела — находка (закрыто при отказе), не пропуск.
        if depth >= 4:
            add(ln, 'shell text nested deeper than the limit', 'SH_PARSE')
        else:
            out.extend(sh_findings(path, s, ln, depth + 1, shared))

    def code_dir(w):
        v = w['val']
        m_ = re.match(r'^"?\$\{?([A-Za-z_]\w*)\}?', w['raw'])
        if v.startswith(X) and m_ and m_.group(1) in consts:
            v = consts[m_.group(1)] + v[1:]
        v = re.sub(r'/+', '/', v)
        if '..' in v.split('/'):  # аудит M3310-R17B-03: /tmp/../etc/… — это /etc/…; «..» в пути записи — находка
            return True
        v = norm_path(v) + ('/' if v.endswith('/') else '')
        return v.startswith(CODE_DIRS) or v.rstrip('/') + '/' in CODE_DIRS

    def writes(c, ws_):
        # Запись в папки кода и настроек запуска (CODE_DIRS): перенаправление, tee, dd of=, touch, truncate — всегда
        # находка; install/cp/mv/ln — находка, кроме install (cp) файлов проверенного дерева "$HERE/…" установщиком
        # и install -d (папка).
        # Аудит M3310-R20-02: КАЖДЫЙ путь записи помечается (taint) — не только путь в CODE_DIRS (см. taint).
        state['c'] = c
        for op, w in c['redir']:
            # >&ФАЙЛ (не номер потока и не «-») — тоже запись в файл
            if op in ('>', '>>', '>|', '&>', '<>') or op == '>&' and not (
                    w['lit'] and re.fullmatch(r'\d+-?|-', w['val'])):
                taint(w)
                if code_dir(w):
                    add(w['line'], 'shell writes into a folder of code or start settings', 'SH_EXEC')
        p_ = os.path.basename(ws_[0]['val'])
        args = ws_[1:]
        # touch меняет только время файла, не его байты: не помечает
        if p_ in ('tee', 'truncate', 'fallocate', 'mkfs.ext4'):
            # значение опции (размер, метка) — не путь; опция вне списка — её значение помечается как путь
            vopt = {'truncate': ('-s', '-r', '--size', '--reference'), 'fallocate': ('-o', '-l', '--offset', '--length'),
                    'mkfs.ext4': ('-b', '-C', '-d', '-E', '-e', '-g', '-G', '-i', '-I', '-J', '-L', '-l', '-m', '-M',
                                  '-N', '-o', '-O', '-r', '-t', '-T', '-U')}.get(p_, ())
            for j_, w in enumerate(args):
                if not (w['lit'] and w['val'].startswith('-')) and not (
                        j_ and args[j_ - 1]['lit'] and args[j_ - 1]['val'] in vopt):
                    taint(w)
        elif p_ == 'dd':
            for w in args:
                if w['val'].startswith('of=') or not w['lit']:
                    taint({'val': w['val'][3:] if w['val'].startswith('of=') else w['val'], 'lit': w['lit'],
                           'raw': w['raw'].replace('of=', '', 1)})
        elif p_ in SH_OUT_OPTS:
            # опция, значение которой — путь записи: --опция=ПУТЬ, --опция ПУТЬ, -о ПУТЬ, -оПУТЬ и -ао… (буква опции в
            # группе коротких опций: остаток группы или следующее слово)
            oo = SH_OUT_OPTS[p_]
            for j_, w in enumerate(args):
                v_ = w['val']
                if v_.startswith('--'):
                    if v_.partition('=')[0] in oo and '=' in v_:
                        taint({'val': v_.partition('=')[2], 'lit': w['lit'], 'raw': w['raw'].partition('=')[2]})
                    elif v_ in oo and j_ + 1 < len(args):
                        taint(args[j_ + 1])
                elif v_.startswith('-') and len(v_) > 1:
                    k_ = next((k for k in range(1, len(v_)) if '-' + v_[k] in oo), None)
                    if k_ is not None and k_ + 1 < len(v_):
                        taint({'val': v_[k_ + 1:], 'lit': w['lit'], 'raw': w['raw'][k_ + 1:] if w['lit'] else ''})
                    elif k_ is not None and j_ + 1 < len(args):
                        taint(args[j_ + 1])
            # usermod -m переносит прежнюю домашнюю папку (путь неизвестен) в новую
            if p_ == 'usermod' and any(w['val'] == '--move-home' or re.fullmatch(r'-[A-Za-z]*m[A-Za-z]*', w['val'])
                                       for w in args):
                tainted.add('*')
        if p_ in ('tee', 'touch', 'truncate'):
            bad = [w for w in args if not w['val'].startswith('-') and code_dir(w)]
        elif p_ == 'dd':
            bad = [w for w in args if w['val'].startswith('of=') and
                   code_dir({'val': w['val'][3:], 'raw': w['raw'].replace('of=', '', 1)})]
        elif p_ in ('install', 'cp', 'mv', 'ln'):
            files_ = [w for w in args if not (w['lit'] and w['val'].startswith('-'))]
            opts_ = [w['val'] for w in args if w['lit'] and w['val'].startswith('-')]
            j = 0
            while j < len(args):  # значения опций -o -g -m -t -S у install/cp/mv/ln не файлы
                if args[j]['lit'] and args[j]['val'] in ('-o', '-g', '-m', '-S', '--suffix') and j + 1 < len(args):
                    files_ = [w for w in files_ if w is not args[j + 1]]
                    j += 1
                j += 1
            if p_ == 'mv':  # перенос из любого пути тоже меняет файл, который потом прочтут
                for w in files_[:-1]:
                    taint(w)
            # ссылка (ln, cp -s, cp -l) даёт файлу второе имя: запись по любому имени меняет поставленный файл
            if p_ == 'ln' or p_ == 'cp' and any(o in ('--link', '--symbolic-link') or not o.startswith('--') and (
                    's' in o or 'l' in o) for o in opts_):
                tainted.add('*')
            if any(o.startswith('-t') or o.startswith('--target') for o in opts_):
                bad = [w for w in args if w['val'].startswith(('-t', '--target'))]
                tainted.add('*')
            elif p_ == 'install' and '-d' in opts_:
                bad = []
            elif p_ == 'ln' and any(code_dir(w) for w in files_):
                # ссылка на файл или папку кода даёт путь записи вне CODE_DIRS (аудит M3310-R17B-03, на опережение)
                bad = [w for w in files_ if code_dir(w)]
            elif files_ and code_dir(files_[-1]):
                from_tree = p_ in ('install', 'cp') and here_ok and all(
                    re.match(r'^"\$HERE/[^"$`\\/]+"$', w['raw']) or (
                        re.match(r'^"\$HERE/\$([a-z_]+)"$', w['raw']) and
                        re.match(r'^"\$HERE/\$([a-z_]+)"$', w['raw']).group(1) in forvars) for w in files_[:-1])
                bad = [] if from_tree else [files_[-1]]
                dest = files_[-1]
                src_ = re.match(r'^"\$HERE/([^"$`\\/]+)"$', files_[0]['raw']) if len(files_) == 2 else None
                # Аудит M3310-R19-02/03: установка засчитывается, только если выполняется всегда (once, set -e) и
                # источник — файл папки самого сценария в дереве; иначе путь назначения помечен как чужая запись.
                good = from_tree and c['once'] and state['errexit'] and src_ is not None and \
                    posixpath.join(posixpath.dirname(path), src_.group(1)) in TREE_PATHS
                if good and dest['lit'] and norm_path(dest['val']) == dest['val'] and (
                        src_.group(1).endswith('.tmpfiles.conf') and dest['val'].startswith('/etc/tmpfiles.d/') or
                        src_.group(1).endswith('.nft') and dest['val'].startswith('/etc/zavod/') and
                        dest['val'].endswith('.nft')):
                    installed.add(dest['val'])
                else:
                    taint(dest)
                if from_tree and c['once'] and state['errexit'] and len(files_) == 2:
                    unit_install(files_[0], dest, c)
            else:
                bad = []
                if files_:
                    taint(files_[-1])
        else:
            bad = []
        for w in bad:
            add(w['line'], f'{p_} writes into a folder of code or start settings', 'SH_EXEC')
            taint(w)

    def taint(w):
        # Запись в путь, который потом может прочесть nft или systemd-tmpfiles. Аудит M3310-R20-02: помечается путь
        # любого начала. Постоянный полный путь — сам путь. Путь из подстановки — по постоянному хвосту после
        # последней подстановки: «…/ИМЯ» — ИМЯ части пути; «…ОКОНЧАНИЕ» без «/» — ОКОНЧАНИЕ части пути. Путь без
        # подстановки, но относительный (зависит от cd) или с «..» — ИМЯ последней части. Нет хвоста, ИМЯ «.» или
        # «..», шаблон *?[ — любой путь.
        ex = expand(w.get('raw', ''))
        if ex is not None:
            for p in ex:  # «папка/X» — любая часть пути в постоянной папке: помечена вся папка
                taint({'val': p[:-2] if p.endswith('/' + X) else p, 'lit': True})
            return
        v = w['val']
        m_ = re.match(r'^"?\$\{?([A-Za-z_]\w*)\}?', w.get('raw', ''))
        if v.startswith(X) and m_ and m_.group(1) in consts:
            v = consts[m_.group(1)] + v[1:]
        v = re.sub(r'/+', '/', v)
        tail = v.rsplit(X, 1)[-1]
        b = tail.rsplit('/', 1)[-1]
        if re.search(r'[*?\[]', v):
            tainted.add('*')
        elif X not in v and v.startswith('/') and '..' not in v.split('/'):
            tainted.add(norm_path(v))
        elif (X not in v or '/' in tail) and b not in ('', '.', '..'):
            names.add(b)
        elif X in v and '/' not in tail and tail:
            suffixes.add(tail)
        else:
            tainted.add('*')

    def expand(raw):
        # Путь записи "текст$ИМЯ…" в двойных кавычках без других подстановок: ИМЯ — постоянная переменная (её текст),
        # переменная объемлющего for по постоянным именам без «/» (каждое имя) или последняя часть пути — переменная,
        # присвоенная один раз выводом systemd-escape без -u (в выводе нет «/», «.» и «..»; X). Ответ — варианты пути
        # (не больше 64); иначе None.
        if not re.fullmatch(r'"[^"\\`]*"', raw) or '$' not in raw:
            return None
        bits = re.split(r'\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))', raw[1:-1])
        alts = ['']
        for k in range(0, len(bits), 3):
            if '$' in bits[k]:
                return None
            alts = [a + bits[k] for a in alts]
            if k + 1 >= len(bits):
                break
            name = bits[k + 1] or bits[k + 2]
            fr = next((f for f in reversed(state['c']['nest']) if f[0] == 'f' and f[1] == name), None)
            a0 = assigned[name][0]['raw'][len(name) + 1:] if single(name) else ''
            if name in consts:
                vals = [consts[name]]
            elif fr:
                vals = list(fr[2])
            elif k + 4 == len(bits) and bits[-1] == '' and re.fullmatch(r'"?\$\(systemd-escape\s[^()`]*\)"?', a0) \
                    and all(o in ('-p', '--path') or o.startswith(('--suffix=', '--template='))
                            for o in a0.split() if o.startswith('-')):
                vals = [X]
            else:
                return None
            alts = [a + v for a in alts for v in vals]
        if len(alts) > 64 or any(X in a and not (a.endswith('/' + X) and a.count(X) == 1) for a in alts):
            return None
        return alts

    def from_tree_file(v):
        # путь поставлен из дерева, и запись сценария его не меняет: ни сам путь, ни папка на пути не помечены, ни
        # одна часть пути не равна помеченному ИМЕНИ и не кончается помеченным ОКОНЧАНИЕМ
        if not (v in installed and '*' not in tainted and norm_path(v) == v):
            return False
        parts = v.split('/')
        return not any('/'.join(parts[:k]) in tainted or parts[k - 1] in names or
                       parts[k - 1].endswith(tuple(suffixes)) for k in range(2, len(parts) + 1))

    def unit_install(src, dest, c):
        # Аудит M3310-R19-01: юнит, который сценарий ставит всегда из файла своей папки дерева в /etc/systemd/system/:
        # постоянное имя; for u in … — каждое имя списка; "$ИМЯ" (ИМЯ присвоено один раз) — ('$', сценарий, ИМЯ).
        d = posixpath.dirname(path)
        m_src = re.match(r'^"\$HERE/([^"$`\\/]+)"$', src['raw'])
        m_var = re.match(r'^"\$HERE/\$([a-z_]+)"$', src['raw'])
        m_dv = re.match(r'^"' + re.escape(SD_DIR) + r'\$\{?([A-Za-z_]\w*)\}?"$', dest['raw'])
        if dest['lit'] and dest['val'].startswith(SD_DIR) and norm_path(dest['val']) == dest['val'] and \
                '/' not in dest['val'][len(SD_DIR):] and m_src and posixpath.join(d, m_src.group(1)) in TREE_PATHS:
            UNITS_INSTALLED.add(dest['val'][len(SD_DIR):])
        elif m_dv and m_var and m_var.group(1) == m_dv.group(1):
            fr = next((f for f in reversed(c['nest']) if f[0] == 'f' and f[1] == m_var.group(1)), None)
            for v in fr[2] if fr else ():
                if posixpath.join(d, v) in TREE_PATHS:
                    UNITS_INSTALLED.add(v)
        elif m_dv and m_src and posixpath.join(d, m_src.group(1)) in TREE_PATHS and single(m_dv.group(1)):
            UNITS_INSTALLED.add(('$', path, m_dv.group(1)))

    def unit_use(w, verb='starts'):
        # имя юнита у systemctl start/restart/reload/enable (и у остановки, аудит M3310-R21-01): постоянное (без
        # шаблонов поиска *?[), экземпляр шаблона имя@….service (экземпляр выбирает только аргумент юнита дерева) или
        # "$ИМЯ", присвоенное один раз; у остановки ещё имя@*.service — все экземпляры шаблона
        if w['lit']:
            u = w['val'] if '.' in w['val'] else w['val'] + '.service'
            m_t = re.fullmatch(r'([A-Za-z][\w:.-]*)@(?:[^/*?\[]+|\*)(\.service)' if verb == 'stops' else
                               r'([A-Za-z][\w:.-]*)@[^/*?\[]+(\.service)', u)
            key = m_t.group(1) + '@' + m_t.group(2) if m_t else None if re.search(r'[*?\[/]', u) else u
        else:
            m_t = re.fullmatch(r'"([A-Za-z][\w:.-]*)@[^"/`\\*?\[]+(\.service)"', w['raw'])
            m_v = re.fullmatch(r'"\$\{?([A-Za-z_]\w*)\}?"', w['raw'])
            key = m_t.group(1) + '@' + m_t.group(2) if m_t else \
                ('$', path, m_v.group(1)) if m_v and single(m_v.group(1)) else None
        if key is None:
            add(w['line'], f'systemctl {verb} unit {w["val"].replace(X, "?")}: name is not fixed', 'SH_EXEC')
        elif key not in SYSTEM_UNITS_OK:
            UNITS_STARTED.append((path, w['line'], key, verb))

    def opts_closed(p, rest):
        # Аудит M3310-R21-02: опции программы из CLOSED_OPTS — только из её закрытого списка: короткие (и в группе
        # -ab, -oПУТЬ), длинные целиком (--опция=ЗНАЧЕНИЕ или --опция ЗНАЧЕНИЕ); после «--» опций нет. У sort слово из
        # подстановки с неизвестным первым знаком вне значения опции — находка: оно может стать опцией.
        s0, s1, l0, l1 = CLOSED_OPTS[p]
        j = 0
        while j < len(rest):
            w = rest[j]
            v = w['val']

            def fixed(n):
                # первые n знаков слова написаны буквами, а не взяты из подстановки
                return w['lit'] or X not in v[:n] and w['raw'].startswith(v[:n])
            if v == '--' and w['lit']:
                return
            if v.startswith('--'):
                key, eq, _ = v.partition('=')
                if not fixed(len(key) + len(eq)) or key not in l0 | l1 or key in l0 and eq:
                    add(w['line'], f'{p} option {key.replace(X, "?")} outside the closed list', 'SH_CMD')
                j += 2 if key in l1 and not eq else 1
                continue
            if v.startswith('-') and len(v) > 1:
                step = 1
                for q in range(1, len(v)):
                    if not fixed(q + 1) or v[q] not in s0 + s1:
                        add(w['line'], f'{p} option -{v[q].replace(X, "?")} outside the closed list', 'SH_CMD')
                        break
                    if v[q] in s1:
                        step = 1 if q + 1 < len(v) else 2
                        break
                j += step
                continue
            if p == 'sort' and not w['lit'] and v[:1] == X:
                add(w['line'], 'sort word from a substitution may become an option (--compress-program runs a '
                    'program)', 'SH_CMD')
            j += 1

    def awk_ok(c, rest):
        # awk запускает программы (system(), "cmd" | getline, print | "cmd"), пишет файлы (print > "f") и читает
        # программу из файла (-f) или подключает её (@include, @load). Разрешён только постоянный текст без этого.
        j = 0
        while j < len(rest) and rest[j]['val'].startswith('-'):
            if not rest[j]['lit'] or rest[j]['val'] not in ('-v', '-F'):
                add(rest[j]['line'], f'awk option {rest[j]["val"].replace(X, "?")} outside the closed list', 'SH_INLINE')
                return
            j += 2
        if j >= len(rest) or not rest[j]['lit']:
            add(rest[j]['line'] if j < len(rest) else c['line'], 'awk program is not fixed text', 'SH_INLINE')
            return
        t = re.sub(r'"(?:[^"\\]|\\.)*"', '""', rest[j]['val'])
        t = re.sub(r'(?<![\w)\]$])/(?:[^/\\\n]|\\.)*/', '//', t).replace('||', ' ')
        if re.search(r'\bsystem\s*\(|\bgetline\b|\||@\s*(include|load|namespace)|\bprintf?\b[^;{}]*>', t):
            add(rest[j]['line'], 'awk program runs commands or writes files', 'SH_INLINE')

    def sed_ok(rest):
        # sed выполняет команды (e, s///e) и пишет файлы (w, s///w, -i); разрешены -n, -E, -r, -e и сценарий из
        # одной команды s или d/p/q с адресом (SED_SCRIPT).
        scripts, j, e_ = [], 0, False
        while j < len(rest):
            w = rest[j]
            if w['val'].startswith('-') and w['val'] != '-':
                if not w['lit'] or w['val'] not in ('-n', '-E', '-r', '-e'):
                    add(w['line'], f'sed option {w["val"].replace(X, "?")} outside the closed list', 'SH_INLINE')
                    return
                if w['val'] == '-e':
                    e_ = True
                    if j + 1 < len(rest):
                        scripts.append(rest[j + 1])
                    j += 1
            elif not e_ and not scripts:
                scripts.append(w)
            j += 1
        for w in scripts:
            if not w['lit'] or not SED_SCRIPT.match(w['val']):
                add(w['line'], 'sed script outside the closed form (one s command, or d/p/q)', 'SH_INLINE')

    def script_ok(w, kind, prog):
        # Файл, который запускает интерпретатор (аудит M3310-R14-05): python3 worker.data исполняет текст без #!
        # под любым суффиксом. Разрешён только файл проверенного дерева своего вида (по имени файла).
        b = w['val'].rsplit('/', 1)[-1]
        if not b or X in b or '$' in b or '`' in b:
            add(w['line'], f'{prog} runs a file whose name is not fixed', 'SH_EXEC')
        elif SCRIPTS.get(b) != kind:
            add(w['line'], f'{prog} runs {b}: not a checked {kind} file of the scanned tree', 'SH_EXEC')
        elif not unit_path(w['val'], UNIT_TREE_DIRS):
            # Самопроверка R15 и аудит M3310-R15B-02: /tmp/kernel.mjs, ../../tmp/zavod-gate.py и ./zavod-gate.py после
            # cd носят имя файла дерева, но это другой файл. Разрешён только полный путь в папке установки.
            add(w['line'], f'{prog} runs {b} not by its full path in the install folder', 'SH_EXEC')

    # Аудит M3310-R20-02: запись в любом месте сценария (и ниже nft -f по тексту: функция, цикл) снимает разрешение.
    # Первый проход собирает пути установки и записи, его находки не берутся; второй проход проверяет.
    n0, k0 = len(UNITS_STARTED), len(out)
    for c in cmds:
        one(c, c['words'])
    del UNITS_STARTED[n0:], out[k0:]
    state['errexit'] = False
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


EXEC_MAGIC = (b'#!', b'PK\x03\x04', b'PK\x05\x06', b'\x7fELF', b'MZ', b'\x1f\x8b', b'BZh', b'\xfd7zXZ',
              b"7z\xbc\xaf'\x1c", b'\x00asm', b'\xca\xfe\xba\xbe', b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe')


def exec_content(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(8)
            first = head + f.readline(200)
    except OSError:
        return False
    # правила сети nft (*.nft, ровно «#!/usr/sbin/nft -f»): язык правил фильтра, программ и кода не запускает
    if path.endswith('.nft') and first == b'#!/usr/sbin/nft -f\n':
        return False
    # .pyc без суффикса: 2 байта номера версии (старший 0x0c..0x0e), затем \r\n
    return head.startswith(EXEC_MAGIC) or len(head) >= 4 and head[1] in (0x0c, 0x0d, 0x0e) and head[2:4] == b'\r\n'


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
# Находки, которые строка разрешений не снимает никогда: cwd и среда загрузки кода у запуска (аудит M3310-R15B-07),
# строка запуска юнита через оболочку «|» (аудит M3310-R16-01).
NO_ALLOW = {'CHILD_OPTS', 'UNIT_SHELL'}
# Находки, разрешение которых требует закрепить файл суммой (PIN): запуск программ и кода.
PIN_RULES = {'CHILD', 'CHILD_IMPORT', 'PY_RUN'}
UNCHECKED_EXT = ('.ts', '.mts', '.cts', '.tsx', '.jsx', '.node', '.wasm', '.so', '.dll', '.dylib', '.pyc', '.pyo',
                 '.pyw', '.pyz', '.pth', '.cmd', '.bat', '.ps1', '.exe', '.pyd', '.zip', '.egg', '.whl', '.jar',
                 '.tar', '.gz', '.tgz', '.bz2', '.xz', '.7z')
# Закрытый список файлов дерева (аудит M3310-R14-05): кроме проверяемого кода (*.py, *.sh, *.mjs, *.js, *.cjs и
# сценариев с #!…python3 или #!…sh) — только эти виды данных и настроек. Любой другой файл (*.txt, *.data …) — находка
# FORMAT: текст программы без #! под чужим суффиксом исполняет «python3 файл».
DATA_EXT = ('.conf', '.mount', '.nft', '.path', '.rules', '.service', '.slice', '.timer')
UNIT_EXT = ('.service', '.mount', '.timer', '.path', '.slice')
UNIT_PROGRAMS = {'nft'}
# Аудит M3310-R16-05: закрытый список разделов и ключей юнита (то, что юниты проекта используют на деле).
# RootDirectory, RootImage, BindPaths, ExecSearchPath, ExecStartPre, LoadCredential … — вне списка, находка UNIT_EXEC.
UNIT_SECTIONS = {'Unit', 'Service', 'Install', 'Mount', 'Timer', 'Path', 'Slice'}
UNIT_KEYS = {
    'AccuracySec', 'After', 'AmbientCapabilities', 'Before', 'CPUQuota', 'CapabilityBoundingSet',
    'DefaultDependencies', 'Description', 'DynamicUser', 'Environment', 'ExecStart', 'ExecStopPost', 'Group',
    'IPAddressAllow', 'IPAddressDeny', 'InaccessiblePaths', 'LimitFSIZE', 'LimitNOFILE', 'LockPersonality',
    'MemoryDenyWriteExecute', 'MemoryMax', 'NoNewPrivileges', 'OnBootSec', 'OnCalendar', 'OnFailure', 'OnSuccess',
    'OnUnitActiveSec', 'Options', 'PathChanged', 'PrivateDevices', 'PrivateIPC', 'PrivateNetwork', 'PrivateTmp',
    'ProcSubset', 'ProtectClock', 'ProtectControlGroups', 'ProtectHome', 'ProtectHostname', 'ProtectKernelLogs',
    'ProtectKernelModules', 'ProtectKernelTunables', 'ProtectProc', 'ProtectSystem', 'ReadWritePaths',
    'RemainAfterExit', 'Requires', 'RequiresMountsFor', 'Restart', 'RestartSec', 'RestrictAddressFamilies',
    'RestrictNamespaces', 'RestrictRealtime', 'RestrictSUIDSGID', 'RuntimeDirectory', 'RuntimeDirectoryMode',
    'RuntimeMaxSec', 'Slice', 'StartLimitIntervalSec', 'StateDirectory', 'StateDirectoryMode',
    'SystemCallArchitectures', 'SystemCallFilter', 'TasksMax', 'TemporaryFileSystem', 'TimeoutStartSec', 'Type',
    'UMask', 'Unit', 'User', 'WantedBy', 'Wants', 'What', 'Where', 'WorkingDirectory'}
# Куда служба может писать (ReadWritePaths) и куда монтировать (Where): только папки данных, не папки кода.
UNIT_DATA_DIRS = ('/run/zavod', '/var/lib/zavod/', '/var/lib/private/zagent')
CODE_EXT = ('.py', '.mjs', '.js', '.cjs', '.sh')
# Папки службы (самопроверка R15): файл дерева служба запускает только из папки установки, программу системы — из
# /usr/bin или /usr/sbin; /tmp/zagent-session с именем файла дерева — находка.
UNIT_TREE_DIRS = ('/usr/local/lib/zavod/', '/etc/zavod/')
UNIT_SYS_DIRS = ('/usr/bin/', '/usr/sbin/')


def unit_path(p, dirs):
    return p.startswith(dirs) and '/../' not in p and '/./' not in p and not re.search(r'[%$`\\]', p)


def unit_findings(text):
    """Строки Exec…= службы systemd (аудит M3310-R14-05): программа — сценарий проверенного дерева или nft -f правил
    из дерева; интерпретатор — только с файлом дерева своего вида, без -c, -m, -e и чтения со входа."""
    out = []
    for i, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith(('#', ';')):
            continue
        if s.endswith('\\'):
            out.append((i, 'unit line continues on the next line', 'UNIT_EXEC'))
            continue
        sec = re.fullmatch(r'\[([^\]]*)\]', s)
        if sec:
            if sec.group(1) not in UNIT_SECTIONS:
                out.append((i, f'unit section [{sec.group(1)}] outside the closed list', 'UNIT_EXEC'))
            continue
        kv = re.fullmatch(r'([A-Za-z][A-Za-z0-9]*)\s*=\s*(.*)', s)
        if not kv or kv.group(1) not in UNIT_KEYS:
            out.append((i, f'unit key {kv.group(1) if kv else s[:40]} outside the closed list', 'UNIT_EXEC'))
            continue
        if kv.group(1) in ('ReadWritePaths', 'Where'):
            for d in kv.group(2).split():
                d = d.lstrip('-')
                if not unit_path(d, UNIT_DATA_DIRS) or d.startswith('/run/zavod') and \
                        not re.fullmatch(r'/run/zavod(/[\w.-]+)*', d):
                    out.append((i, f'unit {kv.group(1)} {d}: outside the data folders', 'UNIT_EXEC'))
            continue
        # Аудит M3310-R15B-06: среда процесса тоже загружает код до проверенного сценария (NODE_OPTIONS=--require,
        # PYTHONPATH, BASH_ENV, LD_PRELOAD …). Закрытый мир: Environment= и PassEnvironment= — только имена из
        # UNIT_ENV_OK; EnvironmentFile= — находка (его текст проверка не видит).
        e = re.match(r'\s*(Environment|PassEnvironment|EnvironmentFile)\s*=\s*(.*)$', raw)
        if e:
            if e.group(1) == 'EnvironmentFile':
                out.append((i, 'unit reads its environment from a file the scan does not see', 'UNIT_EXEC'))
                continue
            try:
                items = shlex.split(e.group(2))
            except ValueError:
                out.append((i, 'unit environment not parsed', 'UNIT_EXEC'))
                continue
            for it in items:
                name = it.split('=', 1)[0] if e.group(1) == 'Environment' else it
                if e.group(1) == 'Environment' and '=' not in it or not UNIT_ENV_OK.match(name):
                    out.append((i, f'unit sets environment {name}: outside the closed list', 'UNIT_EXEC'))
            continue
        m = re.match(r'\s*Exec[A-Za-z]*\s*=\s*(.*)$', raw)
        if not m or not m.group(1).strip():
            continue
        # Аудит M3310-R16-01/02: приставки строки запуска. «|» — запуск через оболочку (хвост «; psql -f» не виден
        # проверке): находка, которую разрешение не снимает. «+», «!», «!!» — запуск с полными правами мимо User= и
        # ограничений: находка UNIT_PRIV, снимается только точной строкой разрешения. «@» — имя программы отдельно от
        # программы: находка. Разрешены «-» и «:».
        val = m.group(1).strip()
        pre = re.match(r'[-@:+!|]*', val).group(0)
        body = val[len(pre):]
        if '|' in pre:
            out.append((i, 'unit runs the command line through a shell (prefix |)', 'UNIT_SHELL'))
            continue
        if '+' in pre or '!' in pre:
            out.append((i, 'unit runs the command with full privileges (prefix + or !)', 'UNIT_PRIV'))
        if '@' in pre:
            out.append((i, 'unit gives the program another name (prefix @)', 'UNIT_EXEC'))
            continue
        if '$' in body:
            out.append((i, 'unit command uses environment substitution ($)', 'UNIT_EXEC'))
            continue
        try:
            words = shlex.split(body)
        except ValueError:
            out.append((i, 'unit command not parsed', 'UNIT_EXEC'))
            continue
        if not words or ';' in words or any(re.search(r'%(?![iI])', w) for w in words):
            out.append((i, 'unit command has several commands (;) or a specifier other than %i', 'UNIT_EXEC'))
            continue
        prog = words[0]
        b = os.path.basename(prog)
        rest = words[1:]
        if not unit_path(prog, UNIT_TREE_DIRS if SCRIPTS.get(b) in ('py', 'sh') else UNIT_SYS_DIRS):
            out.append((i, f'unit runs {prog}: not from the install folder or /usr/bin, /usr/sbin', 'UNIT_EXEC'))
        elif PY_RUNNERS.match(b):
            kind = 'py' if b.startswith(('python', 'pypy')) else 'sh' if b in SH_SHELLS else \
                'js' if b in ('node', 'nodejs') else None
            at = next((j for j, w in enumerate(rest) if not w.startswith('-')), None)
            opts = rest[:at] if at is not None else rest
            if kind is None:
                out.append((i, f'unit runs interpreter {b}: outside the closed list', 'UNIT_EXEC'))
            elif at is None or any(w in ('-c', '-m', '-e', '--eval', '-p', '-', '-s') for w in opts):
                out.append((i, f'unit runs {b} with inline code, a module or standard input', 'UNIT_EXEC'))
            elif SCRIPTS.get(os.path.basename(rest[at])) != kind or not unit_path(rest[at], UNIT_TREE_DIRS):
                out.append((i, f'unit runs {rest[at]}: not a checked {kind} file of the install folder', 'UNIT_EXEC'))
        elif SCRIPTS.get(b) in ('py', 'sh'):
            continue
        elif b in UNIT_PROGRAMS and rest[:1] == ['-f'] and len(rest) == 2 and \
                SCRIPTS.get(os.path.basename(rest[1])) == 'nft' and unit_path(rest[1], UNIT_TREE_DIRS):
            continue
        else:
            out.append((i, f'unit runs {b}: program outside the closed list', 'UNIT_EXEC'))
    return out


# Аудит M3310-R17B-04: правило polkit (*.rules) — JavaScript с правами root. Закрытый мир: без [ ] после имени
# (вычисляемое свойство polkit['sp' + 'awn']), без `…`, имена после точки — только из RULES_MEMBERS, прочие имена —
# из RULES_NAMES или объявлены в файле (var/let/const, параметры function).
RULES_MEMBERS = {'addRule', 'Result', 'NOT_HANDLED', 'NO', 'YES', 'AUTH_SELF', 'AUTH_SELF_KEEP', 'AUTH_ADMIN',
                 'AUTH_ADMIN_KEEP', 'id', 'user', 'indexOf', 'length', 'log', 'lookup', 'isInGroup', 'local',
                 'active'}
RULES_NAMES = {'var', 'let', 'const', 'function', 'return', 'if', 'else', 'polkit', 'String', 'true', 'false',
               'null'}


def rules_findings(text):
    out = []
    code = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)
    code = re.sub(r'//[^\n]*', '', code)
    code = re.sub(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', '""', code)
    declared = set(re.findall(r'\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)', code))
    for m in re.finditer(r'\bfunction\s*[\w$]*\s*\(([^)]*)\)', code):
        declared |= {a.strip() for a in m.group(1).split(',') if a.strip()}
    for m in re.finditer(r'(\.\s*)?([A-Za-z_$][\w$]*)|([\[`\\])', code):
        ln = code.count('\n', 0, m.start()) + 1
        if m.group(3):
            prev = code[:m.start()].rstrip()[-1:]
            if m.group(3) != '[' or re.match(r'[\w$)\]"]', prev or ' '):
                out.append((ln, 'polkit rule: computed property, template text or escape', 'UNIT_EXEC'))
        elif m.group(1) and m.group(2) not in RULES_MEMBERS:
            out.append((ln, f'polkit rule: property {m.group(2)} outside the closed list', 'UNIT_EXEC'))
        elif not m.group(1) and m.group(2) not in RULES_NAMES and m.group(2) not in declared:
            out.append((ln, f'polkit rule: name {m.group(2)} outside the closed list', 'UNIT_EXEC'))
    return out


def data_findings(norm, text):
    """Файлы настроек дерева (аудит M3310-R16-05/06). Юнит и вставка к юниту (drop-in: *.conf с разделом [Service] …)
    — правила unit_findings; tmpfiles.d — только строки вида d (папка); правило polkit (*.rules, JavaScript) — без
    запуска программ и загрузки кода; правила nft — без include. Прочие *.conf — данные."""
    if norm.endswith(UNIT_EXT) or re.search(r'(?m)^\s*\[[A-Za-z]+\]\s*$', text):
        return unit_findings(text)
    out = rules_findings(text) if norm.endswith('.rules') else []
    for i, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        if norm.endswith('.rules') and re.search(r'\b(spawn|eval|Function|require|import|load|exec)\b', s):
            out.append((i, 'polkit rule runs programs or loads code', 'UNIT_EXEC'))
        elif norm.endswith('.nft') and re.match(r'include\b', s):
            out.append((i, 'nft rules include a file the scan does not see', 'UNIT_EXEC'))
        elif norm.endswith('.conf'):
            f = s.split()
            if len(f) >= 2 and re.fullmatch(r'[A-Za-z][-+!=~^]*', f[0]) and f[1].startswith('/') and f[0] != 'd':
                out.append((i, f'tmpfiles line of type {f[0]}: only d (folder) is allowed', 'UNIT_EXEC'))
    return out


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
                if len(parts) != 3 or not ALLOW_CODE.match(parts[1]) or parts[1] in NO_ALLOW or ALLOW_DB.search(parts[2]):
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
    tree = list(files(argv))
    for path in tree:
        b = os.path.basename(path)
        kind = 'js' if b.endswith(('.mjs', '.js', '.cjs')) else None if b.endswith(UNCHECKED_EXT) else \
            'py' if is_python(path) else 'sh' if is_shell(path) else 'nft' if b.endswith('.nft') else None
        if kind:
            SCRIPTS[b] = kind if SCRIPTS.get(b, kind) == kind else 'two files with one name'
    for path in tree:
        norm = path.replace('\\', '/')
        TREE_PATHS.add(norm)
        if norm.endswith(DATA_EXT):
            todo.append((norm, 'data'))
            DATA_FILES.add(os.path.basename(norm))
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
        elif exec_content(path):
            # код или архив под чужим суффиксом (.txt, .data …) — запускается по #! или из архива (аудит M3310-R13-03)
            found += 1
            print(f'SQL_CONCAT {norm}:0: FORMAT: executable content (#! or binary or archive) the scan does not check')
        elif not norm.endswith(DATA_EXT):
            found += 1
            print(f'SQL_CONCAT {norm}:0: FORMAT: file type outside the closed list of the scanned tree')
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
        elif kind == 'data':
            items = [(ln, why, rule, lines[ln - 1].strip() if 0 < ln <= len(lines) else '')
                     for ln, why, rule in data_findings(norm, text)]
        else:
            items = [(ln, *py_rule(why), code) for ln, why, code in py_findings(norm, text)]
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
    # Аудит M3310-R19-01: каждый юнит, который запускает сценарий дерева, ставит всегда какой-то сценарий дерева из
    # своего файла (или это юнит ОС из SYSTEM_UNITS_OK). Разрешением не снимается.
    for norm, ln, key, verb in UNITS_STARTED:
        if key not in UNITS_INSTALLED:
            with open(norm, encoding='utf-8') as f:
                lines = f.read().splitlines()
            name = '$' + key[2] if isinstance(key, tuple) else key
            found += 1
            print(f'SQL_CONCAT {norm}:{ln}: SH_EXEC: systemctl {verb} unit {name}: no scanned script installs it '
                  f'from the tree every time: {(lines[ln - 1].strip() if 0 < ln <= len(lines) else "")[:160]}')
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
