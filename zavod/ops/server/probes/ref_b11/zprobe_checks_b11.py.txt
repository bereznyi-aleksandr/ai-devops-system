#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_checks.py
# ВЕРСИЯ: v0.6 (выпуск B11)  СТАТУС: DRAFT
# v0.6 (2026-11-17 17:33 +02:00, Claude, терминал zavod): PIN_B9 lid_sha/boot/lo0/c0 = значения D14 с сервера (снимок
#   2026-11-17 17:31, только чтение: n=354791 ids=1 dup=0 bad=0 gaps=0, min=lo0=30356, dt=3 с от начала загрузки,
#   якоря 285041/329536/338444 по одной записи). Исключение B11 теперь открыто только для этой аренды и загрузки.
# v0.5 (2026-11-17 07:51 +02:00, Claude, терминал zavod, помощник; REL97 REVISE 0/3/2): M-01 — PIN_B9 привязан к
#   конкретной аренде и загрузке (lid_sha, boot) и к первой записи загрузки (lo0, c0); значения придут с сервера
#   (диагностика D14), пока None: pinned_b9 закрыт по умолчанию; при H4 по альтернативному пути H5 допускается только
#   через ровно 6 записей с SD (other=0 не принимается). M-03 — сплошность журнала считается от ПЕРВОЙ записи
#   загрузки (отдельный проход -b 0 в collect, seq_ok: min = lo0, первая запись = (lo0, c0)). M-02 — в значениях
#   H4/H5 по альтернативному пути рядом с pin= (хеш закреплённого эталона) стоит obs= (хеш НАБЛЮДЕНИЙ: observations/
#   obs_json; те же байты печатает zprobe_r2 строкой R2_OBS) и наблюдённые bd/sd. L-01 — evaluate не бросает
#   исключений на фактах неверного типа: каждая проверка в своей защите, сбой = FAIL этой проверки.
# v0.4 (2026-11-17 06:51 +02:00, Claude, терминал zavod; REL96B AGREED 0/0/2, PATH=A): R2 v4 на сервере дал
#   BLOCKED failed=H4,H5 (H4 — только h4b: journald перезапущен 15.11 06:28:36Z после unattended-upgrade, позже T0;
#   H5 — только other=6: записи runuser наших R1 v6/v7). Оба факта сняты только чтением (D10–D13) и приняты в R0 v14
#   (REL87, REL89). Добавлены узкие исключения ТОЛЬКО для остатка b9/pb1trial2 с закреплённым T0 (PIN_B9): строгий
#   путь B10 не изменён и проверяется первым. H4: перезапуск journald после T0 принимается, только если старт journald
#   = PIN, MainPID = PIN, PID journald с T0 = ровно PIN, в окне PIN есть сообщение PID 1 «Reexecuting» И журнал с T0
#   сплошной (seq_ok: один __SEQNUM_ID = PIN, наименьший номер = lo, наибольший ≥ hj, номера подряд без повторов,
#   у всех записей текущая загрузка, якоря lo/hi/hj по одному и BD совпал). H5: чужие упоминания аренды собираются
#   все (полный JSON каждой записи — ED); принимаются только если их ровно 6, курсоры разные и SD совпал (это
#   закрепляет каждую запись целиком: курсор, загрузку, время, _UID, юнит, _COMM, полный _CMDLINE, MESSAGE) и
#   seq_ok. Любое несовпадение — FAIL. Значения H4/H5 печатают alt= и pin= (SHA-256 закреплённых значений).
# v0.3 (2026-11-15, терминал zavod, чат cb6b67c5; REL65 M-03, L-03): journal_from_cursor — __CURSOR ПЕРВОЙ записи
#   прохода H5 (не курсор якоря); H5 требует from/to одной загрузки (b=boot, одно s=, i(from) <= i(to)) и якорь H9
#   внутри [from, to]. journal_stream — абсолютный срок на всё чтение (сторож убивает journalctl), исход 124.
# v0.2 (2026-11-14 23:42 +02:00, чат «напарник · 04», 869221b9; проект v0.18 4.1): H8 и H10 — функции h8_ok и h10_ok
#   (их же зовёт повторная сверка после заморозки и после печати), сбор svc_mask(); first_start_request_s — из
#   evidence.start_request_s (бегунок B10 пишет его перед заявкой на запуск).
# ДАТА СОЗДАНИЯ: 2026-11-14 23:31 +02:00  ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · напарник · 03» (d6c11f6b)
# ДАТА ОБНОВЛЕНИЯ: 2026-11-14 23:36 +02:00 (ключ H3 t0 -> tzero: ключ значения proof — только буквы и _)
# НАЗНАЧЕНИЕ: проект B10 v0.18 раздел 1.3 — условия H1–H10 «запуска не было», два проверяющих по вызову:
#   'b9' — только остаток pb1trial2 (R2), 'b10' — только уборка серий B10. Решение — чистая функция evaluate(facts)
#   без системы (полностью проверяется тестами); сбор фактов — collect() (только чтение: journalctl, systemctl show,
#   psql SELECT через stdin, чтение файлов по дескриптору). Один и тот же код для уборки 4.1 и R2 1.6.
# ДОПУЩЕНИЯ (на аудит): времена сравниваются в целых секундах (как R0); T0 = opened_at аренды (секунды эпохи);
#   journal_from_cursor — курсор первой, journal_to_cursor — последней записи прохода H5 (проект §5 «Курсоры»);
#   H8 — только служба аренды (без счёта чужих zagent@).
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import threading

