#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/phone/test_zprobe_series_b15b.py
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 21:59 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 22:40 +02:00
# v0.2: REL167 M-355-REL167-01 — случаи «два подряд»: DONE→обрыв→DONE→DONE, DONE→RUNNING→DONE→DONE,
#   DONE→обрезанный→DONE→DONE, DONE→ABSENT→DONE→DONE (без подтверждения) и те же с подменой на 4-м чтении;
#   L-355-REL167-02 — ANCHOR_DUP и ANCHOR_NEW.
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: поведение zprobe_series_b15b.sh v0.20 (вариант B, REL166) на подставном сервере: подставной ssh выполняет
#   НАСТОЯЩИЕ сценарии запуска и чтения пускателя локально (папка /root/zprobe-b и путь zprobe-start заменяются на
#   испытательные), подставные stat (владелец root, права 0700/0600, ошибка прав по списку), mkdir (без -m), setsid (-f —
#   фоновый процесс) и zprobe-start (режимы вывода и кода). Случаи REL166 B_TESTS: PRE_ACK, POST_ACK, DURING_RUN,
#   POST_TERMINAL, EXISTS, SYMLINK, TAMPER, TRUNCATED, DUPLICATE, WRONG_SERIES, UNKNOWN, JOURNAL_REFUSED, CHILD_FAILURE,
#   NO_FILE, RECONNECT; плюс отказ доступа, штатный путь, тайм-аут, рассогласование кода. Во всех случаях — ровно один
#   запуск zprobe-start. Ссылки — MSYS=winsymlinks:sys (Git Bash). Настоящие хосты и телефон не трогаются. Ничего не
#   удаляет: испытательные папки создаются в каталоге временных файлов ОС и остаются.
import hashlib, os, shutil, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASH = shutil.which('bash')
COMMIT = '0123456789abcdef0123456789abcdef01234567'
GOOD = ('commit=%s\nversion=3.5.5-b15\n' % COMMIT).encode()

