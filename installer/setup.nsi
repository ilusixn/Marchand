Unicode true
!include "MUI2.nsh"
Name "Marchand Studio"
OutFile "MarchandStudio-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\Marchand Studio"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ICON "stage\icon.ico"
!define MUI_UNICON "stage\icon.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\MarchandStudio.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Start Marchand Studio"
!insertmacro MUI_PAGE_WELCOME
!define MUI_LICENSEPAGE_CHECKBOX
!insertmacro MUI_PAGE_LICENSE "stage\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  nsExec::Exec `powershell -NoProfile -Command "Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $$_.Path -like '$INSTDIR\*' } | Stop-Process -Force"`
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\python"
  SetOutPath "$INSTDIR"
  File /r "stage\*.*"
  CreateShortCut "$DESKTOP\Marchand Studio.lnk" "$INSTDIR\MarchandStudio.exe" "" "$INSTDIR\MarchandStudio.exe" 0
  CreateDirectory "$SMPROGRAMS\Marchand Studio"
  CreateShortCut "$SMPROGRAMS\Marchand Studio\Marchand Studio.lnk" "$INSTDIR\MarchandStudio.exe" "" "$INSTDIR\MarchandStudio.exe" 0
  CreateShortCut "$SMPROGRAMS\Marchand Studio\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarchandStudio" "DisplayName" "Marchand Studio"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarchandStudio" "DisplayIcon" "$INSTDIR\MarchandStudio.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarchandStudio" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarchandStudio" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarchandStudio" "Publisher" "Marchand"
SectionEnd

Section "Uninstall"
  nsExec::Exec `powershell -NoProfile -Command "Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $$_.Path -like '$INSTDIR\*' } | Stop-Process -Force"`
  Delete "$DESKTOP\Marchand Studio.lnk"
  RMDir /r "$SMPROGRAMS\Marchand Studio"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarchandStudio"
SectionEnd
