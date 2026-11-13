#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_journal.py
# ВЕРСИЯ: v0.6  СТАТУС: DRAFT
# v0.6 (2026-11-13 05:59 +02:00, аудит R5 M-R5-03, L-R5-02): до запуска службы серия получает долговечную отметку
#   начала /var/lib/zavod/probes/started/<серия> (новый файл O_EXCL, fsync файла и папки; команда reserve, её зовёт
#   zprobe-start). Повторная отметка того же имени — отказ навсегда, поэтому имя серии не может быть занято снова,
#   даже если её сегмент оборвался раньше, чем в него попало имя. Сегмент пишется только для серии с отметкой и
#   тем же вызовом. Паспорт ниже исправлен: журнал — папка сегментов, а не один файл.
# v0.5 (2026-11-12 23:41 +02:00, аудит R4 M-R4-04): журнал — папка /var/lib/zavod/probes/journal, одна серия — один
#   НОВЫЙ файл-сегмент 000001.jsonl, 000002.jsonl… (O_EXCL, запись до конца, fsync файла и папки). Обрыв записи
#   оставляет недописанный сегмент как есть (ничего не правится и не удаляется); следующий сегмент продолжает
#   цепочку от последнего целого и называет недописанные в skipped_segments; проверка — R.journal_chain (одна для
#   сервера и телефона). В START — run_utc, в ATTEMPT — окно попытки session_window.
# v0.4 (2026-11-12 23:14 +02:00, аудит R3 M-R3-03): журнал пишется только из ExecStopPost ПОСЛЕ уборки; COMPLETE —
#   лишь при итоге прогона RUN_DONE и уборке SAFE (cleanup.json, проверка R.cleanup_problem), иначе одно новое
#   событие INTERRUPTED с причиной; итог уборки входит в SERIES_END; запись — цикл os.write до конца и fsync.
# ДАТА СОЗДАНИЯ: 2026-11-12 19:05 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-12 19:50 +02:00 (v0.3 по аудиту R2 C-01: в
#   правила передаётся запись START для привязки попыток к назначению). Прежняя (v0.2: аудит ChatGPT STAGE355 R1 —
#   строк из stdin больше не принимает: только свидетельство службы прогона evidence.json, собранное по доверенным
#   полям journald (C-02); исход ставят правила zprobe_rules.py (C-01); серия пишется одним куском START → попытки
#   → END, END.records — число записей своей серии (M-09); любой сбой — запись INTERRUPTED (И.13 п. 2); неверная
#   строка журнала — отказ с кодом 3 без записи (L-11))
# ИСПОЛНИТЕЛЬ: Claude (чат 87eee078-952e-4855-8936-7f4d449aa9ac)
# НАЗНАЧЕНИЕ: журнал проб (протокол Завода v4 ред12, И.13 п. 2; DESIGN_3_5_5_PB1_v0_2.md, раздел 5). Запускается
#   от учётной записи zprobe: reserve — из zprobe-start до запуска службы, commit — последней строкой ExecStopPost
#   службы zprobe-run@<серия>.service. Серия — новый файл-сегмент в папке /var/lib/zavod/probes/journal (строки JSON
#   с цепочкой сумм). Ничего не переписывает и не удаляет; замок flock на время записи; занятое имя — отказ.
# ВЫЗОВ: zprobe_journal.py reserve <серия>  — отметка начала по /run/zprobe/<серия>/request.json (имя занято — код 3)
#        zprobe_journal.py commit  <серия>  — внести серию по /run/zprobe/<серия>/{request,evidence,cleanup}.json;
#   неполный или неудачный прогон даёт START + END(INTERRUPTED) с причиной.
#   Коды: 0 — записано или уже есть; 2 — неверный вызов; 3 — журнал повреждён, имя занято или нет отметки начала.
import fcntl
import hashlib
import json
import os
import pwd
import re
import sys
import time

sys.path.insert(0, '/usr/local/lib/zavod/probes')
import zprobe_rules as R  # noqa: E402