SSH = r'''#!/usr/bin/env bash
echo "ssh $*" >> "$FAKE_LOG"
case "$*" in
  *"cat /usr/local/lib/zavod/probes-b15/RELEASE"*) cat "$FAKE_RELEASE"; exit 0;;
esac
a=("$@"); i=0
while [ $i -lt ${#a[@]} ] && [ "${a[$i]}" != "-s" ]; do i=$((i + 1)); done
rest=("${a[@]:$((i + 2))}")
script=$(cat | sed -e "s|/root/zprobe-b|$FAKE_SRV|g" -e "s|/usr/local/lib/zavod/probes-b15/zprobe-start|$FAKE_DIR/zprobe-start|g")
run() { printf '%s\n' "$script" | PATH="$(cygpath -u "$FAKE_DIR")/srvbin:$PATH" bash -s -- "${rest[@]}"; }
in_list() { case ",$1," in *",$2,"*) return 0;; esac; return 1; }
if [ ${#rest[@]} = 2 ]; then                       # запуск
  echo LAUNCH >> "$FAKE_LOG"
  case "${FAKE_LAUNCH:-}" in
    pre) exit 255;;
    post) run > /dev/null 2>&1; exit 255;;
    *) run; exit $?;;
  esac
fi
n=$(cat "$FAKE_DIR/rcnt" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$FAKE_DIR/rcnt"
P="$FAKE_SRV/${rest[0]}"
if in_list "${FAKE_TAMPER:-}" "$n"; then echo "ZPROBE_START CONFIRMED series=evil" >> "$P/start.out"; fi
if in_list "${FAKE_SYMLINK:-}" "$n"; then mv "$P/start.out" "$FAKE_DIR/moved.out"; MSYS=winsymlinks:sys ln -s "$FAKE_DIR/moved.out" "$P/start.out"; fi
if in_list "${FAKE_HIDE:-}" "$n"; then mv "$P/start.err" "$FAKE_DIR/moved.err"; fi
if in_list "${FAKE_EXTRA:-}" "$n"; then echo x > "$P/extra"; fi
if in_list "${FAKE_RUNSTATE:-}" "$n"; then echo "ZPROBE_B STATE RUNNING out_bytes=0 series=${rest[0]}"; echo "ZPROBE_B READ_END"; exit 0; fi
if in_list "${FAKE_ABSENT:-}" "$n"; then echo "ZPROBE_B STATE ABSENT series=${rest[0]}"; echo "ZPROBE_B READ_END"; exit 0; fi
if in_list "${FAKE_DROP:-}" "$n"; then echo "ssh: connect to host: Connection timed out" >&2; exit 255; fi
out=$(run); rc=$?
if in_list "${FAKE_TRUNC:-}" "$n"; then printf '%s\n' "$out" | head -n -1; exit 255; fi
if in_list "${FAKE_DUP:-}" "$n"; then out=$(printf '%s\n' "$out" | sed '1p'); fi
if in_list "${FAKE_WRONG:-}" "$n"; then out=$(printf '%s\n' "$out" | sed "s/ series=${rest[0]}\$/ series=zz/"); fi
printf '%s\n' "$out"; exit $rc
'''
STAT = r'''#!/usr/bin/env bash
fmt=; p=
for x in "$@"; do case "$x" in -c|--) ;; *%*) fmt=$x;; *) p=$x;; esac; done
[ -e "$p" ] || [ -L "$p" ] || { echo "stat: cannot statx '$p'" >&2; exit 1; }
if [ -L "$p" ]; then t="symbolic link"; m=777
elif [ -d "$p" ]; then t=directory; m=700
elif [ -s "$p" ]; then t="regular file"; m=600
else t="regular empty file"; m=600; fi
if [ -s "$FAKE_DIR/badperm" ] && grep -qxF "$(basename "$p")" "$FAKE_DIR/badperm"; then m=644; [ -d "$p" ] && m=755; fi
h=$(/usr/bin/stat -c %h -- "$p")
case "$fmt" in *%h*) echo "0 $m $h $t";; *) echo "0 $m $t";; esac
'''
MKDIR = r'''#!/usr/bin/env bash
a=(); skip=0
for x in "$@"; do if [ $skip = 1 ]; then skip=0; continue; fi; [ "$x" = -m ] && { skip=1; continue; }; a+=("$x"); done
exec /usr/bin/mkdir "${a[@]}"
'''
SETSID = r'''#!/usr/bin/env bash
[ "$1" = -f ] && shift
"$@" &
exit 0
'''
ZSTART = r'''#!/usr/bin/env bash
S=$1; m=${FAKE_ZS:-ok}
echo "ZPROBE_START RESERVED series=$S"
echo "ZPROBE_START unit=zprobe-run-b15@$S.service fragment=/etc/systemd/system/zprobe-run-b15@.service"
echo "zprobe-start stderr line" >&2
case "$m" in
  slow) sleep 2;;
  die) kill -9 $PPID; exit 0;;
esac
T="ZPROBE_STATUS TERMINAL series=$S reason=S_and_E retry=NO"
case "$m" in
  ok|slow) echo "$T"; echo "ZPROBE_START CONFIRMED series=$S seg=000006 seq=9 last_sha256=ab"; exit 0;;
  unknown) echo "$T"; echo "ZPROBE_START UNKNOWN series=$S SERIES_END UNKNOWN x"; exit 4;;
  refused) echo "$T"; echo "ZPROBE_START JOURNAL_REFUSED series=$S SERIES_END JOURNAL_REFUSED x"; exit 4;;
  dup) echo "$T"; echo "ZPROBE_START CONFIRMED series=$S a"; echo "ZPROBE_START CONFIRMED series=$S a"; exit 0;;
  wrong) echo "ZPROBE_STATUS TERMINAL series=other reason=x retry=NO"; echo "ZPROBE_START CONFIRMED series=other"; exit 0;;
  nofinal) echo "$T"; exit 0;;
  rcmis) echo "$T"; echo "ZPROBE_START CONFIRMED series=$S a"; exit 4;;
  hang) sleep 30; exit 0;;
esac
'''
SCP = r'''#!/usr/bin/env bash
echo "scp $*" >> "$FAKE_LOG"
for last; do :; done
mkdir -p "$last"
exit 0
'''
PY3 = r'''#!/usr/bin/env bash
echo "python3 $*" >> "$FAKE_LOG"
if [ "$1" = "-c" ]; then echo 00112233445566778899aabbccddeeff; exit 0; fi
if [ -n "${FAKE_VERDICT_ANCHOR:-}" ]; then echo "ZPROBE_VERDICT stub | chain=OK | anchor=$FAKE_VERDICT_ANCHOR"; exit 0; fi
echo "ZPROBE_VERDICT stub | chain=NO"
exit 0
'''

