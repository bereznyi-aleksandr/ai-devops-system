# ДОКУМЕНТ: zavod/ops/server/probes/ci_b9/iso_probe.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-14 11:02 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 11:02 +02:00
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 05» (c241e855)
# НАЗНАЧЕНИЕ: только для CI B9 (проект v0.3 раздел 2): что видит процесс внутри изоляции службы журнала — сокеты
#   AF_INET, AF_INET6, AF_NETLINK, файловые сокеты хоста, dbus, абстрактный сокет, очереди и память SysV хоста.
#   Тот же код запускается и на хосте (контроль: слушатели хоста есть). Печатает одну строку ZPROBE_ISO {...}.
import ctypes
import errno
import json
import socket
import sys

res = {}
for name, fam, typ in (('inet', socket.AF_INET, socket.SOCK_STREAM), ('inet6', socket.AF_INET6, socket.SOCK_STREAM),
                       ('netlink', socket.AF_NETLINK, socket.SOCK_RAW)):
    try:
        socket.socket(fam, typ).close()
        res[name] = 'ALLOWED'
    except OSError as e:
        res[name] = 'DENIED:' + errno.errorcode.get(e.errno, str(e.errno))
for name, path in (('host_run_sock', '/run/zprobe-ci-host.sock'), ('host_var_sock', '/var/tmp/zprobe-ci-host.sock'),
                   ('dbus', '/run/dbus/system_bus_socket'), ('abstract', '\0zprobe-ci-abstract')):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(3)
        s.connect(path)
        res[name] = 'CONNECTED'
    except OSError as e:
        res[name] = 'DENIED:' + errno.errorcode.get(e.errno, str(e.errno))
    finally:
        s.close()
libc = ctypes.CDLL(None, use_errno=True)
for name, rc in (('msgget', libc.msgget(0x5a50, 0)), ('shmget', libc.shmget(0x5a51, 0, 0))):
    res[name] = 'FOUND' if rc >= 0 else 'DENIED:' + errno.errorcode.get(ctypes.get_errno(), '?')
print('ZPROBE_ISO ' + sys.argv[1] + ' ' + json.dumps(res, sort_keys=True), flush=True)