JDIR = '/var/lib/zavod/probes/journal'  # тесты CI подменяют атрибут модуля, не окружение
SDIR = '/var/lib/zavod/probes/started'  # отметки начала серий (R5 M-03); тесты тоже подменяют атрибут
RUN = '/run/zprobe'


class Bad(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def read_segments(jdir):
    """[(имя, байты)] по порядку; в папке допустимы только сегменты NNNNNN.jsonl и файл замка .lock."""
    out = []
    for n in sorted(os.listdir(jdir)):
        if n == '.lock':
            continue
        if not R.SEG_NAME.match(n):
            raise Bad(3, 'foreign file in journal: ' + n[:60])
        with open(os.path.join(jdir, n), 'rb') as f:
            out.append((n, f.read()))
    return out


def marker(series, challenge):
    return f'ZPROBE_STARTED series={series} challenge={challenge}\n'.encode('ascii')


def _fsync_dir(d):
    if hasattr(os, 'O_DIRECTORY'):   # имя нового файла тоже на диске
        dfd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)


def reserve(series, challenge):
    """R5 M-03: отметка начала серии — новый файл; имя уже отмечено — отказ (повтор имени невозможен навсегда)."""
    if not re.fullmatch(r'[0-9a-f]{32}', str(challenge)):
        raise Bad(3, 'bad challenge')
    os.makedirs(SDIR, mode=0o750, exist_ok=True)
    try:
        fd = os.open(os.path.join(SDIR, series), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
                     | getattr(os, 'O_NOFOLLOW', 0), 0o640)
    except FileExistsError:
        raise Bad(3, 'series name already used') from None
    try:
        data = marker(series, challenge)
        if os.write(fd, data) != len(data):
            raise Bad(4, 'short write')
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(SDIR)


def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            v = json.load(f)
        return v if isinstance(v, dict) else None
    except (OSError, ValueError):
        return None


def short_env(ev):
    return hashlib.sha256(json.dumps(ev.get('env'), sort_keys=True).encode()).hexdigest()


def build(series, req, ev, mode, cl=None):
    """Записи серии без seq/prev/time. Чистая функция — её проверяют тесты CI."""
    ch = (req or {}).get('challenge', '-')
    base = {'series': series, 'challenge': ch, 'probe': 'ПБ-1'}
    code = (ev or {}).get('code_sha256', {}).get('pb1_session.py', '-') if isinstance(ev, dict) else '-'
    start = dict(base, kind='SERIES_START', probes=(req or {}).get('probes'))
    cl_bad = R.cleanup_problem(cl)
    complete = mode == 'commit' and isinstance(ev, dict) and ev.get('status') == 'RUN_DONE' \
        and ev.get('series') == series and ev.get('challenge') == ch and cl_bad is None
    if not complete:
        why = 'runner_failed' if not isinstance(ev, dict) else f"{ev.get('status')}:{ev.get('step')}:{ev.get('reason', '-')}"
        why += '|cleanup:' + (cl_bad or 'SAFE')
        return [start, dict(base, kind='SERIES_END', records=1, status='INTERRUPTED', reason=why[:300],
                            cleanup=cl if isinstance(cl, dict) else None)]
    for k in ('targets', 'gh_names', 'cred_paths', 'meta_sha256', 'dns', 'code_sha256', 'env', 'release', 'lease',
              'control', 'lease_state', 'kernel_log', 'run_utc'):
        start[k] = ev.get(k)
    start['proxy_log'] = ev.get('proxy_log', [])
    ctx = {'lease': ev.get('lease'), 'control': ev.get('control', {}), 'proxy_log': start['proxy_log'],
           'start': start}   # R2 C-01: привязка имени попытки к назначению
    atts = [a for a in ev.get('attempts', []) if isinstance(a, dict)]
    judged = R.judge(atts, ctx)
    recs = [start]
    for a, (name, oc, why) in zip(atts, judged):
        recs.append(dict(base, kind='ATTEMPT', name=name, attempt_kind=a.get('kind'), facts=a.get('facts'),
                         outcome=oc, why=why, step=R.step_of(str(name)), code_sha256=code, env=short_env(ev),
                         lease=ev.get('lease'), session_window=a.get('window'),
                         **({'session_seq': a['seq']} if 'seq' in a else {})))
    recs.append(dict(base, kind='SERIES_END', records=len(recs), status='COMPLETE', reason='-', cleanup=cl))
    return recs


