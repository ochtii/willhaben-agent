@echo off
rem Willhaben KI-Agent - Installation unter Windows. Doppelklick genuegt.
rem Startet install.ps1 (PowerShell) aus diesem Ordner; das Arbeitsverzeichnis liegt ausserhalb,
rem damit der Quellordner nach der Installation geloescht werden kann.
pushd "%USERPROFILE%" & powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %* & exit /b
