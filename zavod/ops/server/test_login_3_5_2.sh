#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/test_login_3_5_2.sh — испытания login_3_5_2.sh (только CI, под root, подставные программы)
# ВЕРСИЯ: v0.7  СТАТУС: DRAFT  ДАТА ОБНОВЛЕНИЯ: 2026-11-09 06:17 +02:00 (v0.7: папка ключей root:root 755, как у
#   install_cell.sh: 13 и 28 — папка 775 и 700 отказ; 40 — рядом папка службы (0700, чужой владелец): не тронута,
#   чужая учётная запись не читает ключ и codex-home;
#   v0.6: аудит R4 — 39 файл PAM не читается;
#   v0.5: аудит R3 — 34 многострочный статус Codex, 38 сбой ps;
#   v0.4: аудит R2 — 33 «O K», 34 статус Codex не ровно
#   «Logged in using ChatGPT», 35 сбой Codex после переноса, 36 запись нажатий и сеанса, 37 оператор не подтвердил имя;
#   v0.3: под программу v0.3 — подставные
#   claude и codex лежат в папках, которые проходят настоящую опись tools_tar_3_5_1b.py (сама она — по закреплённой
#   сумме); испытывается копия программы с суммами описи этих папок; новые 22–32: сверка описи, сверка tools_tar,
#   лишний файл, путь с записью для группы, неудачный вход Codex, Codex без auth.json, check при открытой папке
#   ключей, неверный адрес аккаунта, чистое окружение и запрет дампов, «OK» с ошибкой и «OK but failed»; v0.2: 17–21 — «NOT OK», «Not logged in», bash -x)
# ДАТА СОЗДАНИЯ: 2026-11-08 20:36 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сменщик 03, сессия ae87bcd9)
# НАЗНАЧЕНИЕ: на чистой машине CI ставит подставные claude и codex по путям шага 3.5.1б и проверяет: отказы без SSH,
#   без шага 3.5.1б, с чужим именем; неверный ключ не сохраняется; верный — новый файл root 0400 в папке root 0755;
#   значение ключа не попадает ни в вывод программы, ни в отчёт; повтор — отказ, файл тот же; проверка ключа —
#   WORKS / FAILED; вход Codex — в новой папке, auth.json root 600; ничего не удалено.
# ВЫЗОВ: sudo bash test_login_3_5_2.sh PATH_TO_login_3_5_2.sh. Не запускать на сервере.
set -euo pipefail
export LC_ALL=C
L0=$(readlink -f "${1:?usage: test_login_3_5_2.sh login_3_5_2.sh}")
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
[ -n "${GITHUB_ACTIONS:-}" ] || { echo "CI only"; exit 1; }
n=0; fail() { echo "FAIL $n: $*"; exit 1; }
ok() { echo "PASS $n: $*"; }
W=$(mktemp -d)
GOOD="sk-ant-oat01-$(python3 -I -c 'import secrets, string; a = string.ascii_letters + string.digits + "_-"; print("".join(secrets.choice(a) for _ in range(95)))')"
BAD="sk-ant-oat01-$(python3 -I -c 'import secrets, string; a = string.ascii_letters + string.digits + "_-"; print("".join(secrets.choice(a) for _ in range(95)))')"
[ ${#GOOD} = 108 ] && [ ${#BAD} = 108 ] || fail "token generator"
printf '%s' "$GOOD" > /root/ci-good-token; chmod 600 /root/ci-good-token
ACC=ci-work@example.com
# Настоящая tools_tar_3_5_1b.py — по пути пакета шага 3.5.1б (программа сверяет её по закреплённой сумме).
TP=/root/zavod-pkg-e7cdcb866499/zavod/ops/server/tools_tar_3_5_1b.py
install -d -m 0755 -o root -g root /root/zavod-pkg-e7cdcb866499 /root/zavod-pkg-e7cdcb866499/zavod \
  /root/zavod-pkg-e7cdcb866499/zavod/ops /root/zavod-pkg-e7cdcb866499/zavod/ops/server
install -m 0644 -o root -g root "$(dirname "$L0")/tools_tar_3_5_1b.py" "$TP"
CD=/opt/zavod/tools/claude-code-2.1.318-linux-arm64; CL=$CD/claude
XD=/opt/zavod/tools/codex-0.166.0-linux-arm64; CX=$XD/vendor/aarch64-unknown-linux-musl/bin/codex
stat -c 'CI /opt was %U:%G %a' /opt; chmod go-w /opt   # на машине CI /opt открыт для записи; на сервере — 755 (иначе программа откажет)
install -d -m 0755 -o root -g root /opt/zavod /opt/zavod/tools "$CD" "$XD" "$XD/vendor" \
  "$XD/vendor/aarch64-unknown-linux-musl" "$(dirname "$CX")"
cat > "$CL" <<'EOF'
#!/bin/bash
case "${1:-}" in
  setup-token) echo "Open https://claude.ai/oauth/authorize?code=TEST and sign in"; echo "Token shown on this screen"; exit 0 ;;
  -p) env | cut -d= -f1 | sort > /root/ci-claude-env; ulimit -c > /root/ci-claude-ulimit
      if [ -e /root/ci-claude-out ]; then cat /root/ci-claude-out; exit "$(cat /root/ci-claude-rc)"; fi
      if [ "${CLAUDE_CODE_OAUTH_TOKEN:-}" = "$(cat /root/ci-good-token)" ]; then echo OK; exit 0; fi
      echo "Invalid token $CLAUDE_CODE_OAUTH_TOKEN"; echo "Invalid token $CLAUDE_CODE_OAUTH_TOKEN" >&2; exit 1 ;;
