#!/usr/bin/env bash
# ДОКУМЕНТ: win/build_jobhost.sh
# ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
# ДАТА СОЗДАНИЯ: 2026-10-07 22:20 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 22:39 +03:00 (DRAFT → CANDIDATE: тесты jobhost и fencer прошли на Windows)
# ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
# НАЗНАЧЕНИЕ: сборка win/zavod_jobhost.exe компилятором C# из .NET Framework 4 (есть в Windows,
#   установка не нужна). Печатает SHA-256 собранного файла.
# ВЫЗОВ: bash win/build_jobhost.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
csc="${CSC:-/c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe}"
[ -x "$csc" ] || { echo "JOBHOST_BUILD_FAILED: csc not found: $csc" >&2; exit 1; }
"$csc" -nologo -optimize+ -platform:x64 -target:exe -out:"$(cygpath -w "$here/zavod_jobhost.exe")" "$(cygpath -w "$here/zavod_jobhost.cs")"
echo "JOBHOST_BUILT=$(sha256sum "$here/zavod_jobhost.exe" | cut -d' ' -f1)"
