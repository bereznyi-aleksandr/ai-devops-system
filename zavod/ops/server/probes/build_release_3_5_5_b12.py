#!/usr/bin/python3
# ДОКУМЕНТ: zavod/ops/server/probes/build_release_3_5_5_b12.py
# ВЕРСИЯ: v0.3 (выпуск B12)  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-17 23:50 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-18 01:12 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат zavod (ad796548; v0.2, v0.3 — чат-сменщик пускателя)
# v0.3 (REL113 REVISE 0/1/2): M-01 — папка Q и все предки до «/» проверяются в КАЖДОМ режиме до действий и ещё раз
#   перед запуском Python (root, не ссылка, без записи для группы и прочих); L-01 — точное число аргументов (режим — 1,
#   report — 2); L-02 — PATH закреплён, Python по полному пути, BASH_ENV/ENV или функции из окружения — отказ.
# v0.2 (REL112 REVISE 0/1/2): M-01 — свой шаблон .sh: распаковка пакета ТОЛЬКО режимом stage (новая папка, перечень
#   созданного; существующая папка: равна описи — ничего не делает, иначе отказ); preflight, verify-installed, report и
#   install требуют папки после stage, равной описи, и сами ничего не распаковывают. L-02 — zprobe_checks.py и
#   zprobe_r2.py обязаны иметь SHA-256, принятые REL111 (ACCEPTED), иначе выпуск не собирается.
# НАЗНАЧЕНИЕ: сборка выпуска B12 (REL111 AGREED: B12_RELEASE_BUILD_ALLOWED=YES) из коммита с программами — тем же
#   порядком, что build_release_3_5_5_b11.py (берёт его и через него сборщики B10, B9 и основной), меняет состав:
#   zavod/ops/zprobe_pins_b12.txt — отпечатки B12 (ключи — семь модулей папки probes-b12 и копия отпечатков B9);
#   zavod/ops/server/probes/zprobe-release-3.5.5-b12.sh — файл для сервера (режимы preflight, verify-installed, report,
#   install; пакет в новой папке /var/lib/zavod/probes-pkg-<12 знаков коммита B12>; установка — zprobe_release_b12.py).
#   В пакете — отпечатки B8, B9, B10 и B11: по ним B12 сверяет, что B8–B11 не тронуты. Новых служб нет, SQL нет.
# ОГРАНИЧЕНИЯ: ничего на сервере не делает. Выпуск не собирается, если: 1) любой из четырёх файлов отпечатков коммита
#   не равен известной сумме (PIN_FILES — файлы замороженного выпуска B11 abb1575f9);
#   2) отпечатки B11 коммита — не выпуск B11 76db3a69c…; 3) любой модуль B12, кроме zprobe_checks.py и zprobe_r2.py,
#   не равен (байт в байт) отпечатку B11.
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_release_3_5_5_b11 as B11B  # noqa: E402  — подключает сборщики B9, B10, B11; ниже состав заменяется на B12

B = B11B.B
B9B = B11B.B9B
P = B.PROBES
MODULES = B11B.MODULES
CHANGED = ('zprobe_checks.py', 'zprobe_r2.py')
INSTALLER_CHAIN = B11B.INSTALLER_CHAIN + ('zprobe_release_b12.py',)   # то, что импортирует zprobe_release_b12.py
B8_PINS, B9_PINS, B10_PINS = B11B.B8_PINS, B11B.B9_PINS, B11B.B10_PINS
B11_PINS = 'zavod/ops/zprobe_pins_b11.txt'
B.VERSION = '3.5.5-b12'
B.FILES = [P + n for n in MODULES + INSTALLER_CHAIN] + [B8_PINS, B9_PINS, B10_PINS, B11_PINS]
B.FILES = list(dict.fromkeys(B.FILES))
B.EXEC = {P + n for n in ('zprobe_release.py', 'zprobe_release_b9.py', 'zprobe_release_b10.py', 'zprobe_release_b11.py',
                          'zprobe_release_b12.py')}
