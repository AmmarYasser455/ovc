; OVC installer (Inno Setup 6). Built by build.ps1:
;   ISCC /DAppVersion=3.6.0 packaging\windows\ovc.iss
; Paths are relative to this file. Output: dist\OVC-Setup.exe

#ifndef AppVersion
  #error Pass /DAppVersion=<version> to ISCC
#endif

[Setup]
; Never change AppId: it is how Windows recognises an upgrade of OVC.
AppId={{8F3C2A51-6E1B-4C2D-9B7A-0F5E3D2C1A90}
AppName=OVC
AppVersion={#AppVersion}
AppVerName=OVC {#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoDescription=OVC - Overlap Violation Checker setup
AppPublisher=OpenTerra
AppPublisherURL=https://github.com/AmmarYasser455/ovc
AppSupportURL=https://github.com/AmmarYasser455/ovc/issues
AppUpdatesURL=https://github.com/AmmarYasser455/ovc/releases
AppCopyright=Copyright (c) Ammar Yasser Abdalazim, OpenTerra
; Per-user install by default (no administrator rights needed); the
; analyst can choose "all users" on the first page.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
DefaultDirName={autopf}\OVC
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=OVC-Setup
SetupIconFile=..\..\ovc\app\static\ovc.ico
UninstallDisplayIcon={app}\OVC.exe
UninstallDisplayName=OVC - Overlap Violation Checker
WizardStyle=modern
WizardImageFile=wizard-large.bmp
WizardSmallImageFile=wizard-small.bmp
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; An update closes a running OVC first; the installer then reopens it.
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Remove the previous version's libraries so no stale file survives an upgrade.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\..\dist\OVC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\OVC"; Filename: "{app}\OVC.exe"; Comment: "Overlap Violation Checker"
Name: "{autodesktop}\OVC"; Filename: "{app}\OVC.exe"; Comment: "Overlap Violation Checker"; Tasks: desktopicon

[Run]
; Checked "Launch OVC" box after a normal install; runs by itself after an
; in-app update (silent install). /NOLAUNCH turns it off (packaging tests).
Filename: "{app}\OVC.exe"; Description: "{cm:LaunchProgram,OVC}"; Flags: nowait postinstall; Check: ShouldLaunch

[Code]
function ShouldLaunch(): Boolean;
var
  I: Integer;
begin
  Result := True;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/NOLAUNCH') = 0 then
      Result := False;
end;
