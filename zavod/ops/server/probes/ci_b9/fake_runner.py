# ДОКУМЕНТ: zavod/ops/server/probes/ci_b9/fake_runner.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-14 11:02 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 11:02 +02:00
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 05» (c241e855)
# НАЗНАЧЕНИЕ: только для CI B9: заменяет строки прогона и уборки службы zprobe-run-b9@ (клетки, ядра и сети на
#   машине CI нет). Файлы пишет настоящей put_new прогонщика B9 (0640 root:zprobe). Вид серии — файл
#   /run/zprobe/ci-control/mode-<серия>: ok (по умолчанию) | slow | crash | cleanupfail.
import grp
import json
import os
import sys
import time

sys.path.insert(0, '/usr/local/lib/zavod/probes-b9')
import zprobe_runner as N  # noqa: E402

what, s = sys.argv[1], sys.argv[2]
d = os.path.join('/run/zprobe', s)
gid = grp.getgrnam('zprobe').gr_gid
mp = os.path.join('/run/zprobe/ci-control', 'mode-' + s)
mode = open(mp, encoding='ascii').read().strip() if os.path.exists(mp) else 'ok'
with open(os.path.join(d, 'request.json'), encoding='utf-8') as f:
    req = json.load(f)
CL = {'status': 'SAFE', 'unit_active_after': 'inactive', 'load_state': 'masked', 'session_state': 'INTERRUPTED',
      'kept_copy': '/var/lib/zavod/probes/archive/s1/50-zprobe.conf', 'lease': 'a' * 32}
if what == 'run':
    if mode == 'slow':
        time.sleep(8)
    if mode == 'crash':
        print('CI_RUNNER_CRASH', flush=True)
        sys.exit(1)
    N.put_new(os.path.join(d, 'evidence.json'), json.dumps({'status': 'RUN_DONE', 'series': s,
                                                           'challenge': req['challenge'], 'code_sha256': {},
                                                           'attempts': []}), 0o640, gid)
else:
    N.put_new(os.path.join(d, 'cleanup.json'), 'not json' if mode == 'cleanupfail' else json.dumps(CL), 0o640, gid)
