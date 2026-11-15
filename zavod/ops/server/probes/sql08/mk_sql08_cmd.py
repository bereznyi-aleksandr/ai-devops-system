# ДОКУМЕНТ: mk_sql08_cmd.py (сборщик строки команды оператора «установка SQL 08», выпуск B10, шаг 3.5.5)
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-15 21:40 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-15 22:44 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальные чаты f23e7e60 (v0.1), 3ff53398 (v0.2) и bad05778 (v0.3).
# v0.2 (аудит REL81): M-01 — psql с пустым окружением (env -i: переменные PG* не действуют) и явной целью
#   -h /var/run/postgresql -p 5432 -U postgres -d bem. L-01 — сбой psql: нет строки CHECKED → откат до COMMIT (rc=3);
#   есть CHECKED, нет COMMITTED → INSTALL_OUTCOME_UNKNOWN (rc=5); есть COMMITTED → COMMITTED_FINAL_CHECK_FAILED (rc=5).
#   rc=5 — дальше только отдельная проверка чтением. Успех (rc=0) — только со строкой COMMITTED и точной строкой OK.
# v0.3 (аудит REL82, L-355-REL82-01): отсутствие строки CHECKED больше не считается доказательством отката. rc=3
#   «REFUSED before COMMIT» — только когда сервер сам вернул отказ обёртки (ERROR: SQL08_REFUSED / SQL08_ALREADY_PRESENT …
#   nothing changed): такие отказы поднимаются только до COMMIT и обрывают транзакцию. Любой другой сбой psql без строк
#   CHECKED и COMMITTED (обрыв, потеря вывода, ожидание блокировки и т. п.) → INSTALL_OUTCOME_UNKNOWN, rc=5.
# НАЗНАЧЕНИЕ: строит одну строку для Termux. Начало (pkg_ok, сверка пакета cad786a71) — дословно из допущенной команды
#   CMD_B10_VERIFY_V01 (REL80). Дальше: байты файла 08 читаются из пакета один раз, сумма считается от тех же байтов;
#   обёртка sql08_wrap.sql подаётся сжатой (gzip, base64), её сумма сверяется после распаковки; файл 08 вставляется
#   на место строки-метки; psql от postgres; итог — последняя строка должна быть точной строкой OK.
# ЗАПУСК: python mk_sql08_cmd.py <sql08_wrap.sql> <08_zavod_ext_06.sql> <ожидаемая SHA-256 добавленного> <выход>
import base64, gzip, hashlib, sys

P = '/var/lib/zavod/probes-pkg-cad786a7158b'
MS = 'c4accd34db7ff6a69fef03c0b98bc7d009b88743ed2a4b63a099e601553cbe45'
NF = '36'
LS = 'ebad0641e5dd16e75475cfdfed6c1fa9d60792248832d76bf777c935cb61ee97'
REL = 'cad786a71'
SQL_REL = 'zavod/kernel/db/08_zavod_ext_06.sql'
MARK = '--@@SQL08@@'
OK_LINE = ('ZPROBE_B10_SQL08=OK table=bem_control.lease_seal '
           'function=bem_control.lease_seal_unstarted(text,uuid,text)')

PKG_OK = ('pkg_ok() { [ -d "$P" ] && [ ! -L "$P" ] && [ -f "$P/MANIFEST.sha256" ] && [ ! -L "$P/MANIFEST.sha256" ] '
          '|| return 1; [ "$(sha256sum < "$P/MANIFEST.sha256" | cut -d\' \' -f1)" = "$MS" ] || return 1; '
          '(cd "$P" && sha256sum -c --strict --quiet MANIFEST.sha256) || return 1; '
          '[ "$(find "$P" ! -type d | wc -l)" = "$NF" ] || return 1; '
          '[ "$(cd "$P" && find . -printf \'%y %m %p\\n\' | LC_ALL=C sort | sha256sum | cut -d\' \' -f1)" = "$LS" ] '
          '|| return 1; [ -z "$(find "$P" \\( -type l -o ! -user root -o ! -group root -o -perm /022 -o '
          '\\( -type f -links +1 \\) \\) -print)" ] || return 1; }; ')


