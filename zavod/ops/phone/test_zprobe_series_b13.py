#!/usr/bin/env python3
# ДОКУМЕНТ: zavod/ops/phone/test_zprobe_series_b13.py
# ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-11-18 13:38 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 13:44 +02:00
# v0.2 (REL126 L-355-REL126-01): X18–X22 — строка unit= в start.out: верная, B10, другая серия, нет строки, две строки.
# ИСПОЛНИТЕЛЬ: Claude; проект B13 v0.3, п. 6 (ж), REL125 M-02
# НАЗНАЧЕНИЕ: поведение zprobe_series_b13.sh v0.14 на подставных ssh, scp и python3 (настоящие хосты и телефон не
#   трогаются): строка запуска; чужой выпуск сервера, неверный RELEASE и код ssh не 0 — отказ до папки серии и до
#   zprobe-start; изменённый свой файл, verify или rules — отказ до ssh; верный — запуск. Ничего не удаляет:
#   испытательные папки создаются в каталоге временных файлов ОС и остаются.
import hashlib, os, shutil, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASH = shutil.which('bash')
COMMIT = '0123456789abcdef0123456789abcdef01234567'
OTHER = 'fedcba9876543210fedcba9876543210fedcba98'
GOOD = ('commit=%s\nversion=3.5.5-b13\n' % COMMIT).encode()
START = '/usr/local/lib/zavod/probes-b13/zprobe-start'

