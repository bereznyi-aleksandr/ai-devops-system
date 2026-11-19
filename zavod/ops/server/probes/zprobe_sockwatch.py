#!/usr/bin/python3 -I
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_sockwatch.py
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-19 12:42 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-19 12:42 +02:00
# ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# НАЗНАЧЕНИЕ: B15 С1 — наблюдение сокетов процесса git и его потомков (DECISION_B15 v0.3/v0.4 часть A). Только чтение
#   /proc своего uid: /proc/<pid>/task/*/children (дерево), /proc/<pid>/stat (starttime, поле 22), /proc/<pid>/fd/*
#   (inode сокетов) и /proc/self/net/tcp{,6} (inode → четвёрка и состояние). Новых прав не нужно: сеанс и git — один
#   uid (DynamicUser), в zagent@ нет ProcSubset=pid. Опрос пропустил короткий сокет — его строки ядра останутся без пары,
#   и zprobe_gitlink.link_verdict() даст NOT_PROVEN (fail-closed).
import os
import threading
import time

import zprobe_gitlink as G


def _read(path):
    try:
        with open(path, encoding='ascii', errors='replace') as fh:
            return fh.read()
    except OSError:
        return None


def starttime(pid):
    s = _read(f'/proc/{pid}/stat')
    if not s or ')' not in s:
        return None
    try:
        return int(s[s.rindex(')') + 2:].split()[19])
    except (ValueError, IndexError):
        return None


def comm(pid):
    return (_read(f'/proc/{pid}/comm') or '').strip()


def tree(root):
    """PID корня и всех потомков (по /proc/<pid>/task/<tid>/children)."""
    out, todo = [], [root]
    while todo:
        p = todo.pop()
        out.append(p)
        try:
            tids = os.listdir(f'/proc/{p}/task')
        except OSError:
            continue
        for t in tids:
            ch = _read(f'/proc/{p}/task/{t}/children') or ''
            todo.extend(int(x) for x in ch.split() if x.isdigit())
    return out


def fd_links(pid):
    try:
        names = os.listdir(f'/proc/{pid}/fd')
    except OSError:
        return []
    out = []
    for n in names:
        try:
            out.append(os.readlink(f'/proc/{pid}/fd/{n}'))
        except OSError:
            continue
    return out


def net_table():
    t = {}
    for f in ('/proc/self/net/tcp', '/proc/self/net/tcp6'):
        s = _read(f)
        if s:
            t.update(G.parse_net_tcp(s))
    return t


class Watch:
    """Опрос дерева git раз в interval секунд в отдельном потоке до stop(). Итог — sockets(): список
    {pid, start, comm, inode, quad, states, first, last} (время — CLOCK_MONOTONIC в микросекундах)."""

    def __init__(self, root_pid, interval=0.02):
        self.root, self.interval = root_pid, interval
        self._seen, self._halt = {}, threading.Event()
        self.polls, self.errors = 0, 0
        self._th = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._th.start()
        return self

    def _run(self):
        while not self._halt.is_set():
            self.poll()
            self._halt.wait(self.interval)
        self.poll()

    def poll(self):
        try:
            now = time.clock_gettime_ns(time.CLOCK_MONOTONIC) // 1000
            pids = tree(self.root)
            want = {}
            for p in pids:
                st = starttime(p)
                if st is None:
                    continue
                for ino in G.socket_inodes(fd_links(p)):
                    want[ino] = (p, st)
            if want:
                net = net_table()
                for ino, (p, st) in want.items():
                    row = net.get(ino)
                    if row is None:
                        continue
                    key = (p, st, ino)
                    rec = self._seen.get(key)
                    if rec is None:
                        rec = self._seen[key] = {'pid': p, 'start': st, 'comm': comm(p), 'inode': ino,
                                                 'quad': row['quad'], 'states': [], 'first': now, 'last': now}
                    if rec['quad'] != row['quad']:
                        rec['quad_changed'] = True
                    if row['state'] not in rec['states']:
                        rec['states'].append(row['state'])
                    rec['last'] = now
            self.polls += 1
        except Exception:   # noqa: BLE001 — сбой опроса не ломает попытку; сокет без пары даст NOT_PROVEN
            self.errors += 1

    def stop(self):
        self._halt.set()
        self._th.join(5)
        return self

    def sockets(self):
        return [dict(r) for r in self._seen.values() if not r.get('quad_changed')]