B.PINS_PATH = 'zavod/ops/zprobe_pins_b12.txt'
B.SH_PATH = P + 'zprobe-release-3.5.5-b12.sh'
B.PIN_KEYS = [(n, P + n) for n in MODULES] + [('zprobe_pins_b9.txt', B9_PINS)]
# REL112 M-01: свой шаблон (не цепочка замен B9–B11). Единственное место записи оболочки — ветка stage.
# Строка «Q=/var/lib/zavod» — единственная строка с этим путём (испытание подменяет только её на свою папку).
B.SH_TEMPLATE = r'''#!/bin/bash
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe-release-3.5.5-b12.sh (собран build_release_3_5_5_b12.py v0.3, руками не править)
# ВЕРСИЯ: v0.3  СТАТУС: DRAFT  ВЫПУСК: 3.5.5 B12 (ПБ-1)  release_commit=@C@
# НАЗНАЧЕНИЕ: один файл выпуска B12 для сервера zavod-1. Внутри — tar пакета (base64), его SHA-256, сумма описи
#   MANIFEST.sha256, число файлов и сумма перечня папки. Пакет — новая папка probes-pkg-@C12@ в папке Q (ниже).
# ЗАПИСИ ПО РЕЖИМАМ (REL112 M-01):
#   stage — ЕДИНСТВЕННЫЙ режим этого файла, который пишет: проверяет сумму tar ДО записи и папку Q (root, без записи
#     для группы и прочих); создаёт НОВУЮ папку пакета (mkdir), распаковывает в неё tar, печатает перечень созданного
#     (строки CREATED) и сверяет с описью. Папка уже есть и равна описи — ничего не делает (STAGE=ALREADY). Есть и не
#     равна (чужое имя, ссылка, лишний или изменённый файл) — отказ, ничего не меняет. Больше ничего не пишет.
#   preflight | verify-installed | report preflight|verify-installed — НИЧЕГО не создают и не меняют: нужна папка
#     пакета после stage, равная описи (иначе отказ без записи); затем zprobe_release_b12.py только читает (python -B,
#     без байт-кода); report печатает отчёт и его SHA-256 только в stdout.
#   install — нужна папка после stage, равная описи; zprobe_release_b12.py ставит только новые цели B12 в
#     /usr/local/lib/zavod/probes-b12 (без служб) и пишет новый дневник /root/zprobe-install-3.5.5-b12-*.
#   Ничего не удаляет, не переименовывает и не перезаписывает.
# ВЫЗОВ (root, сеанс SSH на zavod-1): bash <этот файл> stage | preflight | verify-installed | install |
#   report preflight | report verify-installed
#   Запуск — только с пустым окружением (REL113 L-02): env -i /bin/bash --norc --noprofile <этот файл> <режим>.
#   Окружение (REL113 L-02): PATH закреплён ниже (/usr/sbin:/usr/bin:/sbin:/bin), Python — /usr/bin/python3; заданы
#   BASH_ENV или ENV, или из окружения пришли функции оболочки — отказ (код 2) до любых действий.
#   Папка Q и все её предки до «/» (REL113 M-01) — в КАЖДОМ режиме до любых действий и перед запуском Python: обычная
#   папка (не ссылка), владелец root, без записи для группы и прочих; иначе отказ, ничего не пишется, Python не запускается.
set -eu -o pipefail
umask 022
IFS=$' \t\n'
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
[ -z "${BASH_ENV:-}${ENV:-}" ] || { echo "REFUSED: BASH_ENV or ENV is set; run with env -i; nothing done"; exit 2; }
[ -z "$(declare -F)" ] || { echo "REFUSED: shell functions came from the environment; run with env -i; nothing done"; exit 2; }
M=bad
R=
case "$#:${1:-}" in 1:stage|1:preflight|1:verify-installed|1:install) M=$1;; 2:report) case "$2" in preflight|verify-installed) M=report; R=$2;; esac;; esac
[ "$M" != bad ] || { echo "usage: bash $0 stage|preflight|verify-installed|install|report preflight|report verify-installed"; exit 2; }
[ "$(id -u)" = 0 ] || { echo "REFUSED: run as root"; exit 2; }
C=@C@
Q=/var/lib/zavod
P=$Q/probes-pkg-@C12@
TS=@TS@
MS=@MS@
NF=@NF@
LS=@LS@
payload() { sed -n '/^__ZPROBE_PKG_BASE64__$/,$p' "$0" | tail -n +2 | base64 -d; }
pkg_ok() {
  [ -d "$P" ] && [ ! -L "$P" ] && [ -f "$P/MANIFEST.sha256" ] && [ ! -L "$P/MANIFEST.sha256" ] || return 1
  [ "$(sha256sum < "$P/MANIFEST.sha256" | cut -d' ' -f1)" = "$MS" ] || return 1
  (cd "$P" && sha256sum -c --strict --quiet MANIFEST.sha256) || return 1
  [ "$(find "$P" ! -type d | wc -l)" = "$NF" ] || return 1
  [ "$(cd "$P" && find . -printf '%y %m %p\n' | LC_ALL=C sort | sha256sum | cut -d' ' -f1)" = "$LS" ] || return 1
  [ -z "$(find "$P" \( -type l -o ! -user root -o ! -group root -o -perm /022 -o \( -type f -links +1 \) \) -print)" ] || return 1
}
q_ok() {
  case "$Q" in /*) ;; *) return 1;; esac
  d=$Q
  while :; do
    [ -d "$d" ] && [ ! -L "$d" ] && [ "$(stat -c %u "$d")" = 0 ] && [ -z "$(find "$d" -maxdepth 0 -perm /022)" ] || return 1
    [ "$d" = / ] && return 0
    d=$(dirname "$d")
  done
}
q_ok || { echo "REFUSED: $Q or one of its parent folders is not a root-only plain folder; nothing done"; exit 1; }
if [ "$M" = stage ]; then
  if [ -e "$P" ] || [ -L "$P" ]; then
    pkg_ok || { echo "ZPROBE_B12_STAGE=REFUSED $P exists and differs from the embedded inventory of release $C; nothing changed"; exit 1; }
    echo "ZPROBE_B12_STAGE=ALREADY $P equals the embedded inventory of release $C; nothing changed"
    exit 0
  fi
  [ "$(payload | sha256sum | cut -d' ' -f1)" = "$TS" ] || { echo "ZPROBE_B12_STAGE=REFUSED embedded package sum differs; nothing changed"; exit 1; }
  mkdir -m 0755 "$P" || { echo "ZPROBE_B12_STAGE=REFUSED cannot create new folder $P; nothing changed"; exit 1; }
  echo "CREATED d 755 $P"
  payload | tar -C "$P" --no-same-owner -xf - \
    || { echo "ZPROBE_B12_STAGE=PARTIAL unpacking into new $P failed; $P kept as evidence, nothing installed"; exit 1; }
  (cd "$P" && find . -mindepth 1 -printf "CREATED %y %m $P/%P\n" | LC_ALL=C sort)
  pkg_ok || { echo "ZPROBE_B12_STAGE=PARTIAL new $P differs from the embedded inventory; kept as evidence, nothing installed"; exit 1; }
  echo "ZPROBE_B12_STAGE=OK $P files=$NF (only this new folder was written)"
  exit 0
fi
{ { [ -e "$P" ] || [ -L "$P" ]; } && pkg_ok; } \
  || { echo "REFUSED: package folder $P is missing or differs from the embedded inventory of release $C; run stage first; nothing written"; exit 1; }
q_ok || { echo "REFUSED: $Q or one of its parent folders is not a root-only plain folder (checked again before Python start); nothing done"; exit 1; }
echo "PACKAGE_DIR=$P (equal to the embedded inventory; not unpacked by this mode)"
exec /usr/bin/python3 -I -B "$P/zavod/ops/server/probes/zprobe_release_b12.py" "$M" "$P" ${R:+"$R"}
__ZPROBE_PKG_BASE64__
'''
assert B.SH_TEMPLATE.count('\nQ=/var/lib/zavod\n') == 1 and B.SH_TEMPLATE.count('/var/lib/zavod') == 1, 'template Q'
# Известные суммы файлов отпечатков и коммит B11 — те же, что zprobe_release_b12.PINS_FILE_SHA и B11_RELEASE_COMMIT
# (установщик здесь не импортируется: ему нужны модули Linux; равенство проверяет тест test_zprobe_release_b12 W16).
B11_RELEASE_COMMIT = '76db3a69c7819c370000b58524cf672a10d48057'
PIN_FILES = {B8_PINS: 'ef5c9962fd5aa15ce11a1832529693bbcbecc85353ed2687b426e5088bc61fe1',
             B9_PINS: '91ed266ae21a3719463a4b49d20c5d9f5ed797cd6dbbdaf9dbbaa60d4fbaa712',
             B10_PINS: 'a86ea709d6de2c789a39efeb047a6fc5f25365a200dc3df39e0d3924aed883db',
             B11_PINS: 'f0a989d642ce1f459ad64b205743b82a8012ace6eac905082ef75b9d759c1089'}
