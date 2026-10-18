# ДОКУМЕНТ: install/install_zavod_kernel.ps1
# ВЕРСИЯ: v0.6  СТАТУС: DRAFT
# ДАТА СОЗДАНИЯ: 2026-10-18 14:27 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 20:44 +03:00
# ИСПОЛНИТЕЛЬ: Claude (v0.1 сессия fd43469f; v0.2–v0.5 сессия 9951b86f; v0.6 сессия 2fc9a1c8)
# v0.6: учётке ядра выдаётся право «вход как пакетное задание» (secedit, только её SID) — без него задача с паролем не
#   запускалась (CI 18.10: Ready, 0x41303); в gate_diag добавлены события планировщика.
# v0.5: права bin ставятся сразу после программ (служба базы запускает postgres.exe из bin до шага acl); на время
#   initdb учётке установщика дана запись в data (initdb под администратором работает с урезанным маркером), затем
#   снимается вместе с Admins; обход каталогов — $P.get_Keys() (у $P есть ключ 'keys').
#   Список пакетов npm читает install/npm_lock_list.mjs (ConvertFrom-Json PowerShell 5.1 не читает package-lock.json).
#   Права: записи только на каталог, вложенное — /reset к унаследованным (icacls /T оставлял файлам пустой список).
#   Admins снимается с data только после схемы (схема пишет pg_hba.conf).
#   Задача привратника пишет stdout/stderr в logs\gate.log; при GATE_HEALTH_TIMEOUT в квитанции — gate_diag.
# v0.4: установщик EDB той же сборки, что архив, — 16.15-5 (CI 18.10: у EDB есть сборки 16.15-1…5; установщик 16.15-1
#   отличался от архива 16.15-5 в 183 файлах). Тройная сверка (установщик, архив, список коммита) возвращена;
#   отпечаток сертификата подписи EnterpriseDB закреплён; сумма установщика — из эталонного прогона CI 18.10
#   (1635 файлов совпали с архивом); копируются ровно файлы списка. v0.3 (только установщик 16.15-1) — отменён.
# v0.2: права корня без рекурсии (v0.1 давал Users чтение admin и data и сбрасывал владельца rules); корень закрыт
#   сразу после создания (до этого действовали права C:\ — запись для всех вошедших); снимок прав в квитанции.
# НАЗНАЧЕНИЕ: план установки Z-INSTALL-01 §3–§4.C — один запуск оператора «от администратора»: учётка zavod-kernel,
#   каталоги C:\ZavodKernel с правами §2, скачивание и сверка программ (§3), ключи (install/make_certs.mjs), база под
#   службой ZavodKernelPg (install/db_setup.mjs), правила (git clone без входа), проба прав под zavod-kernel
#   (ci/service_probe.mjs), задача ZavodKernel, квитанция public\install_receipt.json. MODE не active, аренд нет.
# ЗАПУСК (оператор, окно PowerShell «от администратора», команда из инструкции с суммой этого файла):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "<скачать файл коммита в память, сверить SHA-256, выполнить>"
#   с параметром -Commit <40 знаков коммита слияния>.
# ОГРАНИЧЕНИЯ: пароль учётки zavod-kernel создаётся случайным в памяти этого процесса, нигде не пишется и никому не
#   показывается (задача хранит его в LSA Windows). Существующий каталог установки — отказ: ничего не перезаписывается
#   и не удаляется. Любой сбой проверки — квитанция FAILED, задача не включается.

