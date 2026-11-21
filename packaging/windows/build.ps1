# Build dist\OVC\OVC.exe (no console window) and dist\OVC-windows.zip.
# Run from the repository root in an environment where OVC is installed:
#   pip install . pyinstaller
#   powershell -File packaging\windows\build.ps1
$ErrorActionPreference = "Stop"

pyinstaller --noconfirm --clean --windowed --name OVC `
  --icon ovc\app\static\ovc.ico `
  --hidden-import tkinter `
  --hidden-import tkinter.filedialog `
  --collect-data ovc.app `
  --collect-data ovc.sample_data `
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
