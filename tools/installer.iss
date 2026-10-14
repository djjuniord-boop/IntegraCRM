; Instalator IntegraCRM (Inno Setup) – budowany w GitHub Actions z folderu pkg\IntegraCRM.
; Instaluje do %LOCALAPPDATA%\IntegraCRM bez uprawnień administratora (aktualizacje programu
; podmieniają pliki w app\, więc folder musi być zapisywalny dla użytkownika).
; Folder data\ (ustawienia, sesja) nigdy nie jest nadpisywany ani usuwany.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1E7A52-3F4B-4D8E-9A61-1B2C3D4E5F60}
AppName=IntegraCRM
AppVersion={#AppVersion}
AppPublisher=Latex Serwis
DefaultDirName={localappdata}\IntegraCRM
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..
OutputBaseFilename=IntegraCRM-setup
SetupIconFile=..\app\assets\icon.ico
UninstallDisplayIcon={app}\IntegraCRM.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "Ikona na pulpicie"; Flags: checkedonce

[Files]
Source: "..\pkg\IntegraCRM\*"; DestDir: "{app}"; Excludes: "data\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\pkg\IntegraCRM\data\*"; DestDir: "{app}\data"; Flags: onlyifdoesntexist uninsneveruninstall recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\IntegraCRM"; Filename: "{app}\IntegraCRM.exe"
Name: "{autodesktop}\IntegraCRM"; Filename: "{app}\IntegraCRM.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\IntegraCRM.exe"; Description: "Uruchom IntegraCRM"; Flags: nowait postinstall skipifsilent
