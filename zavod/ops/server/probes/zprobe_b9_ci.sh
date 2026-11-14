#!/bin/bash
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_b9_ci.sh
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-14 11:02 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 11:02 +02:00
# ИСПОЛНИТЕЛЬ: Claude, чат «Завод 3.5.5 ПБ-1 · 05» (c241e855)
# НАЗНАЧЕНИЕ: проверка B9 в настоящем systemd одноразовой машины CI (проект DESIGN_B9_3_5_5_20261114_v0_9.md
#   раздел 3; v0.4 разделы 4–5; v0.3 раздел 2). Только от root, только на машине CI, НЕ на сервере.
#   Часть 1 — установка: B8 ставится копиями файлов коммита B8, журнал pb1trial1 собирается кодом; выпуск B9
#   собирается build_release_3_5_5_b9.py; preflight, чужой файл, ссылка вместо родителя, обрыв после 3-го CREATED,
#   доводка, verify-installed, повтор install, report.
#   Часть 2 — завершение серий: в проверочных службах меняется только ExecStart (и уборка: клетки на CI нет);
#   журнал — настоящий main B9 под обёрткой с подменой os.fsync; каждое состояние — новая папка, подключённая
#   bind-монтированием поверх /var/lib/zavod/probes (ничего не удаляется). Проверки 1–17; 18 и 19 — в test_zprobe.py.
#   Часть 3 — изоляция службы журнала: отрицательные случаи v0.3 раздел 2 и контроль на хосте.
# ВЫЗОВ: sudo bash zprobe_b9_ci.sh <корень хранилища>
set -uo pipefail
REPO=$(cd "$1" && pwd)
SRC=$REPO/zavod/ops/server/probes
B8C=0468f70cd030191e35cb8b5b86460edb8d409a4b
LIB=/usr/local/lib/zavod/probes-b9
CI=/usr/local/lib/zavod/probes-b9-ci
CTL=/run/zprobe/ci-control
DATA=/var/lib/zavod/probes
CH=0123456789abcdef0123456789abcdef
OUT=/root/zci
FAILS=0
K=0
echo "PROVENANCE sha=${GITHUB_SHA:-?} run=${GITHUB_RUN_ID:-?} attempt=${GITHUB_RUN_ATTEMPT:-?} arch=$(uname -m) head=$(git -C "$REPO" rev-parse HEAD)"
(cd "$SRC" && sha256sum zprobe_journal.py zprobe-start zprobe-run-b9@.service zprobe-journal-b9@.service zprobe_runner.py \
  zprobe_release_b9.py build_release_3_5_5_b9.py ci_b9/*.py) | sed 's/^/PROVENANCE_SHA256 /'
mkdir -m 0700 "$OUT"
ok() { echo "CI $1 PASS ${2:-}"; }
bad() { echo "CI $1 FAIL ${2:-}"; FAILS=$((FAILS + 1)); }
has() { if grep -qE -- "$3" "$2"; then ok "$1" "$(grep -E -- "$3" "$2" | head -1 | cut -c1-220)"; else bad "$1" "no /$3/ in: $(tr '\n' ' ' < "$2" | cut -c1-600)"; fi; }
hasnt() { if grep -qE -- "$3" "$2"; then bad "$1" "unexpected /$3/: $(grep -E -- "$3" "$2" | head -1 | cut -c1-220)"; else ok "$1" "no /$3/"; fi; }
eq() { if [ "$2" = "$3" ]; then ok "$1" "$4=$2"; else bad "$1" "$4: got $2 want $3"; fi; }
nseg() { find "$DATA/journal" -maxdepth 1 -name '*.jsonl' 2>/dev/null | wc -l; }
segs() { echo "SEGMENTS $(nseg) $( (cd "$DATA/journal" 2>/dev/null && sha256sum ./*.jsonl 2>/dev/null) | awk '{printf "%s:%s ", substr($2,3), substr($1,1,16)}')"; }
mk() { runuser -u zprobe -- env ZB8="$CI/b8" /usr/bin/python3 -I "$CI/mkstate.py" "$@"; }
ctl() { (set -C; printf '%s\n' "$2" > "$CTL/$1"); }
o() { K=$((K + 1)); echo "$OUT/$(printf %03d $K)-$1.out"; }
run() { local f; f=$(o "$1"); shift; "$@" > "$f" 2>&1; echo "rc=$?" >> "$f"; echo "$f"; }
start() { run "start-$1" "$LIB/zprobe-start" "$1" "$CH" ПБ-1; }
retry() { run "retry-$1" "$LIB/zprobe-start" --journal-retry "$1"; }
jlog() { local f; f=$(o "jlog-$1"); journalctl -u "zprobe-journal-b9@$1.service" --no-pager -o cat > "$f" 2>&1; echo "$f"; }
waitfor() { local i; for i in $(seq 1 120); do eval "$1" && return 0; sleep 0.5; done; return 1; }
SN=0
scen() {
  SN=$((SN + 1))
  if mountpoint -q "$DATA"; then umount "$DATA"; fi
  local d=/var/lib/zavod/ci-data/$SN-$1
  install -d -m 0750 -o zprobe -g zprobe "$d"
  mount --bind "$d" "$DATA"
  echo "=== scenario $SN $1 ($d)"
}
manual_reserve() {   # как zprobe-start до запуска службы, затем «убит»
  install -d -m 0750 -o root -g zprobe "/run/zprobe/$1"
  (umask 0137; set -C; printf '{"challenge":"%s","probes":["ПБ-1"],"series":"%s"}\n' "$CH" "$1" > "/run/zprobe/$1/request.json")
  chgrp zprobe "/run/zprobe/$1/request.json"
  runuser -u zprobe -- /usr/bin/python3 -I "$LIB/zprobe_journal.py" reserve "$1"
}
request_only() {
  install -d -m 0750 -o root -g zprobe "/run/zprobe/$1"
  (umask 0137; set -C; printf '{"challenge":"%s","probes":["ПБ-1"],"series":"%s"}\n' "$CH" "$1" > "/run/zprobe/$1/request.json")
  chgrp zprobe "/run/zprobe/$1/request.json"
}

echo "##### setup: B8 as installed on zavod-1 (files of B8 commit $B8C)"
id zprobe > /dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin zprobe
install -d -m 0755 /usr/local/lib/zavod /usr/local/lib/zavod/probes /etc/zavod "$CI" "$CI/b8"
install -d -m 0750 -o zprobe -g zprobe "$DATA"
install -d -m 0755 /var/lib/zavod/ci-data
install -d -m 0750 -o root -g zprobe /run/zprobe
install -d -m 0755 "$CTL"
b8() { git -C "$REPO" show "$B8C:$1"; }
for f in pb1_session.py zprobe_rules.py zprobe_runner.py zprobe_journal.py; do b8 "zavod/ops/server/probes/$f" > "/usr/local/lib/zavod/probes/$f"; done
b8 zavod/ops/server/probes/zprobe-start > /usr/local/lib/zavod/probes/zprobe-start
chmod 0755 /usr/local/lib/zavod/probes/zprobe-start
printf 'commit=%s\nversion=3.5.5\n' "$B8C" > /usr/local/lib/zavod/probes/RELEASE
b8 zavod/ops/server/probes/zprobe-run@.service > /etc/systemd/system/zprobe-run@.service
b8 zavod/ops/server/cell/zagent@.service > /etc/systemd/system/zagent@.service
b8 zavod/ops/server/cell/zavod-proxy > /usr/local/lib/zavod/zavod-proxy
b8 zavod/ops/server/cell/zavod-gate > /usr/local/lib/zavod/zavod-gate
b8 zavod/ops/server/cell/zavod-egress.nft > /etc/zavod/zavod-egress.nft
b8 zavod/ops/server/probes/zprobe_journal.py > "$CI/b8/zprobe_journal.py"
for u in zavod-proxy zavod-nft; do
  printf '[Unit]\nDescription=CI stub %s\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/bin/true\n' "$u" > "/etc/systemd/system/$u.service"
done
install -m 0644 "$SRC"/ci_b9/*.py "$CI/"
systemctl daemon-reload

echo "##### part 1: install B9 beside B8"
scen pb1
mk seg pb1trial1 INTERRUPTED
D=$(mk digest); echo "$D"
DG=$(echo "$D" | sed -n 's/.* digest=\([0-9a-f]*\).*/\1/p'); LS=$(echo "$D" | sed -n 's/.* last_sha256=\([0-9a-f]*\).*/\1/p')
[ ${#DG} = 64 ] && [ ${#LS} = 64 ] && ok I0 "pb1trial1 journal digest=${DG:0:16} last=${LS:0:16}" || bad I0 "$D"
python3 -I -B "$SRC/build_release_3_5_5_b9.py" "$REPO" "$(git -C "$REPO" rev-parse HEAD)" | tee "$(o build)"
SH=$SRC/zprobe-release-3.5.5-b9.sh
P=/var/lib/zavod/probes-pkg-$(git -C "$REPO" rev-parse HEAD | cut -c1-12)
f=$(run pre-real bash "$SH" preflight)
has I1a "$f" '^PACKAGE_UNPACKED='
has I1b "$f" '^CHECK JOURNAL FAIL expected journal anchor is not the full value'
for c in B8 UNITS ACCOUNT STARTED TARGETS_ABSENT PARENTS; do has "I1-$c" "$f" "^CHECK $c OK"; done
has I1c "$f" '^rc=1$'
zrel() {
  python3 -I -B -c "
import os, sys
sys.path.insert(0, sys.argv[1] + '/zavod/ops/server/probes')
import zprobe_release_b9 as Z
Z.EXPECT_DIGEST, Z.EXPECT_LAST = sys.argv[2], sys.argv[3]
if os.environ.get('ZLIB'):
    Z.LIB = Z.REL.LIB = os.environ['ZLIB']
    Z.UNIT_DIR = os.environ['ZUNIT']
if os.environ.get('ZFAULT'):
    n = [0]
    def fault(step, path):
        if step == 'record':
            n[0] += 1
        elif n[0] >= int(os.environ['ZFAULT']):
            raise RuntimeError('CI fault after CREATED number ' + os.environ['ZFAULT'])
    Z.REL.FAULT = fault
sys.argv = ['zprobe_release_b9.py'] + sys.argv[4:]
sys.exit(Z.main())
" "$P" "$DG" "$LS" "$@"
}
f=$(run pre-ok zrel preflight "$P"); has I2 "$f" '^ZPROBE_B9_PREFLIGHT=OK '
install -d -m 0755 /opt/zci /opt/zci/f /opt/zci/f/lib /opt/zci/f/sd
printf 'foreign\n' > /opt/zci/f/sd/zprobe-journal-b9@.service
FS=$(sha256sum /opt/zci/f/sd/zprobe-journal-b9@.service)
f=$(ZLIB=/opt/zci/f/lib/probes-b9 ZUNIT=/opt/zci/f/sd run pre-foreign zrel preflight "$P"); has I3a "$f" '^CHECK TARGETS_ABSENT FAIL present: .*zprobe-journal-b9@.service'
f=$(ZLIB=/opt/zci/f/lib/probes-b9 ZUNIT=/opt/zci/f/sd run inst-foreign zrel install "$P"); has I3b "$f" '^ZPROBE_B9_INSTALL=REFUSED conflicts='
eq I3c "$(sha256sum /opt/zci/f/sd/zprobe-journal-b9@.service)" "$FS" foreign_file_unchanged
eq I3d "$(test -e /opt/zci/f/lib/probes-b9 && echo created || echo absent)" absent lib_not_created
install -d -m 0755 /opt/zci/l /opt/zci/l/real /opt/zci/l/sd
ln -s real /opt/zci/l/lnk
f=$(ZLIB=/opt/zci/l/lnk/probes-b9 ZUNIT=/opt/zci/l/sd run pre-link zrel preflight "$P"); has I4a "$f" '^CHECK PARENTS FAIL .*lnk is not a plain folder'
f=$(ZLIB=/opt/zci/l/lnk/probes-b9 ZUNIT=/opt/zci/l/sd run inst-link zrel install "$P"); has I4b "$f" '^ZPROBE_B9_INSTALL=REFUSED'
eq I4c "$(ls -A /opt/zci/l/real | wc -l)" 0 nothing_created_through_link
f=$(ZFAULT=3 run inst-partial zrel install "$P"); has I5a "$f" '^ZPROBE_B9_INSTALL=PARTIAL '
f=$(run pre-partial zrel preflight "$P"); has I5b "$f" '^CHECK TARGETS_ABSENT FAIL present:'
f=$(run inst-finish zrel install "$P"); has I5c "$f" '^ZPROBE_B9_INSTALL=OK'
f=$(run verify zrel verify-installed "$P"); has I6 "$f" '^ZPROBE_B9_VERIFY_INSTALLED=OK '
f=$(run inst-again zrel install "$P"); has I7 "$f" '^ZPROBE_B9_INSTALL=REFUSED already installed; nothing created'
f=$(run report zrel report "$P" verify-installed); has I8 "$f" '^REPORT=/root/zprobe-install-3.5.5-b9-'
eq I9 "$(git -C "$REPO" show "$B8C:zavod/ops/server/probes/zprobe_journal.py" | sha256sum | cut -c1-64)" \
  "$(sha256sum < /usr/local/lib/zavod/probes/zprobe_journal.py | cut -c1-64)" b8_journal_untouched

echo "##### part 2: completion of series in real systemd"
JL=$(grep '^ExecStopPost=+/usr/bin/systemctl start --no-block zprobe-journal-b9@%i.service$' /etc/systemd/system/zprobe-run-b9@.service)
[ -n "$JL" ] && ok C0 "journal start line is in the installed unit" || bad C0 "no journal start line"
install -d -m 0755 /etc/systemd/system/zprobe-run-b9@.service.d /etc/systemd/system/zprobe-journal-b9@.service.d
printf '[Service]\nExecStart=\nExecStart=+/usr/bin/python3 -I %s/fake_runner.py run %%i\nExecStopPost=\nExecStopPost=-+/usr/bin/python3 -I %s/fake_runner.py cleanup %%i\n%s\n' \
  "$CI" "$CI" "$JL" > /etc/systemd/system/zprobe-run-b9@.service.d/ci.conf
printf '[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I %s/journal_wrap.py commit %%i\n' "$CI" > /etc/systemd/system/zprobe-journal-b9@.service.d/ci.conf
systemctl daemon-reload
scen main
f=$(start c1); has 1 "$f" '^ZPROBE_START CONFIRMED series=c1 SERIES_END COMPLETE '; eq 1n "$(nseg)" 1 segments; segs
ctl mode-c2 crash; f=$(start c2); has 2 "$f" '^ZPROBE_START CONFIRMED series=c2 SERIES_END INTERRUPTED .*runner_missing'; segs
ctl mode-c3 cleanupfail; f=$(start c3); has 3 "$f" '^ZPROBE_START CONFIRMED series=c3 SERIES_END INTERRUPTED .*cleanup:cleanup_bad'; segs
ctl fault-c4 startfail; f=$(start c4); has 4a "$f" '^ZPROBE_START UNKNOWN series=c4 .*ABSENT'; eq 4n "$(nseg)" 3 segments
eq 4b "$(grep -c CI_STARTFAIL "$(jlog c4)")" 1 journal_unit_runs
ctl clear-c4 x; f=$(retry c4); has 4c "$f" '^ZPROBE_START CONFIRMED series=c4 '; eq 4d "$(nseg)" 4 segments; segs
ctl fault-c5 hold
f5=$(o start-c5); ( "$LIB/zprobe-start" c5 "$CH" ПБ-1 > "$f5" 2>&1; echo "rc=$?" >> "$f5" ) & B5=$!
waitfor "grep -q CI_HOLD \"\$(jlog c5)\"" && ok 5a "journal held after write, before fsync" || bad 5a "no hold"
sleep 3
W5=$(grep -l '"series":"c5"' "$DATA"/journal/*.jsonl | head -1)
eq 5b "$(tail -c 1 "$W5" | od -An -c | tr -d ' ')" '\n' segment_readable_whole
kill -0 $B5 2> /dev/null && ! grep -q CONFIRMED "$f5" && ok 5c "zprobe-start gives no CONFIRMED while fsync is held" || bad 5c "$(cat "$f5")"
ctl release-c5 x; wait $B5; has 5d "$f5" '^ZPROBE_START CONFIRMED series=c5 '; segs
ctl fault-c6 fail; f=$(start c6); has 6a "$f" '^ZPROBE_START UNKNOWN series=c6 .*WHOLE_UNCONFIRMED'; N6=$(nseg)
f=$(start c6b); hasnt 6b "$f" '^ZPROBE_START CONFIRMED'; eq 6c "$(nseg)" "$N6" segments_while_fault
has 6d "$(jlog c6b)" 'ZPROBE_JOURNAL REFUSED FSYNC'
ctl clear-c6 x; f=$(retry c6); has 6e "$f" '^ZPROBE_START CONFIRMED series=c6 '; eq 6f "$(nseg)" "$N6" no_new_write
has 6g "$(jlog c6)" 'CONFIRMED series=c6 .* write=already'
f=$(retry c6b); has 6h "$f" '^ZPROBE_START CONFIRMED series=c6b '; eq 6i "$(nseg)" $((N6 + 1)) segments; segs
N7=$(nseg); f=$(retry c1); has 7a "$f" '^ZPROBE_START CONFIRMED series=c1 '; eq 7b "$(nseg)" "$N7" segments
ctl fault-c8 hold
f8=$(o start-c8); ( "$LIB/zprobe-start" c8 "$CH" ПБ-1 > "$f8" 2>&1; echo "rc=$?" >> "$f8" ) & B8=$!
waitfor "grep -q CI_HOLD \"\$(jlog c8)\"" || bad 8x "no hold"
f=$(retry c8); has 8a "$f" 'ZPROBE_START REFUSED: units of c8 are active or queued'
ctl release-c8 x; wait $B8; has 8b "$f8" '^ZPROBE_START CONFIRMED series=c8 '
eq 8c "$(grep -c CI_HOLD "$(jlog c8)")" 1 journal_unit_runs
ctl mode-c9a slow
f9=$(o start-c9a); ( "$LIB/zprobe-start" c9a "$CH" ПБ-1 > "$f9" 2>&1; echo "rc=$?" >> "$f9" ) & B9=$!
waitfor "test -e $DATA/started/c9a" || bad 9x "c9a not reserved"
f=$(start c9b); has 9a "$f" 'ZPROBE_START REFUSED: reserve: .*BUSY'
eq 9b "$(test -e "$DATA/started/c9b" && echo yes || echo no)" no started_c9b
wait $B9; has 9c "$f9" '^ZPROBE_START CONFIRMED series=c9a '
f=$(start c9c); has 9d "$f" '^ZPROBE_START CONFIRMED series=c9c '
f=$(start c9b); has 9e "$f" 'REFUSED: series folder already exists'   # имя после BUSY занято папкой /run/zprobe/c9b
manual_reserve c9d
f=$(start c9e); has 9a1 "$f" 'ZPROBE_START REFUSED: reserve: .*BUSY'
eq 9a2 "$(test -e "$DATA/started/c9e" && echo yes || echo no)" no started_c9e
f=$(retry c9d); has 9a3 "$f" '^ZPROBE_START CONFIRMED series=c9d SERIES_END INTERRUPTED '
f=$(start c9f); has 9a4 "$f" '^ZPROBE_START CONFIRMED series=c9f '
f=$(start c10a); f=$(start c10b); f=$(retry c10a)
W10=$(grep -l '"series":"c10a"' "$DATA"/journal/*.jsonl | head -1)
L10=$(tail -n 1 "$W10" | tr -d '\n' | sha256sum | cut -c1-64)
has 10 "$f" "^ZPROBE_START CONFIRMED series=c10a .* seg=$(basename "$W10") seq=[0-9]+ last_sha256=$L10 "; segs

scen orphans9b
mk seg z0 COMPLETE; request_only g1; request_only g2; mk mark g1 "$CH"; mk mark g2 "$CH"; N=$(nseg)
systemctl start zprobe-journal-b9@g1.service; systemctl start zprobe-journal-b9@g2.service
has 9b1 "$(jlog g1)" 'REFUSED ORPHAN'; has 9b2 "$(jlog g2)" 'REFUSED ORPHAN'; eq 9b3 "$(nseg)" "$N" nothing_written

scen torn11
f=$(start t1); mk torn; N=$(nseg); segs
f=$(start t2); has 11a "$f" 'ZPROBE_START REFUSED: reserve: .*TORN_HISTORY'
f=$(retry t1); hasnt 11b "$f" '^ZPROBE_START CONFIRMED'
systemctl start zprobe-journal-b9@t1.service; has 11c "$(jlog t1)" 'REFUSED TORN_HISTORY'; eq 11d "$(nseg)" "$N" nothing_written
scen torn12
f=$(start u1); manual_reserve u2; mk torn u2; N=$(nseg)
f=$(retry u2); has 12a "$f" '^ZPROBE_START JOURNAL_REFUSED series=u2 '; has 12b "$(jlog u2)" 'REFUSED TORN_HISTORY'
eq 12c "$(nseg)" "$N" nothing_written
for v in foreign wrongch badbytes foreignfile otherseries; do
  scen "marks13-$v"
  case $v in
    wrongch) mk seg m0 COMPLETE --markch ffffffffffffffffffffffffffffffff;;
    badbytes) mk seg m0 COMPLETE --nomark; mk rawmark m0 garbage;;
    *) mk seg m0 COMPLETE;;
  esac
  case $v in foreign) mk mark FOREIGN "$CH";; foreignfile) mk foreign x.txt;; otherseries) mk mark s0x "$CH";; esac
  request_only m1; mk mark m1 "$CH"; N=$(nseg)
  systemctl start zprobe-journal-b9@m1.service
  has "13-$v" "$(jlog m1)" 'REFUSED ORPHAN'; eq "13-$v-n" "$(nseg)" "$N" nothing_written
  if [ $v = foreign ]; then f=$(start m2); has 13-reserve "$f" 'REFUSED: reserve: .*(BUSY|ORPHAN)'; eq 13-reserve-m "$(test -e "$DATA/started/m2" && echo yes || echo no)" no started_m2; fi
done
scen dup14
mk dup d1; request_only d2; mk mark d2 "$CH"; N=$(nseg)
systemctl start zprobe-journal-b9@d2.service; has 14a "$(jlog d2)" 'REFUSED CORRUPT: series d1 is in two segments'; eq 14b "$(nseg)" "$N" nothing_written
scen midbad15
mk midbad e1 e2; request_only e3; mk mark e3 "$CH"; N=$(nseg)
systemctl start zprobe-journal-b9@e3.service; has 15a "$(jlog e3)" 'REFUSED CORRUPT'; eq 15b "$(nseg)" "$N" nothing_written
scen b8race16
f=$(start v0)
fb=$(o b8-b8a); ( mk b8 b8a hold-die > "$fb" 2>&1 ) & BB=$!
waitfor "grep -q CI_B8_HOLD $fb" || bad 16x "B8 not held"
fv=$(o start-v1); ( "$LIB/zprobe-start" v1 "$CH" ПБ-1 > "$fv" 2>&1; echo "rc=$?" >> "$fv" ) & BV=$!
sleep 4
eq 16a "$(test -e "$DATA/started/v1" && echo yes || echo no)" no v1_waits_for_the_shared_lock
eq 16b "$(grep -c '"series":"v1"' "$DATA"/journal/*.jsonl | awk -F: '{s+=$2} END {print s+0}')" 0 v1_not_written
ctl release-b8a x; wait $BB; has 16c "$fb" 'CI_B8_DIE before fsync'
wait $BV; has 16d "$fv" '^ZPROBE_START CONFIRMED series=v1 '; eq 16e "$(nseg)" 3 segments; has 16f "$(run d16 mk digest)" 'CHECK OK segments=3'
scen b8race16f
f=$(start w0)
fb=$(o b8-b8b); ( mk b8 b8b hold-die > "$fb" 2>&1 ) & BB=$!
waitfor "grep -q CI_B8_HOLD $fb" || bad 16y "B8 not held"
ctl fault-b8b fail
fv=$(o start-w1); ( "$LIB/zprobe-start" w1 "$CH" ПБ-1 > "$fv" 2>&1; echo "rc=$?" >> "$fv" ) & BV=$!
sleep 2; ctl release-b8b x; wait $BB; wait $BV
hasnt 16g "$fv" '^ZPROBE_START CONFIRMED'; has 16h "$(jlog w1)" 'REFUSED FSYNC'; eq 16i "$(nseg)" 2 segments
scen b8after17
f=$(start x0); f=$(run b8-b8c mk b8 b8c ok); has 17a "$f" 'CI_B8_APPENDED series=b8c'
f=$(start x1); has 17b "$f" '^ZPROBE_START CONFIRMED series=x1 '; eq 17c "$(nseg)" 3 segments; has 17d "$(run d17 mk digest)" 'CHECK OK segments=3'

echo "##### part 3: isolation of the journal unit"
python3 -I -c "
import ctypes, os, socket, time
libc = ctypes.CDLL(None, use_errno=True)
libc.msgget(0x5a50, 0o1000 | 0o666); libc.shmget(0x5a51, 4096, 0o1000 | 0o666)
ss = []
for p in ('/run/zprobe-ci-host.sock', '/var/tmp/zprobe-ci-host.sock', '\0zprobe-ci-abstract'):
    s = socket.socket(socket.AF_UNIX); s.bind(p); s.listen(8); ss.append(s)
    if not p.startswith('\0'):
        os.chmod(p, 0o777)
time.sleep(90)
" & BL=$!
sleep 2
f=$(run iso-host runuser -u zprobe -- /usr/bin/python3 -I "$CI/iso_probe.py" host)
for k in host_run_sock host_var_sock abstract; do has "X0-$k" "$f" "\"$k\": \"CONNECTED\""; done
for k in msgget shmget; do has "X0-$k" "$f" "\"$k\": \"FOUND\""; done
sed -e "s|^ExecStart=.*|ExecStart=/usr/bin/python3 -I $CI/iso_probe.py unit|" -e 's|^Description=.*|Description=CI isolation probe %i|' \
  /etc/systemd/system/zprobe-journal-b9@.service > /run/systemd/system/zprobe-journal-b9-iso@.service
diff <(grep -v '^ExecStart=\|^Description=' /etc/systemd/system/zprobe-journal-b9@.service) \
     <(grep -v '^ExecStart=\|^Description=' /run/systemd/system/zprobe-journal-b9-iso@.service) && ok X1 "iso unit differs only by ExecStart" || bad X1 "iso unit differs"
systemctl daemon-reload; request_only iso
systemctl start zprobe-journal-b9-iso@iso.service
f=$(o iso-unit); journalctl -u zprobe-journal-b9-iso@iso.service --no-pager -o cat > "$f"
for k in inet inet6 netlink host_run_sock host_var_sock dbus abstract msgget shmget; do has "X2-$k" "$f" "\"$k\": \"DENIED:"; done
kill $BL 2> /dev/null
if mountpoint -q "$DATA"; then umount "$DATA"; fi
echo "CI_FAILS=$FAILS"
[ "$FAILS" = 0 ] && echo ZPROBE_COMPLETION_CI_OK
