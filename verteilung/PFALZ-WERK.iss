; Setup-Programm für PFALZ-WERK (Inno Setup 6). Baut aus dist\PFALZ-WERK die Datei PFALZ-WERK-Setup-<Fassung>.exe.
; Installiert ohne Administratorrechte in den eigenen Benutzerordner. Die Daten (Datenbank, Sicherungen) liegen
; getrennt im Ordner „Dokumente\PFALZ-WERK-Daten“ und bleiben bei Updates und beim Deinstallieren erhalten.
#ifndef Fassung
  #define Fassung "0"
#endif

[Setup]
AppId=PFALZ-WERK
AppName=PFALZ-WERK
AppVersion={#Fassung}
DefaultDirName={localappdata}\Programs\PFALZ-WERK
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PFALZ-WERK-Setup-{#Fassung}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=PFALZ-WERK

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktop"; Description: "Verknüpfung auf dem Desktop anlegen"; GroupDescription: "Zusätzlich:"

[InstallDelete]
; altes eingebettetes Python vor dem Update entfernen (Programmdateien werden überschrieben; Daten liegen nicht hier)
Type: filesandordirs; Name: "{app}\python"

[Files]
Source: "..\dist\PFALZ-WERK\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PFALZ-WERK"; Filename: "{app}\PFALZ-WERK starten.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\PFALZ-WERK"; Filename: "{app}\PFALZ-WERK starten.bat"; WorkingDir: "{app}"; Tasks: desktop

[Run]
Filename: "{app}\PFALZ-WERK starten.bat"; Description: "PFALZ-WERK jetzt starten"; WorkingDir: "{app}"; Flags: postinstall shellexec nowait skipifsilent
