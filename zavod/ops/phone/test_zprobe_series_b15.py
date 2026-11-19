#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/phone/test_zprobe_series_b15.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-19 14:15 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 16:10 +02:00
# v0.2 (REL156 M-355-REL156-01): подставной zprobe-start в штатном пути печатает строку ZPROBE_STATUS (по умолчанию
#   TERMINAL своей серии). Z01–Z05 — штатный путь с UNKNOWN, без строки, с двумя строками, с чужой серией, TERMINAL+UNKNOWN:
#   «НЕВЕРНО», код 3, без --status и без повтора, журнал забран. Z06 — обрыв и TERMINAL своей серии: итог принят. 39 случаев.
# v0.1 (Claude, терминал zavod; выпуск B15): копия test_zprobe_series_b15.py v0.1 на имена B15 (X01–X27 те же по смыслу;
#   X26 — RELEASE выпуска B15, X27 — строка unit= службы B15) и Y01–Y06 — обрыв связи до итоговой строки zprobe-start:
#   телефон серию не повторяет (ровно один запуск), спрашивает только --status до итога не STARTED/QUEUED и не дольше
#   STATUS_TRIES раз; итог не TERMINAL и обрыв — код 3; журнал забирается всегда.
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: поведение zprobe_series_b15.sh v0.17 на подставных ssh, scp и python3 (настоящие хосты и телефон не
#   трогаются). Ничего не удаляет: испытательные папки создаются в каталоге временных файлов ОС и остаются.
import hashlib, os, shutil, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASH = shutil.which('bash')
COMMIT = '0123456789abcdef0123456789abcdef01234567'
OTHER = 'fedcba9876543210fedcba9876543210fedcba98'
GOOD = ('commit=%s\nversion=3.5.5-b15\n' % COMMIT).encode()
START = '/usr/local/lib/zavod/probes-b15/zprobe-start'

SSH = r'''#!/usr/bin/env bash
echo "ssh $*" >> "$FAKE_LOG"
case "$*" in
  *"cat /usr/local/lib/zavod/probes-b15/RELEASE"*) cat "$FAKE_RELEASE"; exit "${FAKE_SSH_RC:-0}";;
  *"zprobe-start --status"*)
    n=$(cat "$FAKE_SCNT" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$FAKE_SCNT"
    line=$(printf '%s\n' "$FAKE_STATUS" | tr '|' '\n' | sed -n "${n}p")
    [ -n "$line" ] || line=$(printf '%s\n' "$FAKE_STATUS" | tr '|' '\n' | tail -n 1)
    [ "$line" = NONE ] || echo "ZPROBE_STATUS $line series=s1 reason=x retry=NO"; exit 0;;
  *zprobe-start*)
    printf '%b' "$FAKE_UNIT"
    if [ -n "${FAKE_BREAK:-}" ]; then exit 255; fi
    printf '%b' "$FAKE_MAIN_STATUS"
    echo "ZPROBE_START CONFIRMED series=s1 SERIES_END COMPLETE"; exit 0;;
esac
exit 9
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
echo "ZPROBE_VERDICT stub | chain=NO"
exit 0
'''


def sha(b):
    return hashlib.sha256(b).hexdigest()


def unit_line(series, b='b15'):
    return 'ZPROBE_START unit=zprobe-run-%s@%s.service fragment=/etc/systemd/system/zprobe-run-%s@.service\n' % (b, series, b)


TERMINAL_S1 = 'ZPROBE_STATUS TERMINAL series=s1 reason=x retry=NO\\n'


def run_case(release=GOOD, ssh_rc=0, mutate=None, pins_commit=COMMIT, series='s1', unit=None, brk='', status='',
             tries='5', main_status=TERMINAL_S1):
    root = tempfile.mkdtemp(prefix='zb15_')
    phone, fake = os.path.join(root, 'phone'), os.path.join(root, 'fake')
    os.mkdir(phone)
    os.mkdir(fake)
    for name, body in (('ssh', SSH), ('scp', SCP), ('python3', PY3)):
        p = os.path.join(fake, name)
        with open(p, 'w', newline='\n') as f:
            f.write(body)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
    own = os.path.join(phone, 'zprobe_series_b15.sh')
    shutil.copyfile(os.path.join(HERE, 'zprobe_series_b15.sh'), own)
    for n, b in (('zprobe_verify.py', b'verify stub\n'), ('zprobe_rules.py', b'rules stub\n')):
        with open(os.path.join(phone, n), 'wb') as f:
            f.write(b)
    with open(os.path.join(phone, 'zprobe_pins.txt'), 'w', newline='\n') as f:
        if pins_commit:
            f.write('release_commit %s\n' % pins_commit)
        for key, n in (('phone_zprobe_series_b15.sh', 'zprobe_series_b15.sh'), ('phone_zprobe_verify.py', 'zprobe_verify.py'),
                       ('phone_zprobe_rules.py', 'zprobe_rules.py')):
            with open(os.path.join(phone, n), 'rb') as g:
                f.write('%s %s\n' % (key, sha(g.read())))
    if mutate:                                   # изменение уже ПОСЛЕ записи отпечатков
        with open(os.path.join(phone, mutate), 'ab') as f:
            f.write(b'# changed\n')
    with open(os.path.join(phone, 'zprobe_pins.txt'), 'rb') as f:
        PINS_SHA[0] = sha(f.read())
    rel = os.path.join(root, 'release.bin')
    with open(rel, 'wb') as f:
        f.write(release)
    log = os.path.join(root, 'log.txt')
    open(log, 'w').close()
    env = dict(os.environ, PATH=fake + os.pathsep + os.environ['PATH'], FAKE_LOG=log, FAKE_RELEASE=rel,
               FAKE_SSH_RC=str(ssh_rc), HOME=root, FAKE_UNIT=unit_line(series) if unit is None else unit,
               FAKE_BREAK=brk, FAKE_STATUS=status, FAKE_SCNT=os.path.join(root, 'scnt'), STATUS_PAUSE='0',
               STATUS_TRIES=tries, FAKE_MAIN_STATUS=main_status)
    r = subprocess.run([BASH, own, series], env=env, capture_output=True, cwd=root)
    with open(log, encoding='utf-8') as f:
        calls = f.read().splitlines()
    LAST_PHONE[0] = phone
    return r.returncode, r.stdout.decode('utf-8', 'replace'), calls, os.path.isdir(os.path.join(phone, series))


FAILED = []
PINS_SHA = ['']
LAST_PHONE = ['']        # SHA-256 zprobe_pins.txt последнего прогона run_case


def case(name, ok, why=''):
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ' :: ' + why))
    if not ok:
        FAILED.append(name)


