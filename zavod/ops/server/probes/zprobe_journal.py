#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_journal.py
# ВЕРСИЯ: v0.7 (выпуск B9)  СТАТУС: DRAFT
# v0.7 (2026-11-14 10:40 +02:00, проект B9 v0.9, приёмка ChatGPT REL31 AGREED): журнал B9 рядом с B8. Программа ставится в
#   /usr/local/lib/zavod/probes-b9; журнал и отметки — общие с B8 (/var/lib/zavod/probes/journal, started).
#   Шлюз записи под общим замком journal/.lock (тот же файл, что берёт append B8): цепочка цела (иначе CORRUPT);
#   недописанных сегментов нет вовсе (иначе TORN_HISTORY); каждая серия ровно в одном сегменте с одной START и
#   одной END (иначе CORRUPT); отметки по именам и байтам, orphan допустима только у своей серии (иначе ORPHAN);
#   fsync всех сегментов и папки; запись новой функцией write_segment (байты как у append B8; append не зовётся);
#   подтверждение — строка CONFIRMED по байтам сегмента своей серии. reserve — под тем же замком и только без
#   orphan вовсе (второй одновременный запуск — BUSY до создания отметки). Новые команды: check (только чтение,
#   для preflight), outcome (итог серии для zprobe-start по журналу и journalctl). Таблица итога различает
#   «нет файла», «не читается», «не JSON» (проект v0.4 раздел 3). Функции read_segments, marker, _fsync_dir,
#   reserve — текст B8 без изменений (проверка ast.dump в CI).
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
# ВЫЗОВ (B9): reserve <серия> | commit <серия> (от zprobe) | check | outcome <серия> <курсор journalctl> (от root).
#   Коды B9: 0 — подтверждено; 2 — неверный вызов; 3 — отказ шлюза; 4 — итог не CONFIRMED; 5 — BUSY.
# Прежний вызов B8: zprobe_journal.py reserve <серия>  — отметка начала по /run/zprobe/<серия>/request.json (имя занято — код 3)
#        zprobe_journal.py commit  <серия>  — внести серию по /run/zprobe/<серия>/{request,evidence,cleanup}.json;
#   неполный или неудачный прогон даёт START + END(INTERRUPTED) с причиной.
#   Коды: 0 — записано или уже есть; 2 — неверный вызов; 3 — журнал повреждён, имя занято или нет отметки начала.
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import time

sys.path.insert(0, '/usr/local/lib/zavod/probes-b9')
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


def load3(path):
    """B9 (v0.4 раздел 3): ('ok', объект) | ('missing'|'unreadable'|'bad', None) — причины различаются."""
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except FileNotFoundError:
        return 'missing', None
    except OSError:
        return 'unreadable', None
    try:
        v = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return 'bad', None
    return ('ok', v) if isinstance(v, dict) else ('bad', None)


def load(path):
    return load3(path)[1]


def short_env(ev):
    return hashlib.sha256(json.dumps(ev.get('env'), sort_keys=True).encode()).hexdigest()


def build(series, req, ev, mode, cl=None, ev_state='ok', cl_state='ok'):
    """Записи серии без seq/prev/time. Чистая функция — её проверяют тесты CI. B9: таблица итога v0.4 раздел 3."""
    ch = (req or {}).get('challenge', '-')
    base = {'series': series, 'challenge': ch, 'probe': 'ПБ-1'}
    code = (ev or {}).get('code_sha256', {}).get('pb1_session.py', '-') if isinstance(ev, dict) else '-'
    start = dict(base, kind='SERIES_START', probes=(req or {}).get('probes'))
    if cl_state != 'ok' or not isinstance(cl, dict):
        cl_bad = 'cleanup_' + (cl_state if cl_state != 'ok' else 'missing')
        cl = None
    else:
        cl_bad = R.cleanup_problem(cl)
    complete = mode == 'commit' and ev_state == 'ok' and isinstance(ev, dict) and ev.get('status') == 'RUN_DONE' \
        and ev.get('series') == series and ev.get('challenge') == ch and cl_bad is None
    if not complete:
        if ev_state != 'ok' or not isinstance(ev, dict):
            why = 'runner_' + (ev_state if ev_state != 'ok' else 'missing')
        else:
            why = f"{ev.get('status')}:{ev.get('step')}:{ev.get('reason', '-')}"
        why += '|cleanup:' + (cl_bad or 'SAFE')
        return [start, dict(base, kind='SERIES_END', records=1, status='INTERRUPTED', reason=why[:300], cleanup=cl)]
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


