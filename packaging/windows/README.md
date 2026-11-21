# Windows app

`build.ps1` freezes the map app with PyInstaller into `dist\OVC\OVC.exe` and
zips the folder as `OVC-windows.zip`. The exe carries the OVC icon and has no
console window: a double-click shows the splash window, then opens OVC in its
own window (Microsoft Edge in app mode; Edge is part of Windows 10 and 11, and
nothing is bundled for it). If no window can be shown it falls back to a
browser tab.

The [Windows app workflow](../../.github/workflows/windows-app.yml) runs this
script on every pull request and push to `main`, runs the exe's self-test
(read the bundled sample, check it, export, reopen the export), checks that
the splash window, a file dialog window and the app window can open, and uploads
the zip as the `OVC-windows` artifact. When a GitHub release is published,
the zip is attached to it.

To build locally:

```powershell
pip install . pyinstaller
powershell -File packaging\windows\build.ps1
```

The icon and splash logo are generated from `assets/brand/logo-dark.svg` by
[`packaging/brand/make_icons.py`](../brand/make_icons.py).
