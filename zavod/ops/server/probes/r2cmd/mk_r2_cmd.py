# ДОКУМЕНТ: mk_r2_cmd.py (сборщик команды оператора R2 частями для Termux)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 21:08 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
# НАЗНАЧЕНИЕ: r2_precheck.sh → gzip → base64, части по ≤ 1900 знаков (Termux обрывает длинную вставку). Части 1..n-1
#   только запоминают текст (G=…; печать R2_PARTi/n и длины). Последняя часть распаковывает, сверяет SHA-256 тела и
#   только при совпадении запускает его в bash с env -i и PATH=/usr/bin:/bin (утилиты — по абсолютному пути).
#   Последняя строка вывода — rc=<код>; код всей вставленной строки равен этому коду ((exit $R); REL91B L-01).
# ЗАПУСК: python mk_r2_cmd.py <r2_precheck.sh> <выход CMD_R2_PARTS.txt>
import base64, gzip, hashlib, sys

PART = 1900


def build(body: bytes) -> list:
    sha = hashlib.sha256(body).hexdigest()
    b64 = base64.b64encode(gzip.compress(body, mtime=0)).decode()
    chunks = [b64[i:i + PART] for i in range(0, len(b64), PART)]
    n = len(chunks)
    out = []
    for i, c in enumerate(chunks, 1):
        head = f"G='{c}'" if i == 1 else f"G=\"$G\"'{c}'"
        if i < n:
            out.append(f'{head}; echo R2_PART{i}/{n} ${{#G}}')
        else:
            out.append(
                f'{head}; S=$(printf %s "$G" | /usr/bin/base64 -d 2>/dev/null | /usr/bin/gunzip -c 2>/dev/null; printf x); S=${{S%x}}; '
                f'if [ "$(printf %s "$S" | /usr/bin/sha256sum | /usr/bin/cut -c1-64)" = {sha} ]; then /usr/bin/clear; '
                '/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C.UTF-8 /bin/bash --norc --noprofile -c "$S" 2>&1 '
                '| /usr/bin/tail -20; R=${PIPESTATUS[0]}; '
                "else echo 'R2=REFUSED_INPUT transport_sha'; R=2; fi; echo \"rc=$R\"; (exit $R)")
    return out


if __name__ == '__main__':
    body = open(sys.argv[1], 'rb').read()
    parts = build(body)
    with open(sys.argv[2], 'x', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(parts) + '\n')
    print(len(parts), [len(p) for p in parts], hashlib.sha256(body).hexdigest())
