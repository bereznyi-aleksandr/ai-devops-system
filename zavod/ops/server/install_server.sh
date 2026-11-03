#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_server.sh
# ВЕРСИЯ: v0.5  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-02 11:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-03 03:33 +02:00 (v0.5: аудит M3311-R1-03 — после проверки копии выпуска установщик перезапускает себя из неё (exec), службы и настройки ставятся из "$HERE/…" (сканер И.7а); M3311-R1-04 — в отчёте ОС, ядро, версии пакетов APT и сумма списка всех пакетов; M3311-R1-02 — до сверки сумм в пакете только обычные файлы и папки, без жёстких ссылок, путь пакета без ссылок (pwd -P); права файлов сверяются с описью в пакете и в выпуске; Claude, сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d; v0.4 от 03:02: учётную запись zflowable создаёт install_cell.sh (фильтр nft ссылается на её имя); Claude, сессия 2bf4a72a-0dfd-45e6-8828-338d117e688d; v0.3 от 12:19: служба движка zavod-engine — учётная запись zflowable, база bem_engine, вход peer через сокет, учётная запись администратора движка создаётся на сервере (решение оператора 2026-11-02); v0.2 от 11:44: CI — вход цепочки базы под её ролями через временную карту peer, без trust; v0.1 от 11:33: карта 3.3.11.1–3.3.11.4)
# ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
# НАЗНАЧЕНИЕ: установка сервера Завода из пакета build_server_package.py на чистую Ubuntu 24.04 (протокол v3.1 И.7,
#   Р.59; карта 3.3.11). Порядок (3.3.11.2):
#   1) сверка всех файлов пакета с MANIFEST.sha256 — без совпадения ничего не ставится;
#   2) пакеты системы из закрытого списка (PostgreSQL 16, nftables, python3, unzip, zip, Java 21);
#   3) Node.js 22 из пакета в /opt/zavod/node-<версия>, ссылка /usr/bin/node (служба ядра запускает её);
#   4) файлы пакета в /opt/zavod/releases/<коммит>, ссылка /opt/zavod/current;
#   5) PostgreSQL 16 только на сокете; цепочка базы (H1.31, Z-EXT-01..05) ставится один раз, затем — итоговая
#      проверка состояния базы при каждом запуске;
#   6) ячейка install_cell.sh (учётные записи И.7, клетка, привратник, посредник, фильтр, приём архивов);
#   7) служба ядра zavod-kernel (zkernel) и файл настроек (из примера, если файла ещё нет);
#   7б) служба движка zavod-engine (zflowable, база bem_engine, только 127.0.0.1:8091), ENGINE=OK;
#   8) отчёт: ZAVOD_SERVER_INSTALL=OK и сумма описи установленных файлов (3.3.11.4).
#   Повторный запуск даёт тот же результат.
# ВЫЗОВ: sudo bash install_server.sh <папка распакованного пакета> [параметры install_cell.sh …]
# ОГРАНИЧЕНИЯ: ничего не удаляет; прежние выпуски остаются в /opt/zavod/releases. Ключей не создаёт и не читает.
#   Единственный пароль — администратора движка: создаётся один раз в файл root:root 0600 и не выводится.
set -euo pipefail
export LC_ALL=C
PKG=${1:?usage: install_server.sh PACKAGE_DIR [install_cell.sh options]}
shift
PKG=$(cd "$PKG" && pwd -P)
# Папка самого сценария: первый проход — пакет, второй (после exec ниже) — закрытая копия выпуска.
HERE=$(cd "$(dirname "$0")" && pwd)
die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || die "Ubuntu 24.04 only (found ${ID:-?} ${VERSION_ID:-?})"

echo "=== 1. сверка пакета с MANIFEST.sha256"
M="$PKG/MANIFEST.sha256"
[ -f "$M" ] || die "no MANIFEST.sha256"
# Аудит M3311-R1-02: до любой сверки сумм — в пакете только обычные файлы и папки (sha256sum идёт по ссылке,
# find -type f её не видит), без жёстких ссылок; путь пакета — настоящий (pwd -P), без ссылок в предках.
odd=$(cd "$PKG" && find . -mindepth 1 ! -type f ! -type d -printf '%P\n' -quit)
[ -z "$odd" ] || die "not a regular file or directory: $odd"
hard=$(cd "$PKG" && find . -type f -links +1 -printf '%P\n' -quit)
[ -z "$hard" ] || die "hard link in the package: $hard"
# Права каждого файла — как в описи (строки «#mode ППП путь»); опись перечисляет права всех файлов.
# (цикл читает из подстановки процесса, не из конвейера: ранний выход не роняет sed по pipefail)
modes_differ() { local m p; while read -r m p; do [ "$(stat -c %a -- "$1/$p")" = "$m" ] || { echo "$p"; return 0; }; done \
  < <(sed -n 's/^#mode \([0-7][0-7][0-7]\) \(.*\)$/\1 \2/p' "$M"); }
