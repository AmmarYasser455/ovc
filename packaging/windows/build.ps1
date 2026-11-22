# Build dist\OVC\OVC.exe (no console window), the portable dist\OVC-windows.zip,
# and the installer dist\OVC-Setup.exe with its dist\OVC-Setup.exe.sha256.
# Run from the repository root in an environment where OVC is installed:
#   pip install . pyinstaller
#   powershell -File packaging\windows\build.ps1
$ErrorActionPreference = "Stop"

pyinstaller --noconfirm --clean --windowed --name OVC `
  --icon ovc\app\static\ovc.ico `
  --hidden-import tkinter `
  --hidden-import tkinter.filedialog `
  --collect-data ovc.app `
  --collect-all pyogrio `
  --collect-all pyproj `
  --collect-data geopandas `
  --exclude-module folium `
  --exclude-module geoqa `
  --exclude-module matplotlib `
  packaging\windows\ovc_app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Copy-Item LICENSE dist\OVC\LICENSE.txt
Copy-Item ovc\app\static\vendor\leaflet\LICENSE dist\OVC\LICENSE-Leaflet.txt
Copy-Item ovc\app\static\vendor\lucide\LICENSE dist\OVC\LICENSE-Lucide.txt
Copy-Item ovc\app\static\vendor\geoman\LICENSE dist\OVC\LICENSE-Leaflet-Geoman.txt

# Prove the frozen app has its data files and geospatial libraries.
$report = Join-Path $PWD "dist\self-test.json"
$p = Start-Process -FilePath "dist\OVC\OVC.exe" -ArgumentList "--self-test", "`"$report`"" -Wait -PassThru
Get-Content $report
if ($p.ExitCode -ne 0) { throw "OVC.exe self-test failed" }

# Prove the splash window and the native file dialog can open (Tk is bundled).
$p = Start-Process -FilePath "dist\OVC\OVC.exe" -ArgumentList "--splash-test" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "OVC.exe could not show its splash window" }
$request = Join-Path $PWD "dist\pick-request.json"
$result = Join-Path $PWD "dist\pick-result.json"
@{ mode = "test"; title = "test"; result = $result } | ConvertTo-Json | Set-Content -Path $request -Encoding utf8
$p = Start-Process -FilePath "dist\OVC\OVC.exe" -ArgumentList "--pick", "`"$request`"" -Wait -PassThru
if ($p.ExitCode -ne 0 -or -not (Test-Path $result)) { throw "OVC.exe could not open a file dialog window" }

# Prove OVC opens in its own window and the page starts inside it.
$p = Start-Process -FilePath "dist\OVC\OVC.exe" -ArgumentList "--window-test" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "OVC.exe could not open its app window" }

# Prove it serves the map page.
$app = Start-Process -FilePath "dist\OVC\OVC.exe" -ArgumentList "--no-browser", "--port", "8791" -PassThru
try {
  $ok = $false
  foreach ($i in 1..40) {
    Start-Sleep -Milliseconds 500
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:8791/" -UseBasicParsing
      if ($r.StatusCode -eq 200 -and $r.Content -match "Overlap Violation Checker") { $ok = $true; break }
    } catch { }
  }
  if (-not $ok) { throw "OVC.exe did not serve the map page" }
} finally {
  Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
}

Compress-Archive -Path dist\OVC -DestinationPath dist\OVC-windows.zip -Force
Write-Host "Built dist\OVC-windows.zip"

# ---- Installer (Inno Setup 6) -------------------------------------------
$iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
  choco install innosetup -y --no-progress
  if ($LASTEXITCODE -ne 0) { throw "Could not install Inno Setup" }
}
$version = python -c "import ovc; print(ovc.__version__)"
& $iscc "/DAppVersion=$version" packaging\windows\ovc.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
$hash = (Get-FileHash dist\OVC-Setup.exe -Algorithm SHA256).Hash.ToLower()
Set-Content -Path dist\OVC-Setup.exe.sha256 -Value "$hash  OVC-Setup.exe" -Encoding ascii -NoNewline

# Prove the installer installs, the installed copy works and knows it was
# installed (so in-app updates are offered), and the uninstaller removes it.
$base = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$dir = Join-Path $base "ovc-install-test"
$p = Start-Process -FilePath "dist\OVC-Setup.exe" -Wait -PassThru -ArgumentList `
  "/VERYSILENT", "/SUPPRESSMSGBOXES", "/CURRENTUSER", "/NOLAUNCH", "/DIR=`"$dir`""
if ($p.ExitCode -ne 0) { throw "OVC-Setup.exe failed with exit code $($p.ExitCode)" }
foreach ($f in "OVC.exe", "unins000.exe") {
  if (-not (Test-Path (Join-Path $dir $f))) { throw "The installer did not create $f" }
}
$report = Join-Path $base "installed-self-test.json"
$p = Start-Process -FilePath (Join-Path $dir "OVC.exe") -ArgumentList "--self-test", "`"$report`"" -Wait -PassThru
if ($p.ExitCode -ne 0) { Get-Content $report; throw "The installed OVC.exe failed its self-test" }
$info = Join-Path $base "install-info.json"
$p = Start-Process -FilePath (Join-Path $dir "OVC.exe") -ArgumentList "--install-info", "`"$info`"" -Wait -PassThru
$kind = (Get-Content $info | ConvertFrom-Json).kind
if ($kind -ne "installer") { throw "The installed OVC reports install kind '$kind'" }
$shortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "OVC.lnk"
if (-not (Test-Path $shortcut)) { throw "No Start menu shortcut at $shortcut" }

# Installing the same setup again over itself is how an update runs.
$p = Start-Process -FilePath "dist\OVC-Setup.exe" -Wait -PassThru -ArgumentList `
  "/VERYSILENT", "/SUPPRESSMSGBOXES", "/CURRENTUSER", "/NOLAUNCH"
if ($p.ExitCode -ne 0) { throw "Upgrading over an existing install failed" }
if (-not (Test-Path (Join-Path $dir "OVC.exe"))) { throw "The upgrade did not reuse the install folder" }

Start-Process -FilePath (Join-Path $dir "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES" -Wait
foreach ($i in 1..60) {
  if (-not (Test-Path (Join-Path $dir "OVC.exe"))) { break }
  Start-Sleep -Seconds 1
}
if (Test-Path (Join-Path $dir "OVC.exe")) { throw "The uninstaller did not remove OVC" }
if (Test-Path $shortcut) { throw "The uninstaller left the Start menu shortcut" }
Write-Host "Built dist\OVC-Setup.exe ($hash)"