# append B8 — текст без изменений, только для проверок совместимости в CI (проект B9 раздел 3, п. 16 и 18).
# main B9 его не зовёт: запись B9 — write_segment под замком шлюза.
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


class Refused(Exception):
    """Отказ шлюза B9: kind — CORRUPT | TORN_HISTORY | ORPHAN | BUSY | FSYNC | DENIED."""
    def __init__(self, kind, msg):
        super().__init__(msg)
        self.kind = kind


def lock_journal():
    """Общий замок B8 и B9: flock на JDIR/.lock — тот же файл, что берёт append B8 (проект B9 v0.9 раздел 1)."""
    os.makedirs(JDIR, mode=0o750, exist_ok=True)
    lfd = os.open(os.path.join(JDIR, '.lock'), os.O_RDWR | os.O_CREAT | getattr(os, 'O_BINARY', 0), 0o600)
    lk = os.fdopen(lfd, 'rb+')
    fcntl.flock(lk, fcntl.LOCK_EX)
    return lk


def series_key(series):
    return json.dumps({'series': series}, ensure_ascii=False, separators=(',', ':'))[1:-1].encode('utf-8')


def whole_segments(segs, broken):
    """[(имя, байты, записи)] целых сегментов."""
    return [(n, d, [json.loads(x) for x in d.split(b'\n')[:-1]]) for n, d in segs if n not in broken]


def read_markers():
    """{имя: байты} отметок started. Только имена по R.SERIES_NAME и обычные файлы (не ссылки)."""
    if not os.path.lexists(SDIR):
        return {}
    if not stat.S_ISDIR(os.lstat(SDIR).st_mode):
        raise Refused('ORPHAN', 'started is not a directory')
    out = {}
    for n in sorted(os.listdir(SDIR)):
        p = os.path.join(SDIR, n)
        if not R.SERIES_NAME.match(n) or not stat.S_ISREG(os.lstat(p).st_mode):
            raise Refused('ORPHAN', 'foreign entry in started: ' + n[:60])
        fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
        with os.fdopen(fd, 'rb') as f:
            out[n] = f.read()
    return out


def gate_check(series, own_marker, allow_own_orphan):
    """Пункты 1–4 шлюза, только чтение. own_marker — байты отметки серии этого вызова (по её request.json).
    allow_own_orphan=False — orphan не допускается вовсе (reserve, preflight): BUSY. → (segs, wholes, state)."""
    try:
        segs = read_segments(JDIR) if os.path.isdir(JDIR) else []
    except Bad as e:
        raise Refused('CORRUPT', str(e)) from None
    done, broken, why, state = R.journal_chain(segs)
    if why:
        raise Refused('CORRUPT', why)                                     # п. 1
    if broken:
        raise Refused('TORN_HISTORY', 'broken segment in history: ' + broken[0])   # п. 2
    wholes = whole_segments(segs, broken)
    names = {}
    for n, d, recs in wholes:                                             # п. 3
        ss = {r.get('series') for r in recs}
        kinds = [r.get('kind') for r in recs]
        if len(ss) != 1 or kinds.count('SERIES_START') != 1 or kinds.count('SERIES_END') != 1 \
                or not isinstance(recs[0].get('series'), str):
            raise Refused('CORRUPT', f'{n}: segment must hold exactly one series START … END')
        s = recs[0]['series']
        if s in names:
            raise Refused('CORRUPT', f'series {s[:40]} is in two segments: {names[s][0]} and {n}')
        names[s] = (n, recs[0].get('challenge'))
    marks = read_markers()                                                # п. 4
    for s, (n, ch) in names.items():
        if marks.get(s) != marker(s, ch):
            raise Refused('ORPHAN', f'series {s[:40]}: start mark missing or differs')
    for s in marks:
        if s in names:
            continue
        if allow_own_orphan and s == series and own_marker is not None and marks[s] == own_marker:
            continue
        raise Refused('ORPHAN' if allow_own_orphan else 'BUSY', f'start mark without a whole segment: {s[:40]}')
    return segs, wholes, state