FAILED = []


def sha(b):
    return hashlib.sha256(b).hexdigest()


def put(path, body):
    with open(path, 'w', newline='\n', encoding='utf-8') as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


def run_case(series='s1', mutate=None, pre_exists=False, badperm='', env_extra=None):
    root = tempfile.mkdtemp(prefix='zb15b_').replace('\\', '/')
    phone, fake, srv = root + '/phone', root + '/fake', root + '/srv'
    os.mkdir(phone)
    os.mkdir(fake)
    os.mkdir(fake + '/srvbin')
    for name, body in (('ssh', SSH), ('scp', SCP), ('python3', PY3), ('zprobe-start', ZSTART)):
        put(fake + '/' + name, body)
    for name, body in (('stat', STAT), ('mkdir', MKDIR), ('setsid', SETSID)):
        put(fake + '/srvbin/' + name, body)
    with open(fake + '/badperm', 'w') as f:
        f.write(badperm)
    if pre_exists:
        os.makedirs(srv + '/' + series)
    own = phone + '/zprobe_series_b15b.sh'
    shutil.copyfile(os.path.join(HERE, 'zprobe_series_b15b.sh'), own)
    for n, b in (('zprobe_verify.py', b'verify stub\n'), ('zprobe_rules.py', b'rules stub\n')):
        with open(phone + '/' + n, 'wb') as f:
            f.write(b)
    with open(phone + '/zprobe_pins.txt', 'w', newline='\n') as f:
        f.write('release_commit %s\n' % COMMIT)
        for key, n in (('phone_zprobe_series_b15b.sh', 'zprobe_series_b15b.sh'), ('phone_zprobe_verify.py', 'zprobe_verify.py'),
                       ('phone_zprobe_rules.py', 'zprobe_rules.py')):
            with open(phone + '/' + n, 'rb') as g:
                f.write('%s %s\n' % (key, sha(g.read())))
    if (env_extra or {}).get('FAKE_ANCHORS_PRE'):
        with open(phone + '/anchors.log', 'w', newline='\n') as f:
            f.write(env_extra['FAKE_ANCHORS_PRE'] + '\n')
    if mutate:
        with open(phone + '/' + mutate, 'ab') as f:
            f.write(b'# changed\n')
    with open(root + '/release.bin', 'wb') as f:
        f.write(GOOD)
    log = root + '/log.txt'
    open(log, 'w').close()
    env = dict(os.environ, PATH=fake + os.pathsep + os.environ['PATH'], FAKE_LOG=log, FAKE_RELEASE=root + '/release.bin',
               FAKE_SRV=srv, FAKE_DIR=fake, HOME=root, READ_PAUSE='0.3', READ_TRIES='40')
    env.update(env_extra or {})
    r = subprocess.run([BASH, own, series], env=env, capture_output=True, cwd=root, timeout=300)
    with open(log, encoding='utf-8') as f:
        calls = f.read().splitlines()
    return {'rc': r.returncode, 'out': r.stdout.decode('utf-8', 'replace'), 'calls': calls, 'phone': phone,
            'srv': srv, 'series': series}


def rd(path):
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError:
        return None


CASES = [0]


def case(name, ok, res=None):
    CASES[0] += 1
    why = '' if ok or res is None else ' :: rc=%s out=%s' % (res['rc'], res['out'][-600:].replace('\n', ' / '))
    print(('PASS ' if ok else 'FAIL ') + name + why)
    if not ok:
        FAILED.append(name)


