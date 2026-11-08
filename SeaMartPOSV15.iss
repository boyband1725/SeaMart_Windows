#define MyAppName "SeaMart POS V15"
#define MyAppVersion "15.0.0"
#define MyAppExeName "SeaMartPOSV15.exe"
[Setup]
AppId={{9D3EAC4A-03F4-48A8-9A1C-8D4C2D9F1551}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\SeaMart POS V15
DefaultGroupName=SeaMart POS V15
OutputDir=Output
OutputBaseFilename=SeaMartPOSV15-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\SeaMart POS V15"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SeaMart POS V15"; Filename: "{app}\{#MyAppExeName}"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Jalankan SeaMart POS V15"; Flags: postinstall nowait skipifsilent