esac
exit 2
EOF
cat > "$CX" <<'EOF'
#!/bin/bash
case "${1:-} ${2:-}" in
  "login --device-auth") echo "Open https://auth.openai.com/codex/device and enter ABCD-1234"
     if [ -e /root/ci-codex-login-rc ]; then exit "$(cat /root/ci-codex-login-rc)"; fi
     if [ -e /root/ci-codex-noauth ]; then exit 0; fi
     printf '{"tokens":"CODEXSECRET"}' > "$CODEX_HOME/auth.json"; chmod 644 "$CODEX_HOME/auth.json"; exit 0 ;;
  "login status") if [ -e /root/ci-codex-fail-final ] && [ "${CODEX_HOME##*/}" = codex-home ]; then echo "Not logged in" >&2; exit 1; fi
     if [ -e /root/ci-codex-status ]; then cat /root/ci-codex-status >&2; exit 0; fi
     if [ -f "$CODEX_HOME/auth.json" ]; then echo "Logged in using ChatGPT" >&2; exit 0; fi
     echo "Not logged in" >&2; exit 1 ;;
esac
exit 2
EOF
chmod 0755 "$CL" "$CX"
inv() { python3 -I "$TP" inventory "$1" | sha256sum | cut -c1-64; }
CI_INV=$(inv "$CD"); XI_INV=$(inv "$XD")
# Испытуемая копия: отличается от программы только двумя суммами описи (суммы подставных папок).
L=$W/login_3_5_2.sh
sed -e "s/^CLAUDE_INV=.*/CLAUDE_INV=$CI_INV/" -e "s/^CODEX_INV=.*/CODEX_INV=$XI_INV/" "$L0" > "$L"
[ "$(diff "$L0" "$L" | grep -c '^>')" = 2 ] && grep -qx "CLAUDE_INV=$CI_INV" "$L" && grep -qx "CODEX_INV=$XI_INV" "$L" \
  || fail "test copy must differ only in the two inventory sums"
install -d -m 0755 -o root -g root /etc/zavod
run() { local o=$1; shift; rc=0; "$@" > "$W/$o.out" 2>&1 || rc=$?; }
leak() { ! grep -qF -e "$GOOD" -e "$BAD" -e CODEXSECRET "$@" /root/zavod-login-3.5.2-*.txt 2>/dev/null; }
in3() { printf '%s\n%s\n%s\n' "$2" "$3" "$1"; }   # ввод оператора: адрес аккаунта, ключ, подтверждение имени ($1)

