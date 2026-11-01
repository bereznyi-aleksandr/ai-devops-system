#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/cell/intake_ci.sh
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-11-01 15:33 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-01 21:12 +02:00 (v0.2: пробы M33-R2-03 — карантин после проверки приёма
#   ждёт; M33-R2-04 — раздел приёма: предел inode и места, диск сервера не тратится)
# ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
# НАЗНАЧЕНИЕ: проба ПБ-4 (протокол v3.1 И.13; карта 3.3.9.4) на машине GitHub ubuntu-24.04 после install_cell.sh:
#   строгая опись (лишнее поле — отказ), правильный архив принят, испорченные архивы отклонены карантином,
#   подмены между карантином и приёмом отклонены приёмом, openat2 и запасной пошаговый путь не проходят по ссылке.
#   Каждая проверка печатает строку INTAKE_OK или INTAKE_FAIL; итог — INTAKE_CI=PASS.
# ВЫЗОВ: bash intake_ci.sh   (от пользователя CI с sudo)
# ОГРАНИЧЕНИЯ: только для одноразовой машины CI: пишет опись и архивы напрямую, временно скрывает службу приёма.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
I=/var/lib/zavod/intake
PROG=/usr/local/lib/zavod/zavod_intake.py
FAILS=0
TMP=$(mktemp -d)
ok() { echo "INTAKE_OK $*"; }
bad() { echo "INTAKE_FAIL $*"; FAILS=$((FAILS + 1)); }
newlease() { od -An -tx1 -N16 /dev/urandom | tr -d ' \n'; }
manifest() { # аренда [json вместо стандартной описи]
  local m=${2:-"{\"v\":1,\"lease\":\"$1\",\"dirs\":[\"src/\",\"tests/\"],\"max_files\":10,\"max_bytes\":65536,\"max_file_bytes\":32768,\"max_depth\":4,\"exec\":[\"tests/run.sh\"]}"}
  printf '%s' "$m" | sudo -u zkernel tee "$I/manifest/$1.json" >/dev/null
  sudo -u zkernel chmod 0644 "$I/manifest/$1.json"
}
put_tar() { # аренда случай — архив кладёт «привратник» zgate
  python3 -I "$HERE/intake_gen.py" "$2" "$TMP/$1.tar"
  sudo install -o zgate -g zquarantine -m 0640 "$TMP/$1.tar" "$I/in/$1.tar"
}
jline() { sudo grep -h "\"lease\":\"$2\"" "/var/lib/zavod/intake-journal/$1/$1.jsonl" 2>/dev/null | tail -1 || true; }
jreason() { jline "$1" "$2" | sed -n 's/.*"reason":"\([^"]*\)".*/\1/p'; }
jresult() { jline "$1" "$2" | sed -n 's/.*"result":"\([^"]*\)".*/\1/p'; }
archived() { sudo find "$I/archive" -maxdepth 1 -name "$1-*-$2" | wc -l; }
wait_for() { local n=$1; shift; for _ in $(seq 1 "$n"); do if "$@"; then return 0; fi; sleep 1; done; return 1; }
import_done() { [ -n "$(jresult import "$1")" ]; }
inactive() { case "$(systemctl is-active "$1" 2>/dev/null || true)" in active|activating|deactivating) return 1;; esac; }

