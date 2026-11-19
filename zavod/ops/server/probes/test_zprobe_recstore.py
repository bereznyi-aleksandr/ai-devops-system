#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_recstore.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:57 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 13:06 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: офлайн-тесты части C (zprobe_recstore.py v0.2 + PENDING в zprobe_start_status.classify): порядок шагов
#   (имя .ok появляется только после fsync своего содержимого и папки), чтение до .ok (служба жива → QUEUED, мертва →
#   UNKNOWN), обрыв на каждом шаге, сбой каждого fsync и link, .ok пропал после сбоя питания, .ok с чужой суммой, .ok без
#   данных, барьер чтения (сбой fsync у читателя → UNKNOWN), два писателя одного имени, заранее положенные файлы и
#   символьные ссылки на месте <имя>, <имя>.ok.part, <имя>.ok. v0.2 — по аудиту REL154 M-355-REL154-02.
# ОГРАНИЧЕНИЯ: временные папки — tempfile.TemporaryDirectory (в ОС-папке временных файлов, живут один прогон, ничего
#   не доказывают сами: итог — строка ZPROBE_RECSTORE_TESTS). Символьные ссылки на Windows без прав — SKIP с причиной;
#   CI-лаборатория (ubuntu-24.04) гоняет их без пропуска, и там же — запись и чтение настоящими fsync (W30).
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zprobe_recstore as W  # noqa: E402
import zprobe_start_status as ST  # noqa: E402

OK, BAD, SKIP = [], [], []
SER, CH, INV = 'pb1trial5', 'c' * 32, 'a' * 32
REC_S = {'series': SER, 'challenge': CH, 'invocation_id': INV}
REC_I = {'series': SER, 'challenge': CH}
ALIVE = {'active': 'activating', 'invocation': INV, 'job': False}
DEAD = {'active': 'inactive', 'invocation': '', 'job': False}


def check(name, good, info=''):
    (OK if good else BAD).append(name)
    print(('PASS ' if good else 'FAIL ') + name + (f' ({info})' if info else ''), flush=True)


class TestOps(W.Ops):
    """Журнал шагов и сбой на нужном вызове. fsync здесь только считается (порядок проверяется по журналу); настоящий
    fsync — в W30 на Linux."""
    def __init__(self, fail_fsync_at=None, fail_dir_at=None, fail_link=False):
        self.log, self.n_fsync, self.n_dir = [], 0, 0
        self.fail_fsync_at, self.fail_dir_at, self.fail_link = fail_fsync_at, fail_dir_at, fail_link
        self._names = {}

    def open(self, path, flags, mode=0o444):
        fd = super().open(path, flags, mode)
        self._names[fd] = os.path.basename(path)
        self.log.append(('open', os.path.basename(path)))
        return fd

    def fsync(self, fd):
        self.n_fsync += 1
        self.log.append(('fsync', self._names.get(fd, '?')))
        if self.n_fsync == self.fail_fsync_at:
            raise OSError(5, 'EIO injected')

    def link(self, src, dst):
        self.log.append(('link', os.path.basename(dst)))
        if self.fail_link:
            raise OSError(5, 'EIO injected (link)')
        super().link(src, dst)

    def fsync_dir(self, d):
        self.n_dir += 1
        self.log.append(('fsync_dir', ''))
        if self.n_dir == self.fail_dir_at:
            raise OSError(5, 'EIO injected (dir)')



def rd(d, n, k, ops=None):
    return W.read_record(d, n, k, ops or TestOps())


def status(d, unit, ops=None):
    s = rd(d, 'S', 'S', ops)
    rec = {'R': dict(REC_I), 'I': rd(d, 'I', 'I'), 'Q': None, 'S': [s] if s is not None else [], 'E': []}
    return ST.classify(SER, rec, unit)


def exists(d, n):
    return os.path.lexists(os.path.join(d, n))