# REL112 L-02: принятые REL111 суммы двух изменённых модулей (те же, что zprobe_release_b12.ACCEPTED_SHA; равенство — W16).
ACCEPTED = {'zprobe_checks.py': '8604b73e0877c3e4353d0c218a0d7920c3c6e622dcc1e8e4f1cc4bfcdaa7ff5c',
            'zprobe_r2.py': 'bb7ce5f49fdb32de995cad3c475556e0aad80511fc2ebf46bfa2aeca774e8ee9'}


def pins_problem(get):
    """Четыре файла отпечатков — известные суммы; отпечатки B11 — коммит выпуска B11 (иначе строка отказа, иначе None)."""
    bad = [p for p, h in sorted(PIN_FILES.items()) if B.sha(get(p)) != h]
    if bad:
        return f'pins files differ from the known B11-release sums: {bad}'
    rc = B9B.parse(get(B11_PINS)).get('release_commit')
    return None if rc == B11_RELEASE_COMMIT else f'B11 pins release_commit {rc} is not {B11_RELEASE_COMMIT}'


def unchanged_problem(pins11, get):
    """Модули B12, кроме CHANGED, равны отпечаткам B11 (иначе строка отказа, иначе None)."""
    bad = [n for n in MODULES if n not in CHANGED and (n not in pins11 or B.sha(get(P + n)) != pins11[n])]
    return f'modules differ from B11 pins: {bad}' if bad else None


def accepted_problem(get):
    """REL112 L-02: CHANGED — ровно суммы, принятые REL111 (иначе строка отказа, иначе None)."""
    bad = [n for n in CHANGED if B.sha(get(P + n)) != ACCEPTED[n]]
    return f'changed modules differ from the REL111-accepted sums: {bad}' if bad else None


def build(root, commit):
    """Сборка B12: сверка файлов отпечатков с известными суммами и CHANGED с принятыми суммами, оригинальная сборка,
    затем сверка остальных модулей с отпечатками B11."""
    get = lambda p: B.blob(root, commit, p)  # noqa: E731
    bad = pins_problem(get) or accepted_problem(get)
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    pins, tar, sh_b = B9B._build(root, commit)
    bad = unchanged_problem(B9B.parse(get(B11_PINS)), get)
    if bad:
        raise SystemExit('RELEASE_REFUSED ' + bad)
    return pins, tar, sh_b


B.build = build
if __name__ == '__main__':
    sys.exit(B.main())
