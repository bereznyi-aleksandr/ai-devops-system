# ДОКУМЕНТ: mk_chk08_cmd.py (сборщик строки команды оператора «проверка базы после SQL 08, только чтение», выпуск B10)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 20:12 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
# НАЗНАЧЕНИЕ: одна строка для Termux. chk08.sql подаётся сжатой (gzip, base64), её сумма сверяется после распаковки;
#   psql от postgres с пустым окружением (env -i), цель задана явно (-h /var/run/postgresql -p 5432 -U postgres -d bem),
#   PGOPTIONS=-c default_transaction_read_only=on — база не принимает записи даже вне транзакции файла.
#   Пакет на диске не читается. Успех (rc=0) — только когда последняя строка точно ZPROBE_B10_CHK08=OK;
#   иначе ZPROBE_B10_CHK08=FAILED и rc=3. Изменений нет при любом исходе (READ ONLY + ROLLBACK).
# ЗАПУСК: python mk_chk08_cmd.py <chk08.sql> <число строк lease_seal> <SHA-256 добавленного SQL 08> <выход>
import base64, gzip, hashlib, sys

OK_LINE = 'ZPROBE_B10_CHK08=OK'


def build(chk: bytes, cnt: str, expect: str) -> str:
    assert cnt.isdigit() and 0 < int(cnt) < 1000
    assert len(expect) == 64 and all(c in '0123456789abcdef' for c in expect)
    csha = hashlib.sha256(chk).hexdigest()
    b64 = base64.b64encode(gzip.compress(chk, mtime=0)).decode()
    return (
        'clear; (set -eu -o pipefail; umask 022; cd /root; '
        f"Q=$(printf %s '{b64}' | base64 -d | gunzip -c && printf x) "
        '|| { echo "REFUSED: check does not decode; nothing run"; exit 1; }; Q=${Q%x}; '
        f'[ "$(printf %s "$Q" | sha256sum | cut -c1-64)" = "{csha}" ] '
        '|| { echo "REFUSED: check differs; nothing run"; exit 1; }; '
        'O=$(printf %s "$Q" | runuser -u postgres -- env -i PATH=/usr/bin:/bin LC_ALL=C.UTF-8 '
        "PGOPTIONS='-c default_transaction_read_only=on' "
        'psql -X -A -t -q -v ON_ERROR_STOP=1 -h /var/run/postgresql -p 5432 -U postgres -d bem '
        f'-v cnt={cnt} -v expect={expect} -f - 2>&1) '
        '|| { printf \'%s\\n\' "$O" | tail -8 | cut -c1-220; echo "ZPROBE_B10_CHK08=FAILED: see the line above; nothing changed"; exit 3; }; '
        'printf \'%s\\n\' "$O" | tail -8 | cut -c1-220; '
        f'[ "$(printf \'%s\\n\' "$O" | tail -1)" = "{OK_LINE}" ] '
        '|| { echo "ZPROBE_B10_CHK08=FAILED: last line differs; nothing changed"; exit 3; }) '
        '2>&1 | tail -20; echo "rc=${PIPESTATUS[0]}"'
    )


if __name__ == '__main__':
    chk = open(sys.argv[1], 'rb').read()
    line = build(chk, sys.argv[2], sys.argv[3])
    with open(sys.argv[4], 'x', encoding='utf-8', newline='\n') as f:
        f.write(line + '\n')
    print(len(line), hashlib.sha256((line + '\n').encode()).hexdigest())