with tempfile.TemporaryDirectory() as d:
    ops = TestOps()
    h = W.write_record(d, 'S', REC_S, ops)
    check('W01 write then read -> record', rd(d, 'S', 'S') == REC_S)
    okline = open(os.path.join(d, 'S.ok'), 'rb').read()
    check('W02 .ok holds SHA-256 of data file', okline == f'OK sha256={h}\n'.encode())
    check('W03 files are read-only 0444 on POSIX', os.name != 'posix'
          or (os.stat(os.path.join(d, 'S')).st_mode & 0o777) == 0o444)
    want = [('open', 'S'), ('fsync', 'S'), ('fsync_dir', ''), ('open', 'S.ok.part'), ('fsync', 'S.ok.part'),
            ('fsync_dir', ''), ('link', 'S.ok'), ('fsync_dir', '')]
    check('W20 order: data fsync, dir, .ok.part fsync, dir, THEN name .ok (link), dir', ops.log == want, ops.log)
    check('W21 .ok.part kept (nothing deleted or replaced)', exists(d, 'S.ok.part'))
    try:
        W.write_record(d, 'S', dict(REC_S, invocation_id='b' * 32), TestOps())
        check('W04 second writer of the same name -> EEXIST', False, 'no error')
    except FileExistsError:
        check('W04 second writer of the same name -> EEXIST, first record intact', rd(d, 'S', 'S') == REC_S)
    for bad in ('../x', '.hidden', 'S.ok', 'S.part', 'a\\b'):
        try:
            W.write_record(d, bad, REC_S, TestOps())
            check(f'W05 bad name {bad!r} refused', False)
        except ValueError:
            check(f'W05 bad name {bad!r} refused', True)

for label, unit, want in (('alive', ALIVE, 'QUEUED'), ('dead', DEAD, 'UNKNOWN')):
    with tempfile.TemporaryDirectory() as d:
        W.write_record(d, 'I', REC_I, TestOps())
        open(os.path.join(d, 'S'), 'wb').write(W.encode(REC_S))      # шаг 1 сделан, .ok ещё нет
        check(f'W06 read after step 1 before .ok -> PENDING ({label})', rd(d, 'S', 'S') == ST.PENDING)
        st = status(d, unit)
        check(f'W07 status: data without .ok, unit {label} -> {want}', st[0] == want, st[1])
        open(os.path.join(d, 'S.ok.part'), 'wb').write(b'OK sha256=' + W.hashlib.sha256(W.encode(REC_S)).hexdigest()
                                                       .encode() + b'\n')
        check(f'W22 read after step 2 (.ok.part only, no .ok) -> PENDING ({label})', rd(d, 'S', 'S') == ST.PENDING)

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'I', REC_I, TestOps())
    full = W.encode(REC_S)
    open(os.path.join(d, 'S'), 'wb').write(full[:len(full) // 2])   # обрыв посреди шага 1
    check('W08 torn data without .ok -> PENDING (not CORRUPT)', rd(d, 'S', 'S') == ST.PENDING)
    check('W09 torn data, unit dead -> UNKNOWN', status(d, DEAD)[0] == 'UNKNOWN')

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'I', REC_I, TestOps())
    W.write_record(d, 'S', REC_S, TestOps())
    os.replace(os.path.join(d, 'S.ok'), os.path.join(d, 'lost.ok.bak'))   # имя .ok пропало после сбоя питания
    check('W10 .ok lost after power cut, unit dead -> UNKNOWN (not STARTED)', status(d, DEAD)[0] == 'UNKNOWN')
    check('W11 .ok lost after power cut, unit alive -> QUEUED (not STARTED)', status(d, ALIVE)[0] == 'QUEUED')

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'S', REC_S, TestOps())
    os.chmod(os.path.join(d, 'S.ok'), 0o644)
    open(os.path.join(d, 'S.ok'), 'wb').write(b'OK sha256=' + b'0' * 64 + b'\n')
    check('W12 .ok with another sum -> CORRUPT', rd(d, 'S', 'S') == ST.CORRUPT)
    open(os.path.join(d, 'S.ok'), 'wb').write(b'OK sha256=zz\n')
    check('W13 .ok malformed -> CORRUPT', rd(d, 'S', 'S') == ST.CORRUPT)

with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'S.ok'), 'wb').write(b'OK sha256=' + b'0' * 64 + b'\n')
    check('W14 .ok without data -> CORRUPT', rd(d, 'S', 'S') == ST.CORRUPT)
    W.write_record(d, 'I', REC_I, TestOps())
    check('W15 status with .ok without data -> UNKNOWN', status(d, ALIVE)[0] == 'UNKNOWN')

# Сбой на каждом шаге писателя: до link имени .ok нет; запись не видна как сделанная
STEPS = (('data fsync', dict(fail_fsync_at=1)), ('dir fsync after data', dict(fail_dir_at=1)),
         ('.ok.part fsync', dict(fail_fsync_at=2)), ('dir fsync after .ok.part', dict(fail_dir_at=2)),
         ('link', dict(fail_link=True)))
