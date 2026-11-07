#define MyAppName "BandTab Studio"
#define MyAppVersion "0.2.0"
[Setup]
AppId={{C893045E-E753-491D-93B0-FD1EF9088E15}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\BandTab Studio
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=BandTabStudio-Windows-x64-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BandTabStudio.exe
[Files]
Source: "..\dist\BandTabStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\BandTab Studio"; Filename: "{app}\BandTabStudio.exe"
Name: "{autodesktop}\BandTab Studio"; Filename: "{app}\BandTabStudio.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\BandTabStudio.exe"; Description: "Launch BandTab Studio"; Flags: nowait postinstall skipifsilent
