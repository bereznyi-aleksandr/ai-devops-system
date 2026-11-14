# ДОКУМЕНТ: zavod/ops/server/probes/ci_b9/mkstate.py
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-14 11:02 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 11:17 +02:00
# v0.2: код журнала B9 — из папки $ZJLIB (копия исходников; до установки B9 папки LIB нет).
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 05» (c241e855)
# НАЗНАЧЕНИЕ: только для CI B9: собирает состояния журнала /var/lib/zavod/probes кодом проверки (только новые файлы,
#   ничего не меняет и не удаляет). Запуск от zprobe:
#   seg S STATUS [--markch CH | --nomark]  — целый сегмент серии S (COMPLETE|INTERRUPTED) и её отметка
#   mark S CH | rawmark S TEXT | foreign NAME — отметка B8 reserve() | отметка с любыми байтами | посторонний файл
#   torn [S]   — недописанный сегмент (без имени или с именем серии S)
#   dup S      — две целые сцепленные записи одной серии S
#   midbad S S2 — сегмент серии S с испорченной строкой, за ним целый сегмент S2 (порча — в середине журнала)
#   b8 S MODE  — append B8 (код коммита B8 из $ZB8): MODE ok | hold-die | hold-ok (удержание после полного write до
#                fsync под .lock до файла /run/zprobe/ci-control/release-S; die — выход до fsync)
#   digest     — печать CHECK: число сегментов, якорь, seq, последний SHA-256
import importlib.util
import json
import os
import sys
import time

sys.path.insert(0, os.environ.get('ZJLIB', '/usr/local/lib/zavod/probes-b9'))
import zprobe_journal as J  # noqa: E402
import zprobe_rules as R  # noqa: E402

D = '/var/lib/zavod/probes'
J.JDIR, J.SDIR = os.path.join(D, 'journal'), os.path.join(D, 'started')
C = '0123456789abcdef0123456789abcdef'
CL = {'status': 'SAFE', 'unit_active_after': 'inactive', 'load_state': 'masked', 'session_state': 'INTERRUPTED',
      'kept_copy': '/var/lib/zavod/probes/archive/s1/50-zprobe.conf', 'lease': 'a' * 32}


def recs(s, status):
    req = {'challenge': C, 'probes': ['ПБ-1'], 'series': s}
    ev = {'status': 'RUN_DONE', 'series': s, 'challenge': C, 'code_sha256': {}, 'attempts': []}
    return J.build(s, req, ev if status == 'COMPLETE' else None, 'commit', CL)


def state():
    os.makedirs(J.JDIR, mode=0o750, exist_ok=True)
    os.makedirs(J.SDIR, mode=0o750, exist_ok=True)
    segs = J.read_segments(J.JDIR)
    return segs, R.journal_chain(segs)[3]


def new(path, data):
    with open(path, 'xb') as f:
        f.write(data)


def main():
    a = sys.argv[1:]
    k = a[0]
    if k == 'seg':
        segs, st = state()
        if '--nomark' not in a:
            new(os.path.join(J.SDIR, a[1]), J.marker(a[1], a[a.index('--markch') + 1] if '--markch' in a else C))
        J.write_segment(segs, st, recs(a[1], a[2]))
    elif k == 'mark':
        state()
        J.reserve(a[1], a[2])
    elif k == 'rawmark':
        state()
        new(os.path.join(J.SDIR, a[1]), a[2].encode('utf-8'))
    elif k == 'foreign':
        state()
        new(os.path.join(J.SDIR, a[1]), b'x\n')
    elif k == 'torn':
        segs, st = state()
        body = b'{"seq"' if len(a) == 1 else ('{"series":"%s","seq"' % a[1]).encode()
        new(os.path.join(J.JDIR, '%06d.jsonl' % (len(segs) + 1)), body)
    elif k == 'dup':
        segs, st = state()
        new(os.path.join(J.SDIR, a[1]), J.marker(a[1], C))
        J.write_segment(segs, st, recs(a[1], 'COMPLETE'))
        segs, st = state()
        J.write_segment(segs, st, recs(a[1], 'COMPLETE'))
    elif k == 'midbad':
        segs, st = state()
        new(os.path.join(J.SDIR, a[1]), J.marker(a[1], C))
        rows = recs(a[1], 'INTERRUPTED')
        seq, prev, pend = st
        lines = []
        for i, r in enumerate(rows):
            r = dict(seq=seq + i + 1, prev_sha256=prev, time='2026-11-14T00:00:00Z', **r)
            if i == 0:
                r['skipped_segments'] = pend
            ln = json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            lines.append(ln)
            prev = J.hashlib.sha256(ln).hexdigest()
        lines[0] = lines[0].replace(b'{"', b'{x', 1)
        new(os.path.join(J.JDIR, '%06d.jsonl' % (len(segs) + 1)), b''.join(x + b'\n' for x in lines))
        # вслед — целый сегмент серии a[2], сцепленный с испорченным: испорченная строка оказывается в середине
        segs = J.read_segments(J.JDIR)
        new(os.path.join(J.SDIR, a[2]), J.marker(a[2], C))
        J.write_segment(segs, (seq + len(rows), prev, 0), recs(a[2], 'COMPLETE'))
    elif k == 'b8':
        spec = importlib.util.spec_from_file_location('zj8', os.path.join(os.environ['ZB8'], 'zprobe_journal.py'))
        B8 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(B8)
        B8.JDIR, B8.SDIR = J.JDIR, J.SDIR
        s, mode = a[1], a[2]
        real = B8.os.fsync

        def fs(fd):
            try:
                with open(f'/proc/self/fd/{fd}', 'rb') as f:
                    data = f.read()
            except OSError:
                data = b''
            if mode != 'ok' and J.series_key(s) in data:
                print(f'CI_B8_HOLD series={s}', flush=True)
                while not os.path.exists('/run/zprobe/ci-control/release-' + s):
                    time.sleep(0.2)
                if mode == 'hold-die':
                    print('CI_B8_DIE before fsync', flush=True)
                    os._exit(1)
            return real(fd)
        B8.os.fsync = fs
        state()
        B8.reserve(s, C)
        B8.append(s, recs(s, 'INTERRUPTED'))
        print(f'CI_B8_APPENDED series={s}', flush=True)
    elif k == 'digest':
        try:
            print(J.journal_digest())
        except J.Refused as e:
            print(f'ZPROBE_JOURNAL REFUSED {e.kind}: {e}')


main()
