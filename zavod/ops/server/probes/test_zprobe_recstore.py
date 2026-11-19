#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/test_zprobe_recstore.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:57 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 12:57 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: офлайн-тесты части C проекта DECISION_B15_PUSH_AND_START v0.4 (zprobe_recstore.py + PENDING в
#   zprobe_start_status.classify): чтение после шага 1 до .ok (служба жива → QUEUED, мертва → UNKNOWN); .ok пропал после
#   сбоя питания; .ok с чужой суммой; .ok без данных; ошибка fsync на шаге 1 и fsync папки (нет .ok); два писателя одного
#   имени (EEXIST у второго, данные первого целы); заранее положенная символьная ссылка на месте <имя> или <имя>.ok.
# ОГРАНИЧЕНИЯ: временные папки — tempfile.TemporaryDirectory (в ОС-папке временных файлов, живут один прогон, ничего
#   не доказывают сами: итог — строка ZPROBE_RECSTORE_TESTS). Символьные ссылки на Windows без прав — SKIP с причиной.
import hashlib
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
    """fsync папки на Windows недоступен — в тестах заменён счётчиком; сбой можно включить на нужном вызове."""
    def __init__(self, fail_fsync_at=None, fail_dir_at=None):
        self.n_fsync, self.n_dir = 0, 0
        self.fail_fsync_at, self.fail_dir_at = fail_fsync_at, fail_dir_at

    def fsync(self, fd):
        self.n_fsync += 1
        if self.n_fsync == self.fail_fsync_at:
            raise OSError(5, 'EIO injected')
        os.fsync(fd)

    def fsync_dir(self, d):
        self.n_dir += 1
        if self.n_dir == self.fail_dir_at:
            raise OSError(5, 'EIO injected (dir)')


def status(d, unit):
    rec = {'R': dict(REC_I), 'I': W.read_record(d, 'I', 'I'), 'Q': None,
           'S': [x for x in [W.read_record(d, 'S', 'S')] if x is not None], 'E': []}
    return ST.classify(SER, rec, unit)


with tempfile.TemporaryDirectory() as d:
    # Нормальный путь: данные + .ok → запись читается
    h = W.write_record(d, 'S', REC_S, TestOps())
    got = W.read_record(d, 'S', 'S')
    check('W01 write then read -> record', got == REC_S)
    okline = open(os.path.join(d, 'S.ok'), 'rb').read()
    check('W02 .ok holds SHA-256 of data file', okline == f'OK sha256={h}\n'.encode()
          and hashlib.sha256(open(os.path.join(d, 'S'), 'rb').read()).hexdigest() == h)
    check('W03 files are read-only 0444 on POSIX', os.name != 'posix'
          or (os.stat(os.path.join(d, 'S')).st_mode & 0o777) == 0o444)
    # Два писателя одного имени
    try:
        W.write_record(d, 'S', dict(REC_S, invocation_id='b' * 32), TestOps())
        check('W04 second writer of the same name -> EEXIST', False, 'no error')
    except FileExistsError:
        check('W04 second writer of the same name -> EEXIST', W.read_record(d, 'S', 'S') == REC_S)
    # Имена
    for bad in ('../x', '.hidden', 'S.ok'):
        try:
            W.write_record(d, bad, REC_S, TestOps())
            check(f'W05 bad name {bad!r} refused', False)
        except ValueError:
            check(f'W05 bad name {bad!r} refused', True)

