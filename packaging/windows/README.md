# Windows app

`build.ps1` freezes the map app with PyInstaller into `dist\OVC\OVC.exe` and
zips the folder as `OVC-windows.zip`. The exe has no console window: a
double-click starts OVC and opens it in the default browser.

The [Windows app workflow](../../.github/workflows/windows-app.yml) runs this
script on every pull request and push to `main`, runs the exe's self-test
(read the bundled sample, check it, export, reopen the export) and uploads
the zip as the `OVC-windows` artifact. When a GitHub release is published,
the zip is attached to it.

To build locally:

```powershell
pip install . pyinstaller
powershell -File packaging\windows\build.ps1
```
