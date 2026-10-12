# ДОКУМЕНТ: zavod/ops/liveness_watch.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:38 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: этап 6, критерий E6-4 — сторож живости продукта. Каждые PERIOD секунд запускает команду проверки
#   (на сервере: systemctl is-active --quiet <служба>); код 0 — жив. Если продукт не жив подряд дольше GRACE
#   секунд — одна тревога оператору в Telegram (sendMessage); пока продукт лежит, тревога повторяется не чаще
#   REPEAT секунд; когда продукт снова жив — одно сообщение «снова работает». Журнал — строки JSON: время,
#   событие, код проверки, итог отправки. Токен берётся только из переменной окружения ALERT_BOT_TOKEN и в
#   журнал, вывод и текст сообщений не попадает.
# ОГРАНИЧЕНИЯ: только stdlib Python 3. Сторож сам продукт не перезапускает (это делает systemd Restart=) и
#   ничего не удаляет. Сбой отправки тревоги пишется в журнал и повторяется на следующем шаге.
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

VERSION = 'v0.1'


class Watch:
    """Логика без времени и сети: шаг получает текущее время и итог проверки, возвращает, что отправить."""

    def __init__(self, grace, repeat):
        self.grace = grace
        self.repeat = repeat
        self.down_since = None
        self.alerted_at = None

    def step(self, now, alive):
        if alive:
            was_alerted = self.alerted_at is not None
            self.down_since = None
            self.alerted_at = None
            return 'up' if was_alerted else None
        if self.down_since is None:
            self.down_since = now
        if now - self.down_since < self.grace:
            return None
        if self.alerted_at is None or now - self.alerted_at >= self.repeat:
            self.alerted_at = now
            return 'down'
        return None


def telegram_sender(base, token, chat_id, timeout=20):
    def send(text):
        body = json.dumps({'chat_id': chat_id, 'text': text}).encode('utf-8')
        req = urllib.request.Request(f'{base}/bot{token}/sendMessage', data=body,
                                     headers={'content-type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8')).get('ok') is True
        except Exception:
            return False
    return send


def run(check_cmd, name, period, grace, repeat, send, journal, clock=time.monotonic, sleep=time.sleep, max_steps=None):
    w = Watch(grace, repeat)
    steps = 0

    def log(o):
        with open(journal, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': datetime.now(timezone.utc).isoformat(timespec='seconds'), **o},
                               ensure_ascii=False) + '\n')

    log({'event': 'start', 'tool': f'liveness_watch {VERSION}', 'name': name, 'period': period, 'grace': grace,
         'repeat': repeat})
    while max_steps is None or steps < max_steps:
        steps += 1
        try:
            rc = subprocess.run(check_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=max(1, period)).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
        now = clock()
        what = w.step(now, rc == 0)
        if what == 'down':
            ok = send(f'Завод: {name} не работает больше {grace} с. Проверьте сервер.')
            log({'event': 'alert_down', 'rc': rc, 'sent': ok})
            if not ok:
                w.alerted_at = None
        elif what == 'up':
            ok = send(f'Завод: {name} снова работает.')
            log({'event': 'alert_up', 'sent': ok})
        elif rc != 0:
            log({'event': 'not_alive', 'rc': rc})
        sleep(period)
    log({'event': 'stop', 'steps': steps})


def main(argv):
    if len(argv) < 2:
        print('usage: liveness_watch.py NAME CHECK_CMD  (env: ALERT_BOT_TOKEN, ALERT_CHAT_ID, WATCH_JOURNAL, '
              'WATCH_PERIOD=15, WATCH_GRACE=60, WATCH_REPEAT=1800, TELEGRAM_API_BASE, WATCH_MAX_STEPS)', file=sys.stderr)
        return 2
    token = os.environ.get('ALERT_BOT_TOKEN', '')
    chat = os.environ.get('ALERT_CHAT_ID', '')
    if not token or not chat:
        print('ALERT_BOT_TOKEN and ALERT_CHAT_ID are required', file=sys.stderr)
        return 2
    base = os.environ.get('TELEGRAM_API_BASE', 'https://api.telegram.org').rstrip('/')
    ms = os.environ.get('WATCH_MAX_STEPS')
    run(argv[1], argv[0], float(os.environ.get('WATCH_PERIOD', '15')), float(os.environ.get('WATCH_GRACE', '60')),
        float(os.environ.get('WATCH_REPEAT', '1800')), telegram_sender(base, token, chat),
        os.environ.get('WATCH_JOURNAL', 'liveness_watch.jsonl'), max_steps=int(ms) if ms else None)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