echo "=== права папок"
[ "$(stat -c '%U:%G %a' $I/in)" = 'zgate:zquarantine 2750' ] && ok "in 2750 zgate:zquarantine" || bad "in rights"
[ "$(stat -c '%U:%G %a' $I/out)" = 'zquarantine:zimport 2750' ] && ok "out 2750 zquarantine:zimport" || bad "out rights"
[ "$(stat -c '%U:%G %a' $I/accepted)" = 'zimport:zgithub 2750' ] && ok "accepted 2750 zimport:zgithub" || bad "accepted rights"
if sudo -u zquarantine touch $I/in/x 2>/dev/null; then bad "zquarantine wrote into in"; else ok "zquarantine cannot write in"; fi
if sudo -u zimport ls $I/in >/dev/null 2>&1; then bad "zimport lists in"; else ok "zimport cannot read in"; fi
if sudo -u zimport touch $I/out/x 2>/dev/null; then bad "zimport wrote into out"; else ok "zimport cannot write out"; fi
if sudo -u zquarantine touch $I/accepted/x 2>/dev/null; then bad "zquarantine wrote into accepted"; else ok "zquarantine cannot write accepted"; fi
if sudo -u zgate touch $I/manifest/x 2>/dev/null; then bad "zgate wrote a manifest"; else ok "only zkernel writes manifest"; fi

echo "=== клетка карантина и приёма"
Z=00000000000000000000000000000000
for u in zquarantine zimport; do
  [ "$(systemctl show -p PrivateNetwork --value "$u@$Z.service")" = yes ] && ok "$u no network" || bad "$u network"
  [ "$(systemctl show -p User --value "$u@$Z.service")" = "$u" ] && ok "$u runs as $u" || bad "$u user"
  [ "$(systemctl show -p RuntimeMaxUSec --value "$u@$Z.service")" = 5min ] && ok "$u RuntimeMaxSec 300" || bad "$u runtime"
  systemd-analyze security --no-pager "$u@$Z.service" | tail -1 || true
done

echo "=== 3.3.9.1 строгая опись ядра"
L=$(newlease)
mcheck() { sudo -u zimport python3 -I "$PROG" manifest-check "$L" | awk '{print $4 ($5 == "-" ? "" : " " $5)}'; }
manifest "$L"; [ "$(mcheck)" = OK ] && ok "manifest ok" || bad "manifest ok: $(mcheck)"
std="\"lease\":\"$L\",\"dirs\":[\"src/\"],\"max_files\":10,\"max_bytes\":65536,\"max_file_bytes\":32768,\"max_depth\":4"
for c in "extra|{\"v\":1,$std,\"exec\":[],\"note\":\"x\"}|MANIFEST_FIELDS" \
         "duplicate|{\"v\":1,\"v\":1,$std,\"exec\":[]}|MANIFEST_DUPLICATE_KEY" \
         "float|{\"v\":1,\"lease\":\"$L\",\"dirs\":[\"src/\"],\"max_files\":1.5,\"max_bytes\":65536,\"max_file_bytes\":32768,\"max_depth\":4,\"exec\":[]}|MANIFEST_BAD_NUMBER" \
         "bool|{\"v\":true,$std,\"exec\":[]}|MANIFEST_VERSION" \
         "lease|{\"v\":1,\"lease\":\"$(newlease)\",\"dirs\":[\"src/\"],\"max_files\":10,\"max_bytes\":65536,\"max_file_bytes\":32768,\"max_depth\":4,\"exec\":[]}|MANIFEST_LEASE" \
         "dirs|{\"v\":1,\"lease\":\"$L\",\"dirs\":[\"src\"],\"max_files\":10,\"max_bytes\":65536,\"max_file_bytes\":32768,\"max_depth\":4,\"exec\":[]}|MANIFEST_DIRS" \
         "exec_outside|{\"v\":1,$std,\"exec\":[\"docs/x\"]}|MANIFEST_EXEC_OUTSIDE_DIRS" \
         "file_over_total|{\"v\":1,\"lease\":\"$L\",\"dirs\":[\"src/\"],\"max_files\":10,\"max_bytes\":10,\"max_file_bytes\":11,\"max_depth\":4,\"exec\":[]}|MANIFEST_LIMIT_MAX_FILE_BYTES"; do
  IFS='|' read -r n j want <<<"$c"
  manifest "$L" "$j"
  [ "$(mcheck)" = "REFUSED $want" ] && ok "manifest $n refused" || bad "manifest $n: $(mcheck)"
