; Instalador de Onitune para Windows (Inno Setup 6).
; No se compila a mano: lo hace build.py, que le pasa la versión y las carpetas:
;   ISCC.exe /DAppVersion=1.0.0 /DSourceDir=<carpeta de la app> /DOutputDir=<dist> installer\onitune.iss
;
; Se instala solo para el usuario (sin permisos de administrador) en
; %LOCALAPPDATA%\Programs\Onitune, como VS Code o Discord.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\carpeta\Onitune"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

[Setup]
; El AppId identifica a la app en Windows: NO cambiarlo nunca (si cambia,
; Windows cree que es otra app y no actualiza la instalación anterior).
AppId={{54E2849F-63CB-4C91-8011-7F025CDFDA58}
AppName=Onitune
AppVersion={#AppVersion}
AppVerName=Onitune {#AppVersion}
AppPublisher=angelqqi
AppPublisherURL=https://github.com/angelqqi/Onitune
AppSupportURL=https://github.com/angelqqi/Onitune/issues
AppUpdatesURL=https://github.com/angelqqi/Onitune/releases
VersionInfoVersion={#AppVersion}
; Sin admin: {autopf} pasa a ser %LOCALAPPDATA%\Programs
PrivilegesRequired=lowest
DefaultDirName={autopf}\Onitune
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=Onitune-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Onitune.exe
UninstallDisplayName=Onitune
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Casilla para el acceso directo del Escritorio (desmarcada por defecto)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Al actualizar, borra las librerías de la versión anterior para no mezclar archivos viejos
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Onitune"; Filename: "{app}\Onitune.exe"
Name: "{autodesktop}\Onitune"; Filename: "{app}\Onitune.exe"; Tasks: desktopicon

[Run]
; Casilla "Ejecutar Onitune" al terminar la instalación
Filename: "{app}\Onitune.exe"; Description: "{cm:LaunchProgram,Onitune}"; Flags: nowait postinstall skipifsilent

[Code]
// Al desinstalar: preguntar si también se borran ajustes, historial, yt-dlp y ffmpeg.
// Las canciones y videos descargados están en otras carpetas y nunca se tocan.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\Onitune');
    if DirExists(DataDir) and (not UninstallSilent) then
      if MsgBox('¿Borrar también los ajustes, el historial y los componentes descargados (yt-dlp y ffmpeg)?' + #13#10 + #13#10 +
                'Tus canciones y videos descargados no se borran.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
