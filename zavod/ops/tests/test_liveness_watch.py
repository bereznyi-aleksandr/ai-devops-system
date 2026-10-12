# ДОКУМЕНТ: zavod/ops/tests/test_liveness_watch.py
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-12 08:38 +03:00
# ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
# НАЗНАЧЕНИЕ: проверки zavod/ops/liveness_watch.py (E6-4): логика шага (короткий сбой — без тревоги, долгий —
#   одна тревога, повтор не чаще REPEAT, восстановление — одно «снова работает»); сквозной прогон с заглушкой
#   Telegram на 127.0.0.1: продукт «остановлен» → тревога пришла за время не больше GRACE + 2·PERIOD + запас,
#   продукт «вернулся» → одно сообщение; ненастоящий токен не попал в журнал; сбой отправки — тревога повторяется.
# ОГРАНИЧЕНИЯ: временные папки — tempfile.TemporaryDirectory; четыре условия P4.718 те же, что в
#   test_sqlite_backup.py v0.1: tmpdir ОС, один тест одного процесса, итог — вывод unittest, только синтетика.
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import liveness_watch as lw  # noqa: E402

FAKE_TOKEN = '123456:TEST-not-a-real-token'


class WatchLogicTest(unittest.TestCase):
    def test_short_blip_no_alert(self):
        w = lw.Watch(grace=60, repeat=600)
        self.assertIsNone(w.step(0, True))
        self.assertIsNone(w.step(15, False))
        self.assertIsNone(w.step(45, False))
        self.assertIsNone(w.step(60, True))

    def test_long_outage_one_alert_then_repeat_then_up(self):
        w = lw.Watch(grace=60, repeat=600)
        self.assertIsNone(w.step(0, False))
        self.assertEqual(w.step(60, False), 'down')
        self.assertIsNone(w.step(75, False))
        self.assertIsNone(w.step(659, False))
        self.assertEqual(w.step(660, False), 'down')
        self.assertEqual(w.step(675, True), 'up')
        self.assertIsNone(w.step(690, True))


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('content-length', 0))
        body = json.loads(self.rfile.read(n).decode('utf-8'))
        self.server.calls.append({'path_ok': self.path == f'/bot{FAKE_TOKEN}/sendMessage', 'text': body['text'],
                                  'chat': body['chat_id'], 'at': time.monotonic()})
        ok = not self.server.fail_next
        self.server.fail_next = False
        self.send_response(200)
        self.send_header('content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': ok}).encode('utf-8'))

    def log_message(self, *a):
        pass


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = self._td.name
        self.srv = HTTPServer(('127.0.0.1', 0), Stub)
        self.srv.calls = []
        self.srv.fail_next = False
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        self.alive = os.path.join(self.d, 'alive')
        open(self.alive, 'w').close()
        self.check = f'"{sys.executable}" -I -c "import os,sys; sys.exit(0 if os.path.exists(sys.argv[1]) else 1)" "{self.alive}"'
        self.journal = os.path.join(self.d, 'watch.jsonl')

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self._td.cleanup()

    def start(self, steps, period=0.1, grace=0.5):
        send = lw.telegram_sender(self.base, FAKE_TOKEN, '42')
        t = threading.Thread(target=lw.run, args=(self.check, 'p1-bot', period, grace, 100, send, self.journal),
                             kwargs={'max_steps': steps}, daemon=True)
        t.start()
        return t

    def stop_product(self):
        os.replace(self.alive, self.alive + '.stopped')
        return time.monotonic()

    def test_stop_alert_within_bound_then_recovery(self):
        period, grace = 0.1, 0.5
        t = self.start(40, period, grace)
        time.sleep(0.5)
        stopped = self.stop_product()
        deadline = stopped + 10
        while not self.srv.calls and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(len(self.srv.calls), 1)
        delay = self.srv.calls[0]['at'] - stopped
        self.assertLessEqual(delay, grace + 2 * period + 2.0, delay)
        self.assertIn('не работает', self.srv.calls[0]['text'])
        os.replace(self.alive + '.stopped', self.alive)
        t.join(30)
        self.assertEqual([c['text'].endswith('снова работает.') for c in self.srv.calls], [False, True])
        self.assertTrue(all(c['path_ok'] and c['chat'] == '42' for c in self.srv.calls))
        with open(self.journal, encoding='utf-8') as f:
            text = f.read()
        self.assertNotIn(FAKE_TOKEN, text)
        self.assertNotIn('TEST-not-a-real-token', text)
        events = [json.loads(s)['event'] for s in text.splitlines()]
        self.assertEqual([e for e in events if e.startswith('alert')], ['alert_down', 'alert_up'])

    def test_failed_send_is_retried(self):
        self.srv.fail_next = True
        self.stop_product()
        t = self.start(25)
        t.join(30)
        self.assertGreaterEqual(len(self.srv.calls), 2)
        with open(self.journal, encoding='utf-8') as f:
            sent = [json.loads(s).get('sent') for s in f if '"alert_down"' in s]
        self.assertEqual(sent[:2], [False, True])


if __name__ == '__main__':
    unittest.main()
