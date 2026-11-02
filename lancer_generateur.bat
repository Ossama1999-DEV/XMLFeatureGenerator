@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 houston_xml_generator.py
) else (
  python houston_xml_generator.py
)
if errorlevel 1 (
  echo.
  echo Echec du lancement. Installe Python 3 avec Tkinter et verifie PATH.
  pause
)