def build(wrap: bytes, sql08: bytes, expect: str) -> str:
    assert wrap.count(MARK.encode()) == 1
    assert len(expect) == 64 and all(c in '0123456789abcdef' for c in expect)
    wsha = hashlib.sha256(wrap).hexdigest()
    ssha = hashlib.sha256(sql08).hexdigest()
    b64 = base64.b64encode(gzip.compress(wrap, mtime=0)).decode()
    return (
        'clear; (set -eu -o pipefail; umask 022; cd /root; '
        f'P={P}; MS={MS}; NF={NF}; LS={LS}; ' + PKG_OK +
        f'pkg_ok || {{ echo "REFUSED: $P is missing or differs from the inventory of release {REL}; nothing run"; exit 1; }}; '
        'echo "PACKAGE_DIR_VERIFIED=$P"; '
        f'S8=$(cat "$P/{SQL_REL}" && printf x) || {{ echo "REFUSED: cannot read 08_zavod_ext_06.sql; nothing run"; exit 1; }}; '
        'S8=${S8%x}; '
        f'[ "$(printf %s "$S8" | sha256sum | cut -c1-64)" = "{ssha}" ] '
        '|| { echo "REFUSED: 08_zavod_ext_06.sql differs; nothing run"; exit 1; }; '
        f"W=$(printf %s '{b64}' | base64 -d | gunzip -c && printf x) "
        '|| { echo "REFUSED: wrapper does not decode; nothing run"; exit 1; }; W=${W%x}; '
        f'[ "$(printf %s "$W" | sha256sum | cut -c1-64)" = "{wsha}" ] '
        '|| { echo "REFUSED: wrapper differs; nothing run"; exit 1; }; '
        f"M='{MARK}'; " + 'W1=${W%%"$M"*}; W2=${W#*"$M"}; '
        'O=$(printf %s%s%s "$W1" "$S8" "$W2" | runuser -u postgres -- env -i PATH=/usr/bin:/bin LC_ALL=C.UTF-8 '
        'psql -X -A -t -q -v ON_ERROR_STOP=1 -h /var/run/postgresql -p 5432 -U postgres -d bem '
        f'-v expect={expect} -f - 2>&1) '
        '|| { printf \'%s\\n\' "$O" | tail -8 | cut -c1-200; '
        'if printf \'%s\\n\' "$O" | grep -qx ZPROBE_B10_SQL08_COMMITTED; then '
        'echo "ZPROBE_B10_SQL08=COMMITTED_FINAL_CHECK_FAILED: changes are saved; run the read-only check"; exit 5; '
        'elif printf \'%s\\n\' "$O" | grep -q \'^ZPROBE_B10_SQL08_CHECKED \'; then '
        'echo "INSTALL_OUTCOME_UNKNOWN: COMMIT not confirmed; run the read-only check, do nothing else"; exit 5; '
        'elif printf \'%s\\n\' "$O" | grep -qE \'ERROR: +SQL08_(REFUSED|ALREADY_PRESENT): .*nothing changed\'; then '
        'echo "ZPROBE_B10_SQL08=REFUSED before COMMIT by the server check; nothing changed"; exit 3; '
        'else echo "INSTALL_OUTCOME_UNKNOWN: psql failed without a server refusal line; run the read-only check, do nothing else"; exit 5; fi; }; '
        'printf \'%s\\n\' "$O" | tail -8 | cut -c1-200; '
        'printf \'%s\\n\' "$O" | grep -qx ZPROBE_B10_SQL08_COMMITTED '
        '|| { echo "INSTALL_OUTCOME_UNKNOWN: no COMMITTED line; run the read-only check, do nothing else"; exit 5; }; '
        f'[ "$(printf \'%s\\n\' "$O" | tail -1)" = "{OK_LINE}" ] '
        '|| { echo "ZPROBE_B10_SQL08=COMMITTED_FINAL_CHECK_FAILED: last line differs; run the read-only check"; exit 5; }) '
        '2>&1 | tail -40; echo "rc=${PIPESTATUS[0]}"'
    )


if __name__ == '__main__':
    wrap = open(sys.argv[1], 'rb').read()
    sql08 = open(sys.argv[2], 'rb').read()
    line = build(wrap, sql08, sys.argv[3])
    with open(sys.argv[4], 'w', encoding='utf-8', newline='\n') as f:
        f.write(line + '\n')
    print(len(line), hashlib.sha256((line + '\n').encode()).hexdigest())