def launches(res):
    return sum(1 for c in res['calls'] if c == 'LAUNCH')


def zstarts(res):        # сколько раз сервер реально запустил zprobe-start: по числу созданных start.out
    return 1 if os.path.exists(res['srv'] + '/' + res['series'] + '/start.out') else 0


def reads(res):          # сколько чтений сделал пускатель (счётчик подставного ssh)
    v = rd(os.path.dirname(res['srv']) + '/fake/rcnt')
    return int(v.decode().strip()) if v else 0


def fetched(res):
    return any(c.startswith('scp ') and 'journal' in c for c in res['calls'])


def local(res, name):
    return rd(res['phone'] + '/' + res['series'] + '/' + name)


def srvf(res, name):
    return rd(res['srv'] + '/' + res['series'] + '/' + name)


def rejected(res, needle):
    return res['rc'] == 3 and 'НЕВЕРНО' in res['out'] and needle in res['out'] and launches(res) == 1 and fetched(res)


# B00 штатный путь: принят, start.out и start.err байт в байт как на сервере, код выхода сохранён.
r = run_case()
case('B00 ok: принят, stdout/stderr/код сохранены байт в байт, один запуск',
     r['rc'] == 0 and launches(r) == 1 and local(r, 'start.out') == srvf(r, 'start.out') and local(r, 'start.out')
     and local(r, 'start.err') == srvf(r, 'start.err') == b'zprobe-start stderr line\n' and local(r, 'start.rc') == b'rc=0\n'
     and srvf(r, 'start.rc') == b'rc=0\n' and b'ZPROBE_FETCH ssh_rc=0 started_rc=0 journal_rc=0' in local(r, 'fetch.txt')
     and 'ack=1' in local(r, 'launch.txt').decode(), r)
# PRE_ACK: обрыв до выполнения на сервере — чтение ABSENT трижды, запуск не повторяется.
r = run_case(env_extra={'FAKE_LAUNCH': 'pre'})
case('PRE_ACK обрыв до запуска: НЕВЕРНО «не найден», один запуск, zprobe-start не запускался',
     rejected(r, 'запуск не подтверждён') and zstarts(r) == 0, r)
# POST_ACK: сервер запустил, подтверждение потеряно — только чтение, серия принята.
r = run_case(env_extra={'FAKE_LAUNCH': 'post'})
case('POST_ACK подтверждение потеряно: только чтение, принят, ack=0', r['rc'] == 0 and launches(r) == 1
     and 'ack=0' in local(r, 'launch.txt').decode() and local(r, 'start.out') == srvf(r, 'start.out'), r)
# DURING_RUN: обрыв чтения во время работы, затем итог.
r = run_case(env_extra={'FAKE_ZS': 'slow', 'FAKE_DROP': '2'})
case('DURING_RUN RUNNING и обрыв чтения: принят, один запуск', r['rc'] == 0 and launches(r) == 1 and 'RUNNING' in r['out'], r)
# POST_TERMINAL: обрыв на чтении после итога (первое DONE не дошло).
r = run_case(env_extra={'FAKE_DROP': '1,2'})
case('POST_TERMINAL обрыв после итога: повтор только чтения, принят', r['rc'] == 0 and launches(r) == 1, r)
# RECONNECT: несколько обрывов подряд.
r = run_case(env_extra={'FAKE_DROP': '1,2,3,4'})
case('RECONNECT 4 обрыва чтения: принят, один запуск', r['rc'] == 0 and launches(r) == 1, r)
# TRUNCATED: ответ чтения без последней строки — повтор чтения; итог принят.
r = run_case(env_extra={'FAKE_TRUNC': '1,2'})
case('TRUNCATED обрезанный ответ чтения: повтор чтения, принят', r['rc'] == 0 and launches(r) == 1, r)
# TRUNCATED stdout: нет итоговой строки CONFIRMED при коде 0.
r = run_case(env_extra={'FAKE_ZS': 'nofinal'})
case('TRUNCATED start.out без CONFIRMED: НЕВЕРНО', rejected(r, 'не согласован'), r)
# EXISTS: папка серии на сервере уже есть — отказ, zprobe-start не запускался, чтения нет.
r = run_case(pre_exists=True)
case('EXISTS папка серии есть: отказ, код 2, ни одного чтения', r['rc'] == 2 and 'REFUSED EXISTS' in r['out']
     and launches(r) == 1 and zstarts(r) == 0 and sum(1 for c in r['calls'] if c.startswith('ssh ')) == 2, r)
