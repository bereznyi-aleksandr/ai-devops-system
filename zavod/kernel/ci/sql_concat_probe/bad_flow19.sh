#!/usr/bin/env bash
# ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow19.sh — проба 3.3.10.2 (аудит M3310-R16): обёртки, вложенность, программы вне списка, среда, запись в папки кода.
# ДАТА: 2026-11-02 15:54 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
env -S 'psql -f /tmp/query.sql'
sh -c 'sh -c '"'"'sh -c '"'"'"'"'"'"'"'"'sh -c '"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'sh -c '"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'psql -f /tmp/query.sql'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"''"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"'"''"'"'"'"'"'"'"'"''"'"''
sudo -s psql
sudo -E psql -X -c "SELECT 1"
runuser -u zdb -- psql -X -c "SELECT 1"
NODE_OPTIONS=--require=/tmp/extra.cjs python3 -I /usr/local/lib/zavod/zavod-gate
PATH=/tmp:/usr/bin
export PSQLRC=/tmp/psqlrc
git -c core.sshCommand=/tmp/run fetch
ed -s /tmp/file
cp /tmp/run /usr/local/lib/zavod/zavod-gate
printf '[Service]\nExecStart=/tmp/run\n' > /etc/systemd/system/zavod-gate.service.d/x.conf
awk 'BEGIN { system("psql -f /tmp/query.sql") }'
sed 's/x/psql -f \/tmp\/query.sql/e' /tmp/file
systemctl set-environment PSQLRC=/tmp/psqlrc
find /tmp -name x -exec git pull \;
tar -xf /tmp/a.tar -C /usr/local/lib/zavod
systemd-run -p ExecStartPre=/tmp/run true
set -a
flock /tmp/lock git pull
ip -b /tmp/commands
ip netns exec ns1 git pull
xargs psql < /tmp/list
find /tmp -delete