done
sudo mv "$I/manifest/$L.json" "$TMP/zkernel-manifest.json"
printf '{}' | sudo tee "$I/manifest/$L.json" >/dev/null
[ "$(mcheck)" = "REFUSED MANIFEST_BAD_OWNER" ] && ok "manifest by root refused" || bad "manifest owner: $(mcheck)"
sudo mv "$I/manifest/$L.json" "$TMP/root-manifest.json"
sudo -u zkernel ln -s /etc/passwd "$I/manifest/$L.json"
[ "$(mcheck)" = "REFUSED MANIFEST_SYMLINK" ] && ok "manifest symlink refused" || bad "manifest symlink: $(mcheck)"

# Диагностика: какой код даёт openat2 вне службы и в службе с разными фильтрами (печатает, не решает).
openat2_diag() {
  local probe='import ctypes,os;L=ctypes.CDLL(None,use_errno=True);L.syscall.restype=ctypes.c_long
class H(ctypes.Structure): _fields_=[("f",ctypes.c_uint64),("m",ctypes.c_uint64),("r",ctypes.c_uint64)]
h=H(os.O_RDONLY|os.O_CLOEXEC,0,0);fd=L.syscall(ctypes.c_long(437),ctypes.c_int(-100),ctypes.c_char_p(b"/etc/hostname"),ctypes.byref(h),ctypes.c_size_t(24))
print("fd",fd,"errno",ctypes.get_errno())'
  echo "OPENAT2_DIAG kernel $(uname -r) $(systemctl --version | head -1)"
  echo "OPENAT2_DIAG direct: $(sudo python3 -I -c "$probe" 2>&1)"
  echo "OPENAT2_DIAG nofilter: $(sudo systemd-run -q --wait --pipe python3 -I -c "$probe" 2>&1)"
  echo "OPENAT2_DIAG system-service: $(sudo systemd-run -q --wait --pipe -p SystemCallFilter=@system-service python3 -I -c "$probe" 2>&1)"
  echo "OPENAT2_DIAG +openat2: $(sudo systemd-run -q --wait --pipe -p SystemCallFilter=@system-service -p SystemCallFilter=openat2 python3 -I -c "$probe" 2>&1)"
  echo "OPENAT2_DIAG +suidsgid: $(sudo systemd-run -q --wait --pipe -p RestrictSUIDSGID=yes python3 -I -c "$probe" 2>&1)"
  echo "OPENAT2_DIAG +native: $(sudo systemd-run -q --wait --pipe -p SystemCallFilter=@system-service -p SystemCallArchitectures=native python3 -I -c "$probe" 2>&1)"
  echo "OPENAT2_DIAG unit filter has openat2: $(systemctl show zimport@00000000000000000000000000000000.service -p SystemCallFilter | tr ' ' '\n' | grep -cx openat2)"
}
echo "=== 3.3.9.2–3.3.9.3 правильный архив: карантин, затем приём"
L=$(newlease); manifest "$L"; put_tar "$L" ok
sudo systemctl start "zquarantine@$L.service" || true
[ "$(jresult quarantine "$L")" = ACCEPTED ] && ok "quarantine accepted ok" || bad "quarantine ok: $(jline quarantine "$L")"
wait_for 30 import_done "$L" || true
[ "$(jresult import "$L")" = ACCEPTED ] && ok "import accepted ok" || { bad "import ok: $(jline import "$L")"; sudo journalctl -u "zimport@$L.service" --no-pager | tail -20; }
jline import "$L" | grep -q '"openat2":[1-9][0-9]*,"fallback":0' && ok "import used openat2 only" || { bad "openat2 not used: $(jline import "$L")"; openat2_diag; }
A=$I/accepted/$L
[ "$(sudo stat -c '%U:%G %a' "$A")" = 'zimport:zgithub 750' ] && ok "accepted dir 750 zimport:zgithub" || bad "accepted dir $(sudo stat -c '%U:%G %a' "$A" 2>&1)"
[ "$(sudo stat -c '%a' "$A/tests/run.sh")" = 750 ] && ok "exec only by manifest (run.sh 750)" || bad "run.sh mode"
[ "$(sudo stat -c '%a %G' "$A/src/a.py")" = '640 zgithub' ] && ok "plain file 640" || bad "a.py mode $(sudo stat -c '%a %G' "$A/src/a.py")"
[ "$(sudo cat "$A/src/a.py")" = "print('zavod')" ] && ok "content intact" || bad "content"
[ "$(sudo find "$A" -type f | wc -l)" = 3 ] && ok "exactly 3 files" || bad "file count"
wait_for 10 inactive "zimport@$L.service" || true
[ "$(archived "$L" import)" = 1 ] && ok "in/out archived after import" || bad "archive after import"
sudo test -e "$I/in/$L.tar" && bad "in left" || ok "in moved, not deleted"
sudo test -e "$I/out/$L" && bad "out left" || ok "out moved, not deleted"
sudo test -s "$(sudo find "$I/archive" -maxdepth 1 -name "$L-*-import")/in.tar" && ok "archived tar kept" || bad "archived tar"