param(
  [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Commit,
  [string]$Root = 'C:\ZavodKernel',
  [int]$DbPort = 54390,
  [int]$GatePort = 18960,
  [int]$HealthPort = 18961
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version 3
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

# --- Закреплённые источники (§3.2). Эти суммы закреплены вместе с файлом его собственной суммой. ---
$Repo        = 'bereznyi-aleksandr/ai-devops-system'
$KernelUser  = 'zavod-kernel'
$PgService   = 'ZavodKernelPg'
$TaskName    = 'ZavodKernel'
$Src = [ordered]@{
  node    = @{ url = 'https://nodejs.org/dist/v22.23.2/win-x64/node.exe'; sha = '0d0f5e39f9f3d9587bc19f73eab3c2c9c4903fd02d6dbf9c853dd81b3d95fad4'; signer = 'OpenJS Foundation' }
  mingit  = @{ url = 'https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.2/MinGit-2.55.0.2-64-bit.zip'; sha = 'e3ea2944cea4b3fabcd69c7c1669ef69b1b66c05ac7806d81224d0abad2dec31' }
  pgsetup = @{ url = 'https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64.exe'; sha = '4065dbc5ffb52010e7357dfd6a74934878f1c6faf7a75cad1411a22e11b7b929'; signer = 'EnterpriseDB Corporation'; thumbprint = '7BEDD1269FCCF7A5D95F18274750B79893C06C70' }
  pgzip   = @{ url = 'https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64-binaries.zip'; sha = '43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281' }
}

$receipt = [ordered]@{ format = 'zavod-install-receipt@v1'; status = 'IN_PROGRESS'; commit = $Commit; repo = $Repo; root = $Root
  ports = @{ db = $DbPort; gate = $GatePort; health = $HealthPort }; started_at = (Get-Date).ToUniversalTime().ToString('o')
  sources = [ordered]@{}; steps = @(); mode_active = $false }
function Step([string]$name) { $script:receipt.steps += $name; Write-Host "== $name" }
function Fail([string]$code) { throw "INSTALL_FAILED: $code" }

function Get-Sha([string]$path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() }
function Save-Verified([string]$key, [string]$out) {
  $s = $Src[$key]
  if ($s.sha -notmatch '^[0-9a-f]{64}$') { Fail "PIN_MISSING_$key" }
  Invoke-WebRequest -UseBasicParsing -Uri $s.url -OutFile $out
  $got = Get-Sha $out
  if ($got -ne $s.sha) { Fail "SHA_MISMATCH_$key got=$got" }
  $entry = [ordered]@{ url = $s.url; sha256 = $got }
  if ($s.ContainsKey('signer')) {
    $sig = Get-AuthenticodeSignature -LiteralPath $out
    if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch [regex]::Escape("CN=$($s.signer)")) { Fail "SIGNATURE_$key" }
    if ($s.ContainsKey('thumbprint') -and $sig.SignerCertificate.Thumbprint -ne $s.thumbprint) { Fail "SIGNER_THUMBPRINT_$key" }
    $entry.signer = $sig.SignerCertificate.Subject; $entry.signer_thumbprint = $sig.SignerCertificate.Thumbprint
  }
  $script:receipt.sources[$key] = $entry
}
function Invoke-Checked([string]$exe, [string[]]$argv, [string]$code) {
  & $exe @argv
  if ($LASTEXITCODE -ne 0) { Fail "$code exit=$LASTEXITCODE" }
}

# Права каталога: наследование выключено, владелец — администраторы, ровно перечисленные записи.
$SID_ADMINS = '*S-1-5-32-544'; $SID_SYSTEM = '*S-1-5-18'; $SID_USERS = '*S-1-5-32-545'
# Записи ставятся только на сам каталог: Windows сама переносит наследуемые записи на вложенное. Ключ /T здесь нельзя —
# у файла флаги (OI)(CI) недопустимы, и /T оставлял файлам пустой список доступа (CI 18.10: node.exe — Access denied).
# Без -Here вложенное затем сбрасывается к одним унаследованным записям (/reset); владелец — у всего дерева.
# -Here: только сам каталог (для корня: у вложенных каталогов свои права).
function Set-Acl2([string]$dir, [string[]]$grants, [string]$owner = $SID_ADMINS, [switch]$Here) {
  $icacls = "$env:SystemRoot\System32\icacls.exe"
  $rec = if ($Here) { @('/C', '/Q') } else { @('/T', '/C', '/Q') }
  Invoke-Checked $icacls (@($dir, '/setowner', $owner) + $rec) "ACL_OWNER $dir"
  $argv = @($dir, '/inheritance:r', '/remove:g', '*S-1-5-11', '*S-1-3-0', '*S-1-3-4')
  $argv += @('/grant:r') + $grants + @('/C', '/Q')
  Invoke-Checked $icacls $argv "ACL $dir"
  if (-not $Here) { Invoke-Checked $icacls @((Join-Path $dir '*'), '/reset', '/T', '/C', '/Q') "ACL_RESET $dir" }
}

# Право «вход как пакетное задание» (SeBatchLogonRight) для учётки ядра: без него задача с сохранённым паролем не
# запускается совсем (CI 18.10: Ready, код 0x41303 «ещё не запускалась», журнала нет). По умолчанию право есть только у
# Administrators, Backup Operators и Performance Log Users. Добавляется ровно SID учётки; прежний список сохраняется.
# Шаблон и база secedit остаются в admin (только администраторы); паролей и ключей в них нет.
function Grant-BatchLogon([string]$sid) {
  $secedit = "$env:SystemRoot\System32\secedit.exe"
  $cur = Join-Path $P['admin'] 'user_rights_before.inf'
  Invoke-Checked $secedit @('/export', '/areas', 'USER_RIGHTS', '/cfg', $cur, '/quiet') 'BATCH_RIGHT_EXPORT'
  $line = @(Get-Content -LiteralPath $cur | Where-Object { $_ -match '^\s*SeBatchLogonRight\s*=' })
  $have = if ($line.Count) { @(($line[0] -split '=', 2)[1] -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }) } else { @() }
  $deny = @(Get-Content -LiteralPath $cur | Where-Object { $_ -match '^\s*SeDenyBatchLogonRight\s*=' -and $_ -match [regex]::Escape("*$sid") })
  if ($deny.Count) { Fail 'BATCH_RIGHT_DENIED' }
  if ($have -contains "*$sid") { return 'present' }
  $inf = Join-Path $P['admin'] 'user_rights_batch.inf'
  @('[Unicode]', 'Unicode=yes', '[Version]', 'signature="$CHICAGO$"', 'Revision=1', '[Privilege Rights]',
    "SeBatchLogonRight = $((@($have) + "*$sid") -join ',')") | Set-Content -LiteralPath $inf -Encoding Unicode
  Invoke-Checked $secedit @('/configure', '/db', (Join-Path $P['admin'] 'user_rights_batch.sdb'), '/cfg', $inf, '/areas', 'USER_RIGHTS', '/quiet') 'BATCH_RIGHT_CONFIGURE'
  $chk = Join-Path $P['admin'] 'user_rights_after.inf'
  Invoke-Checked $secedit @('/export', '/areas', 'USER_RIGHTS', '/cfg', $chk, '/quiet') 'BATCH_RIGHT_VERIFY'
  $after = @(Get-Content -LiteralPath $chk | Where-Object { $_ -match '^\s*SeBatchLogonRight\s*=' })
  if (-not $after.Count -or @(($after[0] -split '=', 2)[1] -split ',' | ForEach-Object { $_.Trim() }) -notcontains "*$sid") { Fail 'BATCH_RIGHT_NOT_SET' }
  return 'granted'
}

