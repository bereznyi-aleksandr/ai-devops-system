#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/ops/server/test_login_3_5_2.sh — испытания login_3_5_2.sh (только CI, под root, подставные программы)
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  (v0.2: 17–21 — ответ «NOT OK», «Not logged in», трассировка bash -x)
# ДАТА СОЗДАНИЯ: 2026-11-08 20:36 +02:00
# ИСПОЛНИТЕЛЬ: Claude (сменщик 03, сессия ae87bcd9)
# НАЗНАЧЕНИЕ: на чистой машине CI ставит подставные claude и codex по путям шага 3.5.1б и проверяет: отказы без SSH,
#   без шага 3.5.1б, с чужим именем; неверный ключ не сохраняется; верный — новый файл root 0400 в папке root 0700;
#   значение ключа не попадает ни в вывод программы, ни в отчёт; повтор — отказ, файл тот же; проверка ключа —
#   WORKS / FAILED; вход Codex — auth.json закрыт; ничего не удалено.
# ВЫЗОВ: sudo bash test_login_3_5_2.sh PATH_TO_login_3_5_2.sh. Не запускать на сервере.
set -euo pipefail
export LC_ALL=C
L=$(readlink -f "${1:?usage: test_login_3_5_2.sh login_3_5_2.sh}")
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
[ -n "${GITHUB_ACTIONS:-}" ] || { echo "CI only"; exit 1; }
n=0; fail() { echo "FAIL $n: $*"; exit 1; }
ok() { echo "PASS $n: $*"; }
W=$(mktemp -d)
GOOD="sk-ant-oat01-$(python3 -I -c 'import secrets, string; a = string.ascii_letters + string.digits + "_-"; print("".join(secrets.choice(a) for _ in range(95)))')"
BAD="sk-ant-oat01-$(python3 -I -c 'import secrets, string; a = string.ascii_letters + string.digits + "_-"; print("".join(secrets.choice(a) for _ in range(95)))')"
[ ${#GOOD} = 108 ] && [ ${#BAD} = 108 ] || fail "token generator"
printf '%s' "$GOOD" > /root/ci-good-token; chmod 600 /root/ci-good-token
CL=/opt/zavod/tools/claude-code-2.1.318-linux-arm64/claude
CX=/opt/zavod/tools/codex-0.166.0-linux-arm64/vendor/aarch64-unknown-linux-musl/bin/codex
install -d -m 0755 "$(dirname "$CL")" "$(dirname "$CX")"
cat > "$CL" <<'EOF'
#!/bin/bash
case "${1:-}" in
  setup-token) echo "Open https://claude.ai/oauth/authorize?code=TEST and sign in"; echo "Token shown on this screen"; exit 0 ;;
  -p) if [ -e /root/ci-claude-out ]; then cat /root/ci-claude-out; exit "$(cat /root/ci-claude-rc)"; fi
      if [ "${CLAUDE_CODE_OAUTH_TOKEN:-}" = "$(cat /root/ci-good-token)" ]; then echo OK; exit 0; fi
      echo "Invalid token $CLAUDE_CODE_OAUTH_TOKEN"; echo "Invalid token $CLAUDE_CODE_OAUTH_TOKEN" >&2; exit 1 ;;
esac
exit 2
EOF
cat > "$CX" <<'EOF'
#!/bin/bash
case "${1:-} ${2:-}" in
  "login --device-auth") echo "Open https://auth.openai.com/codex/device and enter ABCD-1234"
     printf '{"tokens":"CODEXSECRET"}' > "$CODEX_HOME/auth.json"; chmod 644 "$CODEX_HOME/auth.json"; exit 0 ;;
  "login status") if [ -e /root/ci-codex-status ]; then cat /root/ci-codex-status >&2; exit 0; fi
     if [ -f "$CODEX_HOME/auth.json" ]; then echo "Logged in using ChatGPT" >&2; exit 0; fi
     echo "Not logged in" >&2; exit 1 ;;
esac
exit 2
EOF
chmod 0755 "$CL" "$CX"
install -d -m 0755 -o root -g root /etc/zavod
run() { local o=$1; shift; rc=0; "$@" > "$W/$o.out" 2>&1 || rc=$?; }
leak() { ! grep -qF -e "$GOOD" -e "$BAD" -e CODEXSECRET "$@" /root/zavod-login-3.5.2-*.txt 2>/dev/null; }