n=1; run nossh env -u SSH_CONNECTION bash "$L" check claude-work
[ $rc = 1 ] && grep -q "inside an SSH root session" "$W/nossh.out" || fail "no SSH must refuse"; ok "refused outside SSH"
export SSH_CONNECTION="10.0.0.1 5000 10.0.0.2 22"
n=2; run no351b bash "$L" check claude-work
[ $rc = 1 ] && grep -q "step 3.5.1b is not done" "$W/no351b.out" || fail "no 3.5.1b must refuse"; ok "refused without 3.5.1b"
R=/root/zavod-install-3.5.1b-20261108T000000.0Z-1.txt; (umask 077; printf 'ZAVOD_3_5_1B_TIME=x\nZAVOD_3_5_1B=OK\n' > "$R")
n=3; run badname bash "$L" claude claude-other
[ $rc = 1 ] && grep -q "name must be" "$W/badname.out" || fail "bad name"; ok "refused unknown name"
n=22; run realinv bash "$L0" claude claude-work < <(in3 claude-work "$ACC" "$GOOD")
[ $rc = 1 ] && grep -q "$CD differs from step 3.5.1b (inventory $CI_INV)" "$W/realinv.out" && [ ! -e /etc/zavod/secrets ] \
  || { cat "$W/realinv.out"; fail "tool folder that differs from 3.5.1b must refuse"; }
run realinvx bash "$L0" codex
[ $rc = 1 ] && grep -q "$XD differs from step 3.5.1b" "$W/realinvx.out" || fail "codex folder must be checked"
ok "program folders that differ from the pinned inventory: refused before any change"
n=23; cp -p "$TP" "$W/tt.bak"; echo '#' >> "$TP"; run tarchg bash "$L" check claude-work; cat "$W/tt.bak" > "$TP"
[ $rc = 1 ] && grep -q "tools_tar_3_5_1b.py differs from step 3.5.1b" "$W/tarchg.out" || fail "changed tools_tar"; ok "changed tools_tar refused"
n=24; install -m 0644 /dev/null "$CD/extra"; run extra bash "$L" check claude-work; mv "$CD/extra" "$W/extra.moved"
[ $rc = 1 ] && grep -q "$CD differs from step 3.5.1b" "$W/extra.out" || fail "extra file in tool folder"; ok "extra file in program folder refused"
n=25; chmod g+w /opt/zavod/tools; run gw bash "$L" check claude-work; chmod g-w /opt/zavod/tools
[ $rc = 1 ] && grep -q "/opt/zavod/tools is writable by group or others" "$W/gw.out" || fail "group-writable path"; ok "path writable by group refused"
n=4; run badkey bash "$L" claude claude-work < <(in3 claude-work "$ACC" "hello-not-a-key")
[ $rc = 1 ] && grep -q "not a Claude key" "$W/badkey.out" && [ ! -e /etc/zavod/secrets/claude-work ] || fail "bad key saved?"
[ "$(stat -c '%U:%G %a' /etc/zavod/secrets)" = "root:root 755" ] || fail "secrets dir mode"; ok "wrong key not saved; folder root 755"
# как у install_cell.sh: в папке ключей — папки служб (0700, владелец — служба); 40 проверяет, что они не тронуты
install -d -m 0700 -o nobody -g nogroup /etc/zavod/secrets/zgithub; echo service-mark > /etc/zavod/secrets/zgithub/mark
n=29; run bademail bash "$L" claude claude-work < <(in3 claude-work "not an e-mail" "$GOOD")
[ $rc = 1 ] && grep -q "not an e-mail address" "$W/bademail.out" && [ ! -e /etc/zavod/secrets/claude-work ] && leak "$W/bademail.out" \
  || fail "bad e-mail"; ok "wrong account address: nothing saved"