for label, kw in STEPS:
    with tempfile.TemporaryDirectory() as d:
        W.write_record(d, 'I', REC_I, TestOps())
        try:
            W.write_record(d, 'S', REC_S, TestOps(**kw))
            check(f'W16 {label} error -> writer raises', False, 'no error')
            continue
        except OSError:
            pass
        check(f'W16 {label} error -> writer raises, no name .ok', not exists(d, 'S.ok'))
        st_a, st_d = status(d, ALIVE), status(d, DEAD)
        check(f'W17 {label} error -> status alive QUEUED, dead UNKNOWN (never STARTED)',
              (st_a[0], st_d[0]) == ('QUEUED', 'UNKNOWN'), (st_a, st_d))

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'I', REC_I, TestOps())
    try:
        W.write_record(d, 'S', REC_S, TestOps(fail_dir_at=3))
        check('W23 last dir fsync error -> writer raises', False)
    except OSError:
        check('W23 last dir fsync error -> writer raises', True)
    # Имя .ok видно, его содержимое и данные уже на диске; барьер чтения сбрасывает папку сам до ответа «есть».
    ops = TestOps()
    got = rd(d, 'S', 'S', ops)
    check('W24 reader barrier: fsync data, .ok and folder BEFORE positive answer',
          got == REC_S and ops.log == [('fsync', '?'), ('fsync', '?'), ('fsync_dir', '')], ops.log)
    for label, kw in (('data', dict(fail_fsync_at=1)), ('.ok', dict(fail_fsync_at=2)), ('folder', dict(fail_dir_at=1))):
        check(f'W25 reader barrier fails on {label} -> CORRUPT', rd(d, 'S', 'S', TestOps(**kw)) == ST.CORRUPT)
        st = status(d, ALIVE, TestOps(**kw))
        check(f'W26 status with failed reader barrier ({label}) -> UNKNOWN, not STARTED', st[0] == 'UNKNOWN', st[1])

with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'S.ok'), 'wb').write(b'OK sha256=' + b'1' * 64 + b'\n')   # чужой .ok заранее
    try:
        W.write_record(d, 'S', REC_S, TestOps())
        check('W27 pre-existing .ok -> link EEXIST', False)
    except FileExistsError:
        check('W27 pre-existing .ok -> link EEXIST, not replaced; reader CORRUPT',
              open(os.path.join(d, 'S.ok'), 'rb').read().startswith(b'OK sha256=111') and rd(d, 'S', 'S') == ST.CORRUPT)
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'S.ok.part'), 'wb').write(b'x')
    try:
        W.write_record(d, 'S', REC_S, TestOps())
        check('W28 pre-existing .ok.part -> EEXIST', False)
    except FileExistsError:
        check('W28 pre-existing .ok.part -> EEXIST, no .ok', not exists(d, 'S.ok'))

for target in ('S', 'S.ok.part', 'S.ok'):
    with tempfile.TemporaryDirectory() as d:
        aim = os.path.join(d, 'elsewhere')
        open(aim, 'wb').write(b'x')
        try:
            os.symlink(aim, os.path.join(d, target))
        except (OSError, NotImplementedError) as e:
            SKIP.append(f'W18 {target}')
            print(f'SKIP W18 pre-placed symlink at {target} (no symlink right on this OS: {e.__class__.__name__})')
            continue
        try:
            W.write_record(d, 'S', REC_S, TestOps())
            check(f'W18 pre-placed symlink at {target} -> EEXIST', False, 'no error')
        except FileExistsError:
            check(f'W18 pre-placed symlink at {target} -> EEXIST, target untouched', open(aim, 'rb').read() == b'x')
        if target != 'S.ok.part':
            check(f'W19 reader refuses symlink at {target} -> CORRUPT or PENDING, never record',
                  rd(d, 'S', 'S') in (ST.CORRUPT, ST.PENDING))

if os.name == 'posix':
    with tempfile.TemporaryDirectory() as d:
        W.write_record(d, 'S', REC_S)                    # настоящие fsync файла и папки
        check('W30 Linux: real fsync write, real barrier read -> record', W.read_record(d, 'S', 'S') == REC_S)
else:
    SKIP.append('W30')
    print('SKIP W30 real fsync of a folder needs Linux (runs in CI lab)')

print(f'ZPROBE_RECSTORE_TESTS {len(OK)}/{len(OK) + len(BAD)} ' + ('PASS' if not BAD else 'FAIL')
      + (f' SKIP={len(SKIP)}' if SKIP else ''))
sys.exit(1 if BAD else 0)