START_JOB = '7d4958e842da4a758f6c1cdc7b36dcc5'      # systemd: «служба запускается»
LOSS = re.compile(r'suppress|missed|corrupt|truncat|ignoring|unclean|failed to write|no space|disk full')
UNIT_FIELDS = ('UNIT', '_SYSTEMD_UNIT', 'OBJECT_SYSTEMD_UNIT', 'USER_UNIT', '_SYSTEMD_USER_UNIT')
HEX32 = re.compile(r'[0-9a-f]{32}')
HEX64 = re.compile(r'[0-9a-f]{64}')
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
SERIES = re.compile(r'[0-9A-Za-z_-]{1,40}')
B9_SERIES = 'pb1trial2'
B9_STATE = {'lease', 'lease_id', 'dropin'}
B10_STATE = {'series', 'runner', 'lease', 'lease_id', 'dropin'}
ROLE, OPENED_BY = '01_install_probe', 'zprobe-run'
MAX_LINE = 1 << 20
CHECKS = tuple(f'H{i}' for i in range(1, 11))
JOURNALCTL = ['journalctl']    # тесты подменяют на зависающий процесс (проверка срока чтения)

# B11: закреплённые значения остатка pb1trial2 (сняты только чтением D10–D13, приняты в R0 v14: REL87, REL89).
#   sid/lo/hi/hj/bd — сплошность журнала с T0 (D10–D12), sd — 6 записей runuser наших R1 целиком (D13),
#   jd_*/rx_* — перезапуск journald автообновлением 15.11 (D8, D10B). Для иных формата, серии и T0 не действуют.
PIN_B9 = {'series': 'pb1trial2', 't0': 1794667569, 'sid': 'd3cdd7404a194a9dbeac067ca4900372',
          'lo': 285041, 'hi': 329536, 'hj': 338444,
          'bd': '9e851c6953367ea654cd8d5b1fbbaeaa831a2922cf171c0e24c41340d7cb2148',
          'sd': '4c61d994cf89b4c4b64a73f63819e9984c9e564fa444a045a3bf3735463152b4', 'self_n': 6,
          'jd_start': 1794724116, 'jd_pid': '383173', 'jd_pids': ['323', '383173'],
          'rx_from': 1794724105, 'rx_to': 1794724117,
          # REL97 M-01/M-03: значения D14 (сервер 2026-11-17 17:31, только чтение)
          'lid_sha': 'ef548a9ac3f3f45e6f0b8fd3c574738a2d6fa677bedcd17f5f36739b47b3c648',  # SHA-256 строки lease_id
          'boot': 'bc77431fecfe48f88031169be02868da',   # boot id без дефисов
          'lo0': 30356,                                 # __SEQNUM первой записи текущей загрузки
          'c0': '671193ec161b0f94f03a8bdd2777ab2b'}     # SHA-256(__CURSOR первой записи загрузки)[:32]
