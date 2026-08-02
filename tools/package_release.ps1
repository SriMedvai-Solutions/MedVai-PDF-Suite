param(
    [string]$ExePath = ".\dist\MedVai_PDF_Suite.exe",
    [string]$Version = "3.0.5-beta"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Exe = Resolve-Path (Join-Path $Root $ExePath)
$OutputRoot = Join-Path $Root "release_output"
$FolderName = "MedVai_PDF_Suite_Windows_x64_$Version"
$Stage = Join-Path $OutputRoot $FolderName
$ZipPath = Join-Path $OutputRoot "$FolderName.zip"

Remove-Item -Recurse -Force $Stage -ErrorAction SilentlyContinue
Remove-Item -Force $ZipPath -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Copy-Item $Exe (Join-Path $Stage "MedVai_PDF_Suite.exe")
Copy-Item (Join-Path $Root "release_template\README_FIRST.txt") $Stage
Copy-Item (Join-Path $Root "LICENSE") $Stage
Copy-Item (Join-Path $Root "NOTICE") $Stage
Copy-Item (Join-Path $Root "THIRD_PARTY_NOTICES.md") $Stage
Copy-Item -Recurse (Join-Path $Root "third_party_licenses") $Stage

$Hash = Get-FileHash (Join-Path $Stage "MedVai_PDF_Suite.exe") -Algorithm SHA256
"$($Hash.Hash)  MedVai_PDF_Suite.exe" | Set-Content -Encoding ASCII (Join-Path $Stage "SHA256.txt")

Compress-Archive -Path "$Stage\*" -DestinationPath $ZipPath -CompressionLevel Optimal
Write-Host "Created: $ZipPath"