echo "=== ПБ-4: испорченные архивы — отказ карантина, приём не запускается"
for c in symlink:ENTRY_SYMLINK hardlink:ENTRY_HARDLINK chardev:ENTRY_CHAR_DEVICE fifo:ENTRY_FIFO \
         dotdot:BAD_PATH_DOTDOT absolute:BAD_PATH_ABSOLUTE outside:PATH_OUTSIDE_DIRS \
         twin_case:NAME_TWIN twin_nfd:NAME_TWIN windows_name:BAD_NAME_WINDOWS_RESERVED \
         control_char:BAD_NAME_CONTROL_CHAR type_conflict:TYPE_CONFLICT deep:TOO_DEEP too_many:TOO_MANY_FILES \
         total_too_large:TOTAL_TOO_LARGE archive_too_large:ARCHIVE_TOO_LARGE bomb:FILE_TOO_LARGE \
         gnu_format:ARCHIVE_NOT_USTAR pax_format:ENTRY_PAX_HEADER bad_checksum:ARCHIVE_BAD_CHECKSUM \
         trailing:ARCHIVE_TRAILING_DATA truncated:ARCHIVE_TRUNCATED exec_missing:EXEC_FILE_MISSING; do
  n=${c%%:*}; want=${c#*:}
  L=$(newlease); manifest "$L"; put_tar "$L" "$n"
  sudo systemctl start "zquarantine@$L.service" 2>/dev/null || true
  got=$(jreason quarantine "$L")
  if [ "$(jresult quarantine "$L")" = REFUSED ] && [ "$got" = "$want" ]; then ok "archive $n refused ($want)"; else bad "archive $n: $(jline quarantine "$L")"; fi
  wait_for 10 inactive "zquarantine@$L.service" || true
  [ -z "$(jresult import "$L")" ] && ok "archive $n: import not started" || bad "archive $n: import ran"
  [ "$(archived "$L" quarantine)" = 1 ] && ok "archive $n: in/out archived" || bad "archive $n: not archived"
  sudo test -e "$I/accepted/$L" && bad "archive $n: accepted exists" || true
done
L=$(newlease); manifest "$L" "{\"v\":1,\"lease\":\"$L\",\"dirs\":[\"src/\",\"tests/\"],\"max_files\":10,\"max_bytes\":65536,\"max_file_bytes\":32768,\"max_depth\":4,\"exec\":[\"tests/run.sh\"],\"extra\":1}"
put_tar "$L" ok
sudo systemctl start "zquarantine@$L.service" 2>/dev/null || true
[ "$(jreason quarantine "$L")" = MANIFEST_FIELDS ] && ok "quarantine refuses manifest with extra field" || bad "extra field: $(jline quarantine "$L")"

echo "=== ПБ-4: подмена между карантином и приёмом — отказ приёма"
staged() { # аренда → карантин принят, приём ещё не запущен (служба приёма скрыта на время подмены)
  manifest "$1"; put_tar "$1" ok
  sudo systemctl mask --runtime "zimport@$1.service" >/dev/null 2>&1
  sudo systemctl start "zquarantine@$1.service" || true
  [ "$(jresult quarantine "$1")" = ACCEPTED ] || bad "staged quarantine $1"
  sudo systemctl unmask --runtime "zimport@$1.service" >/dev/null 2>&1
  sudo systemctl reset-failed "zimport@$1.service" >/dev/null 2>&1 || true
}
run_import() { sudo systemctl start "zimport@$1.service" 2>/dev/null || true; wait_for 30 import_done "$1" || true; }
expect_import() { # аренда причина имя
  if [ "$(jresult import "$1")" = REFUSED ] && [ "$(jreason import "$1")" = "$2" ]; then ok "$3 refused ($2)"
  else bad "$3: $(jline import "$1")"; fi
  sudo test -e "$I/accepted/$1" && bad "$3: accepted exists" || true
}
F=files
L=$(newlease); staged "$L"
sudo -u zquarantine sh -c "printf Z | dd of=$I/out/$L/$F/src/a.py bs=1 count=1 conv=notrunc status=none"
run_import "$L"; expect_import "$L" SHA256_MISMATCH "file swapped after quarantine"
L=$(newlease); staged "$L"
sudo -u zquarantine sh -c "mv $I/out/$L/$F/src $I/out/$L/$F/src.real && ln -s src.real $I/out/$L/$F/src"
run_import "$L"; expect_import "$L" OUT_NOT_REGULAR "parent folder swapped for a symlink"
L=$(newlease); staged "$L"
sudo -u zquarantine sh -c "ln $I/out/$L/$F/src/sub/b.txt $I/out/$L/$F/src/a.new && mv -f $I/out/$L/$F/src/a.new $I/out/$L/$F/src/a.py"
run_import "$L"; expect_import "$L" HARDLINK_IN_OUT "file with two hard links"
L=$(newlease); staged "$L"
sudo -u zquarantine touch "$I/out/$L/$F/src/extra.txt"
run_import "$L"; expect_import "$L" EXTRA_FILE "extra file after report"
L=$(newlease); staged "$L"
sudo -u zquarantine mv "$I/out/$L/$F/src/sub/b.txt" "$I/out/$L/b.moved"
run_import "$L"; expect_import "$L" FILE_MISSING "missing file after report"
L=$(newlease); staged "$L"
sudo sh -c "printf x > $I/out/$L/$F/src/root.txt"
run_import "$L"; expect_import "$L" OUT_FOREIGN_ENTRY "file of another owner"
L=$(newlease); staged "$L"
sudo -u zquarantine sleep 120 &
sleep 1
run_import "$L"; expect_import "$L" QUARANTINE_PROCESS_ALIVE "quarantine process still alive"
sudo pkill -u zquarantine -x sleep || true

echo "=== запасной путь без openat2 (пошагово с O_NOFOLLOW)"
L=$(newlease); staged "$L"
sudo systemctl mask --runtime "zimport@$L.service" >/dev/null 2>&1
sudo -u zimport python3 -I "$PROG" import "$L" --no-openat2 >/dev/null || true
[ "$(jresult import "$L")" = ACCEPTED ] && jline import "$L" | grep -q '"openat2":0,"fallback":[1-9]' \
  && ok "fallback path accepted ok" || bad "fallback: $(jline import "$L")"
sudo python3 -I "$PROG" archive "$L" import >/dev/null
sudo systemctl unmask --runtime "zimport@$L.service" >/dev/null 2>&1
sudo python3 -I - "$PROG" <<'EOF' && ok "openat2 and fallback refuse links, '..', absolute paths" || bad "open_beneath"
import importlib.util, os, sys, tempfile
spec = importlib.util.spec_from_file_location("zi", sys.argv[1]); zi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zi)
d = tempfile.mkdtemp()
os.mkdir(d + "/real"); open(d + "/real/f", "w").write("x")
os.symlink("real", d + "/link"); os.symlink("/etc/passwd", d + "/real/p"); os.symlink("/proc/self/root/etc", d + "/m")
fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
for use in (True, False):
    f, used = zi.open_beneath(fd, "real/f", os.O_RDONLY, use)
    os.close(f)
    assert used is use, ("openat2 not used" if use else "fallback not used")
    for bad in ("link/f", "real/p", "../etc/passwd", "/etc/passwd", "m/passwd", "real/../../x"):
        try:
            f, _ = zi.open_beneath(fd, bad, os.O_RDONLY, use)
            os.close(f)
            raise SystemExit(f"opened {bad} use_openat2={use}")
        except zi.Refuse:
            pass