def fsync_tail(segs):
    """П. 5: каждый сегмент — fsync (только чтение), затем fsync папки."""
    try:
        for n, _ in segs:
            # Linux — только чтение; Windows (местные испытания) не даёт fsync на дескрипторе только для чтения
            mode = os.O_RDONLY if hasattr(os, 'O_DIRECTORY') else os.O_RDWR | getattr(os, 'O_BINARY', 0)
            fd = os.open(os.path.join(JDIR, n), mode)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        _fsync_dir(JDIR)
    except OSError as e:
        raise Refused('FSYNC', 'fsync failed: ' + type(e).__name__) from None


def write_segment(segs, state, recs):
    """Сегмент B9 — байт в байт как append B8 (проект B9 раздел 1, CI 18). Зовётся только под замком шлюза."""
    seq, prev, pending = state
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
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise Bad(4, 'short write')
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(JDIR)


def seg_of(series, segs):
    """(имя, seq последней строки, SHA-256 последней строки, запись END) целого сегмента серии или None."""
    for n, d in segs:
        lines = d.split(b'\n')
        if lines[-1] != b'' or len(lines) < 3:
            continue
        recs = [json.loads(x) for x in lines[:-1]]
        if recs[0].get('series') == series:
            return n, recs[-1].get('seq'), hashlib.sha256(lines[-2]).hexdigest(), recs[-1]
    return None


def confirm(series):
    """П. 7: сегмент S — fsync, fsync папки; итог по байтам самого сегмента S (не по хвосту журнала)."""
    segs = read_segments(JDIR)
    got = seg_of(series, segs)
    if got is None:
        raise Refused('CORRUPT', 'series segment not found')
    fsync_tail([s for s in segs if s[0] == got[0]])
    return got


def own_marker_from_request(series):
    st, req = load3(os.path.join(RUN, series, 'request.json'))
    if st != 'ok' or req.get('series') != series or not re.fullmatch(r'[0-9a-f]{32}', str(req.get('challenge'))):
        return None, req
    return marker(series, req['challenge']), req


def do_commit(series):
    own, req = own_marker_from_request(series)
    if own is None:
        raise Refused('ORPHAN', 'request.json of this series is missing or differs')
    d = os.path.join(RUN, series)
    with lock_journal():
        segs, wholes, state = gate_check(series, own, True)
        fsync_tail(segs)                                                   # п. 5
        if seg_of(series, segs) is None:                                   # п. 6: ABSENT
            if not os.path.lexists(os.path.join(SDIR, series)):
                raise Refused('ORPHAN', 'series not reserved')
            es, ev = load3(os.path.join(d, 'evidence.json'))
            cs, cl = load3(os.path.join(d, 'cleanup.json'))
            try:
                write_segment(segs, state, build(series, req, ev, 'commit', cl, es, cs))
            except (Bad, OSError) as e:
                raise Refused('FSYNC', 'write failed: ' + str(e)[:80]) from None
            what = 'written'
        else:
            what = 'already'                                               # WHOLE: только подтверждение
        seg, seq, last, end = confirm(series)                              # п. 7
        print(f'ZPROBE_JOURNAL CONFIRMED series={series} seg={seg} seq={seq} last_sha256={last} '
              f'status={end.get("status")} write={what}', flush=True)


def do_reserve(series):
    """M-355-REL29-01: проверка «orphan нет» и создание отметки — под одним общим замком journal/.lock."""
    own, req = own_marker_from_request(series)
    if own is None:
        raise Refused('DENIED', 'request is for another series')
    with lock_journal():
        gate_check(series, None, False)
        if os.path.lexists(os.path.join(SDIR, series)):
            raise Refused('DENIED', 'series name already used')
        try:
            reserve(series, req.get('challenge'))                          # функция B8 без изменений
        except Bad as e:
            raise Refused('DENIED', str(e)) from None
    print(f'ZPROBE_JOURNAL RESERVED series={series}', flush=True)


def journal_digest():
    """Только чтение (preflight, verify-installed): шлюз пп. 1–4, orphan нет вовсе; без замка и fsync."""
    segs, wholes, state = gate_check('', None, False)
    n, h = R.segments_digest(segs)
    return f'ZPROBE_JOURNAL CHECK OK segments={n} digest={h} seq={state[0]} last_sha256={state[1]}'


UNIT_SUCCESS = '7ad2d189f7e94e70a38c781354912448'   # systemd: «Deactivated successfully» (Result=success)


