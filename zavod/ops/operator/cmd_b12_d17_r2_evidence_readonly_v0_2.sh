# ДОКУМЕНТ: zavod/ops/operator/cmd_b12_d17_r2_evidence_readonly_v0_2.sh — команда оператора D17 v0.2: ТОЛЬКО ЧТЕНИЕ
#   доказательств второго R2 B12 (шаг 3.5.5 ПБ-1; REL119 M-355-REL119-01; REL120 REVISE M-01, M-02, L-01)
# ВЕРСИЯ: v0.2  СТАТУС: DRAFT (не выдавать оператору до независимого аудита)
# ДАТА СОЗДАНИЯ: 2026-11-18 09:46 +02:00  ИСПОЛНИТЕЛЬ: Claude (терминал zavod, пускатель)
# ЗАМЕНЯЕТ: cmd_b12_d17_r2_evidence_readonly_v0_1.SUPERSEDED.sh.txt (REL120 REVISE 0/2/1)
# ПРОГРАММА: zavod/ops/operator/d17_r2_evidence_v0_2.py в коммите 08cf3f13b44a5475fda48fcb5ca8b3a80a1d2cc5: 19047 Б, SHA-256 103c26e5a5d2cfad8aab9059b129b958b4e3dae28c92a5c49a5e412113a2d43f.
#   Строка скачивает её В ПАМЯТЬ (curl только https, TLS 1.2+, предел размера), печатает D17_PROG size=.. sha256=..,
#   при равенстве N и S — D17_PROG_OK и выполняет байты в /usr/bin/python3 -I -B; иначе — строка REFUSED, код 3, ничего
#   не выполнено. На диск ничего не пишется. Что проверяет и печатает программа — её паспорт.
# ВЫВОД: разделы r2_out, obs, proof, src, db, r2_text; по каждому SEC <раздел> PASS|FAIL; итог D17_OK или
#   D17_FAIL <список>; затем RC d17 = <код> и D17_DONE (метка конца, НЕ успеха).
# НЕ ДЕЛАЕТ: ничего не создаёт, не пишет, не удаляет; R2, печать, установку, службы не запускает; номер аренды не печатает.
# Оператор вставляет ПОСЛЕДНЮЮ строку файла целиком в сессию root@zavod-1. Испытание: CI zavod-probes-3-5-5 v0.42,
#   задание b12-d17-readonly.
/usr/bin/env -i /bin/bash --norc --noprofile -c 'set -u; umask 077; PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH; cd /; [ "$(id -u)" = 0 ] || { echo "REFUSED: run as root; nothing done"; exit 1; }; U=https://raw.githubusercontent.com/bereznyi-aleksandr/ai-devops-system/08cf3f13b44a5475fda48fcb5ca8b3a80a1d2cc5/zavod/ops/operator/d17_r2_evidence_v0_2.py; N=19047; S=103c26e5a5d2cfad8aab9059b129b958b4e3dae28c92a5c49a5e412113a2d43f; /usr/bin/python3 -I -B -c "import hashlib,subprocess,sys; p=subprocess.run([\"curl\",\"-q\",\"-fsSL\",\"--proto\",\"=https\",\"--proto-redir\",\"=https\",\"--tlsv1.2\",\"--connect-timeout\",\"30\",\"--max-time\",\"120\",\"--max-filesize\",sys.argv[2],sys.argv[1]],stdout=subprocess.PIPE).stdout; h=hashlib.sha256(p).hexdigest(); print(\"D17_PROG size=%d sha256=%s\" % (len(p),h)); ok=len(p)==int(sys.argv[2]) and h==sys.argv[3]; print(\"D17_PROG_OK\" if ok else \"REFUSED: program size or sum differs; nothing run\"); sys.stdout.flush(); ok and exec(compile(p,\"d17\",\"exec\")); sys.exit(0 if ok else 3)" "$U" "$N" "$S"; echo "RC d17 = $?"; echo "D17_DONE"'