n=5; run spacekey bash "$L" claude claude-work < <(in3 claude-work "$ACC" "sk-ant-oat01-aaaa bbbb$(printf 'c%.0s' $(seq 90))")
[ $rc = 1 ] && grep -q "unexpected sign" "$W/spacekey.out" && [ ! -e /etc/zavod/secrets/claude-work ] || fail "key with space"; ok "key with space not saved"
n=6; run shortkey bash "$L" claude claude-work < <(in3 claude-work "$ACC" "sk-ant-oat01-short")
[ $rc = 1 ] && grep -q "outside 80..300" "$W/shortkey.out" || fail "short key"; ok "short key not saved"
n=7; run good env ZAVOD_CI_MARK=1 bash "$L" claude claude-work < <(in3 claude-work "$ACC" "$GOOD")
[ $rc = 0 ] || { cat "$W/good.out"; fail "good key rc=$rc"; }
F=/etc/zavod/secrets/claude-work
[ "$(stat -c '%U:%G %a' "$F")" = "root:root 400" ] && [ "$(cat "$F")" = "$GOOD" ] || fail "key file"
grep -q "ZAVOD_3_5_2_SAVED=claude-work file=$F mode=root:root 400 len=108 account_declared=$ACC" "$W/good.out" || fail "saved line"
grep -q "ZAVOD_3_5_2_CHECK=claude-work WORKS" "$W/good.out" && grep -q "ZAVOD_3_5_2=OK step=claude name=claude-work" "$W/good.out" || fail "check"
leak "$W/good.out" || fail "key leaked to output or report"
ls /root/zavod-login-3.5.2-*.txt > /dev/null && [ "$(stat -c %a /root/zavod-login-3.5.2-*.txt | sort -u)" = 600 ] || fail "report mode"
ok "good key saved root 400 with declared account, check WORKS, value not in output or report"
n=30; if grep -qx -e ZAVOD_CI_MARK -e SSH_CONNECTION -e SUDO_USER /root/ci-claude-env || ! grep -qx CLAUDE_CODE_OAUTH_TOKEN /root/ci-claude-env \
  || [ "$(cat /root/ci-claude-ulimit)" != 0 ]; then cat /root/ci-claude-env; fail "claude must run with a clean environment and no core dumps"; fi
ok "claude runs with a clean environment (env -i) and core dumps off"
S1=$(sha256sum "$F")
n=8; run again bash "$L" claude claude-work < <(in3 claude-work "$ACC" "$BAD")
[ $rc = 1 ] && grep -q "already exists" "$W/again.out" && [ "$(sha256sum "$F")" = "$S1" ] || fail "repeat must refuse"; ok "repeat refused, file unchanged"
n=9; run wrongacct bash "$L" claude claude-personal < <(in3 claude-personal "$ACC" "$BAD")
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CHECK=claude-personal FAILED rc=1" "$W/wrongacct.out" || { cat "$W/wrongacct.out"; fail "failed check"; }
grep -q "ZAVOD_3_5_2_NOT_SAVED=claude-personal key_did_not_work kept_aside=/etc/zavod/secrets/.rejected-claude-personal-" "$W/wrongacct.out" \
  && [ ! -e /etc/zavod/secrets/claude-personal ] && [ "$(stat -c '%U:%G %a' /etc/zavod/secrets/.rejected-claude-personal-*)" = "root:root 400" ] \
  || fail "rejected key must stay aside, not under the name"
leak "$W/wrongacct.out" || fail "rejected key leaked (the program printed it, ours must not)"; ok "key that does not work: FAILED, not saved under the name, kept aside 400, value not shown"
n=10; run check bash "$L" check claude-work
[ $rc = 0 ] && grep -q "WORKS" "$W/check.out" && leak "$W/check.out" || fail "check"; ok "check WORKS"
n=28; for m in 0775 0757 0700; do
  chmod "$m" /etc/zavod/secrets; run checkopen bash "$L" check claude-work; chmod 0755 /etc/zavod/secrets
  [ $rc = 1 ] && grep -q "not a root:root 755 folder" "$W/checkopen.out" || fail "check with secrets folder $m"
