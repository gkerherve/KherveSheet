; Inno Setup script for KherveSheet.
;
; Produces a single Setup_KherveSheet_<version>.exe installer that drops
; the one-folder PyInstaller build under Program Files\KherveSheet and
; wires up a Start-menu entry, optional desktop icon, .ksheet association,
; and an uninstaller.
;
; Build steps:
;   1. pip install -r requirements.txt
;   2. pip install pyinstaller
;   3. pyinstaller KherveSheet.spec --noconfirm
;   4. ISCC.exe KherveSheet_setup.iss
;      (Inno Setup 6 — https://jrsoftware.org/isinfo.php)
;
; Output lands in .\installer\.

#define MyAppName        "KherveSheet"
#define MyAppPublisher   "Gwilherm Kerherve"
#define MyAppExeName     "KherveSheet.exe"
#ifndef MyAppVersion
  #define MyAppVersion   "0.1"
#endif

[Setup]
; Globally-unique app ID — keeps the uninstaller info tidy and lets
; users in-place upgrade without leaving stale entries.
AppId={{A7B2D5E1-3F8C-4A29-B6E4-1D9F7C0E5A83}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Default install target: Program Files (autopf picks the right
; "Program Files" or "Program Files (x86)" based on 64/32-bit).
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Need admin to write under Program Files. The override dialog lets
; the user fall back to a per-user install if they want to.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=Setup_KherveSheet_{#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=LICENSE
; Setup wizard icon — same green KS monogram baked into the .exe.
SetupIconFile=build\KherveSheet.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc_ksheet"; Description: "Open .ksheet files with {#MyAppName}"; GroupDescription: "File associations:"; Flags: unchecked
Name: "fileassoc_csv"; Description: "Open .csv files with {#MyAppName}"; GroupDescription: "File associations:"; Flags: unchecked

[InstallDelete]
; Wipe the previous payload before copying the new one.
;
; Inno overwrites files but never removes ones a newer build dropped, so
; upgrading left the union of both builds behind. That is not merely untidy:
; numpy renamed core -> _core between 1.x and 2.x, so an upgrade that changes
; the numpy major leaves the old orphaned package next to the new one, and
; h5py's extensions — ABI-bound to one numpy — then fail to import. The app
; reported that as "h5py is required for .ksheet files".
;
; Everything here is build output reinstalled immediately below; no user data
; lives under {app}.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Sweep the entire PyInstaller dist folder — bootloader + _internal
; with all the bundled wheels (numpy, scipy, matplotlib, PyQt5,
; h5py, lmfit, pygit2, qtawesome, AI providers, etc.).
Source: "dist\KherveSheet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Optional .ksheet association — only writes when the user ticks the
; corresponding task.
Root: HKA; Subkey: "Software\Classes\.ksheet\OpenWithProgids"; ValueType: string; ValueName: "KherveSheet.Document"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc_ksheet
Root: HKA; Subkey: "Software\Classes\KherveSheet.Document"; ValueType: string; ValueData: "KherveSheet Document"; Flags: uninsdeletekey; Tasks: fileassoc_ksheet
Root: HKA; Subkey: "Software\Classes\KherveSheet.Document\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"; Tasks: fileassoc_ksheet
Root: HKA; Subkey: "Software\Classes\KherveSheet.Document\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc_ksheet
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
; Optional .csv association.
Root: HKA; Subkey: "Software\Classes\.csv\OpenWithProgids"; ValueType: string; ValueName: "KherveSheet.CSV"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc_csv
Root: HKA; Subkey: "Software\Classes\KherveSheet.CSV"; ValueType: string; ValueData: "CSV Spreadsheet"; Flags: uninsdeletekey; Tasks: fileassoc_csv
Root: HKA; Subkey: "Software\Classes\KherveSheet.CSV\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"; Tasks: fileassoc_csv
Root: HKA; Subkey: "Software\Classes\KherveSheet.CSV\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc_csv

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
