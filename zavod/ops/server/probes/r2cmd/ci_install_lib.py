# ДОКУМЕНТ: ci_install_lib.py (только CI: папка программ B10 так, как её ставит установщик B10)
# ВЕРСИЯ: v0.1  СТАТУС: DRAFT  ДАТА СОЗДАНИЯ: 2026-11-16 21:08 +02:00
# ИСПОЛНИТЕЛЬ: Claude, терминальный чат (пускатель), сменщик после HANDOFF_20261116_1916.
# НАЗНАЧЕНИЕ: из пакета выпуска B10 (распакован из zprobe-release-3.5.5-b10.sh коммита 64a04f634) берёт цели
#   установщика zprobe_release_b10.targets(pkg) в папке LIB и пишет их байты с их режимами (root:root) — независимо от
#   списка в r2_precheck.sh. Печатает «режим sha имя» по целям (для сверки P00). На сервере не запускается.
# ЗАПУСК (root, одноразовая машина CI): python3 -I -B ci_install_lib.py <папка пакета>
import hashlib
import os
import sys

pkg = sys.argv[1]
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(pkg, 'zavod', 'ops', 'server', 'probes'))
import zprobe_release_b10 as R  # noqa: E402

os.makedirs(R.LIB, mode=0o755, exist_ok=False)
os.chmod(R.LIB, 0o755)
for p, data, mode in R.targets(pkg):
    if os.path.dirname(p) != R.LIB or data is None:
        continue
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    os.chmod(p, mode)
    print(f'{mode:o} {hashlib.sha256(data).hexdigest()} {os.path.basename(p)}')