done; ok "check refuses a secrets folder other than root:root 755 (775, 757, 700)"
n=11; run codex bash "$L" codex
[ $rc = 0 ] && grep -q "ZAVOD_3_5_2_CODEX=LOGGED_IN home=/etc/zavod/secrets/codex-home home_mode=root:root 700 auth_mode=root:root 600" "$W/codex.out" \
  || { cat "$W/codex.out"; fail "codex"; }
[ "$(stat -c '%U:%G %a' /etc/zavod/secrets/codex-home)" = "root:root 700" ] && leak "$W/codex.out" || fail "codex home"
[ "$(find /etc/zavod/secrets -maxdepth 1 -name '.new-codex-home-*' | wc -l)" = 0 ] || fail "temporary codex folder left"
ok "codex logged in via a new folder, auth.json 600"
n=12; run codex2 bash "$L" codex
[ $rc = 1 ] && grep -q "already exists (Codex was signed in before)" "$W/codex2.out" || fail "codex repeat"; ok "codex repeat refused"
n=13; chmod 0775 /etc/zavod/secrets; run opendir bash "$L" claude claude-personal < <(in3 claude-personal "$ACC" "$GOOD"); chmod 0755 /etc/zavod/secrets
[ $rc = 1 ] && grep -q "not a root:root 755 folder" "$W/opendir.out" && [ ! -e /etc/zavod/secrets/claude-personal ] || fail "open dir"
ok "secrets folder writable by group refused"
n=14; ln -s /root/ci-good-token /etc/zavod/secrets/claude-personal
run link bash "$L" claude claude-personal < <(in3 claude-personal "$ACC" "$GOOD")
[ $rc = 1 ] && grep -q "already exists" "$W/link.out" || fail "link must refuse"; ok "link in place of key refused"
n=15; [ "$(ls /root/zavod-login-claude-work-* -d | wc -l)" -ge 1 ] && [ "$(stat -c %a /root/zavod-login-claude-work-* | sort -u)" = 700 ] || fail "login HOME"; ok "login HOME folders kept, root 700"
n=16; mv /etc/zavod/secrets/claude-work /etc/zavod/secrets/claude-work.moved; chmod 0444 /etc/zavod/secrets/claude-work.moved
run modecheck bash "$L" check claude-work
[ $rc = 1 ] && grep -q "missing or not root:root 400" "$W/modecheck.out" || fail "missing key"; ok "check of missing key refused"
F=/etc/zavod/secrets/claude-work; (umask 077; printf '%s' "$GOOD" > "$F"); chmod 0400 "$F"
n=17; echo "NOT OK" > /root/ci-claude-out; echo 1 > /root/ci-claude-rc; run notok1 bash "$L" check claude-work
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CHECK=claude-work FAILED rc=1" "$W/notok1.out" || fail "NOT OK with error accepted"; ok "answer NOT OK with error code: FAILED"
n=18; echo 0 > /root/ci-claude-rc; run notok0 bash "$L" check claude-work
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CHECK=claude-work FAILED rc=0" "$W/notok0.out" || fail "NOT OK with code 0 accepted"; ok "answer NOT OK with code 0: FAILED"
n=19; printf ' OK.\n' > /root/ci-claude-out; run okdot bash "$L" check claude-work
[ $rc = 0 ] && grep -q "WORKS" "$W/okdot.out" || fail "OK. must work"; ok "answer «OK.» with code 0: WORKS"
n=32; echo OK > /root/ci-claude-out; echo 1 > /root/ci-claude-rc; run okrc1 bash "$L" check claude-work
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CHECK=claude-work FAILED rc=1" "$W/okrc1.out" || fail "OK with error code accepted"; ok "answer OK with error code: FAILED"
printf 'OK but failed\n' > /root/ci-claude-out; echo 0 > /root/ci-claude-rc; run okbut bash "$L" check claude-work
[ $rc = 1 ] && grep -q "FAILED rc=0" "$W/okbut.out" || fail "«OK but failed» accepted"; ok "answer «OK but failed» with code 0: FAILED"
n=33; printf 'O K\n' > /root/ci-claude-out; run osk bash "$L" check claude-work
[ $rc = 1 ] && grep -q "FAILED rc=0" "$W/osk.out" || fail "«O K» accepted"
printf 'O\nK\n' > /root/ci-claude-out; run onlk bash "$L" check claude-work
[ $rc = 1 ] && grep -q "FAILED rc=0" "$W/onlk.out" || fail "«O newline K» accepted"; ok "answers «O K» and «O / K» with code 0: FAILED"
rm /root/ci-claude-out /root/ci-claude-rc
n=20; rm /etc/zavod/secrets/claude-personal; run xtrace bash -x "$L" claude claude-personal < <(in3 claude-personal "$ACC" "$GOOD")
[ $rc = 0 ] && leak "$W/xtrace.out" || { cat "$W/xtrace.out"; fail "bash -x leaked the key"; }
rm /etc/zavod/secrets/claude-personal; run shellopts env SHELLOPTS=xtrace bash "$L" claude claude-personal < <(in3 claude-personal "$ACC" "$GOOD")
[ $rc = 0 ] && leak "$W/shellopts.out" || fail "SHELLOPTS=xtrace leaked the key"; ok "bash -x and SHELLOPTS=xtrace: key not in output"
n=37; mv /etc/zavod/secrets/claude-personal /etc/zavod/secrets/claude-personal.t20
run noconfirm bash "$L" claude claude-personal < <(in3 claude-work "$ACC" "$GOOD")
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_NOT_SAVED=claude-personal operator_did_not_confirm kept_aside=/etc/zavod/secrets/.rejected-claude-personal-" "$W/noconfirm.out" \
  && [ ! -e /etc/zavod/secrets/claude-personal ] && leak "$W/noconfirm.out" || { cat "$W/noconfirm.out"; fail "unconfirmed key saved"; }
