# Windows app

`build.ps1` builds three files in `dist\`:

| File | What it is |
|---|---|
| `OVC-Setup.exe` | The installer (Inno Setup, script `ovc.iss`): Start menu and optional desktop shortcut, uninstaller, per-user install without administrator rights. Running a newer one upgrades in place. |
| `OVC-Setup.exe.sha256` | Its checksum. The in-app updater refuses an installer that does not match. |
| `OVC-windows.zip` | The same app as a portable folder. |

The installer is tested in the build: silent install, self-test of the installed copy, check that it reports itself as installed, upgrade over itself, and uninstall.

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