COMMIT=$(sed -n '1s/^# zavod server package; source commit \([0-9a-f]\{40\}\)$/\1/p' "$M")
[ -n "$COMMIT" ] || die "manifest has no source commit"
(cd "$PKG" && grep -v '^#' "$M" | sha256sum --check --strict --quiet) || die "package files differ from the manifest"
# Лишний файл в пакете — тоже отказ: ставится только то, что перечислено.
extra=$(cd "$PKG" && find . -type f ! -name MANIFEST.sha256 -printf '%P\n' | sort | comm -23 - <(grep -v '^#' "$M" | cut -c67- | sort))
[ -z "$extra" ] || die "files not in the manifest: $(echo "$extra" | head -3 | tr '\n' ' ')"
[ "$(grep -c '^#mode ' "$M")" = "$(grep -vc '^#' "$M")" ] || die "manifest modes do not cover every file"
bad=$(modes_differ "$PKG")
[ -z "$bad" ] || die "file mode differs from the manifest: $bad"
echo "PACKAGE_MATCH commit=$COMMIT files=$(grep -vc '^#' "$M")"

echo "=== 2. пакеты системы"
APT=(postgresql-16 postgresql-client-16 nftables python3 unzip zip openjdk-21-jre-headless)
missing=()
for p in "${APT[@]}"; do dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed' || missing+=("$p"); done
if [ ${#missing[@]} -gt 0 ]; then
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${missing[@]}" > /dev/null
fi
for p in "${APT[@]}"; do dpkg-query -W -f='${Status}' "$p" | grep -q 'install ok installed' || die "package $p not installed"; done

echo "=== 3. Node.js 22"
NODE_TAR=$(cd "$PKG/runtime" && ls node-v22.*-linux-x64.tar.xz)
NODE_DIR=/opt/zavod/${NODE_TAR%.tar.xz}
install -d -o root -g root -m 0755 /opt/zavod
if [ ! -x "$NODE_DIR/bin/node" ]; then
  tar -C /opt/zavod -xJf "$PKG/runtime/$NODE_TAR" --no-same-owner
  chown -R root:root "$NODE_DIR"
  chmod -R go-w "$NODE_DIR"
fi
if [ -e /usr/bin/node ] && [ "$(readlink -f /usr/bin/node)" != "$NODE_DIR/bin/node" ]; then
  die "/usr/bin/node is another Node.js ($(readlink -f /usr/bin/node)); remove it by hand"
fi
ln -sfn "$NODE_DIR/bin/node" /usr/bin/node
/usr/bin/node --version | grep -q '^v22\.' || die "node is not v22"

echo "=== 4. файлы выпуска"
REL=/opt/zavod/releases/$COMMIT
install -d -o root -g root -m 0755 /opt/zavod/releases
if [ ! -d "$REL" ]; then
  tmp=$(mktemp -d /opt/zavod/releases/.new-XXXXXX)
  cp -a "$PKG/." "$tmp/"
  chown -R root:root "$tmp"
  chmod -R go-w "$tmp"
  chmod 0755 "$tmp"
  mv "$tmp" "$REL"
fi
odd=$(cd "$REL" && find . -mindepth 1 ! -type f ! -type d -printf '%P\n' -quit)
[ -z "$odd" ] || die "$REL: not a regular file or directory: $odd"
cmp -s "$M" "$REL/MANIFEST.sha256" || die "$REL has another manifest"
(cd "$REL" && grep -v '^#' MANIFEST.sha256 | sha256sum --check --strict --quiet) || die "$REL differs from the manifest"
bad=$(modes_differ "$REL")
[ -z "$bad" ] || die "$REL: file mode differs from the manifest: $bad"
ln -sfn "$REL" /opt/zavod/current.new
mv -T /opt/zavod/current.new /opt/zavod/current
# Аудит M3311-R1-03: дальше всё ставится только из проверенной копии выпуска (root, без записи для других) —
# установщик перезапускает себя оттуда; второй проход повторяет шаги 1–4 над копией (они повторяемы) и идёт дальше.
# Так службы и настройки ставятся из "$HERE/…" — папки самого сценария, которую проверяет сканер И.7а.
if ! [ "$HERE" -ef "$REL/zavod/ops/server" ]; then
  exec bash "$REL/zavod/ops/server/install_server.sh" "$REL" "$@"
fi

echo "=== 5. PostgreSQL 16 и цепочка базы"
PG_CONF=/etc/postgresql/16/main
[ -f "$PG_CONF/postgresql.conf" ] || die "no PostgreSQL 16 cluster main"
# Только сокет: сетевой вход закрыт (И.7, проба CI cell).
install -d -o postgres -g postgres -m 0755 "$PG_CONF/conf.d"
printf "listen_addresses = ''\n" > "$PG_CONF/conf.d/50-zavod-socket-only.conf"
chown postgres:postgres "$PG_CONF/conf.d/50-zavod-socket-only.conf"
systemctl enable --now postgresql.service > /dev/null
systemctl restart postgresql.service
as_pg() { runuser -u postgres -- env -i PATH=/usr/bin:/bin PGHOST=/var/run/postgresql PGUSER=postgres "$@"; }
psqlq() { as_pg psql -X -v ON_ERROR_STOP=1 -q "$@"; }
K="$REL/zavod/kernel"
W=$(mktemp -d)
chown postgres:postgres "$W"
cp -R "$REL/bem954/H1_31_PACKAGE_R51/." "$W/"
chown -R postgres:postgres "$W"
if ! psqlq -d postgres -Atc "select 1 from pg_database where datname = 'bem'" | grep -qx 1; then
  echo "цепочка базы: первая установка"
  # Цепочка входит в базу под своими ролями (владелец схемы и др.) через сокет. На время цепочки системная запись
  # postgres (владелец кластера, у неё и так все права) получает вход под любой ролью: строка peer с картой
  # zavod_install. После цепочки — и при любом выходе — строки убираются. Пароля и trust нет.
  HBA=$PG_CONF/pg_hba.conf IDENT=$PG_CONF/pg_ident.conf
  chain_access_off() { sed -i '/# zavod-install-chain$/d' "$HBA" "$IDENT"; systemctl reload postgresql.service; }
  trap chain_access_off EXIT
  sed -i '1i local all all peer map=zavod_install # zavod-install-chain' "$HBA"
  printf 'zavod_install postgres all # zavod-install-chain\n' >> "$IDENT"
  systemctl reload postgresql.service
  sleep 1
  (cd "$W" && psqlq -d postgres -f 00_cluster_bootstrap.sql > "$W/chain_00.out")
  (cd "$W" && as_pg /usr/bin/node run_migration.mjs --files 01_database_migration.sql > "$W/chain_wrapper.out")
  (cd "$W" && as_pg /usr/bin/node "$K/db/build_ext.mjs" 01_database_migration.sql --check)
  psqlq -d bem -f "$K/db/02_zavod_ext_01.sql" > "$W/chain_ext.out"
  for f in 03_zavod_ext_02 04_zavod_ext_03 06_zavod_ext_04 07_zavod_ext_05; do
    psqlq --single-transaction -d bem -f "$K/db/$f.sql" > "$W/chain_$f.out"
  done
  chain_access_off
  trap - EXIT
  grep -q 'zavod-install-chain' "$HBA" "$IDENT" && die "temporary chain access is still in pg_hba/pg_ident"
else
  echo "цепочка базы: база bem уже есть, ставится только проверка"
fi
(cd "$W" && as_pg /usr/bin/node "$K/db/build_final_ext.mjs" 05_final_state_check.sql --check)
psqlq --single-transaction -d bem -f "$K/db/05_final_state_check_ext01.sql" > "$W/chain_final.out" || {
  grep -m3 -E 'ERROR|ОШИБКА' "$W/chain_final.out" >&2; die "final state check of the database"; }
echo "DB_CHAIN=OK"

echo "=== 6. ячейка"
bash "$REL/zavod/ops/server/cell/install_cell.sh" --pg-conf-dir "$PG_CONF" "$@" | tee "$W/cell.out"
grep -qx ZAVOD_CELL_INSTALL=OK "$W/cell.out" || die "cell installer"

echo "=== 7. служба ядра"
SETTINGS=/etc/zavod/zavod.env
if [ ! -e "$SETTINGS" ]; then
  install -o root -g zkernel -m 0640 "$HERE/zavod.env.example" "$SETTINGS"
fi
[ "$(stat -c '%U:%G %a' "$SETTINGS")" = "root:zkernel 640" ] || die "$SETTINGS must be root:zkernel 640"
install -o root -g root -m 0644 "$HERE/zavod-kernel.service" /etc/systemd/system/zavod-kernel.service
systemctl daemon-reload
systemctl enable zavod-kernel.service > /dev/null

echo "=== 7б. служба движка процессов"
# учётную запись zflowable создаёт install_cell.sh (шаг 6): правило фильтра nft ссылается на её имя
id zflowable > /dev/null 2>&1 || die "zflowable must be created by install_cell.sh"
install -d -o zflowable -g zflowable -m 0750 /var/lib/zavod-engine
psqlq -d postgres -Atc "select 1 from pg_roles where rolname = 'zflowable'" | grep -qx 1 ||
  psqlq -d postgres -c "CREATE ROLE zflowable LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
if ! psqlq -d postgres -Atc "select 1 from pg_database where datname = 'bem_engine'" | grep -qx 1; then
  psqlq -d postgres -c "CREATE DATABASE bem_engine OWNER zflowable"
  psqlq -d bem_engine -c "REVOKE ALL ON SCHEMA public FROM PUBLIC" -c "CREATE SCHEMA bem_engine AUTHORIZATION zflowable"
fi
psqlq -d postgres -c "REVOKE CONNECT, TEMPORARY ON DATABASE bem_engine FROM PUBLIC"
# Учётная запись администратора движка (решение оператора 2026-11-02): создаётся здесь один раз, из случайных
# байтов, сразу в файл root:root 0600. Значение не выводится и не пишется в журнал; systemd передаёт его службе.
ADMIN=/etc/zavod/engine_admin.conf
if [ ! -e "$ADMIN" ]; then
  (umask 077
   t=$(mktemp /etc/zavod/.engine_admin.XXXXXX)
   { echo FLOWABLE_REST_APP_ADMIN_USERID=zavod-engine-admin
     printf 'FLOWABLE_REST_APP_ADMIN_PASSWORD=%s\n' "$(head -c 32 /dev/urandom | base64 -w0 | tr -d '/+=')"; } > "$t"
   mv "$t" "$ADMIN")
fi
[ "$(stat -c '%U:%G %a' "$ADMIN")" = "root:root 600" ] || die "$ADMIN must be root:root 600"
install -o root -g root -m 0644 "$HERE/zavod-engine.service" /etc/systemd/system/zavod-engine.service
systemctl daemon-reload
systemctl enable zavod-engine.service > /dev/null
systemctl restart zavod-engine.service
# Готовность: движок отвечает на 127.0.0.1:8091 и без учётной записи отказывает (401) — демо-входа нет.
code=
for _ in $(seq 1 120); do
  code=$(/usr/bin/node -e "fetch('http://127.0.0.1:8091/flowable-rest/service/management/engine')
    .then(r => console.log(r.status), () => console.log(0))")
  [ "$code" = 401 ] && break
  systemctl is-active --quiet zavod-engine.service || break
  sleep 2
done
[ "$code" = 401 ] || { journalctl -u zavod-engine.service -n 40 --no-pager >&2; die "engine is not up (http $code)"; }
echo "ENGINE=OK"

echo "=== 8. отчёт"
# Аудит M3311-R1-04: версии программ ОС пакет не закрепляет — отчёт называет фактические: ОС, ядро, версии пакетов
# APT и сумму полного списка установленных пакетов (сверяется с отдельно учтённым образом сервера).
for p in "${APT[@]}"; do echo "ZAVOD_SERVER_OS_PACKAGE=$(dpkg-query -W -f='${Package}=${Version}' "$p")"; done
BOM=$(dpkg-query -W -f='${Package}=${Version}\n' | sort | sha256sum | cut -c1-64)
echo "ZAVOD_SERVER_OS=$ID-$VERSION_ID kernel=$(uname -r) packages=$(dpkg-query -W -f='.\n' | wc -l) bom_sha256=$BOM"
INV=$(cd "$REL" && grep -v '^#' MANIFEST.sha256 | sha256sum | cut -c1-64)
echo "ZAVOD_SERVER_RELEASE=$COMMIT inventory_sha256=$INV node=$(/usr/bin/node --version)"
echo ZAVOD_SERVER_INSTALL=OK