grep -q "confirmed_by_operator=yes" "$W/good.out" || fail "confirmation not in the report"
ok "working key not confirmed by the operator: not saved under the name, kept aside"
mv /etc/zavod/secrets/codex-home /etc/zavod/secrets/codex-home.t11
n=36; printf 'session required pam_tty_audit.so enable=*\n' > /etc/pam.d/zz-ci-tty-audit; run pamrec bash "$L" codex; mv /etc/pam.d/zz-ci-tty-audit "$W/"
[ $rc = 1 ] && grep -q "keystroke recording (pam_tty_audit)" "$W/pamrec.out" && [ ! -e /etc/zavod/secrets/codex-home ] || { cat "$W/pamrec.out"; fail "pam_tty_audit not detected"; }
run inscript script -qec "bash $L codex" /dev/null
[ $rc = 1 ] && grep -q "this session runs inside script" "$W/inscript.out" && [ ! -e /etc/zavod/secrets/codex-home ] || { cat "$W/inscript.out"; fail "script recorder not detected"; }
ok "keystroke or screen recording found: refused before the login"
n=38; printf '#!/bin/sh\nexit 1\n' > "$W/fakeps"; chmod 0755 "$W/fakeps"; mount --bind "$W/fakeps" /usr/bin/ps
run psfail bash "$L" codex; umount /usr/bin/ps
[ $rc = 1 ] && grep -q "session check failed" "$W/psfail.out" && ! grep -q "RECORDER=none_found" "$W/psfail.out" && [ ! -e /etc/zavod/secrets/codex-home ] \
  || { cat "$W/psfail.out"; fail "ps failure must refuse"; }
ok "process check cannot read the parent chain (ps fails): refused, no «none_found»"
n=39; ln -s /nonexistent-ci-pam /etc/pam.d/zz-ci-broken; run pamerr bash "$L" codex; rm /etc/pam.d/zz-ci-broken
[ $rc = 1 ] && grep -q "cannot read all of /etc/pam.d (grep rc=2" "$W/pamerr.out" && ! grep -q "RECORDER=none_found" "$W/pamerr.out" && [ ! -e /etc/zavod/secrets/codex-home ] \
  || { cat "$W/pamerr.out"; fail "unreadable PAM file must refuse"; }