def refused_before_series(name, **kw):
    rc, out, calls, made = run_case(**kw)
    starts = [c for c in calls if 'zprobe-start' in c]
    case(name, rc == 2 and 'НЕВЕРНО: server release is not B15' in out and not made and not starts
         and not any(c.startswith(('scp', 'python3')) for c in calls), '%r %r %r %r' % (rc, out, calls, made))


def refused_before_ssh(name, **kw):
    rc, out, calls, made = run_case(**kw)
    case(name, rc == 2 and 'НЕВЕРНО' in out and not made and calls == [], '%r %r %r %r' % (rc, out, calls, made))


def main():
    if not BASH:
        print('FAIL bash not found')
        return 1
    rc, out, calls, made = run_case()
    starts = [c for c in calls if 'zprobe-start' in c]
    case('X01 right release: series folder made, one start line exactly <b15 path> <series> <challenge> ПБ-1',
         rc == 0 and made and len(starts) == 1
         and starts[0].endswith(' ' + START + ' s1 00112233445566778899aabbccddeeff ПБ-1'), '%r %r' % (rc, calls))
    case('X02 release check is a read-only cat on the b15 RELEASE and comes before the start',
         calls[0].startswith('ssh ') and calls[0].endswith('cat /usr/local/lib/zavod/probes-b15/RELEASE')
         and calls.index(starts[0]) > 0, repr(calls[:3]))
    case('X03 no b10 start path used', not any('probes-b10' in c for c in calls), repr(calls))
    refused_before_series('X04 RELEASE of another commit', release=('commit=%s\nversion=3.5.5-b15\n' % OTHER).encode())
    refused_before_series('X05 RELEASE version b10', release=('commit=%s\nversion=3.5.5-b10\n' % COMMIT).encode())
    refused_before_series('X06 RELEASE version b12', release=('commit=%s\nversion=3.5.5-b12\n' % COMMIT).encode())
    refused_before_series('X07 ssh code not 0 though the bytes are right', ssh_rc=255)
    refused_before_series('X08 empty RELEASE', release=b'')
    refused_before_series('X09 RELEASE without final newline', release=GOOD[:-1])
    refused_before_series('X10 RELEASE with an extra line', release=GOOD + b'x\n')
    refused_before_series('X11 RELEASE with CRLF', release=GOOD.replace(b'\n', b'\r\n'))
    refused_before_ssh('X12 own file changed', mutate='zprobe_series_b15.sh')
    refused_before_ssh('X13 zprobe_verify.py changed', mutate='zprobe_verify.py')
    refused_before_ssh('X14 zprobe_rules.py changed', mutate='zprobe_rules.py')
    refused_before_ssh('X15 no release_commit in zprobe_pins.txt', pins_commit=None)
    refused_before_ssh('X16 release_commit not 40 hex', pins_commit='abc')
    with open(os.path.join(HERE, 'zprobe_series_b15.sh'), encoding='utf-8') as f:
        text = f.read()
    body = [ln for ln in text.splitlines() if not ln.lstrip().startswith('#')]
    case('X17 code lines have no probes-b10 path', not any('probes-b10' in ln for ln in body))
    for name, u in (('X19 start.out names the B10 unit', unit_line('s1', 'b10')),
                    ('X20 start.out names another series', unit_line('s2')),
                    ('X21 start.out has no unit line', ''),
                    ('X22 start.out has two unit lines', unit_line('s1') * 2)):
        rc, out, calls, made = run_case(unit=u)
        case(name + ' -> НЕВЕРНО, journal still fetched, exit 3',
             rc == 3 and 'НЕВЕРНО: started unit is not zprobe-run-b15@s1' in out and made
             and any(c.startswith('scp') for c in calls), '%r %r' % (rc, out))
    rc, out, calls, made = run_case()
    case('X18 right unit line -> no НЕВЕРНО about the unit', rc == 0 and 'started unit' not in out, '%r %r' % (rc, out))
    rc, out, calls, made = run_case()
    sums1, first = PINS_SHA[0], out
    shows = [ln for ln in out.splitlines() if 'git show' in ln]
    case('X23 hint: one git show line, only the B15 pins path, no old zprobe_pins.txt path',
         len(shows) == 1 and shows[0].strip() == 'git show <коммит отпечатков>:zavod/ops/zprobe_pins_b15.txt > manifest.txt'
         and 'zavod/ops/zprobe_pins.txt' not in out and 'коммит выпуска' not in out, repr(shows))
    lines = out.splitlines()
    chk = [i for i, ln in enumerate(lines) if 'sha256sum -c' in ln]
    refs = [i for i, ln in enumerate(lines) if ln.startswith('  cd ') and '--refs' in ln]
    case('X24 hint prints the sha256 of own zprobe_pins.txt and the check comes before --refs',
         len(chk) == 1 and len(refs) == 1 and chk[0] < refs[0] and ("'%s  manifest.txt'" % sums1) in lines[chk[0]]
         and len(sums1) == 64, repr(lines[-4:]))
    rc, out, calls, made = run_case(pins_commit=OTHER, release=GOOD.replace(COMMIT.encode(), OTHER.encode()))
    case('X25 printed sum follows the pins file (other pins -> other sum)',
         PINS_SHA[0] != sums1 and ("'%s  manifest.txt'" % PINS_SHA[0]) in out and ("'%s  manifest.txt'" % sums1) not in out,
         repr(out[-300:]))
    rc, out, calls, made = run_case(release=('commit=%s\nversion=3.5.5-b14\n' % COMMIT).encode())  # X26
    starts = [c for c in calls if 'zprobe-start' in c]
    case('X26 RELEASE of B15 (right commit, version b15) -> refused before series folder',
         rc == 2 and 'НЕВЕРНО: server release is not B15' in out and not made and not starts, '%r %r' % (rc, out))
    rc, out, calls, made = run_case(unit=unit_line('s1', 'b14'))
    case('X27 start.out names the B15 unit -> НЕВЕРНО, exit 3',
         rc == 3 and 'НЕВЕРНО: started unit is not zprobe-run-b15@s1' in out and made, '%r %r' % (rc, out))
    def kinds(calls):
        st = [c for c in calls if 'zprobe-start --status' in c]
        go = [c for c in calls if 'zprobe-start' in c and '--status' not in c]
        return st, go
    rc, out, calls, made = run_case(brk='1', status='STARTED|QUEUED|TERMINAL')
    st, go = kinds(calls)
    with open(os.path.join(LAST_PHONE[0], 's1', 'status.out'), encoding='utf-8') as f:
        sout = f.read().splitlines()
    case('Y01 break before the final line: one start, --status until TERMINAL (3 reads), exit 3, journal fetched',
         rc == 3 and len(go) == 1 and len(st) == 3 and 'СОСТОЯНИЕ: ZPROBE_STATUS TERMINAL' in out and len(sout) == 3
         and any(c.startswith('scp') and 'journal' in c for c in calls), '%r %r %r' % (rc, calls, out[-400:]))
    case('Y02 --status is read only: exact command <b15 zprobe-start> --status <series>',
         all(c.endswith(' /usr/local/lib/zavod/probes-b15/zprobe-start --status s1') for c in st), repr(st))
    rc, out, calls, made = run_case(brk='1', status='STARTED', tries='4')
    st, go = kinds(calls)
    case('Y03 series still STARTED: no more than STATUS_TRIES reads, no new start, not accepted',
         rc == 3 and len(go) == 1 and len(st) == 4 and 'итог --status не TERMINAL' in out, '%r %r' % (rc, calls))
    rc, out, calls, made = run_case(brk='1', status='FAILED_AFTER_START')
    st, go = kinds(calls)
    case('Y04 FAILED_AFTER_START: one read, no repeat, exit 3', rc == 3 and len(st) == 1 and len(go) == 1
         and 'СОСТОЯНИЕ: ZPROBE_STATUS FAILED_AFTER_START' in out, '%r %r' % (rc, calls))
    rc, out, calls, made = run_case(brk='1', status='NONE', tries='3')
    st, go = kinds(calls)
    case('Y05 --status answers nothing: reads up to STATUS_TRIES, exit 3', rc == 3 and len(st) == 3 and len(go) == 1
         and 'нет ответа --status' in out, '%r %r' % (rc, out[-300:]))
    rc, out, calls, made = run_case()
    st, go = kinds(calls)
    case('Y06 final line present: no --status reads', rc == 0 and not st and len(go) == 1, '%r %r' % (rc, calls))
    for name, ms in (('Z01 STATUS UNKNOWN then START CONFIRMED', 'ZPROBE_STATUS UNKNOWN series=s1 reason=x retry=NO\\n'),
                     ('Z02 no ZPROBE_STATUS line before START CONFIRMED', ''),
                     ('Z03 two ZPROBE_STATUS lines (TERMINAL twice)', TERMINAL_S1 * 2),
                     ('Z04 TERMINAL of another series', 'ZPROBE_STATUS TERMINAL series=s2 reason=x retry=NO\\n'),
                     ('Z05 TERMINAL and UNKNOWN lines', TERMINAL_S1 + 'ZPROBE_STATUS UNKNOWN series=s1 reason=x retry=NO\\n')):
        rc, out, calls, made = run_case(main_status=ms)
        st, go = kinds(calls)
        case(name + ' -> НЕВЕРНО, not accepted (exit 3), no --status, no repeat, journal fetched',
             rc == 3 and 'НЕВЕРНО: start.out — нужна ровно одна строка ZPROBE_STATUS TERMINAL series=s1' in out
             and not st and len(go) == 1 and any(c.startswith('scp') and 'journal' in c for c in calls),
             '%r %r' % (rc, out[-400:]))
    rc, out, calls, made = run_case(brk='1', status='TERMINAL', tries='2')
    case('Z06 break, --status TERMINAL of own series -> TERM ok (exit 3 only from the break)',
         rc == 3 and 'итог --status не TERMINAL' not in out and 'СОСТОЯНИЕ: ZPROBE_STATUS TERMINAL series=s1' in out,
         '%r %r' % (rc, out[-300:]))
    print('ZPROBE_SERIES_B15_TEST=%s' % ('FAIL' if FAILED else 'PASS'))
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