print("OPEN_BENEATH_OK")
EOF

echo "=== аудит M33-R2-03: карантин, начатый после проверки приёма, ждёт конца приёма"
lock_busy() { local rc=0; sudo flock -n -E 7 "$I/out" true || rc=$?; [ "$rc" = 7 ]; }
LA=$(newlease); staged "$LA"
LB=$(newlease); manifest "$LB"; put_tar "$LB" ok
# Приём LA от zimport. Обёртка только для CI: сразу после проверки процессов карантина приём ждёт 10 секунд.
sudo -u zimport python3 -I - "$PROG" "$LA" >/dev/null 2>&1 <<'EOF' &
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("zi", sys.argv[1]); zi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zi)
check = zi.quarantine_alive
def slow(qu):
    alive = check(qu)
    time.sleep(10)
    return alive
zi.quarantine_alive = slow
sys.argv = [sys.argv[1], "import", sys.argv[2]]
sys.exit(zi.main())
EOF
imp=$!
wait_for 10 lock_busy && ok "M33-R2-03: import holds the intake lock" || bad "M33-R2-03: import took no lock"
sleep 2
sudo systemctl start "zquarantine@$LB.service" 2>/dev/null & qpid=$!
sleep 4
if sudo test -e "$I/out/$LB.partial" || sudo test -e "$I/out/$LB" || [ -n "$(jresult quarantine "$LB")" ]; then
  bad "M33-R2-03: quarantine ran during import"