# SYMLINK: start.out подменён ссылкой.
r = run_case(env_extra={'FAKE_SYMLINK': '1'})
case('SYMLINK start.out — ссылка: НЕВЕРНО UNSAFE', rejected(r, 'UNSAFE what=start.out'), r)
# Отказ доступа: права файла не 0600.
r = run_case(badperm='start.out')
case('PERM права start.out не 0600: НЕВЕРНО UNSAFE', rejected(r, 'UNSAFE what=start.out'), r)
r = run_case(badperm='srv')        # подставная /root/zprobe-b — папка srv
case('PERM_BASE /root/zprobe-b не 0700: отказ запуска, код 2', r['rc'] == 2 and 'base_unsafe' in r['out'] and zstarts(r) == 0, r)
# Лишний файл в папке серии.
r = run_case(env_extra={'FAKE_EXTRA': '1'})
case('EXTRA лишний файл в папке серии: НЕВЕРНО', rejected(r, 'UNSAFE what=extra'), r)
# TAMPER: start.out изменён между первым и контрольным чтением.
r = run_case(env_extra={'FAKE_TAMPER': '2'})
case('TAMPER подмена между чтениями: НЕВЕРНО', rejected(r, 'подмена'), r)
# DUPLICATE: две строки CONFIRMED; повтор строки состояния в ответе.
r = run_case(env_extra={'FAKE_ZS': 'dup'})
case('DUPLICATE две строки CONFIRMED: НЕВЕРНО', rejected(r, 'CONFIRMED 2'), r)
r = run_case(env_extra={'FAKE_DUP': '1'})
case('DUPLICATE_READ повтор строки STATE: НЕВЕРНО без повтора', rejected(r, 'повтор строк'), r)
# WRONG_SERIES: чужая серия в выводе zprobe-start и в ответе чтения.
r = run_case(env_extra={'FAKE_ZS': 'wrong'})
case('WRONG_SERIES вывод чужой серии: НЕВЕРНО', rejected(r, 'TERMINAL series=s1'), r)
r = run_case(env_extra={'FAKE_WRONG': '1'})
case('WRONG_SERIES_READ ответ чтения чужой серии: НЕВЕРНО', rejected(r, 'чужая серия'), r)
# UNKNOWN и JOURNAL_REFUSED: код 4 — серия не принята, журнал забран.
r = run_case(env_extra={'FAKE_ZS': 'unknown'})
case('UNKNOWN: НЕВЕРНО, код 4 сохранён', rejected(r, 'UNKNOWN') and local(r, 'start.rc') == b'rc=4\n', r)
r = run_case(env_extra={'FAKE_ZS': 'refused'})
case('JOURNAL_REFUSED: НЕВЕРНО, код 4 сохранён', rejected(r, 'JOURNAL_REFUSED') and local(r, 'start.rc') == b'rc=4\n', r)
r = run_case(env_extra={'FAKE_ZS': 'rcmis'})
case('RC_MISMATCH CONFIRMED при коде 4: НЕВЕРНО', rejected(r, 'не согласован'), r)
# CHILD_FAILURE: процесс-обёртка погиб без кода выхода.
r = run_case(env_extra={'FAKE_ZS': 'die'})
case('CHILD_FAILURE гибель без start.rc: НЕВЕРНО CHILD_DEAD', rejected(r, 'CHILD_DEAD') and srvf(r, 'start.rc') is None, r)
# NO_FILE: start.err пропал после кода выхода.
r = run_case(env_extra={'FAKE_HIDE': '1'})
case('NO_FILE start.err нет: НЕВЕРНО', rejected(r, 'NO_FILE what=start.err'), r)
# Тайм-аут: zprobe-start не кончается — нет итога за READ_TRIES, повторного запуска нет.
r = run_case(env_extra={'FAKE_ZS': 'hang', 'READ_TRIES': '4'})
case('TIMEOUT нет итога: НЕВЕРНО, один запуск', rejected(r, 'нет итога за 4 чтений'), r)
# M-355-REL167-01: «два подряд» — только соседние чтения; любой не-DONE сбрасывает контрольное чтение.
r = run_case(env_extra={'FAKE_DROP': '2'})
case('PAIR DONE→обрыв→DONE→DONE: принят на 4-м чтении, сброс виден', r['rc'] == 0 and reads(r) == 4
     and 'контрольное чтение сброшено' in r['out'], r)
