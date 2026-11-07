#define MyAppName "BandTab Studio"
#ifndef MyAppVersion
  #define MyAppVersion "0.2.1"
#endif
[Setup]
AppId={{C893045E-E753-491D-93B0-FD1EF9088E15}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=BandTab
AppPublisherURL=https://github.com/Jason-TongR/Muscic-change-to-Band-Tab
DefaultDirName={localappdata}\Programs\BandTab Studio
DefaultGroupName=BandTab Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename=BandTabStudio-Windows-x64-Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BandTabStudio.exe
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.DesktopIcon=创建桌面快捷方式
chinesesimplified.Associate=将 BandTab 添加到 .bandtab 项目的打开方式
chinesesimplified.Launch=启动 BandTab Studio
english.DesktopIcon=Create a desktop shortcut
english.Associate=Add BandTab to Open with for .bandtab projects
english.Launch=Launch BandTab Studio

[Files]
Source: "..\dist\BandTabStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BandTab Studio"; Filename: "{app}\BandTabStudio.exe"; WorkingDir: "{app}"
Name: "{group}\使用说明"; Filename: "{app}\使用说明-Windows.txt"
Name: "{autodesktop}\BandTab Studio"; Filename: "{app}\BandTabStudio.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "{cm:DesktopIcon}"; Flags: unchecked
Name: associate; Description: "{cm:Associate}"

[Registry]
; Per-user OpenWith registration; never replace another application's default.
Root: HKA; Subkey: "Software\Classes\.bandtab\OpenWithProgids"; ValueType: string; ValueName: "BandTabStudio.Project"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\BandTabStudio.Project"; ValueType: string; ValueName: ""; ValueData: "BandTab Studio Project"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\BandTabStudio.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\BandTabStudio.exe,0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\BandTabStudio.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\BandTabStudio.exe"" --open ""%1"""; Tasks: associate

[Run]
Filename: "{app}\BandTabStudio.exe"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent
; User projects live outside {app}; uninstall deliberately retains that library.