else ok "M33-R2-03: quarantine started after the import check waits"; fi
wait "$imp" || true
[ "$(jresult import "$LA")" = ACCEPTED ] && ok "M33-R2-03: import finished" || bad "M33-R2-03: import $(jline import "$LA")"
wait "$qpid" || true
[ "$(jresult quarantine "$LB")" = ACCEPTED ] && ok "M33-R2-03: quarantine ran after import" || bad "M33-R2-03: quarantine $(jline quarantine "$LB")"
wait_for 30 import_done "$LB" || true
[ "$(jresult import "$LB")" = ACCEPTED ] && ok "M33-R2-03: next import accepted" || bad "M33-R2-03: import LB $(jline import "$LB")"
sudo python3 -I "$PROG" archive "$LA" import >/dev/null

echo "=== аудит M33-R2-04: приём на своём разделе с пределом места и числа файлов"
sysfree() { df --output=avail -B1M / | tail -1 | tr -d ' '; }
sysinodes() { df --output=iavail / | tail -1 | tr -d ' '; }
[ "$(findmnt -n -o TARGET --target "$I/out")" = "$I" ] && ok "M33-R2-04: out/ is on the intake partition" || bad "M33-R2-04: out/ not on its partition"
[ "$(stat -c %d "$I/out")" != "$(stat -c %d /var/lib/zavod)" ] && ok "M33-R2-04: intake partition is not the server disk" || bad "M33-R2-04: same device"
itotal=$(df --output=itotal "$I" | tail -1 | tr -d ' ')
[ "$itotal" -le 4096 ] && ok "M33-R2-04: inode limit $itotal" || bad "M33-R2-04: inode limit $itotal"
# Предел числа файлов: архив из 2500 пустых файлов не помещается.
Lm=$(newlease)
manifest "$Lm" "{\"v\":1,\"lease\":\"$Lm\",\"dirs\":[\"src/\"],\"max_files\":3000,\"max_bytes\":65536,\"max_file_bytes\":32768,\"max_depth\":4,\"exec\":[]}"
put_tar "$Lm" many
isys0=$(sysinodes)
sudo systemctl start "zquarantine@$Lm.service" 2>/dev/null || true
if [ "$(jresult quarantine "$Lm")" = REFUSED ] && [ "$(jreason quarantine "$Lm")" = OS_ERROR_ENOSPC ]; then
  ok "M33-R2-04: too many files refused (no inode left)"; else bad "M33-R2-04: inodes: $(jline quarantine "$Lm")"; fi
