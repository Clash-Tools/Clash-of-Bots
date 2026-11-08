# Builds build/ClashOfBots/ClashOfBots.exe (Nuitka standalone, D-003) with adb bundled in tools/adb.
# Run from repo root on Windows after: uv sync --python 3.13 --group build
# Version args default to cob/__init__.py via scripts/release.py (D-011).
param(
    [string]$Version = (uv run python scripts/release.py current),
    [string]$FileVersion = (uv run python scripts/release.py file-version)
)
$ErrorActionPreference = "Stop"
Write-Host "building Clash of Bots $Version (file version $FileVersion)"

$dist = "build/ClashOfBots"
if (Test-Path build) { Remove-Item -Recurse -Force build }

# One exe for GUI and CLI: "hide" keeps a console program (terminals wait, exit codes work) and
# hides the console window Windows opens on double-click, so only the GUI shows (D-019).
# Nuitka logs progress to stderr; Windows PowerShell 5.1 turns redirected native stderr into
# terminating errors under "Stop", so rely on $LASTEXITCODE for this call instead.
$ErrorActionPreference = "Continue"
uv run python -m nuitka `
    --standalone `
    --assume-yes-for-downloads `
    --enable-plugin=pyside6 `
    --windows-console-mode=hide `
    --python-flag=-m `
    --include-package=cob `
    --include-data-dir=assets=assets `
    --output-dir=build `
    --output-filename=ClashOfBots.exe `
    --company-name="Clash of Bots" `
    --product-name="Clash of Bots" `
    --file-version=$FileVersion `
    --product-version=$FileVersion `
    --file-description="Clash of Bots $Version" `
    cob
if ($LASTEXITCODE -ne 0) { throw "nuitka failed" }
$ErrorActionPreference = "Stop"

# Nuitka names the folder after the package (cob.dist); normalise.
Move-Item build/cob.dist $dist

# Official Google platform-tools; only adb + its two DLLs are shipped.
$zip = "build/platform-tools.zip"
Invoke-WebRequest https://dl.google.com/android/repository/platform-tools-latest-windows.zip -OutFile $zip
Expand-Archive $zip -DestinationPath build/pt
New-Item -ItemType Directory -Force "$dist/tools/adb" | Out-Null
Copy-Item build/pt/platform-tools/adb.exe, build/pt/platform-tools/AdbWinApi.dll, build/pt/platform-tools/AdbWinUsbApi.dll "$dist/tools/adb/"

Write-Host "built $dist/ClashOfBots.exe"
