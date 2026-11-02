#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/install_server.sh
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-02 11:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-02 11:33 +02:00 (v0.1: карта 3.3.11.1–3.3.11.4)
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
#   8) отчёт: ZAVOD_SERVER_INSTALL=OK и сумма описи установленных файлов (3.3.11.4).
#   Повторный запуск даёт тот же результат.
# ВЫЗОВ: sudo bash install_server.sh <папка распакованного пакета> [параметры install_cell.sh …]
# ОГРАНИЧЕНИЯ: ничего не удаляет; прежние выпуски остаются в /opt/zavod/releases. Ключей и паролей не создаёт,
#   не читает и не пишет. Движок процессов Flowable (war и драйвер в пакете) — следующая версия установщика.
set -euo pipefail
export LC_ALL=C
PKG=${1:?usage: install_server.sh PACKAGE_DIR [install_cell.sh options]}
shift
PKG=$(cd "$PKG" && pwd)
die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || die "Ubuntu 24.04 only (found ${ID:-?} ${VERSION_ID:-?})"

echo "=== 1. сверка пакета с MANIFEST.sha256"
M="$PKG/MANIFEST.sha256"
[ -f "$M" ] || die "no MANIFEST.sha256"
COMMIT=$(sed -n '1s/^# zavod server package; source commit \([0-9a-f]\{40\}\)$/\1/p' "$M")
[ -n "$COMMIT" ] || die "manifest has no source commit"
(cd "$PKG" && grep -v '^#' "$M" | sha256sum --check --strict --quiet) || die "package files differ from the manifest"
# Лишний файл в пакете — тоже отказ: ставится только то, что перечислено.
extra=$(cd "$PKG" && find . -type f ! -name MANIFEST.sha256 -printf '%P\n' | sort | comm -23 - <(grep -v '^#' "$M" | cut -c67- | sort))
[ -z "$extra" ] || die "files not in the manifest: $(echo "$extra" | head -3 | tr '\n' ' ')"
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
(cd "$REL" && grep -v '^#' MANIFEST.sha256 | sha256sum --check --strict --quiet) || die "$REL differs from the manifest"
ln -sfn "$REL" /opt/zavod/current.new
mv -T /opt/zavod/current.new /opt/zavod/current

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
  (cd "$W" && psqlq -d postgres -f 00_cluster_bootstrap.sql > "$W/chain_00.out")
  (cd "$W" && as_pg /usr/bin/node run_migration.mjs --files 01_database_migration.sql > "$W/chain_wrapper.out")
  (cd "$W" && as_pg /usr/bin/node "$K/db/build_ext.mjs" 01_database_migration.sql --check)
  psqlq -d bem -f "$K/db/02_zavod_ext_01.sql" > "$W/chain_ext.out"
  for f in 03_zavod_ext_02 04_zavod_ext_03 06_zavod_ext_04 07_zavod_ext_05; do
    psqlq --single-transaction -d bem -f "$K/db/$f.sql" > "$W/chain_$f.out"
  done
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
  install -o root -g zkernel -m 0640 "$REL/zavod/ops/server/zavod.env.example" "$SETTINGS"
fi
[ "$(stat -c '%U:%G %a' "$SETTINGS")" = "root:zkernel 640" ] || die "$SETTINGS must be root:zkernel 640"
install -o root -g root -m 0644 "$REL/zavod/ops/server/zavod-kernel.service" /etc/systemd/system/zavod-kernel.service
systemctl daemon-reload
systemctl enable zavod-kernel.service > /dev/null

echo "=== 8. отчёт"
INV=$(cd "$REL" && grep -v '^#' MANIFEST.sha256 | sha256sum | cut -c1-64)
echo "ZAVOD_SERVER_RELEASE=$COMMIT inventory_sha256=$INV node=$(/usr/bin/node --version)"
echo ZAVOD_SERVER_INSTALL=OK