r = run_case(env_extra={'FAKE_DROP': '2', 'FAKE_TAMPER': '4'})
case('PAIR DONE→обрыв→DONE→подмена: НЕВЕРНО (v0.19 принял бы на 3-м)', rejected(r, 'подмена') and reads(r) == 4, r)
r = run_case(env_extra={'FAKE_RUNSTATE': '2'})
case('PAIR DONE→RUNNING→DONE→DONE: принят на 4-м чтении', r['rc'] == 0 and reads(r) == 4
     and 'контрольное чтение сброшено' in r['out'], r)
r = run_case(env_extra={'FAKE_RUNSTATE': '2', 'FAKE_TAMPER': '4'})
case('PAIR DONE→RUNNING→DONE→подмена: НЕВЕРНО', rejected(r, 'подмена') and reads(r) == 4, r)
r = run_case(env_extra={'FAKE_TRUNC': '2'})
case('PAIR DONE→обрезанный→DONE→DONE: принят на 4-м чтении', r['rc'] == 0 and reads(r) == 4, r)
r = run_case(env_extra={'FAKE_LAUNCH': 'post', 'FAKE_ABSENT': '2'})
case('PAIR без подтверждения DONE→ABSENT→DONE→DONE: принят на 4-м чтении', r['rc'] == 0 and reads(r) == 4
     and 'контрольное чтение сброшено' in r['out'], r)
r = run_case(env_extra={'FAKE_LAUNCH': 'post', 'FAKE_ABSENT': '2', 'FAKE_TAMPER': '4'})
case('PAIR без подтверждения DONE→ABSENT→DONE→подмена: НЕВЕРНО', rejected(r, 'подмена'), r)
r = run_case()
case('PAIR штатно: ровно 2 чтения', r['rc'] == 0 and reads(r) == 2, r)
# L-355-REL167-02: якорь, который уже есть в anchors.log, не дописывается повторно.
def run_anchor(pre):
    r = run_case(env_extra={'FAKE_VERDICT_ANCHOR': '7:' + 'ab' * 32, 'FAKE_ANCHORS_PRE': pre})
    return r, rd(r['phone'] + '/anchors.log') or b''
r, al = run_anchor('7 ' + 'ab' * 32)
case('ANCHOR_DUP якорь уже есть: не дописан, строка одна', al.count(('7 ' + 'ab' * 32).encode()) == 1 and 'не дописан' in r['out'], r)
r, al = run_anchor('6 ' + 'cd' * 32)
case('ANCHOR_NEW новый якорь: дописан один раз', al.count(('7 ' + 'ab' * 32).encode()) == 1 and 'не дописан' not in r['out'], r)
# Самопроверка до связи: изменённый пускатель — код 2, ни одного ssh.
r = run_case(mutate='zprobe_series_b15b.sh')
case('PIN изменённый пускатель: код 2, ssh нет', r['rc'] == 2 and not any(c.startswith('ssh ') for c in r['calls']), r)

print('ИТОГ: %d PASS, %d FAIL %s' % (CASES[0] - len(FAILED), len(FAILED), ','.join(FAILED)))
sys.exit(1 if FAILED else 0)