for label, unit, want in (('alive', ALIVE, 'QUEUED'), ('dead', DEAD, 'UNKNOWN')):
    with tempfile.TemporaryDirectory() as d:
        W.write_record(d, 'I', REC_I, TestOps())
        open(os.path.join(d, 'S'), 'wb').write(W.encode(REC_S))      # шаг 1 сделан, .ok ещё нет
        check(f'W06 read after step 1 before .ok -> PENDING ({label})', W.read_record(d, 'S', 'S') == ST.PENDING)
        st = status(d, unit)
        check(f'W07 status: data without .ok, unit {label} -> {want}', st[0] == want, st[1])

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'I', REC_I, TestOps())
    full = W.encode(REC_S)
    open(os.path.join(d, 'S'), 'wb').write(full[:len(full) // 2])   # обрыв посреди шага 1
    check('W08 torn data without .ok -> PENDING (not CORRUPT)', W.read_record(d, 'S', 'S') == ST.PENDING)
    check('W09 torn data, unit dead -> UNKNOWN', status(d, DEAD)[0] == 'UNKNOWN')

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'I', REC_I, TestOps())
    W.write_record(d, 'S', REC_S, TestOps())
    os.replace(os.path.join(d, 'S.ok'), os.path.join(d, 'lost.ok.bak'))   # .ok пропал после сбоя питания
    check('W10 .ok lost after power cut, unit dead -> UNKNOWN (not STARTED)', status(d, DEAD)[0] == 'UNKNOWN')
    check('W11 .ok lost after power cut, unit alive -> QUEUED (not STARTED)', status(d, ALIVE)[0] == 'QUEUED')

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'S', REC_S, TestOps())
    os.chmod(os.path.join(d, 'S.ok'), 0o644)
    open(os.path.join(d, 'S.ok'), 'wb').write(b'OK sha256=' + b'0' * 64 + b'\n')
    check('W12 .ok with another sum -> CORRUPT', W.read_record(d, 'S', 'S') == ST.CORRUPT)
    open(os.path.join(d, 'S.ok'), 'wb').write(b'OK sha256=zz\n')
    check('W13 .ok malformed -> CORRUPT', W.read_record(d, 'S', 'S') == ST.CORRUPT)

with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'S.ok'), 'wb').write(b'OK sha256=' + b'0' * 64 + b'\n')
    check('W14 .ok without data -> CORRUPT', W.read_record(d, 'S', 'S') == ST.CORRUPT)
    W.write_record(d, 'I', REC_I, TestOps())
    rec = {'R': dict(REC_I), 'I': W.read_record(d, 'I', 'I'), 'Q': None, 'S': [W.read_record(d, 'S', 'S')], 'E': []}
    check('W15 status with .ok without data -> UNKNOWN', ST.classify(SER, rec, ALIVE)[0] == 'UNKNOWN')

for label, ops in (('file fsync step 1', TestOps(fail_fsync_at=1)), ('dir fsync step 1', TestOps(fail_dir_at=1)),
                   ('file fsync step 2', TestOps(fail_fsync_at=2)), ('dir fsync step 2', TestOps(fail_dir_at=2))):
    with tempfile.TemporaryDirectory() as d:
        try:
            W.write_record(d, 'S', REC_S, ops)
            check(f'W16 {label} error -> writer raises', False, 'no error')
        except OSError:
            step1 = 'step 1' in label
            no_ok = not os.path.exists(os.path.join(d, 'S.ok'))
            # шаг 1: .ok не создан; шаг 2 (сбой fsync самого .ok или папки после него): писатель падает, итог
            # определит чтение — .ok мог не дойти до диска; повтора нет.
            check(f'W16 {label} error -> writer raises' + (', no .ok' if step1 else ''), no_ok if step1 else True)

with tempfile.TemporaryDirectory() as d:
    W.write_record(d, 'I', REC_I, TestOps())
    try:
        W.write_record(d, 'S', REC_S, TestOps(fail_fsync_at=1))
    except OSError:
        pass
    check('W17 status after fsync error step 1, unit dead -> UNKNOWN', status(d, DEAD)[0] == 'UNKNOWN')

for target in ('S', 'S.ok'):
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
            check(f'W18 pre-placed symlink at {target} -> EEXIST, target untouched',
                  open(aim, 'rb').read() == b'x')
        if os.name == 'posix':
            check(f'W19 reader refuses symlink at {target} -> CORRUPT', W.read_record(d, 'S', 'S') == ST.CORRUPT)

print(f'ZPROBE_RECSTORE_TESTS {len(OK)}/{len(OK) + len(BAD)} ' + ('PASS' if not BAD else 'FAIL')
      + (f' SKIP={len(SKIP)}' if SKIP else ''))
sys.exit(1 if BAD else 0)
