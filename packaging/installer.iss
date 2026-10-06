; Installer for Kara.
;
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
;
; Installs per user, under Local AppData, so Windows never asks for an
; administrator password. A dictation tool is not worth a UAC prompt, and asking
; for one is what makes people close the window and give up.

#define AppName        "Kara"
#define AppPublisher   "bryramirezp"
#define AppURL         "https://github.com/bryramirezp/kara"
#define AppExeName     "Kara.exe"

; Passed in by packaging/build.py, which reads __version__ out of the source so
; the version is written down in exactly one place. The fallback only matters
; when someone runs ISCC by hand.
#ifndef AppVersion
  #define AppVersion "0.3.4"
#endif

#ifdef GpuBuild
  #define SetupFlavor "-GPU"
#else
  #define SetupFlavor ""
#endif

[Setup]
AppId={{7C1B4E62-9A3D-4F58-B0E7-2D6A5F8C1E90}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases

; Use the process environment rather than the Shell Folder registry value.
; This keeps the per-user install working in restricted Windows profiles too.
DefaultDirName={%LOCALAPPDATA}\Programs\Kara
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=..\dist
OutputBaseFilename=Kara-Setup{#SetupFlavor}-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
VersionInfoVersion={#AppVersion}

#ifdef SignKara
; packaging/build.py passes the provider command as /Skara=... and signs the
; setup and uninstaller after Kara.exe has already been signed.
SignTool=kara
SignedUninstaller=yes
#endif

[Languages]
Name: "english";             MessagesFile: "compiler:Default.isl"
Name: "spanish";              MessagesFile: "compiler:Languages\Spanish.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "french";               MessagesFile: "compiler:Languages\French.isl"
Name: "german";               MessagesFile: "compiler:Languages\German.isl"
Name: "italian";              MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked
Name: "startup";     Description: "Start Kara when Windows starts"

[Files]
Source: "..\dist\Kara\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";  Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";      Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Visible in Windows Settings > Apps > Startup, unlike a shortcut buried in
; the Startup folder.  Quotes keep the per-user AppData path safe if it has
; spaces, and uninsdeletevalue removes it when Kara is uninstalled.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "Kara"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[InstallDelete]
; 0.3.2 used this legacy mechanism.  Remove it on every install so an upgrade
; cannot start two copies at login.
Type: files; Name: "{userstartup}\{#AppName}.lnk"
; CPU replaces GPU as well as GPU replacing CPU. Inno only copies source files,
; so remove CUDA left behind by a prior NVIDIA edition without touching settings.
#ifndef GpuBuild
Type: filesandordirs; Name: "{app}\_internal\nvidia"
#endif

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The app is a tray program: it can still be running when the uninstaller
; starts, and a leftover shortcut would point at nothing.
Type: files; Name: "{userstartup}\{#AppName}.lnk"

[Code]
function KaraUILang(): String;
begin
  case ActiveLanguage of
    'spanish': Result := 'es';
    'brazilianportuguese': Result := 'pt';
    'french': Result := 'fr';
    'german': Result := 'de';
    'italian': Result := 'it';
  else
    Result := 'en';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsDir, SettingsFile: String;
begin
  if CurStep = ssPostInstall then begin
    // A user can deselect the task while upgrading. [Registry] then does not
    // create a value, but it also cannot remove the value from a prior install.
    if not WizardIsTaskSelected('startup') then
      RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Kara');

    SettingsDir := GetEnv('LOCALAPPDATA') + '\Kara';
    SettingsFile := SettingsDir + '\settings.json';
    // Only seed on a first install. An upgrade or repair must never overwrite
    // a UI language the user already chose from inside the app -- that would
    // silently undo Settings -> APP LANGUAGE every time a new version installs.
    if not FileExists(SettingsFile) then begin
      ForceDirectories(SettingsDir);
      SaveStringToFile(SettingsFile,
        '{"ui_language": "' + KaraUILang() + '"}', False);
    end;
  end;
end;