SSH = r'''#!/usr/bin/env bash
echo "ssh $*" >> "$FAKE_LOG"
case "$*" in
  *"cat /usr/local/lib/zavod/probes-b13/RELEASE"*) cat "$FAKE_RELEASE"; exit "${FAKE_SSH_RC:-0}";;
  *zprobe-start*) echo "ZPROBE_START CONFIRMED"; printf '%b' "$FAKE_UNIT"; exit 0;;
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


def unit_line(series, b='b13'):
    return 'ZPROBE_START unit=zprobe-run-%s@%s.service fragment=/etc/systemd/system/zprobe-run-%s@.service\n' % (b, series, b)


def run_case(release=GOOD, ssh_rc=0, mutate=None, pins_commit=COMMIT, series='s1', unit=None):
    root = tempfile.mkdtemp(prefix='zb13_')
    phone, fake = os.path.join(root, 'phone'), os.path.join(root, 'fake')
    os.mkdir(phone)
    os.mkdir(fake)
    for name, body in (('ssh', SSH), ('scp', SCP), ('python3', PY3)):
        p = os.path.join(fake, name)
        with open(p, 'w', newline='\n') as f:
            f.write(body)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
    own = os.path.join(phone, 'zprobe_series_b13.sh')
    shutil.copyfile(os.path.join(HERE, 'zprobe_series_b13.sh'), own)
    for n, b in (('zprobe_verify.py', b'verify stub\n'), ('zprobe_rules.py', b'rules stub\n')):
        with open(os.path.join(phone, n), 'wb') as f:
            f.write(b)
    with open(os.path.join(phone, 'zprobe_pins.txt'), 'w', newline='\n') as f:
        if pins_commit:
            f.write('release_commit %s\n' % pins_commit)
        for key, n in (('phone_zprobe_series_b13.sh', 'zprobe_series_b13.sh'), ('phone_zprobe_verify.py', 'zprobe_verify.py'),
                       ('phone_zprobe_rules.py', 'zprobe_rules.py')):
            with open(os.path.join(phone, n), 'rb') as g:
                f.write('%s %s\n' % (key, sha(g.read())))
    if mutate:                                   # изменение уже ПОСЛЕ записи отпечатков
        with open(os.path.join(phone, mutate), 'ab') as f:
            f.write(b'# changed\n')
    rel = os.path.join(root, 'release.bin')
    with open(rel, 'wb') as f:
        f.write(release)
    log = os.path.join(root, 'log.txt')
    open(log, 'w').close()
    env = dict(os.environ, PATH=fake + os.pathsep + os.environ['PATH'], FAKE_LOG=log, FAKE_RELEASE=rel,
               FAKE_SSH_RC=str(ssh_rc), HOME=root, FAKE_UNIT=unit_line(series) if unit is None else unit)
    r = subprocess.run([BASH, own, series], env=env, capture_output=True, cwd=root)
    with open(log, encoding='utf-8') as f:
        calls = f.read().splitlines()
    return r.returncode, r.stdout.decode('utf-8', 'replace'), calls, os.path.isdir(os.path.join(phone, series))


FAILED = []


def case(name, ok, why=''):
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ' :: ' + why))
    if not ok:
        FAILED.append(name)


def refused_before_series(name, **kw):
    rc, out, calls, made = run_case(**kw)
    starts = [c for c in calls if 'zprobe-start' in c]
    case(name, rc == 2 and 'НЕВЕРНО: server release is not B13' in out and not made and not starts
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
    case('X01 right release: series folder made, one start line exactly <b13 path> <series> <challenge> ПБ-1',
         rc == 0 and made and len(starts) == 1
         and starts[0].endswith(' ' + START + ' s1 00112233445566778899aabbccddeeff ПБ-1'), '%r %r' % (rc, calls))
    case('X02 release check is a read-only cat on the b13 RELEASE and comes before the start',
         calls[0].startswith('ssh ') and calls[0].endswith('cat /usr/local/lib/zavod/probes-b13/RELEASE')
         and calls.index(starts[0]) > 0, repr(calls[:3]))
    case('X03 no b10 start path used', not any('probes-b10' in c for c in calls), repr(calls))
    refused_before_series('X04 RELEASE of another commit', release=('commit=%s\nversion=3.5.5-b13\n' % OTHER).encode())
    refused_before_series('X05 RELEASE version b10', release=('commit=%s\nversion=3.5.5-b10\n' % COMMIT).encode())
    refused_before_series('X06 RELEASE version b12', release=('commit=%s\nversion=3.5.5-b12\n' % COMMIT).encode())
    refused_before_series('X07 ssh code not 0 though the bytes are right', ssh_rc=255)
    refused_before_series('X08 empty RELEASE', release=b'')
    refused_before_series('X09 RELEASE without final newline', release=GOOD[:-1])
    refused_before_series('X10 RELEASE with an extra line', release=GOOD + b'x\n')
    refused_before_series('X11 RELEASE with CRLF', release=GOOD.replace(b'\n', b'\r\n'))
    refused_before_ssh('X12 own file changed', mutate='zprobe_series_b13.sh')
    refused_before_ssh('X13 zprobe_verify.py changed', mutate='zprobe_verify.py')
    refused_before_ssh('X14 zprobe_rules.py changed', mutate='zprobe_rules.py')
    refused_before_ssh('X15 no release_commit in zprobe_pins.txt', pins_commit=None)
    refused_before_ssh('X16 release_commit not 40 hex', pins_commit='abc')
    with open(os.path.join(HERE, 'zprobe_series_b13.sh'), encoding='utf-8') as f:
        text = f.read()
    body = [ln for ln in text.splitlines() if not ln.lstrip().startswith('#')]
    case('X17 code lines have no probes-b10 path', not any('probes-b10' in ln for ln in body))
    for name, u in (('X19 start.out names the B10 unit', unit_line('s1', 'b10')),
                    ('X20 start.out names another series', unit_line('s2')),
                    ('X21 start.out has no unit line', ''),
                    ('X22 start.out has two unit lines', unit_line('s1') * 2)):
        rc, out, calls, made = run_case(unit=u)
        case(name + ' -> НЕВЕРНО, journal still fetched, exit 3',
             rc == 3 and 'НЕВЕРНО: started unit is not zprobe-run-b13@s1' in out and made
             and any(c.startswith('scp') for c in calls), '%r %r' % (rc, out))
    rc, out, calls, made = run_case()
    case('X18 right unit line -> no НЕВЕРНО about the unit', rc == 0 and 'started unit' not in out, '%r %r' % (rc, out))
    print('ZPROBE_SERIES_B13_TEST=%s' % ('FAIL' if FAILED else 'PASS'))
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