def outcome(series, entries, segs):
    """Итог серии для zprobe-start (проект B9 раздел 2). entries — записи journalctl -o json после курсора начала,
    segs — сегменты журнала. CONFIRMED — только при целом сегменте S и строке CONFIRMED запуска службы журнала,
    у которого systemd записал успешное завершение (UNIT_SUCCESS, тот же INVOCATION_ID); строка совпадает с
    сегментом, seq и last_sha256, вычисленными здесь по сегменту S. Чистая функция — её проверяют тесты."""
    unit = f'zprobe-journal-b9@{series}.service'
    done, broken, why, _ = R.journal_chain(segs)
    if why:
        return 'JOURNAL_REFUSED', why
    if any(series_key(series) in d for n, d in segs if n in broken):
        return 'JOURNAL_REFUSED', 'series is in a broken segment'
    ok_inv, conf, refused = set(), {}, None
    for e in entries:
        if e.get('UNIT') == unit and e.get('MESSAGE_ID') == UNIT_SUCCESS and e.get('INVOCATION_ID'):
            ok_inv.add(e['INVOCATION_ID'])
        if e.get('_SYSTEMD_UNIT') == unit and isinstance(e.get('MESSAGE'), str):
            m = e['MESSAGE']
            if m.startswith('ZPROBE_JOURNAL CONFIRMED '):
                conf.setdefault(e.get('_SYSTEMD_INVOCATION_ID'), []).append(m)
            elif m.startswith('ZPROBE_JOURNAL REFUSED '):
                refused = m[:200]
    mine = seg_of(series, [s for s in segs if s[0] not in broken])
    if mine is None:
        if refused and refused.split(':')[0].split()[-1] in ('TORN_HISTORY', 'CORRUPT', 'ORPHAN'):
            return 'JOURNAL_REFUSED', refused
        return 'UNKNOWN', 'ABSENT'
    n, seq, last, end = mine
    want = f'ZPROBE_JOURNAL CONFIRMED series={series} seg={n} seq={seq} last_sha256={last} status={end.get("status")} '
    good = sorted(i for i in ok_inv if any(m.startswith(want) for m in conf.get(i, [])))
    if not good:
        return 'UNKNOWN', f'WHOLE_UNCONFIRMED seg={n} seq={seq} last_sha256={last}'
    return 'CONFIRMED', (f'SERIES_END {end.get("status")} invocation={good[-1]} seg={n} seq={seq} last_sha256={last} '
                         f'reason={str(end.get("reason"))[:200]}')


def main():
    a = sys.argv[1:]
    if a == ['check']:
        try:
            print(journal_digest(), flush=True)
        except Refused as e:
            print(f'ZPROBE_JOURNAL REFUSED {e.kind}: {e}', flush=True)
            sys.exit(3)
        return
    if len(a) == 3 and a[0] == 'outcome' and R.SERIES_NAME.match(a[1]):
        import subprocess
        p = subprocess.run(['journalctl', '--no-pager', '-o', 'json', '--after-cursor', a[2]], capture_output=True,
                           text=True, timeout=60)
        entries = []
        for line in p.stdout.splitlines():
            try:
                entries.append(json.loads(line))
            except ValueError:
                pass
        try:
            segs = read_segments(JDIR) if os.path.isdir(JDIR) else []
            kind, text = outcome(a[1], entries, segs)
        except Bad as e:
            kind, text = 'JOURNAL_REFUSED', str(e)
        print(f'ZPROBE_OUTCOME {kind} series={a[1]} journalctl_rc={p.returncode} {text}', flush=True)
        sys.exit(0 if kind == 'CONFIRMED' else 4)
    if len(a) != 2 or a[0] not in ('commit', 'reserve') or not re.fullmatch(r'[0-9A-Za-z_-]{1,40}', a[1]):
        print('ZPROBE_JOURNAL REFUSED DENIED: usage', flush=True)
        sys.exit(2)
    if pwd.getpwuid(os.getuid()).pw_name != 'zprobe':
        print('ZPROBE_JOURNAL REFUSED DENIED: must run as zprobe', flush=True)
        sys.exit(2)
    try:
        (do_reserve if a[0] == 'reserve' else do_commit)(a[1])
    except Refused as e:
        print(f'ZPROBE_JOURNAL REFUSED {e.kind}: {e}', flush=True)
        sys.exit(5 if e.kind == 'BUSY' else 3)


if __name__ == '__main__':
    main()
