#!/bin/bash
# ДОКУМЕНТ: zavod/ops/server/probes/zprobe_b9_ci.sh
# ВЕРСИЯ: v0.7  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-14 11:02 +02:00  ДАТА ОБНОВЛЕНИЯ: 2026-11-14 12:48 +02:00
# v0.7 (аудит ChatGPT REL34): 26–31 — отказ --restore-request ничего не меняет: папка root:root с чужим request,
#   папка root:root с посторонним файлом, request с двумя жёсткими ссылками, файл с именем «перевод строки» и
#   «request.json + перевод строки», /run/zprobe root:root при плохой папке серии — владелец, группа, права, inode,
#   число ссылок и байты до и после равны; 32 — /run/zprobe root:root и папки нет: восстановление идёт, группа zprobe.
# v0.6 (аудит ChatGPT REL33): 20–24 — серия отмечена, request.json нет (сбой сразу после допуска, папка с группой
#   root после сбоя chgrp, перезагрузка — /run пуст): новая серия BUSY, --journal-retry отказывает, --restore-request
#   создаёт request по отметке, затем --journal-retry закрывает серию одним сегментом, новая серия снова идёт;
#   отрицательные — чужой вызов в request, испорченная отметка, второй orphan: отказ, ничего не создано (M-01).
#   V3 — ослабление SystemCallFilter, RestrictNamespaces, InaccessiblePaths → verify-installed FAIL (L-01).
# v0.5 (аудит ChatGPT REL32): 9 — после BUSY нет ни папки, ни request, то же имя затем CONFIRMED (M-01); I10 — чужие
#   файлы с байтами и правами выпуска → install REFUSED, ничего не создано (M-02); V1, V2 — чужой drop-in, подмена
#   ExecStart и ослабление (IPAddressDeny, PrivateIPC) → verify-installed FAIL (M-04); 18 — CONFIRMED без успеха
#   службы и поддельная запись успеха не от PID 1 → UNKNOWN; 19 — код journalctl не 0 → UNKNOWN (M-03).
# v0.4 (CI run 43580163357): число запусков службы журнала — по строкам systemd «Starting …», а не по CI_HOLD
#   (один запуск делает fsync сегмента своей серии больше одного раза).
# v0.3 (CI run 43579946720): в строке итога между series= и SERIES_END стоит journalctl_rc=; проверка 6 — сначала
#   повтор c6b (его отметка без сегмента — orphan для c6, шлюз отказывает c6 до записи c6b), затем c6 (write=already);
#   удержание ищется по своей серии (строки CI_HOLD других серий печатаются при fsync их сегментов).
# v0.2 (CI run 43579303026): mkstate берёт код журнала B9 из копии $CI/src (до установки B9 его нет в LIB);
#   чужие корни — /usr/local/zci (у /opt на машине CI права 0777) с копией службы B8; без неиспользуемой переменной.
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
mk() { runuser -u zprobe -- env ZB8="$CI/b8" ZJLIB="$CI/src" /usr/bin/python3 -I "$CI/mkstate.py" "$@"; }
ctl() { (set -C; printf '%s\n' "$2" > "$CTL/$1"); }
o() { K=$((K + 1)); echo "$OUT/$(printf %03d $K)-$1.out"; }
run() { local f; f=$(o "$1"); shift; "$@" > "$f" 2>&1; echo "rc=$?" >> "$f"; echo "$f"; }
start() { run "start-$1" "$LIB/zprobe-start" "$1" "$CH" ПБ-1; }
retry() { run "retry-$1" "$LIB/zprobe-start" --journal-retry "$1"; }
jlog() { local f; f=$(o "jlog-$1"); journalctl -u "zprobe-journal-b9@$1.service" --no-pager -o cat > "$f" 2>&1; echo "$f"; }
waitfor() { for _ in $(seq 1 120); do eval "$1" && return 0; sleep 0.5; done; return 1; }
SN=0
scen() {
  SN=$((SN + 1))
  if mountpoint -q "$DATA"; then umount "$DATA"; fi
  local d=/var/lib/zavod/ci-data/$SN-$1
  install -d -m 0750 -o zprobe -g zprobe "$d"
  mount --bind "$d" "$DATA"
  echo "=== scenario $SN $1 ($d)"
}
manual_reserve() {   # как zprobe-start до запуска службы (допуск, затем папка и request), затем «убит»
  runuser -u zprobe -- /usr/bin/python3 -I "$LIB/zprobe_journal.py" reserve "$1" "$CH"
  request_only "$1"
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
install -d -m 0755 "$CI/src"
install -m 0644 "$SRC/zprobe_journal.py" "$SRC/zprobe_rules.py" "$CI/src/"
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
has I1b "$f" '^CHECK JOURNAL FAIL journal differs from the anchor after pb1trial1'
hasnt I1d "$f" 'not the full value'
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
install -d -m 0755 /usr/local/zci /usr/local/zci/f /usr/local/zci/f/lib /usr/local/zci/f/sd
printf 'foreign\n' > /usr/local/zci/f/sd/zprobe-journal-b9@.service
install -m 0644 /etc/systemd/system/zprobe-run@.service /usr/local/zci/f/sd/
FS=$(sha256sum /usr/local/zci/f/sd/zprobe-journal-b9@.service)
f=$(ZLIB=/usr/local/zci/f/lib/probes-b9 ZUNIT=/usr/local/zci/f/sd run pre-foreign zrel preflight "$P"); has I3a "$f" '^CHECK TARGETS_ABSENT FAIL present: .*zprobe-journal-b9@.service'
f=$(ZLIB=/usr/local/zci/f/lib/probes-b9 ZUNIT=/usr/local/zci/f/sd run inst-foreign zrel install "$P"); has I3b "$f" '^ZPROBE_B9_INSTALL=REFUSED conflicts='
eq I3c "$(sha256sum /usr/local/zci/f/sd/zprobe-journal-b9@.service)" "$FS" foreign_file_unchanged
eq I3d "$(test -e /usr/local/zci/f/lib/probes-b9 && echo created || echo absent)" absent lib_not_created
install -d -m 0755 /usr/local/zci/l /usr/local/zci/l/real /usr/local/zci/l/sd
ln -s real /usr/local/zci/l/lnk
install -m 0644 /etc/systemd/system/zprobe-run@.service /usr/local/zci/l/sd/
f=$(ZLIB=/usr/local/zci/l/lnk/probes-b9 ZUNIT=/usr/local/zci/l/sd run pre-link zrel preflight "$P"); has I4a "$f" '^CHECK PARENTS FAIL .*lnk is not a plain folder'
f=$(ZLIB=/usr/local/zci/l/lnk/probes-b9 ZUNIT=/usr/local/zci/l/sd run inst-link zrel install "$P"); has I4b "$f" '^ZPROBE_B9_INSTALL=REFUSED'
eq I4c "$(ls -A /usr/local/zci/l/real | wc -l)" 0 nothing_created_through_link
install -d -m 0755 /usr/local/zci/s /usr/local/zci/s/lib /usr/local/zci/s/sd
for u in zprobe-run-b9@.service zprobe-journal-b9@.service; do install -m 0644 "$P/zavod/ops/server/probes/$u" /usr/local/zci/s/sd/; done
install -m 0644 /etc/systemd/system/zprobe-run@.service /usr/local/zci/s/sd/
SS=$(sha256sum /usr/local/zci/s/sd/*)
f=$(ZLIB=/usr/local/zci/s/lib/probes-b9 ZUNIT=/usr/local/zci/s/sd run inst-same zrel install "$P")
has I10a "$f" '^CONFLICT .*zprobe-journal-b9@.service: equal to the release but not created by this release'
has I10b "$f" '^ZPROBE_B9_INSTALL=REFUSED conflicts=2'
eq I10c "$(test -e /usr/local/zci/s/lib/probes-b9 && echo created || echo absent)" absent lib_not_created
eq I10d "$(sha256sum /usr/local/zci/s/sd/*)" "$SS" same_files_untouched
f=$(ZFAULT=3 run inst-partial zrel install "$P"); has I5a "$f" '^ZPROBE_B9_INSTALL=PARTIAL '
f=$(run pre-partial zrel preflight "$P"); has I5b "$f" '^CHECK TARGETS_ABSENT FAIL present:'
f=$(run inst-finish zrel install "$P"); has I5c "$f" '^ZPROBE_B9_INSTALL=OK'
f=$(run verify zrel verify-installed "$P"); has I6 "$f" '^ZPROBE_B9_VERIFY_INSTALLED=OK '
for u in zprobe-journal-b9@check.service zprobe-run-b9@check.service; do
  systemctl show "$u" -p DropInPaths -p NeedDaemonReload -p ExecStartEx -p ExecStopPostEx -p IPAddressDeny -p PrivateIPC \
    -p TemporaryFileSystem -p BindReadOnlyPaths -p ReadOnlyPaths -p CapabilityBoundingSet -p RestrictNamespaces \
    -p InaccessiblePaths -p SystemCallFilter | cut -c1-400 | sed "s|^|SHOW $u |"
done
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
f=$(run verify-dropin zrel verify-installed "$P")
has V1a "$f" '^CHECK UNITS_LOADED FAIL .*zprobe-journal-b9 DropInPaths'
has V1b "$f" '^CHECK UNITS_LOADED FAIL .*zprobe-journal-b9 ExecStartEx'
has V1c "$f" '^CHECK UNITS_LOADED FAIL .*zprobe-run-b9 ExecStopPostEx'
has V1d "$f" '^ZPROBE_B9_VERIFY_INSTALLED=FAIL'
scen main
f=$(start c1); has 1 "$f" '^ZPROBE_START CONFIRMED series=c1 journalctl_rc=0 SERIES_END COMPLETE '; eq 1n "$(nseg)" 1 segments; segs
ctl mode-c2 crash; f=$(start c2); has 2 "$f" '^ZPROBE_START CONFIRMED series=c2 journalctl_rc=0 SERIES_END INTERRUPTED .*reason=runner_missing'; segs
ctl mode-c3 cleanupfail; f=$(start c3); has 3 "$f" '^ZPROBE_START CONFIRMED series=c3 journalctl_rc=0 SERIES_END INTERRUPTED .*cleanup:cleanup_bad'; segs
ctl fault-c4 startfail; f=$(start c4); has 4a "$f" '^ZPROBE_START UNKNOWN series=c4 .*ABSENT'; eq 4n "$(nseg)" 3 segments
eq 4b "$(grep -c '^Starting zprobe-journal-b9@c4.service' "$(jlog c4)")" 1 journal_unit_runs
ctl clear-c4 x; f=$(retry c4); has 4c "$f" '^ZPROBE_START CONFIRMED series=c4 '; eq 4d "$(nseg)" 4 segments; segs
ctl fault-c5 hold
f5=$(o start-c5); ( "$LIB/zprobe-start" c5 "$CH" ПБ-1 > "$f5" 2>&1; echo "rc=$?" >> "$f5" ) & B5=$!
waitfor "grep -q 'CI_HOLD series=c5' \"\$(jlog c5)\"" && ok 5a "journal held after write, before fsync" || bad 5a "no hold"
sleep 3
W5=$(grep -l '"series":"c5"' "$DATA"/journal/*.jsonl | head -1)
eq 5b "$(tail -c 1 "$W5" | od -An -c | tr -d ' ')" '\n' segment_readable_whole
kill -0 $B5 2> /dev/null && ! grep -q CONFIRMED "$f5" && ok 5c "zprobe-start gives no CONFIRMED while fsync is held" || bad 5c "$(cat "$f5")"
ctl release-c5 x; wait $B5; has 5d "$f5" '^ZPROBE_START CONFIRMED series=c5 '; segs
ctl fault-c6 fail; f=$(start c6); has 6a "$f" '^ZPROBE_START UNKNOWN series=c6 .*WHOLE_UNCONFIRMED'; N6=$(nseg)
f=$(start c6b); hasnt 6b "$f" '^ZPROBE_START CONFIRMED'; eq 6c "$(nseg)" "$N6" segments_while_fault
has 6d "$(jlog c6b)" 'ZPROBE_JOURNAL REFUSED FSYNC'
ctl clear-c6 x; f=$(retry c6b); has 6h "$f" '^ZPROBE_START CONFIRMED series=c6b '; eq 6i "$(nseg)" $((N6 + 1)) segments
f=$(retry c6); has 6e "$f" '^ZPROBE_START CONFIRMED series=c6 '; eq 6f "$(nseg)" $((N6 + 1)) no_new_write
has 6g "$(jlog c6)" 'CONFIRMED series=c6 .* write=already'; segs
N7=$(nseg); f=$(retry c1); has 7a "$f" '^ZPROBE_START CONFIRMED series=c1 '; eq 7b "$(nseg)" "$N7" segments
ctl fault-c8 hold
f8=$(o start-c8); ( "$LIB/zprobe-start" c8 "$CH" ПБ-1 > "$f8" 2>&1; echo "rc=$?" >> "$f8" ) & B8=$!
waitfor "grep -q 'CI_HOLD series=c8' \"\$(jlog c8)\"" || bad 8x "no hold"
f=$(retry c8); has 8a "$f" 'ZPROBE_START REFUSED: units of c8 are active or queued'
ctl release-c8 x; wait $B8; has 8b "$f8" '^ZPROBE_START CONFIRMED series=c8 '
eq 8c "$(grep -c '^Starting zprobe-journal-b9@c8.service' "$(jlog c8)")" 1 journal_unit_runs
ctl mode-c9a slow
f9=$(o start-c9a); ( "$LIB/zprobe-start" c9a "$CH" ПБ-1 > "$f9" 2>&1; echo "rc=$?" >> "$f9" ) & B9=$!
waitfor "test -e $DATA/started/c9a" || bad 9x "c9a not reserved"
f=$(start c9b); has 9a "$f" 'ZPROBE_START REFUSED: reserve: .*BUSY'
eq 9b "$(test -e "$DATA/started/c9b" && echo yes || echo no)" no started_c9b
eq 9b2 "$(test -e /run/zprobe/c9b && echo yes || echo no)" no run_folder_c9b
wait $B9; has 9c "$f9" '^ZPROBE_START CONFIRMED series=c9a '
f=$(start c9c); has 9d "$f" '^ZPROBE_START CONFIRMED series=c9c '
f=$(start c9b); has 9e "$f" '^ZPROBE_START CONFIRMED series=c9b '   # M-355-REL32-01: то же имя после BUSY
manual_reserve c9d
f=$(start c9e); has 9a1 "$f" 'ZPROBE_START REFUSED: reserve: .*BUSY'
eq 9a2 "$(test -e "$DATA/started/c9e" && echo yes || echo no)" no started_c9e
eq 9a2r "$(test -e /run/zprobe/c9e && echo yes || echo no)" no run_folder_c9e
f=$(retry c9d); has 9a3 "$f" '^ZPROBE_START CONFIRMED series=c9d journalctl_rc=0 SERIES_END INTERRUPTED '
f=$(start c9f); has 9a4 "$f" '^ZPROBE_START CONFIRMED series=c9f '
f=$(start c10a); f=$(start c10b); f=$(retry c10a)
W10=$(grep -l '"series":"c10a"' "$DATA"/journal/*.jsonl | head -1)
L10=$(tail -n 1 "$W10" | tr -d '\n' | sha256sum | cut -c1-64)
has 10 "$f" "^ZPROBE_START CONFIRMED series=c10a .* seg=$(basename "$W10") seq=[0-9]+ last_sha256=$L10 "; segs
ctl fault-c18 exitfail
CUR18=$(journalctl --show-cursor -n 0 -q | sed -n 's/^-- cursor: //p')
f=$(start c18); has 18a "$f" '^ZPROBE_START UNKNOWN series=c18 .*WHOLE_UNCONFIRMED'
has 18b "$(jlog c18)" 'ZPROBE_JOURNAL CONFIRMED series=c18 .*write=written'
INV=$(journalctl -q --no-pager -o json _SYSTEMD_UNIT=zprobe-journal-b9@c18.service | \
  python3 -I -c 'import json, sys; print([json.loads(x).get("_SYSTEMD_INVOCATION_ID") for x in sys.stdin][-1])')
python3 -I -c "
import socket, sys
m = 'MESSAGE=CI forged success\nMESSAGE_ID=7ad2d189f7e94e70a38c781354912448\nUNIT=zprobe-journal-b9@c18.service\nINVOCATION_ID=' + sys.argv[1] + '\n'
socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM).sendto(m.encode(), '/run/systemd/journal/socket')
" "$INV"
waitfor "journalctl -q --no-pager -o json MESSAGE_ID=7ad2d189f7e94e70a38c781354912448 UNIT=zprobe-journal-b9@c18.service | grep -qF '$INV'" \
  && ok 18c "forged success record with the real invocation $INV is in the journal" || bad 18c "forged record not found"
f=$(run out18 /usr/bin/python3 -I "$LIB/zprobe_journal.py" outcome c18 "$CUR18")
has 18d "$f" '^ZPROBE_OUTCOME UNKNOWN series=c18 journalctl_rc=0 WHOLE_UNCONFIRMED'
f=$(run out19 /usr/bin/python3 -I "$LIB/zprobe_journal.py" outcome c1 not-a-cursor)
has 19 "$f" '^ZPROBE_OUTCOME UNKNOWN series=c1 journalctl_rc=[1-9][0-9]* JOURNALCTL_FAILED'

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
  if [ $v = foreign ]; then f=$(start m2); has 13-reserve "$f" 'REFUSED: reserve: .*(BUSY|ORPHAN)'; eq 13-reserve-m "$(test -e "$DATA/started/m2" && echo yes || echo no)" no started_m2
    eq 13-reserve-r "$(test -e /run/zprobe/m2 && echo yes || echo no)" no run_folder_m2; fi
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

scen restore20
# M-355-REL33-01: отметка начала есть, request.json нет — как zprobe-start, убитый сразу после допуска
zres() { runuser -u zprobe -- /usr/bin/python3 -I "$LIB/zprobe_journal.py" reserve "$1" "$CH"; }
restore() { run "restore-$1" "$LIB/zprobe-start" --restore-request "$1"; }
QB() { printf '{"challenge":"%s","probes":["ПБ-1"],"series":"%s"}\n' "$CH" "$1" | sha256sum | cut -c1-64; }
f=$(start r0); zres r20 > /dev/null; N20=$(nseg)
f=$(start r20b); has 20a "$f" 'ZPROBE_START REFUSED: reserve: .*BUSY'
eq 20b "$(test -e /run/zprobe/r20b && echo yes || echo no)" no run_folder_r20b
f=$(retry r20); has 20c "$f" 'ZPROBE_START REFUSED: no request.json for r20'
f=$(restore r20); has 20d "$f" "^ZPROBE_START REQUEST_RESTORED series=r20 challenge=$CH next: zprobe-start --journal-retry r20$"
eq 20e "$(sha256sum < /run/zprobe/r20/request.json | cut -c1-64)" "$(QB r20)" request_bytes
eq 20f "$(stat -c '%U:%G:%a' /run/zprobe/r20 /run/zprobe/r20/request.json | tr '\n' ' ')" "root:zprobe:750 root:zprobe:640 " owner_mode
f=$(restore r20); has 20g "$f" 'ZPROBE_START REFUSED: request.json of r20 is in place: use --journal-retry r20'
eq 20h "$(nseg)" "$N20" nothing_written_by_restore
f=$(retry r20); has 20i "$f" '^ZPROBE_START CONFIRMED series=r20 journalctl_rc=0 SERIES_END INTERRUPTED '
eq 20j "$(nseg)" $((N20 + 1)) one_segment
f=$(retry r20); has 20k "$f" '^ZPROBE_START CONFIRMED series=r20 '; eq 20l "$(nseg)" $((N20 + 1)) no_new_write
f=$(restore r20); has 20m "$f" 'ZPROBE_START REFUSED: restore-check: .*DENIED: series is already in the journal'
f=$(start r20b); has 20n "$f" '^ZPROBE_START CONFIRMED series=r20b '
# сбой ровно на chgrp: папка серии root:root 0750 пуста
zres r21 > /dev/null; install -d -m 0750 -o root -g root /run/zprobe/r21
f=$(restore r21); has 21a "$f" '^ZPROBE_START REQUEST_RESTORED series=r21 '
eq 21b "$(stat -c '%U:%G:%a' /run/zprobe/r21)" root:zprobe:750 folder_group_fixed
f=$(retry r21); has 21c "$f" '^ZPROBE_START CONFIRMED series=r21 .*SERIES_END INTERRUPTED '
# перезагрузка: /run пуст — нет ни /run/zprobe, ни папки серии (своё пространство монтирования, systemd виден)
zres r22 > /dev/null; install -d -m 0700 /root/zci-oldrun
f=$(run restore-reboot unshare -m --propagation private bash -c "set -e; mount --rbind /run /root/zci-oldrun
  mount -t tmpfs -o mode=0755 tmpfs /run; mkdir /run/systemd; mount --rbind /root/zci-oldrun/systemd /run/systemd
  test ! -e /run/zprobe && echo REBOOT_RUN_EMPTY
  $LIB/zprobe-start --restore-request r22
  stat -c 'STAT %U:%G:%a %n' /run/zprobe /run/zprobe/r22 /run/zprobe/r22/request.json
  echo REQ_SHA \$(sha256sum < /run/zprobe/r22/request.json | cut -c1-64)")
has 22a "$f" '^REBOOT_RUN_EMPTY'; has 22b "$f" '^ZPROBE_START REQUEST_RESTORED series=r22 '
has 22c "$f" '^STAT root:zprobe:750 /run/zprobe$'; has 22d "$f" '^STAT root:zprobe:640 /run/zprobe/r22/request.json$'
has 22e "$f" "^REQ_SHA $(QB r22)$"
f=$(restore r22); has 22f "$f" '^ZPROBE_START REQUEST_RESTORED series=r22 '
f=$(retry r22); has 22g "$f" '^ZPROBE_START CONFIRMED series=r22 .*SERIES_END INTERRUPTED '
# отрицательные: чужой вызов в request, испорченная отметка, второй orphan — отказ и ничего не создано
zres r23 > /dev/null; install -d -m 0750 -o root -g zprobe /run/zprobe/r23
(umask 0137; printf '{"challenge":"%s","probes":["ПБ-1"],"series":"r23"}\n' ffffffffffffffffffffffffffffffff > /run/zprobe/r23/request.json)
S23=$(sha256sum < /run/zprobe/r23/request.json)
f=$(restore r23); has 23a "$f" 'ZPROBE_START REFUSED: request.json of r23 exists and differs'
eq 23b "$(sha256sum < /run/zprobe/r23/request.json)" "$S23" request_untouched
scen restore24
f=$(start q0); mk rawmark q24 'ZPROBE_STARTED series=q24 challenge=zz'
f=$(restore q24); has 24a "$f" 'ZPROBE_START REFUSED: restore-check: .*ORPHAN'
eq 24b "$(test -e /run/zprobe/q24 && echo yes || echo no)" no run_folder_q24
scen restore25
zres q25a > /dev/null; mk mark q25b "$CH"
f=$(restore q25a); has 25a "$f" 'ZPROBE_START REFUSED: restore-check: .*ORPHAN'
eq 25b "$(test -e /run/zprobe/q25a && echo yes || echo no)" no run_folder_q25a

# REL34 M-01, M-02: отказ восстановления не меняет ничего — ни группы, ни прав, ни байтов, ни ссылок
at() { stat -c '%U:%G:%a:%i:%h:%s %n' "$@" | tr '\n' ' '; }
scen restore26
zres p26 > /dev/null; install -d -m 0750 -o root -g root /run/zprobe/p26
(umask 0137; printf '{"challenge":"%s","probes":["ПБ-1"],"series":"p26"}\n' ffffffffffffffffffffffffffffffff > /run/zprobe/p26/request.json)
A0="$(at /run/zprobe/p26 /run/zprobe/p26/request.json) $(sha256sum < /run/zprobe/p26/request.json | cut -c1-64)"
f=$(restore p26); has 26a "$f" 'ZPROBE_START REFUSED: request.json of p26 exists and differs'
eq 26b "$(at /run/zprobe/p26 /run/zprobe/p26/request.json) $(sha256sum < /run/zprobe/p26/request.json | cut -c1-64)" "$A0" unchanged
scen restore27
zres p27 > /dev/null; install -d -m 0750 -o root -g root /run/zprobe/p27; : > /run/zprobe/p27/x
A0=$(at /run/zprobe/p27 /run/zprobe/p27/x)
f=$(restore p27); has 27a "$f" 'ZPROBE_START REFUSED: /run/zprobe/p27 holds other files'
eq 27b "$(at /run/zprobe/p27 /run/zprobe/p27/x)" "$A0" unchanged
eq 27c "$(test -e /run/zprobe/p27/request.json && echo yes || echo no)" no no_request
scen restore28
zres p28 > /dev/null; install -d -m 0750 -o root -g root /run/zprobe/p28
(umask 0137; printf '{"challenge":"%s","probes":["ПБ-1"],"series":"p28"}\n' "$CH" > /run/zprobe/p28/request.json)
ln /run/zprobe/p28/request.json /run/zci-hl28
A0=$(at /run/zprobe/p28 /run/zprobe/p28/request.json /run/zci-hl28)
f=$(restore p28); has 28a "$f" 'ZPROBE_START REFUSED: request.json of p28 has unexpected owner, mode or links'
eq 28b "$(at /run/zprobe/p28 /run/zprobe/p28/request.json /run/zci-hl28)" "$A0" unchanged
scen restore29
zres p29 > /dev/null; install -d -m 0750 -o root -g zprobe /run/zprobe/p29; : > /run/zprobe/p29/$'\n'
A0=$(at /run/zprobe/p29)
f=$(restore p29); has 29a "$f" 'ZPROBE_START REFUSED: /run/zprobe/p29 holds other files'
eq 29b "$(at /run/zprobe/p29)" "$A0" unchanged
eq 29c "$(test -e /run/zprobe/p29/request.json && echo yes || echo no)" no no_request
scen restore30
zres p30 > /dev/null; install -d -m 0750 -o root -g zprobe /run/zprobe/p30
(umask 0137; printf '{"challenge":"%s","probes":["ПБ-1"],"series":"p30"}\n' "$CH" > /run/zprobe/p30/request.json$'\n')
A0=$(at /run/zprobe/p30)
f=$(restore p30); has 30a "$f" 'ZPROBE_START REFUSED: /run/zprobe/p30 holds other files'
eq 30b "$(at /run/zprobe/p30)" "$A0" unchanged
eq 30c "$(test -e /run/zprobe/p30/request.json && echo yes || echo no)" no no_request
scen restore31
chgrp root /run/zprobe; zres p31 > /dev/null; install -d -m 0750 -o root -g root /run/zprobe/p31; : > /run/zprobe/p31/x
A0="$(stat -c '%U:%G:%a' /run/zprobe) $(at /run/zprobe/p31)"
f=$(restore p31); has 31a "$f" 'ZPROBE_START REFUSED: /run/zprobe/p31 holds other files'
eq 31b "$(stat -c '%U:%G:%a' /run/zprobe) $(at /run/zprobe/p31)" "$A0" unchanged
scen restore32
zres p32 > /dev/null
f=$(restore p32); has 32a "$f" '^ZPROBE_START REQUEST_RESTORED series=p32 '
eq 32b "$(stat -c '%U:%G:%a' /run/zprobe /run/zprobe/p32 /run/zprobe/p32/request.json | tr '\n' ' ')" "root:zprobe:750 root:zprobe:750 root:zprobe:640 " owner_mode
eq 32c "$(sha256sum < /run/zprobe/p32/request.json | cut -c1-64)" "$(QB p32)" request_bytes
f=$(retry p32); has 32d "$f" '^ZPROBE_START CONFIRMED series=p32 .*SERIES_END INTERRUPTED '

printf '[Service]\nIPAddressDeny=\nPrivateIPC=no\n' > /etc/systemd/system/zprobe-journal-b9@.service.d/weak.conf
systemctl daemon-reload
f=$(run verify-weak zrel verify-installed "$P")
has V2a "$f" '^UNITS_LOADED_DETAIL zprobe-journal-b9@check.service IPAddressDeny=.{2}$'
has V2b "$f" '^UNITS_LOADED_DETAIL zprobe-journal-b9@check.service PrivateIPC=.no'
grep -E '^(CHECK UNITS_LOADED|UNITS_LOADED_DETAIL|ZPROBE_B9_VERIFY)' "$f" | cut -c1-1500 | sed 's/^/V2 /'
printf '[Service]\nSystemCallFilter=mount\nRestrictNamespaces=no\nInaccessiblePaths=\n' > /etc/systemd/system/zprobe-journal-b9@.service.d/weak3.conf
systemctl daemon-reload
f=$(run verify-weak3 zrel verify-installed "$P")
has V3a "$f" '^UNITS_LOADED_DETAIL zprobe-journal-b9@check.service SystemCallFilter: deny_list=False count=[0-9]+ missing=- forbidden=mount$'
has V3b "$f" '^UNITS_LOADED_DETAIL zprobe-journal-b9@check.service RestrictNamespaces='
has V3c "$f" '^UNITS_LOADED_DETAIL zprobe-journal-b9@check.service InaccessiblePaths='
has V3d "$f" '^ZPROBE_B9_VERIFY_INSTALLED=FAIL'
grep -E '^(CHECK UNITS_LOADED|UNITS_LOADED_DETAIL)' "$f" | cut -c1-600 | sed 's/^/V3 /'

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