PIN_SHA = hashlib.sha256(json.dumps(PIN_B9, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _h(v):
    return hashlib.sha256(str(v).encode()).hexdigest()


def _d(x):
    """Вложенный факт неверного типа читается как пустой словарь (REL97 L-01)."""
    return x if isinstance(x, dict) else {}


def entry_digest(e):
    """ED: SHA-256 всей записи journald (ключи по порядку) — как R0 v12/v14."""
    return _h(json.dumps(e, sort_keys=True, separators=(',', ':'), ensure_ascii=True))


def seq_new():
    return {'sids': {}, 'min': None, 'max': None, 'count': 0, 'seen': set(), 'dup': 0, 'boot_bad': 0, 'anchors': {},
            'first': None}


def seq_add(q, e, boot, anchors=None):
    """Учёт номера записи для seq_ok (без накопления записей; номера — множеством для поиска повторов).
    first — первая запись прохода: [номер или None, SHA-256(курсора)[:32]] (REL97 M-03)."""
    anchors = anchors or (PIN_B9['lo'], PIN_B9['hi'], PIN_B9['hj'])
    sid = str(e.get('__SEQNUM_ID'))
    c32 = _h(e.get('__CURSOR'))[:32]
    try:
        s = str(e['__SEQNUM'])
        n = int(s, 16) if s.startswith('0x') else int(s)
    except (KeyError, ValueError):
        n = None
    if q['first'] is None:
        q['first'] = [n, c32]
    if n is None:
        q['dup'] += 1
        return
    q['sids'][sid] = q['sids'].get(sid, 0) + 1
    q['count'] += 1
    q['min'] = n if q['min'] is None else min(q['min'], n)
    q['max'] = n if q['max'] is None else max(q['max'], n)
    if n in q['seen']:
        q['dup'] += 1
    q['seen'].add(n)
    if str(e.get('_BOOT_ID')) != str(boot):
        q['boot_bad'] += 1
    if n in anchors:
        q['anchors'].setdefault(str(n), []).append(c32)


def seq_summary(q):
    """Итог учёта номеров для фактов (без множества номеров)."""
    return {'sids': dict(q['sids']), 'min': q['min'], 'max': q['max'], 'count': q['count'], 'uniq': len(q['seen']),
            'dup': q['dup'], 'boot_bad': q['boot_bad'], 'anchors': {k: list(v) for k, v in q['anchors'].items()},
            'first': list(q['first']) if q['first'] is not None else None}


def pin_complete(p):
    """Закрыто по умолчанию (REL97 M-01): PIN действует, только если новые ключи заполнены значениями верного типа."""
    try:
        return type(p['lid_sha']) is str and bool(HEX64.fullmatch(p['lid_sha'])) \
            and type(p['boot']) is str and bool(HEX32.fullmatch(p['boot'])) \
            and type(p['lo0']) is int and type(p['lo']) is int and p['lo0'] <= p['lo'] \
            and type(p['c0']) is str and bool(HEX32.fullmatch(p['c0']))
    except (KeyError, TypeError):
        return False


def bd_observed(s, p=None):
    """BD по наблюдениям: SHA-256 «sid|lo|курсор|hi|курсор|hj|курсор» из сводки seq (якоря lo/hi/hj ровно по одному,
    ровно один __SEQNUM_ID) или None."""
    p = p or PIN_B9
    try:
        sids, an = s['sids'], s['anchors']
        if not isinstance(sids, dict) or len(sids) != 1 or not isinstance(an, dict):
            return None
        c = [an.get(str(p[k])) for k in ('lo', 'hi', 'hj')]
        if any(not isinstance(x, list) or len(x) != 1 for x in c):
            return None
        return _h('%s|%d|%s|%d|%s|%d|%s' % (next(iter(sids)), p['lo'], c[0][0], p['hi'], c[1][0], p['hj'], c[2][0]))
    except (KeyError, TypeError, AttributeError, ValueError):
        return None


def sd_observed(items):
    """SD по наблюдениям: SHA-256 отсортированных «SHA-256(курсора)[:32]:ED» или None."""
    if not isinstance(items, list):
        return None
    return _h(' '.join(sorted(str(x) for x in items)))


def seq_ok(s, p=None):
    """Журнал с ПЕРВОЙ записи загрузки сплошной (REL97 M-03): один __SEQNUM_ID = PIN, наименьший номер = lo0, первая
    запись прохода = (lo0, c0), наибольший ≥ hj, подряд без повторов, одна загрузка, якоря lo/hi/hj ровно по одному и
    BD = SHA-256 «sid|lo|курсор|hi|курсор|hj|курсор» (как R0 v12). Отсутствие или неверный тип поля — False."""
    p = p or PIN_B9
    if not isinstance(s, dict) or not pin_complete(p):
        return False
    try:
        sids, an = s['sids'], s['anchors']
        if not isinstance(sids, dict) or not isinstance(an, dict):
            return False
        mn, mx, cnt, uq, dup, bb = s['min'], s['max'], s['count'], s['uniq'], s['dup'], s['boot_bad']
        if not all(type(x) is int for x in (mn, mx, cnt, uq, dup, bb)):
            return False
        fi = s['first']
        if not (isinstance(fi, list) and len(fi) == 2 and type(fi[0]) is int and fi[0] == p['lo0']
                and fi[1] == p['c0']):
            return False
        if not (list(sids) == [p['sid']] and sids[p['sid']] == cnt and mn == p['lo0'] and mx >= p['hj']
                and cnt == uq == mx - mn + 1 and dup == 0 and bb == 0):
            return False
        return bd_observed(s, p) == p['bd']
    except (KeyError, TypeError, AttributeError, ValueError):
        return False


def self_ok(items, p=None):
    """Чужие упоминания = ровно 6 закреплённых записей R1: курсоры разные и SD = SHA-256 отсортированных
    «SHA-256(курсора)[:32]:ED» (как R0 v12/v14)."""
    p = p or PIN_B9
    if not isinstance(items, list) or len(items) != p['self_n']:
        return False
    if len({str(x).split(':', 1)[0] for x in items}) != p['self_n']:
        return False
    return sd_observed(items) == p['sd']


def pinned_b9(f, T0):
    """Исключения B11 применимы: формат b9, серия и T0 закреплены, PIN полон (закрыто по умолчанию) и привязан к
    конкретной аренде (SHA-256 lease_id) и загрузке (boot id) — REL97 M-01. Проверяется до любого альтернативного пути."""
    try:
        lid = f.get('lid')
        return f.get('fmt') == 'b9' and f.get('series') == PIN_B9['series'] and T0 == PIN_B9['t0'] \
            and pin_complete(PIN_B9) and isinstance(lid, str) and _h(lid) == PIN_B9['lid_sha'] \
            and f.get('boot_now') == PIN_B9['boot']
    except (KeyError, TypeError, AttributeError):
        return False


def observations(f):
    """Наблюдения R2 (REL97 M-02): то, что фактически просканировано, — отдельно от закрепления PIN. Сводка seq (sids,
    min, max, count, uniq, dup, boot_bad, first, курсоры якорей), journald_restart (main_pid, pids, rx), старт journald
    (btime + mono // 1e6), отсортированные other_ed, вычисленные из наблюдений BD и SD, SHA-256 аренды и загрузка."""
    f = _d(f)
    sc = _d(f.get('scan'))
    sq, jx = _d(sc.get('seq')), _d(f.get('journald_restart'))
    lid, bt, mono, ed = f.get('lid'), f.get('btime'), f.get('journald_mono_us'), sc.get('other_ed')
    return {'lid_sha': _h(lid) if isinstance(lid, str) else None, 'boot': f.get('boot_now'),
            'seq': {k: sq.get(k) for k in ('sids', 'min', 'max', 'count', 'uniq', 'dup', 'boot_bad', 'first', 'anchors')},
            'jd': {k: jx.get(k) for k in ('main_pid', 'pids', 'rx')},
            'jd_start': bt + mono // 1000000 if type(bt) is int and type(mono) is int else None,
            'n': sc.get('n'), 'other_n': sc.get('other'), 'other_ed': sorted(str(x) for x in ed) if isinstance(ed, list) else None,
            'bd': bd_observed(sq), 'sd': sd_observed(ed)}


def obs_json(f):
    """Каноническая строка наблюдений (sort_keys, разделители ',' ':'); её SHA-256 = obs в proof; её печатает R2_OBS."""
    try:
        return json.dumps(observations(f), sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    except (TypeError, ValueError, AttributeError):
        return json.dumps({'error': 'unserializable'}, sort_keys=True, separators=(',', ':'))


def obs_sha(f):
    return _h(obs_json(f))


def cursor_parts(c):
    """(s, i, b) курсора journald или None."""
    try:
        d = dict(x.split('=', 1) for x in c.split(';'))
        return d['s'], int(d['i'], 16), d['b']
    except (AttributeError, KeyError, ValueError, TypeError):
        return None


def units(fmt, series):
    """Служба пробы своего формата и служба другого формата (её записи → не прошла)."""
    own, other = ('b9', 'b10') if fmt == 'b9' else ('b10', 'b9')
    return f'zprobe-run-{own}@{series}.service', f'zprobe-run-{other}@{series}.service'


def _n(x):
    """Неотрицательное целое для строки значения (формат proof: только цифры)."""
    return str(max(0, int(x)))


def _i0(x):
    """Целый ноль (не False)."""
    return type(x) is int and x == 0


GUARDED = (TypeError, AttributeError, KeyError, ValueError, IndexError, OverflowError, OSError)


def evaluate(f):
    """Решение по фактам. Возвращает {'ok', 'failed', 'checks', 'boot_id', 't0_utc', 'journal_from_cursor',
    'journal_to_cursor'}; checks — H1…H10 {'ok', 'value'} (H9 ещё 'src'). Любой недостающий факт — не прошла; факт
    неверного типа не бросает исключения, а даёт FAIL своей проверки (REL97 L-01)."""
    f = _d(f)
    fmt, S, lid = f.get('fmt'), f.get('series'), f.get('lid')
    res = {}

    def put(k, ok, value):
        res[k] = {'ok': bool(ok), 'value': value}

    def guard(k, fn):
        try:
            ok, value = fn()
        except GUARDED:
            ok, value = False, 'ERROR'
        put(k, ok, value)

    try:
        L = lid.replace('-', '')
        okargs = fmt in ('b9', 'b10') and SERIES.fullmatch(S) and UUID.fullmatch(lid) \
            and (fmt == 'b10' or S == B9_SERIES) and (fmt == 'b9' or S != B9_SERIES)
    except (AttributeError, TypeError):
        okargs, L = False, ''
    if not okargs:
        return {'ok': False, 'failed': ['ARGS'], 'checks': {}}
    row = _d(f.get('lease_row'))
    T0 = row.get('opened_at_s')
    t0ok = type(T0) is int and T0 > 0
    boot = f.get('boot_now')
    bt = f.get('btime')
    dropin = f'/run/systemd/system/zagent@{L}.service.d/50-zprobe.conf'
    sc = _d(f.get('scan'))
    anc = _d(f.get('anchor'))
    alt = {'h4': False}

    # H1 — личность аренды
    def c1():
        st = _d(f.get('state'))
        want = B9_STATE if fmt == 'b9' else B10_STATE
        h1 = set(st) == want and st.get('lease') == L and st.get('lease_id') == lid and st.get('dropin') == dropin \
            and row.get('lease_id') == lid and row.get('holder_session') == 'zprobe-' + S \
            and row.get('opened_by') == OPENED_BY and row.get('role_key') == ROLE and f.get('evidence_lease') == L
        if fmt == 'b10':
            h1 = h1 and st.get('series') == S and st.get('runner') == 'b10'
        else:
            h1 = h1 and HEX64.fullmatch(str(f.get('state_sha_run'))) and f.get('state_sha_run') == f.get(
                'state_sha_manifest') and anc.get('series') == S and anc.get('lease') == L \
                and anc.get('lease_id') == lid and anc.get('boot_id') == boot
        return h1, f'fmt={fmt.upper()} ' + ('OK' if h1 else 'FAIL')
    guard('H1', c1)

    # H2 — своё событие открытия и одна загрузка; эталон файла службы
    def c2():
        ue = _d(f.get('unit_entries'))
        starts, opens, boots = ue.get('start_jobs') or [], ue.get('lease_open') or [], ue.get('boots') or []
        fr, fe = _d(f.get('fragment')), _d(f.get('fragment_expected'))
        h2 = t0ok and len(starts) == 1 and starts[0] <= T0 and list(boots) == [boot] \
            and f.get('other_runner_count') == 0 and fr.get('safe') is True and fr.get('path') \
            and fr.get('path') == fe.get('path') and HEX64.fullmatch(str(fr.get('sha'))) and fr.get('sha') == fe.get('sha')
        if fmt == 'b10':
            h2 = h2 and len(opens) == 1 and opens[0] <= T0
        else:
            since = f.get('evidence_since_s')
            h2 = h2 and type(since) is int and starts[0] <= since <= T0 if h2 else False
        return h2, f'starts={len(starts)} opens={len(opens)} boots={len(boots)} ' + ('OK' if h2 else 'FAIL')
    guard('H2', c2)

    # H3 — перезагрузок не было
    def c3():
        h3 = t0ok and type(bt) is int and HEX32.fullmatch(str(boot)) and bt < T0
        return h3, f'btime={_n(bt or 0)} tzero={_n(T0 or 0)}'
    guard('H3', c3)

    # B11: закрепление остатка b9/pb1trial2 (аренда, загрузка, T0, PIN полон) — до любого альтернативного пути
    try:
        pin = pinned_b9(f, T0)
        sq = pin and seq_ok(sc.get('seq'))
    except GUARDED:
        pin, sq = False, False

    # H4 — журнал без провала
    def c4():
        fe_s, mono, jact, vrc = f.get('first_entry_s'), f.get('journald_mono_us'), f.get('journald_active'), \
            f.get('verify_rc')
        h4a = type(fe_s) is int and type(bt) is int and fe_s <= bt + 60
        h4b = jact == 'active' and type(mono) is int and mono > 0 and t0ok and type(bt) is int \
            and bt + mono // 1000000 < T0
        h4c = sc.get('rc') == 0 and sc.get('loss') == 0
        # B11: перезапуск journald после T0 — только закреплённый (PIN_B9) и только при сплошном журнале (seq_ok)
        jx = _d(f.get('journald_restart'))
        if pin and not h4b:
            rx = jx.get('rx')
            alt['h4'] = bool(sq and jact == 'active' and type(mono) is int and mono > 0 and type(bt) is int
                             and bt + mono // 1000000 == PIN_B9['jd_start'] and jx.get('main_pid') == PIN_B9['jd_pid']
                             and jx.get('pids') == PIN_B9['jd_pids'] and type(rx) is int and rx >= 1)
        h4 = h4a and (h4b or alt['h4']) and h4c and vrc == 0
        v = f'gap={_n((fe_s or 0) - (bt or 0))} verify={_n(vrc if type(vrc) is int else 99)} ' \
            f'loss={_n(sc.get("loss") or 0)} ' + ('OK' if h4 else 'FAIL')
        if alt['h4']:     # 8 токенов: gap verify loss OK alt obs pin bd (obs — наблюдения, pin — закреплённый эталон)
            v += f' alt=R0V14 obs={obs_sha(f)} pin={PIN_SHA} bd={bd_observed(_d(sc.get("seq")))}'
        return h4, v
    guard('H4', c4)

    # H5 — один проход: есть данные, нет следов службы, zagent-start и чужих упоминаний аренды
    # B11: чужие упоминания допускаются только как ровно 6 закреплённых записей R1 целиком (self_ok) и при seq_ok;
    # если H4 прошёл по альтернативному пути, other=0 не принимается (REL97 M-01): только шесть записей с SD
    def c5():
        oth = sc.get('other')
        h5_alt = bool(pin and type(oth) is int and oth == PIN_B9['self_n'] and sq and self_ok(sc.get('other_ed')))
        other_ok = (_i0(oth) and not alt['h4']) or h5_alt
        h5 = sc.get('rc') == 0 and type(sc.get('n')) is int and sc['n'] > 0 and _i0(sc.get('unit_hits')) \
            and _i0(sc.get('start_hits')) and other_ok
        # курсоры прохода: первая и последняя запись H5 этой загрузки; якорь H9 — внутри [from, to] (REL65 M-03)
        cf, cl = cursor_parts(sc.get('first_cursor')), cursor_parts(sc.get('last_cursor'))
        ca = cursor_parts(anc.get('cursor_after') if fmt == 'b9' else anc.get('cursor'))
        h5 = h5 and bool(cf and cl and ca) and cf[0] == cl[0] == ca[0] and cf[2] == cl[2] == ca[2] == boot \
            and cf[1] <= ca[1] <= cl[1]
        if h5 and h5_alt:   # 8 токенов: n u oth OK alt obs pin sd
            return h5, f'n={_n(sc.get("n"))} u={_n(sc.get("unit_hits"))} oth={_n(oth)} OK alt=R0V14 ' \
                       f'obs={obs_sha(f)} pin={PIN_SHA} sd={sd_observed(sc.get("other_ed"))}'
        return h5, f'n={_n(sc.get("n") or 0)} u={_n(sc.get("unit_hits") or 0)} st={_n(sc.get("start_hits") or 0)} ' \
                   f'oth={_n(sc.get("other") or 0)}'
    guard('H5', c5)

    # H6 — БД
    def c6():
        db = _d(f.get('db'))
        h6 = all(db.get(k) == 0 for k in ('session_start', 'session_start_log', 'gate_command', 'live'))
        return h6, ' '.join(f'{k}={_n(db.get(v) if type(db.get(v)) is int else 99)}' for k, v in (
            ('ss', 'session_start'), ('ssl', 'session_start_log'), ('gc', 'gate_command'), ('live', 'live')))
    guard('H6', c6)

    # H7 — заявок не было
    guard('H7', lambda: (f.get('named_files') == 0,
                         f'named={_n(f.get("named_files") if type(f.get("named_files")) is int else 99)}'))

    # H8 — служба сейчас
    def c8():
        h8 = h8_ok(f.get('svc'))
        return h8, 'INACTIVE' if h8 else 'ACTIVE_OR_UNKNOWN'
    guard('H8', c8)

    # H9 — опорная точка: B9 — якорь R1, B10 — anchor_run.json бегунка
    def c9():
        if fmt == 'b9':
            cur, cus = anc.get('cursor_after'), anc.get('cursor_after_us')
        else:
            cur, cus = anc.get('cursor'), anc.get('cursor_us')
        tok = type(cus) is int and cus > 0
        h9 = tok and t0ok and anc.get('boot_id') == boot and anc.get('lease_id') == lid and anc.get('series') == S \
            and cus // 1000000 >= T0 and f.get('anchor_cursor_ok') is True and isinstance(cur, str) and cur
        if fmt == 'b10':
            fsr = f.get('first_start_request_s')
            h9 = h9 and (fsr is None or (type(fsr) is int and cus // 1000000 <= fsr))
        return h9, f'lag={_n(cus // 1000000 - T0) if tok and t0ok else 0} ' + ('OK' if h9 else 'FAIL')
    guard('H9', c9)
    res['H9']['src'] = 'r1' if fmt == 'b9' else 'run'

    # H10 — маска на месте
    def c10():
        h10 = h10_ok(f.get('mask'))
        return h10, 'MASKED' if h10 else 'MASK_FAIL'
    guard('H10', c10)

    failed = [k for k in CHECKS if not res[k]['ok']]
    out = {'ok': not failed, 'failed': failed, 'checks': res, 'boot_id': boot,
           'journal_from_cursor': sc.get('first_cursor'), 'journal_to_cursor': sc.get('last_cursor')}
    if t0ok:
        try:
            out['t0_utc'] = datetime.datetime.fromtimestamp(T0, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        except (OverflowError, OSError, ValueError):
            pass
    return out


def h8_ok(sv):
    """H8: служба аренды сейчас не работает и не запускалась в этой загрузке."""
    sv = sv if isinstance(sv, dict) else {}
    return sv.get('ActiveState') == 'inactive' and sv.get('InvocationID') == '' and sv.get('ActiveEnterTimestamp') == ''


def h10_ok(m):
    """H10: маска --runtime экземпляра на месте, в /etc объекта нет."""
    m = m if isinstance(m, dict) else {}
    return m.get('link') == '/dev/null' and m.get('LoadState') == 'masked' and m.get('UnitFileState') == \
        'masked-runtime' and m.get('etc_exists') is False


def proof_checks(ev):
    """checks для proof.json: только {'ok': True, 'value'} (+ src у H9); вызывать, когда ev['ok']."""
    if not ev.get('ok'):
        raise ValueError('checks_not_ok')
    return {k: dict(v) for k, v in ev['checks'].items()}


# ---------------------------------------------------------------------------------------------------------------
# Сбор фактов (только чтение). Каждая внешняя команда — свой код; ошибка → факт None, evaluate даст «не прошла».

def _run(args, inp=None, timeout=120):
    p = subprocess.run(args, input=inp, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout


def journal_stream(args, each, timeout=600):
    """journalctl -o json потоком: каждая строка ≤1 МБ разбирается и отдаётся each(запись). Возвращает
    (код, число записей, курсор последней). Вывод не накапливается. Срок timeout — на ВСЁ чтение: сторож убивает
    процесс, даже если он завис без конца строки или без конца вывода; тогда код 124 (REL65 L-03)."""
    p = subprocess.Popen(JOURNALCTL + ['-o', 'json', '--no-pager', '-q'] + args, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    expired = threading.Event()

    def kill():
        expired.set()
        p.kill()
    dog = threading.Timer(timeout, kill)
    dog.daemon = True
    dog.start()
    n, last = 0, None
    try:
        while True:
            ln = p.stdout.readline(MAX_LINE + 1)
            if expired.is_set():
                return 124, n, last
            if not ln:
                break
            if len(ln) > MAX_LINE or not ln.endswith(b'\n'):
                p.kill()
                return 98, n, last
            e = json.loads(ln)
            n += 1
            last = e.get('__CURSOR', last)
            each(e)
        rc = p.wait()
        if expired.is_set():
            return 124, n, last
    finally:
        dog.cancel()
        if p.poll() is None:
            p.kill()
            p.wait()
        p.stdout.close()
    return rc, n, last


def psql_stdin(sql, **vars_):
    """SELECT через stdin (номер аренды не попадает в командную строку и в журнал); переменные — \\set."""
    head = ''.join(f"\\set {k} '{v}'\n" for k, v in vars_.items() if re.fullmatch(r'[0-9A-Za-z_-]{1,64}', str(v)))
    rc, out = _run(['runuser', '-u', 'postgres', '--', 'psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1',
                    '-d', 'bem'], inp=head + sql + '\n')
    if rc != 0:
        raise RuntimeError(f'psql_rc_{rc}')
    return out.strip()


def show(unit, *props):
    rc, out = _run(['systemctl', 'show', unit] + [f'-p{p}' for p in props])
    if rc != 0:
        raise RuntimeError(f'show_rc_{rc}')
    return dict(x.split('=', 1) for x in out.splitlines() if '=' in x)


def read_json_at(path, limit=MAX_LINE):
    """Файл по пути без ссылок на последнем шаге; разбор JSON-объекта. (объект, SHA-256) или (None, None)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None, None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            return None, None
        raw = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    try:
        obj = json.loads(raw)
    except ValueError:
        return None, hashlib.sha256(raw).hexdigest()
    return (obj if isinstance(obj, dict) else None), hashlib.sha256(raw).hexdigest()


def collect(fmt, series, lid, sources):
    """Факты для evaluate. sources — пути файлов: {'state', 'evidence', 'anchor', 'manifest_state_sha' (B9),
    'fragment_expected': {'path','sha'}}; сам ничего не пишет."""
    L = lid.replace('-', '')
    U, OTHER = units(fmt, series)
    unit = f'zagent@{L}.service'
    f = {'fmt': fmt, 'series': series, 'lid': lid}
    with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as fh:
        f['boot_now'] = fh.read().strip().replace('-', '')
    with open('/proc/stat', encoding='ascii') as fh:
        f['btime'] = next(int(x.split()[1]) for x in fh if x.startswith('btime '))
    row = psql_stdin("SELECT json_build_object('lease_id', lease_id, 'status', status, 'holder_session', "
                     "holder_session, 'opened_by', opened_by, 'role_key', role_key, 'opened_at_s', "
                     "floor(extract(epoch FROM opened_at))::bigint) FROM bem_control.chat_lease "
                     "WHERE lease_id = :'id'::uuid", id=lid)
    f['lease_row'] = json.loads(row) if row else None
    T0 = (f['lease_row'] or {}).get('opened_at_s') or 0
    f['state'], f['state_sha_run'] = read_json_at(sources['state'])
    f['state_sha_manifest'] = sources.get('manifest_state_sha')
    ev, _ = read_json_at(sources['evidence'])
    f['evidence_lease'] = (ev or {}).get('lease')
    f['first_start_request_s'] = (ev or {}).get('start_request_s')   # B10: заявки на запуск не было — None
    try:   # B9 пишет evidence.since строкой '%Y-%m-%d %H:%M:%S UTC' (zprobe_runner.py B9:179)
        f['evidence_since_s'] = int(datetime.datetime.strptime((ev or {}).get('since', ''), '%Y-%m-%d %H:%M:%S UTC')
                                    .replace(tzinfo=datetime.timezone.utc).timestamp())
    except (TypeError, ValueError):
        f['evidence_since_s'] = None
    f['anchor'], _ = read_json_at(sources['anchor'])
    a = f['anchor'] or {}
    cur = a.get('cursor_after') if fmt == 'b9' else a.get('cursor')
    if isinstance(cur, str) and cur:
        got = []
        rc, _, _ = journal_stream([f'--cursor={cur}', '-n', '1'], got.append, timeout=60)
        f['anchor_cursor_ok'] = rc == 0 and len(got) >= 1 and got[0].get('__CURSOR') == cur
    ue = {'start_jobs': [], 'lease_open': [], 'boots': set()}
    lease_open = f'ZPROBE_LEASE_OPEN series={series} lease_id={lid}'

    def on_unit(e):
        ue['boots'].add(e.get('_BOOT_ID'))
        t = int(e.get('__REALTIME_TIMESTAMP', '0')) // 1000000
        if e.get('MESSAGE_ID') == START_JOB and e.get('UNIT') == U and e.get('_PID') == '1':
            ue['start_jobs'].append(t)
        if e.get('_SYSTEMD_UNIT') == U and e.get('MESSAGE') == lease_open:
            ue['lease_open'].append(t)
    rc1, _, _ = journal_stream(['-u', U], on_unit)
    if rc1 == 0:
        ue['boots'] = sorted(ue['boots'])
        f['unit_entries'] = ue
    cnt = [0]
    rc2, _, _ = journal_stream(['-u', OTHER], lambda e: cnt.__setitem__(0, cnt[0] + 1))
    f['other_runner_count'] = cnt[0] if rc2 == 0 else None
    try:
        fp = show(U, 'FragmentPath').get('FragmentPath', '')
        fd = os.open(fp, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            fst = os.fstat(fd)
            data = os.read(fd, MAX_LINE)
        finally:
            os.close(fd)
        f['fragment'] = {'path': fp, 'sha': hashlib.sha256(data).hexdigest(),
                         'safe': stat.S_ISREG(fst.st_mode) and fst.st_uid == 0 and not fst.st_mode & 0o022}
    except (OSError, RuntimeError):
        f['fragment'] = None
    f['fragment_expected'] = sources.get('fragment_expected')
    tmin = []     # H4а: самая ранняя запись первых 120 с загрузки (как R0: минимум времени, не первая строка)

    def on_first(e):
        t = int(e.get('__REALTIME_TIMESTAMP', '0')) // 1000000
        if not tmin or t < tmin[0]:
            tmin[:] = [t]
    rc3, _, _ = journal_stream(['-b', '0', '--until', f"@{f['btime'] + 120}"], on_first)
    f['first_entry_s'] = tmin[0] if rc3 == 0 and tmin else None
    jd = show('systemd-journald.service', 'ActiveState', 'ExecMainStartTimestampMonotonic')
    f['journald_active'] = jd.get('ActiveState')
    mono = jd.get('ExecMainStartTimestampMonotonic', '')
    f['journald_mono_us'] = int(mono) if mono.isdigit() else None
    try:
        f['verify_rc'] = subprocess.run(['journalctl', '--verify', '-q'], capture_output=True, timeout=120).returncode
    except subprocess.TimeoutExpired:
        f['verify_rc'] = 124
    if fmt == 'b9' and series == PIN_B9['series']:   # B11: факты закреплённого перезапуска journald (только чтение)
        jr = {'main_pid': show('systemd-journald.service', 'MainPID').get('MainPID')}
        pids, rx = set(), [0]
        rp, _, _ = journal_stream(['-b', '0', '--since', f'@{T0}', 'SYSLOG_IDENTIFIER=systemd-journald'],
                                  lambda e: pids.add(str(e.get('_PID'))))
        jr['pids'] = sorted(pids) if rp == 0 else None
        rr, _, _ = journal_stream(['-b', '0', '--since', f'@{PIN_B9["rx_from"]}', '--until', f'@{PIN_B9["rx_to"]}',
                                   '_PID=1'], lambda e: rx.__setitem__(0, rx[0] + str(e.get('MESSAGE', '')).startswith(
                                       'Reexecuting')))
        jr['rx'] = rx[0] if rr == 0 else None
        f['journald_restart'] = jr
    sc = {'unit_hits': 0, 'start_hits': 0, 'loss': 0, 'other': 0, 'first_cursor': None, 'other_ed': []}
    def on_scan(e):
        if sc['first_cursor'] is None:
            sc['first_cursor'] = e.get('__CURSOR')
        if unit in (e.get(k) for k in UNIT_FIELDS):
            sc['unit_hits'] += 1
        m = e.get('MESSAGE')
        m = m if isinstance(m, str) else str(m)
        if e.get('SYSLOG_IDENTIFIER') == 'systemd-journald' and LOSS.search(m.lower()):
            sc['loss'] += 1
        d = json.dumps(e)
        if L in d or lid in d:
            if e.get('_SYSTEMD_UNIT') == 'zagent-start.service':
                sc['start_hits'] += 1
            elif e.get('_SYSTEMD_UNIT') != U:
                sc['other'] += 1
                if len(sc['other_ed']) <= PIN_B9['self_n']:   # больше 6 не нужно: self_ok всё равно откажет
                    sc['other_ed'].append(_h(e.get('__CURSOR'))[:32] + ':' + entry_digest(e))
    sc['rc'], sc['n'], sc['last_cursor'] = journal_stream(['-b', '0', '--since', f'@{T0}'], on_scan)
    if fmt == 'b9' and series == PIN_B9['series']:
        # REL97 M-03: сплошность — от ПЕРВОЙ записи загрузки, а не с T0: отдельный проход по всей загрузке (надмножество
        # прохода --since T0), только для номеров записей; первая запись прохода запоминается в q['first']
        q = seq_new()
        rq, _, _ = journal_stream(['-b', '0'], lambda e: seq_add(q, e, f['boot_now']), timeout=900)
        sc['seq'] = seq_summary(q) if rq == 0 else None
    f['scan'] = sc
    db = psql_stdin("SELECT json_build_object("
                    "'session_start', (SELECT count(*) FROM bem_control.session_start WHERE lease_id = :'id'::uuid), "
                    "'session_start_log', (SELECT count(*) FROM bem_control.session_start_log WHERE lease_id = "
                    ":'id'::uuid), 'gate_command', (SELECT count(*) FROM bem_control.gate_command WHERE lease_id = "
                    ":'id'::uuid), 'live', (SELECT count(*) FROM bem_control.session_start WHERE lease_id = "
                    ":'id'::uuid AND status IN ('STARTING', 'RUNNING')))", id=lid)
    f['db'] = json.loads(db)
    named = 0
    for d in ('/run/zavod/start', '/run/zavod/stop', '/var/lib/zavod/start-archive', '/var/lib/zavod/start-rejected'):
        try:
            named += sum(1 for n in os.listdir(d) if L in n)
        except FileNotFoundError:
            pass
    f['named_files'] = named
    f.update(svc_mask(unit))
    return f


def svc_mask(unit):
    """Факты H8 и H10 (только чтение): {'svc', 'mask'}; их же берёт повторная сверка уборки 4.1."""
    m = show(unit, 'LoadState', 'UnitFileState')
    try:
        link = os.readlink(f'/run/systemd/system/{unit}')
    except OSError:
        link = None
    m['link'] = link
    m['etc_exists'] = os.path.lexists(f'/etc/systemd/system/{unit}')
    return {'svc': show(unit, 'ActiveState', 'InvocationID', 'ActiveEnterTimestamp'), 'mask': m}