ok "a PAM file cannot be read (grep rc=2): refused, no «none_found»"
n=21; echo "Not logged in" > /root/ci-codex-status; run codexnot bash "$L" codex; rm /root/ci-codex-status
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN status_rc=0 kept_aside=/etc/zavod/secrets/.rejected-codex-home-" "$W/codexnot.out" \
  && [ ! -e /etc/zavod/secrets/codex-home ] || { cat "$W/codexnot.out"; fail "Not logged in accepted"; }
ok "codex status «Not logged in» with code 0: refused, folder kept aside"
n=26; echo 1 > /root/ci-codex-login-rc; run codexfail bash "$L" codex; rm /root/ci-codex-login-rc
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN login_rc=1 kept_aside=/etc/zavod/secrets/.rejected-codex-home-" "$W/codexfail.out" \
  && [ ! -e /etc/zavod/secrets/codex-home ] || { cat "$W/codexfail.out"; fail "failed codex login"; }
ok "failed codex login: no codex-home, folder kept aside"
n=27; touch /root/ci-codex-noauth; echo "Logged in using ChatGPT" > /root/ci-codex-status; run codexnoauth bash "$L" codex
rm /root/ci-codex-noauth /root/ci-codex-status
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN auth.json_missing_or_not_root" "$W/codexnoauth.out" && [ ! -e /etc/zavod/secrets/codex-home ] \
  || { cat "$W/codexnoauth.out"; fail "codex without auth.json"; }
ok "codex «Logged in» without auth.json: refused"
n=34; for s in "Logged in: false" "Logged in? No" "Logged in using an API key - sk-test" $'Not logged in
Logged in using ChatGPT' $'Logged in using ChatGPT
Not logged in'; do
  echo "$s" > /root/ci-codex-status; run codexpfx bash "$L" codex; rm /root/ci-codex-status
  [ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN status_rc=0 kept_aside=" "$W/codexpfx.out" && [ ! -e /etc/zavod/secrets/codex-home ] \
    || { cat "$W/codexpfx.out"; fail "codex status «$s» accepted"; }
done; ok "codex status other than exactly «Logged in using ChatGPT»: refused"
n=35; touch /root/ci-codex-fail-final; run codexlate bash "$L" codex; rm /root/ci-codex-fail-final
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN_AFTER_MOVE rc=1 kept_aside=/etc/zavod/secrets/.rejected-codex-home-" "$W/codexlate.out" \
  && [ ! -e /etc/zavod/secrets/codex-home ] || { cat "$W/codexlate.out"; fail "late codex failure must move the folder aside"; }
run codexagain bash "$L" codex
[ $rc = 0 ] && grep -q "ZAVOD_3_5_2_CODEX=LOGGED_IN home=/etc/zavod/secrets/codex-home" "$W/codexagain.out" || { cat "$W/codexagain.out"; fail "repeat after late failure"; }
ok "codex status fails after the move: folder kept aside, a repeat run works"
[ "$(stat -c '%U:%G %a' /etc/zavod/secrets/.rejected-codex-home-* | sort -u)" = "root:root 700" ] || fail "rejected codex folders must be root 700"
n=40; [ "$(stat -c '%U:%G %a' /etc/zavod/secrets/zgithub)" = "nobody:nogroup 700" ] \
  && [ "$(cat /etc/zavod/secrets/zgithub/mark)" = service-mark ] || fail "service folder changed"
! runuser -u nobody -- cat /etc/zavod/secrets/claude-work > /dev/null 2>&1 \
  && ! runuser -u nobody -- ls /etc/zavod/secrets/codex-home > /dev/null 2>&1 \
  && ! runuser -u nobody -- cat /etc/zavod/secrets/codex-home/auth.json > /dev/null 2>&1 || fail "another account reads a key"
[ "$(stat -c '%U:%G %a' /etc/zavod/secrets/claude-work)" = "root:root 400" ] || fail "key file mode"
ok "installer layout: service folder untouched; another account cannot read the key or codex-home"
n=31; [ "$(find /etc/zavod/secrets -maxdepth 1 -name '.new-*' | wc -l)" = 0 ] || fail "temporary files left"; ok "no temporary files left in the secrets folder"
echo "ALL_PASS login_3_5_2.sh 40"