wait_for 10 inactive "zquarantine@$Lm.service" || true
[ "$(sudo find "$I/archive" -maxdepth 1 -name "$Lm-*" | wc -l)" -ge 1 ] && ok "M33-R2-04: refused archive moved to archive/" || bad "M33-R2-04: not archived"
isys1=$(sysinodes)
[ $((isys0 - isys1)) -lt 500 ] && ok "M33-R2-04: server disk inodes untouched ($((isys0 - isys1)))" || bad "M33-R2-04: server inodes used $((isys0 - isys1))"
# Освободить inode раздела для пробы места: перенос на диск машины CI, ничего не удаляется.
sudo sh -c "mv '$I'/archive/$Lm-* '$TMP'/"
# Предел места: архивы по 20 МБ, пока раздел не откажет.
python3 -I "$HERE/intake_gen.py" big "$TMP/big.tar"
sys0=$(sysfree); full=''
for n in 1 2 3 4 5 6 7 8 9 10; do
  Lb=$(newlease)
  mb="{\"v\":1,\"lease\":\"$Lb\",\"dirs\":[\"src/\",\"tests/\"],\"max_files\":10,\"max_bytes\":33554432,\"max_file_bytes\":33554432,\"max_depth\":4,\"exec\":[\"tests/run.sh\"]}"
  if ! printf '%s' "$mb" | sudo -u zkernel tee "$I/manifest/$Lb.json" >/dev/null 2>&1; then full="manifest $n"; break; fi
  sudo -u zkernel chmod 0644 "$I/manifest/$Lb.json"
  if ! sudo install -o zgate -g zquarantine -m 0640 "$TMP/big.tar" "$I/in/$Lb.tar" 2>/dev/null; then full="upload $n"; break; fi
  sudo systemctl start "zquarantine@$Lb.service" 2>/dev/null || true
  if [ "$(jresult quarantine "$Lb")" != ACCEPTED ]; then full="quarantine $n $(jreason quarantine "$Lb")"; break; fi
  wait_for 60 import_done "$Lb" || true
  if [ "$(jresult import "$Lb")" != ACCEPTED ]; then full="import $n $(jreason import "$Lb")"; break; fi
done
echo "INTAKE_INFO intake partition full at: ${full:-never} ($(df --output=used,avail -B1M "$I" | tail -1))"
case "$full" in
  "manifest "*|"upload "*|*OS_ERROR_ENOSPC) ok "M33-R2-04: full partition refuses ($full)" ;;
  *) bad "M33-R2-04: partition did not refuse (${full:-never})" ;;
esac
sys1=$(sysfree)
[ $((sys0 - sys1)) -lt 16 ] && ok "M33-R2-04: server disk not used ($((sys0 - sys1)) MB)" || bad "M33-R2-04: server disk used $((sys0 - sys1)) MB"

echo "=== итог"
if [ "$FAILS" = 0 ]; then echo "INTAKE_CI=PASS"; else echo "INTAKE_CI=FAIL ($FAILS)"; exit 1; fi