$P = @{}
foreach ($d in 'admin', 'admin\staging', 'admin\certs', 'bin', 'app', 'rules', 'keys', 'keys\kernel', 'data', 'run', 'logs', 'public') { $P[$d] = Join-Path $Root $d }
$node = Join-Path $P['bin'] 'node.exe'
$cred = $null
try {
  Step 'preflight'
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  if (-not (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Fail 'NOT_ELEVATED' }
  if (Test-Path -LiteralPath $Root) { Fail 'ROOT_EXISTS' }
  if (Get-LocalUser -Name $KernelUser -ErrorAction SilentlyContinue) { Fail 'USER_EXISTS' }
  if (Get-Service -Name $PgService -ErrorAction SilentlyContinue) { Fail 'SERVICE_EXISTS' }
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Fail 'TASK_EXISTS' }
  foreach ($port in $DbPort, $GatePort, $HealthPort) { if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { Fail "PORT_BUSY_$port" } }
  # Корень закрывается сразу: права C:\ дают запись всем вошедшим, а установка кладёт сюда программы.
  New-Item -ItemType Directory -Path $Root | Out-Null
  Set-Acl2 $Root @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F") -Here
  if (@(Get-ChildItem -LiteralPath $Root -Force).Count -ne 0) { Fail 'ROOT_NOT_EMPTY_AFTER_ACL' }
  foreach ($d in $P.get_Keys() | Sort-Object) { New-Item -ItemType Directory -Path $P[$d] | Out-Null }
  Set-Acl2 $P['admin'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F")

  Step 'account'
  # Случайный пароль в памяти: 40 знаков из криптографического генератора; оператор его не вводит и не знает.
  $bytes = New-Object byte[] 30; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $plain = [Convert]::ToBase64String($bytes) + 'a1!'
  $secure = ConvertTo-SecureString -String $plain -AsPlainText -Force
  New-LocalUser -Name $KernelUser -Password $secure -PasswordNeverExpires -UserMayNotChangePassword -AccountNeverExpires -Description 'Zavod kernel and gate (Z-INSTALL-01)' | Out-Null
  Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $KernelUser
  $cred = New-Object Management.Automation.PSCredential ("$env:COMPUTERNAME\$KernelUser", $secure)

  Step 'download'
  $st = $P['admin\staging']
  Save-Verified 'node' (Join-Path $st 'node.exe')
  Save-Verified 'mingit' (Join-Path $st 'mingit.zip')
  Save-Verified 'pgsetup' (Join-Path $st 'pgsetup.exe')
  Save-Verified 'pgzip' (Join-Path $st 'pgzip.zip')
  $codeZip = Join-Path $st 'code.zip'
  Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/$Repo/zip/$Commit" -OutFile $codeZip
  $receipt.sources['code'] = [ordered]@{ url = "https://codeload.github.com/$Repo/zip/$Commit"; sha256 = (Get-Sha $codeZip) }
  $tar = "$env:SystemRoot\System32\tar.exe"
  foreach ($x in @(@('code.zip', 'code'), @('mingit.zip', 'mingit'), @('pgzip.zip', 'pgzip'))) {
    New-Item -ItemType Directory -Path (Join-Path $st $x[1]) | Out-Null
    Invoke-Checked $tar @('-xf', (Join-Path $st $x[0]), '-C', (Join-Path $st $x[1])) "UNPACK_$($x[1])"
  }
  $repoDir = Join-Path (Join-Path $st 'code') ("ai-devops-system-$Commit")
  if (-not (Test-Path -LiteralPath (Join-Path $repoDir 'zavod\kernel\src\gate_main.mjs'))) { Fail 'CODE_LAYOUT' }

  Step 'programs'
  Copy-Item -LiteralPath (Join-Path $st 'node.exe') -Destination $node
  Copy-Item -Path (Join-Path $repoDir 'zavod\kernel\*') -Destination $P['app'] -Recurse -Exclude 'tests', 'node_modules'
  Copy-Item -LiteralPath (Join-Path $st 'mingit') -Destination (Join-Path $P['bin'] 'git') -Recurse
  New-Item -ItemType Directory -Path (Join-Path $P['bin'] 'nohooks') | Out-Null
  # PostgreSQL: подписанный установщик EDB, только извлечение (без служб и реестра); каждый файл bin/lib/share
  # сверяется со списком коммита, и тот же список обязан совпасть с закреплённым архивом binaries той же сборки.
  $pgx = Join-Path $st 'pg_extract'
  $proc = Start-Process -FilePath (Join-Path $st 'pgsetup.exe') -ArgumentList @('--mode', 'unattended', '--extract-only', '1', '--prefix', "`"$pgx`"") -Wait -PassThru
  if ($proc.ExitCode -ne 0) { Fail "PG_EXTRACT exit=$($proc.ExitCode)" }
  $list = Join-Path $P['app'] 'install\pg16_15_files.sha256'
  $pgRoot = if (Test-Path -LiteralPath (Join-Path $pgx 'bin\postgres.exe')) { $pgx } else { Join-Path $pgx 'pgsql' }
  # Из установщика копируются ровно файлы списка (лишнее — StackBuilder, system_stats — не берётся), копия сверяется строго.
  $check = Join-Path $P['app'] 'install\pg_files_check.mjs'
  $copied = & $node $check '--copy-listed' $pgRoot $list (Join-Path $P['bin'] 'pgsql')
  if ($LASTEXITCODE -ne 0) { Fail "PG_FILES_INSTALLER $copied" }
  Invoke-Checked $node @($check, (Join-Path $P['bin'] 'pgsql'), $list) 'PG_FILES_INSTALLED'
  Invoke-Checked $node @($check, (Join-Path $st 'pgzip\pgsql'), $list) 'PG_FILES_ZIP'
  $receipt.sources['pg_files'] = [ordered]@{ list_sha256 = (Get-Sha $list); installer = ($copied | ConvertFrom-Json); installed = 'match'; zip = 'match' }
  # Программы готовы: права bin ставятся сейчас — служба базы (шаг database) запускает postgres.exe из bin\pgsql
  # под своей виртуальной учёткой, а у корня для Users пока нет записей.
  Set-Acl2 $P['bin'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${SID_USERS}:(OI)(CI)RX")

  Step 'npm'
  # Пакеты из package-lock.json коммита: адрес только registry.npmjs.org, integrity sha512 сверяется до распаковки.
  # Разбор файла — node (install/npm_lock_list.mjs): ConvertFrom-Json PowerShell 5.1 отказывает на пустом имени ключа.
  $lockRows = @(& $node (Join-Path $P['app'] 'install\npm_lock_list.mjs') (Join-Path $P['app'] 'package-lock.json'))
  if ($LASTEXITCODE -ne 0) { Fail "NPM_LOCK $($lockRows -join ' ')" }
  $npmDir = Join-Path $st 'npm'; New-Item -ItemType Directory -Path $npmDir | Out-Null
  $n = 0
  foreach ($row in $lockRows) {
    $name, $url, $want = $row -split "`t"
    if ($url -notmatch '^https://registry\.npmjs\.org/[^?#]+\.tgz$' -or $want -notmatch '^[A-Za-z0-9+/]{86}==$') { Fail "NPM_ROW $name" }
    $tgz = Join-Path $npmDir ("{0:d3}.tgz" -f $n); $n++
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tgz
    $sha = [Security.Cryptography.SHA512]::Create()
    $got = [Convert]::ToBase64String($sha.ComputeHash([IO.File]::ReadAllBytes($tgz)))
    if ($got -ne $want) { Fail "NPM_SHA512 $name" }
    $dest = Join-Path $P['app'] ($name -replace '/', '\')
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Invoke-Checked $tar @('-xzf', $tgz, '-C', $dest, '--strip-components=1') "NPM_UNPACK $name"
  }
  $receipt.sources['npm'] = [ordered]@{ packages = $n; lock_sha256 = (Get-Sha (Join-Path $P['app'] 'package-lock.json')) }

  Step 'keys'
  $certs = $P['admin\certs']
  Invoke-Checked $node @((Join-Path $P['app'] 'install\make_certs.mjs'), $certs) 'MAKE_CERTS'
  foreach ($f in 'ca.crt.pem', 'bem_kernel_rw.crt.pem', 'bem_kernel_rw.key.pem', 'bem_rules_gate.crt.pem', 'bem_rules_gate.key.pem', 'gate_ed25519.key.pem') {
    Copy-Item -LiteralPath (Join-Path $certs $f) -Destination $P['keys\kernel'] }
  foreach ($f in 'ca.crt.pem', 'gate_ed25519.pub.pem', 'certs.json') { Copy-Item -LiteralPath (Join-Path $certs $f) -Destination $P['public'] }
  $foreign = Join-Path $st 'foreign_ca'; New-Item -ItemType Directory -Path $foreign | Out-Null
  Invoke-Checked $node @((Join-Path $P['app'] 'install\make_certs.mjs'), $foreign) 'MAKE_FOREIGN_CA'

  Step 'database'
  $dbCfg = Join-Path $st 'db_setup.json'
  [ordered]@{ pgBin = (Join-Path $P['bin'] 'pgsql\bin'); data = $P['data']; certs = $certs; pkg = (Join-Path $repoDir 'bem954\H1_31_PACKAGE_R51')
    kernelDir = $P['app']; port = $DbPort } | ConvertTo-Json | Set-Content -LiteralPath $dbCfg -Encoding ascii
  # initdb под администратором сам перезапускается с урезанным маркером (группа Administrators — только для запрета),
  # поэтому на время init/config учётке установщика даётся явная запись в data; ниже она снимается вместе с Admins.
  $me = "*$($id.User.Value)"
  Set-Acl2 $P['data'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${me}:(OI)(CI)F")
  Invoke-Checked $node @((Join-Path $P['app'] 'install\db_setup.mjs'), 'init', $dbCfg) 'DB_INIT'
  Invoke-Checked $node @((Join-Path $P['app'] 'install\db_setup.mjs'), 'config', $dbCfg) 'DB_CONFIG'
  Invoke-Checked (Join-Path $P['bin'] 'pgsql\bin\pg_ctl.exe') @('register', '-N', $PgService, '-U', "NT SERVICE\$PgService", '-D', $P['data'], '-S', 'auto', '-w') 'PG_REGISTER'
  Set-Acl2 $P['data'] @("*S-1-5-80-0:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "NT SERVICE\${PgService}:(OI)(CI)F")
  # S-1-5-80-0 («все службы») и учётка установщика снимаются сразу. Admins остаётся до конца шага: схема (db_setup
  # schema) открывает и закрывает окно миграции записью pg_hba.conf и pg_ident.conf (CI 18.10: EPERM без Admins).
  Invoke-Checked "$env:SystemRoot\System32\icacls.exe" @($P['data'], '/remove:g', '*S-1-5-80-0', $me, '/C', '/Q') 'ACL_DATA_TRIM'
  Start-Service -Name $PgService
  $deadline = (Get-Date).AddSeconds(60)
  while (-not (Get-NetTCPConnection -LocalPort $DbPort -State Listen -ErrorAction SilentlyContinue)) {
    if ((Get-Date) -gt $deadline) { Fail 'PG_NOT_LISTENING' }; Start-Sleep -Seconds 1 }
  Invoke-Checked $node @((Join-Path $P['app'] 'install\db_setup.mjs'), 'schema', $dbCfg) 'DB_SCHEMA'
  $dbChecks = & $node (Join-Path $P['app'] 'install\pg_probe.mjs') $DbPort (Join-Path $certs 'ca.crt.pem') $certs $foreign | ConvertFrom-Json
  $receipt.db_checks = $dbChecks
  if (-not $dbChecks.ok) { Fail 'DB_CHECKS' }
  # Схема установлена: доступ к data — только у службы базы и SYSTEM (§2).
  Invoke-Checked "$env:SystemRoot\System32\icacls.exe" @($P['data'], '/remove:g', $SID_ADMINS, '/C', '/Q') 'ACL_DATA_ADMINS'

  Step 'rules'
  $git = Join-Path $P['bin'] 'git\cmd\git.exe'
  # Строка собирается заранее: внутри @(…) запятая сильнее «+», и путь уходил в git отдельным словом (CI 18.10).
  $hooksCfg = "core.hooksPath=$(Join-Path $P['bin'] 'nohooks')"
  Invoke-Checked $git @('-c', $hooksCfg, 'clone', '--no-tags', '--single-branch', '--branch', 'main', "https://github.com/$Repo.git", $P['rules']) 'RULES_CLONE'
  Invoke-Checked $git @('-C', $P['rules'], 'config', 'core.hooksPath', (Join-Path $P['bin'] 'nohooks')) 'RULES_HOOKS'

  Step 'config'
  $gateCfg = [ordered]@{
    db = [ordered]@{ host = '127.0.0.1'; port = $DbPort; database = 'bem'; ca = (Join-Path $P['keys\kernel'] 'ca.crt.pem') }
    kernelCert = [ordered]@{ cert = (Join-Path $P['keys\kernel'] 'bem_kernel_rw.crt.pem'); key = (Join-Path $P['keys\kernel'] 'bem_kernel_rw.key.pem') }
    rulesCert = [ordered]@{ cert = (Join-Path $P['keys\kernel'] 'bem_rules_gate.crt.pem'); key = (Join-Path $P['keys\kernel'] 'bem_rules_gate.key.pem') }
    gate = [ordered]@{ port = $GatePort; key = (Join-Path $P['keys\kernel'] 'gate_ed25519.key.pem') }
    health = [ordered]@{ port = $HealthPort }
    stopFile = (Join-Path $P['run'] 'STOP'); expectedUser = $KernelUser
    rules = [ordered]@{ repo = $Repo; repoDir = $P['rules']; git = $git }
  }
  $gateCfg | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $P['app'] 'gate.json') -Encoding ascii
  Set-Content -LiteralPath (Join-Path $P['run'] 'STOP') -Value 'RUN' -Encoding ascii

  Step 'acl'
  $K = "${KernelUser}"
  Set-Acl2 $P['app'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${SID_USERS}:(OI)(CI)RX")
  Set-Acl2 $P['public'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${SID_USERS}:(OI)(CI)RX")
  Set-Acl2 $P['keys'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${K}:(RX)")
  Set-Acl2 $P['keys\kernel'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${K}:(OI)(CI)RX")
  Set-Acl2 $P['rules'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${K}:(OI)(CI)M", "${SID_USERS}:(OI)(CI)RX") $K
  Set-Acl2 $P['run'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${K}:(OI)(CI)M", "${SID_USERS}:(OI)(CI)RX")
  Set-Acl2 $P['logs'] @("${SID_ADMINS}:(OI)(CI)F", "${SID_SYSTEM}:(OI)(CI)F", "${K}:(OI)(CI)M", "${SID_USERS}:(OI)(CI)RX")
  # Корень: Users только проход и список (без наследования); вложенные каталоги не трогаются.
  Set-Acl2 $Root @("${SID_ADMINS}:F", "${SID_SYSTEM}:F", "${SID_USERS}:RX") -Here
  $acl = [ordered]@{}
  foreach ($d in @('.') + @($P.get_Keys() | Sort-Object)) {
    $path = if ($d -eq '.') { $Root } else { $P[$d] }
    $a = Get-Acl -LiteralPath $path
    $acl[$d] = [ordered]@{ owner = $a.Owner; protected = $a.AreAccessRulesProtected; sddl = $a.Sddl }
  }
  $receipt.acl = $acl

  Step 'service_probe'
  $probe = Start-Process -FilePath $node -ArgumentList @("`"$(Join-Path $P['app'] 'ci\service_probe.mjs')`"", "`"$Root`"", $DbPort) -Credential $cred -WorkingDirectory $P['logs'] -Wait -PassThru -WindowStyle Hidden
  $probeFile = Join-Path $P['logs'] 'service_probe.json'
  if (-not (Test-Path -LiteralPath $probeFile)) { Fail "SERVICE_PROBE_NO_OUTPUT exit=$($probe.ExitCode)" }
  $owner = (Get-Acl -LiteralPath $probeFile).Owner
  $receipt.service_probe = [ordered]@{ exit = $probe.ExitCode; owner = $owner; sha256 = (Get-Sha $probeFile); result = (Get-Content -Raw -LiteralPath $probeFile | ConvertFrom-Json) }
  if ($probe.ExitCode -ne 0 -or $owner -notmatch "\\$([regex]::Escape($KernelUser))$" -or -not $receipt.service_probe.result.ok) { Fail 'SERVICE_PROBE' }

  Step 'task'
  # Журнал привратника (stdout/stderr) дописывается в logs\gate.log: у задачи Windows нет экрана, без файла причина
  # сбоя не видна (CI 18.10: GATE_HEALTH_TIMEOUT без следов). cmd /d — без AutoRun; внешние кавычки снимает cmd /c.
  $gateLog = Join-Path $P['logs'] 'gate.log'
  $gateCmd = "/d /c `"`"$node`" `"$(Join-Path $P['app'] 'src\gate_main.mjs')`" `"$(Join-Path $P['app'] 'gate.json')`" >> `"$gateLog`" 2>&1`""
  $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" -Argument $gateCmd -WorkingDirectory $P['logs']
  $triggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn))
  $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  $receipt.batch_logon_right = Grant-BatchLogon (Get-LocalUser -Name $KernelUser).SID.Value
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -User "$env:COMPUTERNAME\$KernelUser" -Password $plain -RunLevel Limited | Out-Null
  $taskStart = Get-Date
  Start-ScheduledTask -TaskName $TaskName
  $health = $null; $deadline = (Get-Date).AddSeconds(60)
  while (-not $health) {
    try { $health = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:$HealthPort/internal/health" -TimeoutSec 3 } catch { Start-Sleep -Seconds 2 }
    if (-not $health -and (Get-Date) -gt $deadline) {
      # Следы для разбора: состояние задачи, код последнего запуска и хвост журнала привратника (в нём нет ключей).
      $ti = Get-ScheduledTaskInfo -TaskName $TaskName
      $tail = if (Test-Path -LiteralPath $gateLog) { @(Get-Content -LiteralPath $gateLog -Tail 20) } else { @() }
      $receipt.gate_diag = [ordered]@{ task_state = "$((Get-ScheduledTask -TaskName $TaskName).State)"; last_result = $ti.LastTaskResult
        last_run = "$($ti.LastRunTime)"; log_tail = $tail; events = @() }
      # События планировщика (если журнал Operational включён): номер, код результата и первая строка текста.
      try {
        $receipt.gate_diag.events = @(Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-TaskScheduler/Operational'; StartTime = $taskStart } -ErrorAction Stop |
          Where-Object { $_.Message -match [regex]::Escape("\$TaskName") } | Select-Object -First 15 |
          ForEach-Object { "$($_.Id) $(($_.Message -split "`n")[0].Trim())" })
      } catch { $receipt.gate_diag.events = @("NO_EVENTS $($_.Exception.GetType().Name)") }
      Fail 'GATE_HEALTH_TIMEOUT'
    }
  }
  if ($health.gate_port -ne $GatePort -or $health.os_user -ne $KernelUser) { Fail 'GATE_HEALTH_MISMATCH' }
  $receipt.gate_health = $health

  Step 'receipt'
  $sums = [ordered]@{}
  foreach ($base in 'bin', 'app') {
    Get-ChildItem -LiteralPath $P[$base] -Recurse -File | Sort-Object FullName | ForEach-Object {
      $sums[$_.FullName.Substring($Root.Length + 1).Replace('\', '/')] = Get-Sha $_.FullName }
  }
  $receipt.file_sums = $sums
  $receipt.certs = Get-Content -Raw -LiteralPath (Join-Path $P['public'] 'certs.json') | ConvertFrom-Json
  $receipt.status = 'OK'
}
catch {
  $receipt.status = 'FAILED'
  # Строка скрипта, где случился сбой, — без значений переменных (пароль в тексте скрипта не встречается).
  $receipt.error = (($_.Exception.Message -split "`n")[0]) + " @line $($_.InvocationInfo.ScriptLineNumber)"
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Disable-ScheduledTask -TaskName $TaskName | Out-Null }
}
finally {
  $plain = $null; $secure = $null; $cred = $null
  $receipt.finished_at = (Get-Date).ToUniversalTime().ToString('o')
  if (Test-Path -LiteralPath $P['public']) {
    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $P['public'] 'install_receipt.json') -Encoding utf8
  }
  Write-Host "INSTALL_STATUS=$($receipt.status) $(if ($receipt.Contains('error')) { $receipt.error })"
}
if ($receipt.status -ne 'OK') { exit 3 }
