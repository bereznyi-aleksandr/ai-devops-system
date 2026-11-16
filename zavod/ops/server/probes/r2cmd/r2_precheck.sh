# ДОКУМЕНТ: r2_precheck.sh (тело команды оператора R2: проверка только чтением, затем печать остатка pb1trial2)
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 21:08 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
# v0.2 (REL91B M-01, L-02): сверяется ВСЯ папка программ B10 — ровно 16 файлов выпуска (имя, обычный файл не ссылка,
#   root:root, режим, SHA-256 = цели установщика B10 из пакета 64a04f634/cad786a71), а не только 2 файла; путь
#   preserve и путь папки программ — каждый шаг от / как S.open_root; запуск — bash с env -i, PATH=/usr/bin:/bin,
#   утилиты по абсолютному пути. Любое расхождение → R2=REFUSED_INPUT precheck:…, код 2, zprobe-start не запускается.
# ЗАПУСК: только через транспорт r2cmd/CMD_R2_PARTS.txt (сумма тела сверяется до запуска).
set -u
L=/usr/local/lib/zavod/probes-b10
ref() { echo "R2=REFUSED_INPUT precheck:$1"; exit 2; }
for p in / /var /var/lib /var/lib/zavod /var/lib/zavod/preserve /var/lib/zavod/preserve/pb1trial2 \
         /usr /usr/bin /usr/local /usr/local/lib /usr/local/lib/zavod "$L"; do
  { [ -L "$p" ] || [ ! -d "$p" ]; } && ref "not_dir:$p"
  s=$(/usr/bin/stat -c '%u:%g:%a' -- "$p") || ref "stat:$p"
  case "$s" in 0:0:*) ;; *) ref "owner:$p:$s";; esac
  [ $((8#${s##*:} & 8#022)) = 0 ] || ref "mode:$p:$s"
done
EXP='644 b659d51633014adbd53c2ce226a3214578b61e33d7283a304b987e501960dc89 pb1_session.py
644 366437b1fe06f57d1a2bf9d754aad8de49b67034f2b085b4bd6c7f422f0979df zprobe_rules.py
644 3998d5df05b4ea3000a4439e68e79cf8a89e4ef09bdfcdf00e0c56df2fc1b8ba zprobe_runner.py
644 6ed6908f786a3da8307e75f4a4f287604ad38175a684654e7f1bad0cf08880f0 zprobe_journal.py
755 e3e6e1edd2fc8aa3f2a8727acd2053dfaa0a26756aa360dedef0111245845fe0 zprobe-start
644 88ee7bb008600bfecee968084e2b925e2537dd02ea2282830a3b1824dd94a54b zprobe_dropin.py
644 aa2141c42d0c66334b57665fc627300c21d657f90bee4e29b3e727e9bcdd6973 zprobe_checks.py
644 3523e1e0ff38094db22b1c3e9f9a869eae26f05a9d4b752669c24a04829dbf0d zprobe_seal.py
644 b14043ccadca4386faaab26397ab909e913aa6091ebf8a96c2ae18bc764009aa zprobe_unstarted.py
644 b9554e644c7ff96399482cef97e1f5ce4bec4e4595e51a85e15a69e77bf36bb0 zprobe_export_rules.py
644 2b2a16f65c9336487f397ee5db5cc7cb3491080b2b8bdb1041044e49973fe762 zprobe_export.py
644 66ffe1ea33cd781b79226b622b2ddc17fbeac50dd3258ba8f5c82cf2560afaa7 zprobe_r2.py
644 13300ab92897d55b85b68acd9fdbc760bed8451adbc61bb677bca00a5639aebf zevidence_send.py
644 d100a7ee65a75ad10b9263c5b823ceae09d73c722bd7ff2f3e7448569bcabe45 RELEASE
644 91ed266ae21a3719463a4b49d20c5d9f5ed797cd6dbbdaf9dbbaa60d4fbaa712 zprobe_pins_b9.txt
644 addd580d99788504ba396dd24ca5e602c171a90d3852f79975b0c4a72f238934 INSTALLED.sha256'
# Ровно эти имена в папке (лишний файл или __pycache__ — отказ: python3 читает .pyc и при -B)
got=$(cd "$L" && /usr/bin/ls -A | LC_ALL=C /usr/bin/sort) || ref "lib_list"
want=$(printf '%s\n' "$EXP" | /usr/bin/cut -d' ' -f3 | LC_ALL=C /usr/bin/sort)
[ "$got" = "$want" ] || ref "lib_set"
n=0
while read -r m h f; do
  { [ -L "$L/$f" ] || [ ! -f "$L/$f" ]; } && ref "not_file:$f"
  s=$(/usr/bin/stat -c '%u:%g:%a' -- "$L/$f") || ref "stat:$f"
  [ "$s" = "0:0:$m" ] || ref "file_attr:$f:$s"
  [ "$(/usr/bin/sha256sum < "$L/$f" | /usr/bin/cut -c1-64)" = "$h" ] || ref "sha:$f"
  n=$((n + 1))
done <<< "$EXP"
[ "$n" = 16 ] || ref "count:$n"
echo "R2_PRECHECK=OK files=16 lib=$L"
exec "$L/zprobe-start" --seal-residue pb1trial2