n=1; run nossh env -u SSH_CONNECTION bash "$L" check claude-work
[ $rc = 1 ] && grep -q "inside an SSH root session" "$W/nossh.out" || fail "no SSH must refuse"; ok "refused outside SSH"
export SSH_CONNECTION="10.0.0.1 5000 10.0.0.2 22"
n=2; run no351b bash "$L" check claude-work
[ $rc = 1 ] && grep -q "step 3.5.1b is not done" "$W/no351b.out" || fail "no 3.5.1b must refuse"; ok "refused without 3.5.1b"
R=/root/zavod-install-3.5.1b-20261108T000000.0Z-1.txt; (umask 077; printf 'ZAVOD_3_5_1B_TIME=x\nZAVOD_3_5_1B=OK\n' > "$R")
n=3; run badname bash "$L" claude claude-other
[ $rc = 1 ] && grep -q "name must be" "$W/badname.out" || fail "bad name"; ok "refused unknown name"
n=4; run badkey bash "$L" claude claude-work <<< "hello-not-a-key"
[ $rc = 1 ] && grep -q "not a Claude key" "$W/badkey.out" && [ ! -e /etc/zavod/secrets/claude-work ] || fail "bad key saved?"
[ "$(stat -c '%U:%G %a' /etc/zavod/secrets)" = "root:root 700" ] || fail "secrets dir mode"; ok "wrong key not saved; folder root 700"
n=5; run spacekey bash "$L" claude claude-work <<< "sk-ant-oat01-aaaa bbbb$(printf 'c%.0s' $(seq 90))"
[ $rc = 1 ] && grep -q "unexpected sign" "$W/spacekey.out" && [ ! -e /etc/zavod/secrets/claude-work ] || fail "key with space"; ok "key with space not saved"
n=6; run shortkey bash "$L" claude claude-work <<< "sk-ant-oat01-short"
[ $rc = 1 ] && grep -q "outside 80..300" "$W/shortkey.out" || fail "short key"; ok "short key not saved"
n=7; run good bash "$L" claude claude-work <<< "$GOOD"
[ $rc = 0 ] || { cat "$W/good.out"; fail "good key rc=$rc"; }
F=/etc/zavod/secrets/claude-work
[ "$(stat -c '%U:%G %a' "$F")" = "root:root 400" ] && [ "$(cat "$F")" = "$GOOD" ] || fail "key file"
grep -q "ZAVOD_3_5_2_SAVED=claude-work file=$F mode=root:root 400 len=108" "$W/good.out" || fail "saved line"
grep -q "ZAVOD_3_5_2_CHECK=claude-work WORKS" "$W/good.out" && grep -q "ZAVOD_3_5_2=OK step=claude name=claude-work" "$W/good.out" || fail "check"
leak "$W/good.out" || fail "key leaked to output or report"
ls /root/zavod-login-3.5.2-*.txt > /dev/null && [ "$(stat -c %a /root/zavod-login-3.5.2-*.txt | sort -u)" = 600 ] || fail "report mode"
ok "good key saved root 400, check WORKS, value not in output or report"
S1=$(sha256sum "$F")
n=8; run again bash "$L" claude claude-work <<< "$BAD"
[ $rc = 1 ] && grep -q "already exists" "$W/again.out" && [ "$(sha256sum "$F")" = "$S1" ] || fail "repeat must refuse"; ok "repeat refused, file unchanged"
n=9; run wrongacct bash "$L" claude claude-personal <<< "$BAD"
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CHECK=claude-personal FAILED rc=1" "$W/wrongacct.out" || { cat "$W/wrongacct.out"; fail "failed check"; }
grep -q "ZAVOD_3_5_2_NOT_SAVED=claude-personal key_did_not_work kept_aside=/etc/zavod/secrets/.rejected-claude-personal-" "$W/wrongacct.out"   && [ ! -e /etc/zavod/secrets/claude-personal ] && [ "$(stat -c '%U:%G %a' /etc/zavod/secrets/.rejected-claude-personal-*)" = "root:root 400" ] || fail "rejected key must stay aside, not under the name"
leak "$W/wrongacct.out" || fail "rejected key leaked (the program printed it, ours must not)"; ok "key that does not work: FAILED, not saved under the name, kept aside 400, value not shown"
n=10; run check bash "$L" check claude-work
[ $rc = 0 ] && grep -q "WORKS" "$W/check.out" && leak "$W/check.out" || fail "check"; ok "check WORKS"
n=11; run codex bash "$L" codex
[ $rc = 0 ] && grep -q "ZAVOD_3_5_2_CODEX=LOGGED_IN home=/etc/zavod/secrets/codex-home auth_mode=root:root 600" "$W/codex.out" || { cat "$W/codex.out"; fail "codex"; }
[ "$(stat -c '%U:%G %a' /etc/zavod/secrets/codex-home)" = "root:root 700" ] && leak "$W/codex.out" || fail "codex home"; ok "codex logged in, auth.json 600"
n=12; run codex2 bash "$L" codex
[ $rc = 1 ] && grep -q "already signed in" "$W/codex2.out" || fail "codex repeat"; ok "codex repeat refused"
n=13; chmod 0755 /etc/zavod/secrets; run opendir bash "$L" claude claude-personal <<< "$GOOD"; chmod 0700 /etc/zavod/secrets
[ $rc = 1 ] && grep -q "not a root:root 700 folder" "$W/opendir.out" || fail "open dir"; ok "open secrets folder refused"
n=14; ln -s /root/ci-good-token /etc/zavod/secrets/claude-personal
run link bash "$L" claude claude-personal <<< "$GOOD"
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
rm /root/ci-claude-out /root/ci-claude-rc
n=20; rm /etc/zavod/secrets/claude-personal; run xtrace bash -x "$L" claude claude-personal <<< "$GOOD"
[ $rc = 0 ] && leak "$W/xtrace.out" || { cat "$W/xtrace.out"; fail "bash -x leaked the key"; }
rm /etc/zavod/secrets/claude-personal; run shellopts env SHELLOPTS=xtrace bash "$L" claude claude-personal <<< "$GOOD"
[ $rc = 0 ] && leak "$W/shellopts.out" || fail "SHELLOPTS=xtrace leaked the key"; ok "bash -x and SHELLOPTS=xtrace: key not in output"
n=21; mv /etc/zavod/secrets/codex-home /etc/zavod/secrets/codex-home.t11; echo "Not logged in" > /root/ci-codex-status
run codexnot bash "$L" codex
[ $rc = 1 ] && grep -q "ZAVOD_3_5_2_CODEX=NOT_LOGGED_IN rc=0" "$W/codexnot.out" || { cat "$W/codexnot.out"; fail "Not logged in accepted"; }
ok "codex status «Not logged in»: refused"
echo "ALL_PASS login_3_5_2.sh 21"
