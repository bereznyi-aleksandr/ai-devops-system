# ДОКУМЕНТ: zavod/ops/server/test_pty_drive.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-09 14:05 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сменщик 03, сессия ae87bcd9)
# НАЗНАЧЕНИЕ: только для испытаний CI (test_login_3_5_2.sh), на сервер не ставится. Запускает программу в настоящем
#   терминале (псевдотерминал, PTY — как сеанс SSH) и «набирает» за оператора по списку шагов; всё, что программа
#   показала на экране, печатает в свой вывод. Так проверяется то, что при вводе из канала не видно: показ ввода (echo),
#   сброс хвоста вставки, подтверждение кодом.
# ВЫЗОВ: python3 -I test_pty_drive.py STEPS_FILE|- COMMAND [ARGS...]. Код возврата — код программы (124 — не закончилась
#   за 120 с и остановлена). Шаги, по одному в строке:
#   e REGEX — ждать (до 60 с) появления REGEX на экране после прошлого совпадения;
#   s TEXT  — отправить TEXT (\n \r \t \x03 \x04 — перевод строки, CR, табуляция, Ctrl+C, Ctrl+D);
#   c REGEX — ждать REGEX и отправить его первую группу и перевод строки (код подтверждения с экрана);
#   w SEC   — пауза.
#   Если программа закончилась раньше, чем появилось ожидаемое, остальные шаги не выполняются.
import codecs, os, pty, re, select, signal, sys, time

src = sys.stdin if sys.argv[1] == '-' else open(sys.argv[1], encoding='utf-8')
steps = [l.rstrip('\n') for l in src if l.strip()]
cmd = sys.argv[2:]
pid, fd = pty.fork()
if pid == 0:
    os.execvp(cmd[0], cmd)
out = sys.stdout.buffer
buf = b''
pos = 0
alive = True
start = time.time()


def pump(t):
    global buf
    r, _, _ = select.select([fd], [], [], t)
    if not r:
        return True
    try:
        d = os.read(fd, 4096)
    except OSError:
        return False
    if not d:
        return False
    buf += d
    out.write(d)
    out.flush()
    return True


for st in steps:
    kind, _, arg = st.partition(' ')
    if kind in ('e', 'c'):
        rx = re.compile(arg.encode())
        end = time.time() + 60
        m = None
        while True:
            m = rx.search(buf, pos)
            if m or not alive or time.time() > end:
                break
            alive = pump(0.2)
        if not m:
            break
        pos = m.end()
        if kind == 'c':
            os.write(fd, m.group(1) + b'\n')
    elif kind == 's':
        os.write(fd, codecs.decode(arg, 'unicode_escape').encode('latin-1'))
    elif kind == 'w':
        time.sleep(float(arg))
    else:
        sys.exit('bad step: ' + st)

while alive and time.time() - start < 120:
    alive = pump(1.0)
if alive:
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    out.write(b'\nPTY_DRIVE_TIMEOUT\n')
    sys.exit(124)
_, status = os.waitpid(pid, 0)
sys.exit(os.waitstatus_to_exitcode(status))