def append(series, recs):
    """Серия — новый сегмент. Замок .lock (создаётся один раз, не удаляется). Уже есть целая серия — 'already';
    имя серии есть в недописанном сегменте — отказ (итог такой серии — «прервана», повтор не пишется)."""
    os.makedirs(JDIR, mode=0o750, exist_ok=True)
    lfd = os.open(os.path.join(JDIR, '.lock'), os.O_RDWR | os.O_CREAT | getattr(os, 'O_BINARY', 0), 0o600)
    with os.fdopen(lfd, 'rb+') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            with open(os.path.join(SDIR, series), 'rb') as f:
                mk = f.read()
        except OSError:
            mk = None
        if mk != marker(series, recs[0].get('challenge')):
            raise Bad(3, 'series not reserved')       # R5 M-03: только серия с отметкой начала и тем же вызовом
        segs = read_segments(JDIR)
        done, broken, why, state = R.journal_chain(segs)
        if why:
            raise Bad(3, why)
        seq, prev, pending = state
        if any(r.get('series') == series for r in done):
            return seq, prev, 'already'
        key = json.dumps({'series': series}, ensure_ascii=False, separators=(',', ':'))[1:-1].encode('utf-8')
        if any(key in d for n, d in segs if n in broken):
            raise Bad(3, 'series name is in a broken segment')
        buf = b''
        for i, r in enumerate(recs):
            seq += 1
            r = dict(seq=seq, prev_sha256=prev, time=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **r)
            if i == 0:
                r['skipped_segments'] = pending
            line = json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
            buf += line + b'\n'
            prev = hashlib.sha256(line).hexdigest()
        path = os.path.join(JDIR, '%06d.jsonl' % (len(segs) + 1))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
        try:
            view = memoryview(buf)
            while view:                  # до конца; обрыв оставит недописанный сегмент, его опознает journal_chain
                n = os.write(fd, view)
                if n <= 0:
                    raise Bad(4, 'short write')
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(JDIR)
    return seq, prev, 'written'


def main():
    a = sys.argv[1:]
    if len(a) != 2 or a[0] not in ('commit', 'reserve') or not re.fullmatch(r'[0-9A-Za-z_-]{1,40}', a[1]):
        print('ZPROBE_JOURNAL REFUSED: usage', file=sys.stderr)
        sys.exit(2)
    if pwd.getpwuid(os.getuid()).pw_name != 'zprobe':
        print('ZPROBE_JOURNAL REFUSED: must run as zprobe', file=sys.stderr)
        sys.exit(2)
    series = a[1]
    d = os.path.join(RUN, series)
    if a[0] == 'reserve':
        req = load(os.path.join(d, 'request.json')) or {}
        try:
            if req.get('series') != series:
                raise Bad(3, 'request is for another series')
            reserve(series, req.get('challenge'))
        except Bad as e:
            print('ZPROBE_JOURNAL REFUSED: ' + str(e), file=sys.stderr)
            sys.exit(e.code)
        print(f'ZPROBE_JOURNAL RESERVED series={series}', flush=True)
        return
    recs = build(series, load(os.path.join(d, 'request.json')), load(os.path.join(d, 'evidence.json')), a[0],
                 load(os.path.join(d, 'cleanup.json')))
    try:
        seq, prev, what = append(series, recs)
    except Bad as e:
        print('ZPROBE_JOURNAL REFUSED: ' + str(e), file=sys.stderr)
        sys.exit(e.code)
    print(f'ZPROBE_JOURNAL {what.upper()} series={series} seq={seq} last_sha256={prev} '
          f'status={recs[-1]["status"]}', flush=True)


if __name__ == '__main__':
    main()
