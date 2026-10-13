#define MyAppName "AURIX AI"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Luigy Renan"
#define MyAppExeName "AURIX-AI.exe"

[Setup]
AppId={{90B7629B-9B8C-42A4-A338-7D3A77AF30D1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\AURIX AI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist-installer
OutputBaseFilename=AURIX-AI-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\AURIX AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\AURIX AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar o AURIX AI agora"; Flags: postinstall nowait skipifsilent
