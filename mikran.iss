[Setup]
; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

[Setup]
AppName=Mikran2S
AppVersion=1.0
DefaultDirName={autopf}\mikran2s
PrivilegesRequired=admin

[Files]
Source: "dist/mikran.exe"; DestDir: "{app}"
Source: "yoda.png"; DestDir: "{app}"
Source: "slack.txt"; DestDir: "{app}"

[Icons] 
Name: "{commonstartup}\Mikran2s"; Filename: "{app}\mikran.exe"
