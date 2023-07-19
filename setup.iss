
#include "environment.iss"

#define SourceDir "F:\Code\Python\manga_downloader\"
#define MyAppName "Manga Downloader"
#define MyAppVersion "0.1.3"
#define MyAppPublisher "Auto-Life"
#define MyAppExeName "mangadl.exe"
#define MyAppIcoName "manga.ico"
#define AppSaveName "mangadl"

[Setup]
AppId={{CC10DA5C-05CA-4B0F-B054-FDA57359EEE2}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=C:\Program Files\{#MyAppName}    
DisableProgramGroupPage=yes
LicenseFile={#SourceDir}\LICENSE
OutputBaseFilename=setup
SetupIconFile={#SourceDir}\{#MyAppIcoName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: envPath; Description: "Add to PATH variable"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\build\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\{#MyAppIcoName}"; DestDir: "{app}"

[Icons]
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcoName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
    if (CurStep = ssPostInstall) and IsTaskSelected('envPath')
    then EnvAddPath(ExpandConstant('{app}') +'\bin');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
    if CurUninstallStep = usPostUninstall
    then EnvRemovePath(ExpandConstant('{app}') +'\bin');
end;