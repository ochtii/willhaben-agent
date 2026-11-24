<#
  Willhaben KI-Agent - Installation unter Windows (10/11)
  Start: Doppelklick auf "install-windows.cmd" (ruft dieses Skript auf).

  Installiert nach %LOCALAPPDATA%\willhaben-agent NUR die Dateien aus laufzeit-dateien.txt,
  legt eine eigene Python-Umgebung an, erstellt Startmenue- und Desktop-Verknuepfung,
  traegt die App unter "Apps & Features" ein (mit Deinstallation) und bietet an,
  den heruntergeladenen Quellordner zu loeschen.

  Optionen:  -QuelleBehalten   Quellordner nicht loeschen und nicht fragen
             -QuelleLoeschen   Quellordner ohne Rueckfrage loeschen (ausser bei ungesicherten Git-Aenderungen)
  Anderer Ort: Umgebungsvariable WILLHABEN_AGENT_HOME setzen.
#>
param([switch]$QuelleBehalten, [switch]$QuelleLoeschen)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Quelle = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($env:WILLHABEN_AGENT_HOME) { $Ziel = $env:WILLHABEN_AGENT_HOME } else { $Ziel = Join-Path $env:LOCALAPPDATA "willhaben-agent" }
$AppName = "Willhaben KI-Agent"

function Info($t)  { Write-Host $t -ForegroundColor Gray }
function Ok($t)    { Write-Host ("[OK] " + $t) -ForegroundColor Green }
# Externe Programme ausfuehren, ohne dass Meldungen auf dem Fehlerkanal das Skript abbrechen (PowerShell 5.1)
function Nativ([scriptblock]$befehl) {
    $alt = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $befehl } finally { $ErrorActionPreference = $alt }
}
# Ordner im Hintergrund loeschen, sobald er nicht mehr benutzt wird (max. ca. 2 Minuten lang versuchen)
function Spaeter-Loeschen($ordner) {
    $cmd = "/c for /l %i in (1,1,60) do (timeout /t 2 /nobreak >nul & rmdir /s /q `"$ordner`" 2>nul & if not exist `"$ordner`" exit)"
    Start-Process -WindowStyle Hidden -FilePath "cmd.exe" -ArgumentList $cmd
}
function Warn($t)  { Write-Host ("! " + $t) -ForegroundColor Yellow }
function Fehler($t) {
    Write-Host ("X " + $t) -ForegroundColor Red
    Write-Host ""
    Read-Host "Enter zum Beenden" | Out-Null
    exit 1
}

Write-Host ""
Write-Host "== $AppName - Installation nach $Ziel" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Quelle "laufzeit-dateien.txt"))) { Fehler "laufzeit-dateien.txt fehlt in $Quelle" }

# ---------------------------------------------------------------- 1) Python 3.10+ mit Tkinter finden
function Finde-Python {
    $kandidaten = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @("3.13", "3.12", "3.11", "3.10")) { $kandidaten += , @("py", "-$v") }
    }
    foreach ($n in @("python", "python3")) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        # Microsoft-Store-Platzhalter (WindowsApps) ueberspringen - der oeffnet nur den Store
        if ($c -and ($c.Source -notlike "*\WindowsApps\*")) { $kandidaten += , @($c.Source) }
    }
    foreach ($k in $kandidaten) {
        $exe = $k[0]
        $argumente = @()
        if ($k.Count -gt 1) { $argumente = $k[1..($k.Count - 1)] }
        try {
            $pfad = Nativ { & $exe @argumente -c "import sys, tkinter, venv; assert sys.version_info >= (3, 10); print(sys.executable)" 2>$null }
            if ($LASTEXITCODE -eq 0 -and $pfad) { return ([string]($pfad | Select-Object -Last 1)).Trim() }
        } catch { }
    }
    return $null
}

$Py = Finde-Python
if (-not $Py) {
    Warn "Kein passendes Python (3.10 oder neuer, mit Tkinter) gefunden."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $a = Read-Host "Python 3.12 jetzt automatisch installieren? [J/n]"
        if ($a -eq "" -or $a -match "^[jJyY]") {
            Nativ { winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements }
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
            $Py = Finde-Python
        }
    }
}
if (-not $Py) {
    Fehler ("Bitte Python von https://www.python.org/downloads/ installieren (Haken bei 'tcl/tk and IDLE' " +
            "und 'Add python.exe to PATH' setzen) und die Installation danach erneut starten.")
}
Ok "Verwende Python: $Py"

# ---------------------------------------------------------------- 2) Nur die benoetigten Dateien kopieren
New-Item -ItemType Directory -Force -Path $Ziel | Out-Null
$QuelleVoll = (Resolve-Path $Quelle).Path.TrimEnd("\")
$ZielVoll = (Resolve-Path $Ziel).Path.TrimEnd("\")
if ($QuelleVoll -ne $ZielVoll) {
    $anzahl = 0
    foreach ($zeile in Get-Content (Join-Path $Quelle "laufzeit-dateien.txt") -Encoding UTF8) {
        $datei = ($zeile -replace "#.*$", "").Trim()
        if ($datei -eq "") { continue }
        $von = Join-Path $Quelle $datei
        if (-not (Test-Path $von)) { Fehler "$datei fehlt in $Quelle" }
        $nach = Join-Path $Ziel $datei
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $nach) | Out-Null
        Copy-Item -Force $von $nach
        $anzahl++
    }
    Ok "$anzahl Programmdateien nach $Ziel kopiert"
}

# ---------------------------------------------------------------- 3) Python-Umgebung + Pakete
$VenvPy = Join-Path $Ziel ".venv\Scripts\python.exe"
$VenvPyw = Join-Path $Ziel ".venv\Scripts\pythonw.exe"
if (Test-Path $VenvPy) {
    Nativ { & $VenvPy -c "import tkinter" 2>$null }
    if ($LASTEXITCODE -ne 0) { Remove-Item -Recurse -Force (Join-Path $Ziel ".venv") }
}
if (-not (Test-Path $VenvPy)) {
    Info "Lege Python-Umgebung an ..."
    Nativ { & $Py -m venv (Join-Path $Ziel ".venv") }
    if ($LASTEXITCODE -ne 0) { Fehler "Python-Umgebung konnte nicht angelegt werden" }
}
Info "Installiere Python-Pakete (kann ein paar Minuten dauern) ..."
Nativ { & $VenvPy -m pip install -q --disable-pip-version-check --upgrade pip }
Nativ { & $VenvPy -m pip install -q --disable-pip-version-check -r (Join-Path $Ziel "requirements.txt") }
if ($LASTEXITCODE -ne 0) { Fehler "Python-Pakete konnten nicht installiert werden (Internetverbindung?)" }
Nativ { & $VenvPy -c "import tkinter, requests, pydantic, sv_ttk; from google import genai" }
if ($LASTEXITCODE -ne 0) { Fehler "Installation unvollstaendig" }
$marke = Join-Path $Ziel ".pakete_ausstehend"
if (Test-Path $marke) { Remove-Item -Force $marke }
Ok "Python-Pakete installiert"

# ---------------------------------------------------------------- 4) Version merken + aufraeumen
Push-Location $Ziel
try {
    if ((Get-Command git -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $Quelle ".git"))) {
        $sha = ([string](Nativ { git -C $Quelle rev-parse HEAD })).Trim()
        $nummer = "?"
        if (([string](Nativ { git -C $Quelle rev-parse --is-shallow-repository })).Trim() -eq "false") {
            $vCommit = ([string](Nativ { git -C $Quelle log -1 --format=%H -- VERSION })).Trim()
            if ($vCommit) { $nummer = ([string](Nativ { git -C $Quelle rev-list --count "$vCommit..HEAD" })).Trim() }
            else { $nummer = ([string](Nativ { git -C $Quelle rev-list --count HEAD })).Trim() }
        }
        if ($sha) { Nativ { & $VenvPy updater.py --status $sha $nummer } }
    }
    Nativ { & $VenvPy updater.py --aufraeumen }
} finally { Pop-Location }

# ---------------------------------------------------------------- 5) Startdateien und Verknuepfungen
$ascii = New-Object System.Text.ASCIIEncoding
[IO.File]::WriteAllText((Join-Path $Ziel "willhaben-agent.cmd"),
    "@echo off`r`nrem Startet die Oberflaeche mit Protokoll im Konsolenfenster`r`n`"%~dp0.venv\Scripts\python.exe`" `"%~dp0gui.py`" %*`r`n", $ascii)
[IO.File]::WriteAllText((Join-Path $Ziel "willhaben-agent-cli.cmd"),
    "@echo off`r`nrem Terminal-Version, z.B.: willhaben-agent-cli --kategorie laptops --von 200 --bis 600 --bundesland wien`r`n`"%~dp0.venv\Scripts\python.exe`" `"%~dp0agent.py`" %*`r`n", $ascii)

$shell = New-Object -ComObject WScript.Shell
function Verknuepfung($pfad) {
    $lnk = $shell.CreateShortcut($pfad)
    $lnk.TargetPath = $VenvPyw
    $lnk.Arguments = "`"" + (Join-Path $Ziel "gui.py") + "`""
    $lnk.WorkingDirectory = $Ziel
    $lnk.IconLocation = (Join-Path $Ziel "icon.ico") + ",0"
    $lnk.Description = "Durchsucht willhaben.at und bewertet Angebote mit KI"
    $lnk.Save()
}
$startmenue = Join-Path ([Environment]::GetFolderPath("Programs")) "$AppName.lnk"
Verknuepfung $startmenue
Ok "Startmenue-Eintrag angelegt"
$desktop = [Environment]::GetFolderPath("Desktop")
if ($desktop -and (Test-Path $desktop)) {
    Verknuepfung (Join-Path $desktop "$AppName.lnk")
    Ok "Verknuepfung auf dem Desktop angelegt"
}

# ---------------------------------------------------------------- 6) Deinstallation + "Apps & Features"
$deinst = @'
# Willhaben KI-Agent deinstallieren (wird vom Installer erzeugt)
$ErrorActionPreference = "SilentlyContinue"
$Ziel = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "Willhaben KI-Agent"
Write-Host "== $AppName wird deinstalliert ..." -ForegroundColor Cyan
Remove-Item -Force (Join-Path ([Environment]::GetFolderPath("Programs")) "$AppName.lnk")
Remove-Item -Force (Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk")
Remove-Item -Recurse -Force "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\WillhabenKIAgent"
$konfig = Join-Path $env:APPDATA "willhaben-agent"
if (Test-Path $konfig) {
    $a = Read-Host "Auch Einstellungen und gespeicherte API-Keys ($konfig) loeschen? [j/N]"
    if ($a -match "^[jJyY]") { Remove-Item -Recurse -Force $konfig; Write-Host "Einstellungen geloescht." }
}
Write-Host "Ergebnisse in $env:USERPROFILE\willhaben-ergebnisse bleiben erhalten."
Set-Location $env:USERPROFILE
$cmd = "/c for /l %i in (1,1,60) do (timeout /t 2 /nobreak >nul & rmdir /s /q `"$Ziel`" 2>nul & if not exist `"$Ziel`" exit)"
Start-Process -WindowStyle Hidden -FilePath "cmd.exe" -ArgumentList $cmd
Write-Host "Fertig - der Programmordner wird entfernt, sobald dieses Fenster geschlossen ist." -ForegroundColor Green
Start-Sleep -Seconds 2
'@
[IO.File]::WriteAllText((Join-Path $Ziel "deinstallieren.ps1"), $deinst, (New-Object System.Text.UTF8Encoding $true))
[IO.File]::WriteAllText((Join-Path $Ziel "deinstallieren.cmd"),
    "@pushd `"%USERPROFILE%`" & powershell -NoProfile -ExecutionPolicy Bypass -File `"%~dp0deinstallieren.ps1`" & pause & exit /b`r`n", $ascii)

$version = Nativ { & $VenvPy -c "import sys; sys.path.insert(0, r'$Ziel'); import updater; print(updater.version_text())" 2>$null }
if (-not $version) { $version = "1.1" }
$reg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\WillhabenKIAgent"
New-Item -Force -Path $reg | Out-Null
New-ItemProperty -Force -Path $reg -Name DisplayName -Value $AppName | Out-Null
New-ItemProperty -Force -Path $reg -Name DisplayVersion -Value ([string]($version | Select-Object -Last 1)).Trim() | Out-Null
New-ItemProperty -Force -Path $reg -Name Publisher -Value "ochtii" | Out-Null
New-ItemProperty -Force -Path $reg -Name DisplayIcon -Value (Join-Path $Ziel "icon.ico") | Out-Null
New-ItemProperty -Force -Path $reg -Name InstallLocation -Value $Ziel | Out-Null
New-ItemProperty -Force -Path $reg -Name URLInfoAbout -Value "https://github.com/ochtii/willhaben-agent" | Out-Null
New-ItemProperty -Force -Path $reg -Name UninstallString -Value ("cmd.exe /c `"" + (Join-Path $Ziel "deinstallieren.cmd") + "`"") | Out-Null
New-ItemProperty -Force -Path $reg -Name NoModify -Value 1 -PropertyType DWord | Out-Null
New-ItemProperty -Force -Path $reg -Name NoRepair -Value 1 -PropertyType DWord | Out-Null
Ok "Unter 'Apps & Features' eingetragen (dort auch deinstallierbar)"

Write-Host ""
Nativ { & $VenvPy (Join-Path $Ziel "agent.py") --version }

# ---------------------------------------------------------------- 7) Quellordner entfernen (wird nicht mehr benoetigt)
if ($QuelleVoll -ne $ZielVoll) {
    $sicher = (Test-Path (Join-Path $Quelle "install.ps1")) -and (Test-Path (Join-Path $Quelle "laufzeit-dateien.txt"))
    $heim = $env:USERPROFILE.TrimEnd("\")
    if ($QuelleVoll -eq $heim -or $QuelleVoll.Length -le 3 -or $ZielVoll.StartsWith($QuelleVoll + "\")) { $sicher = $false }

    $standard = "j"
    $modus = "fragen"
    if ($QuelleBehalten) { $modus = "behalten" }
    if ($QuelleLoeschen) { $modus = "loeschen" }
    if ((Test-Path (Join-Path $Quelle ".git")) -and (Get-Command git -ErrorAction SilentlyContinue)) {
        $offen = Nativ { git -C $Quelle status --porcelain 2>$null }
        $ungepusht = Nativ { git -C $Quelle log --branches --not --remotes --oneline 2>$null }
        if ($offen -or $ungepusht) {
            Warn "$Quelle enthaelt ungespeicherte oder nicht gepushte Git-Aenderungen."
            $standard = "n"
            if ($modus -eq "loeschen") { $modus = "fragen" }
        }
    }
    if ($sicher -and $modus -ne "behalten") {
        $antwort = $standard
        if ($modus -eq "fragen") {
            $hinweis = "[J/n]"
            if ($standard -eq "n") { $hinweis = "[j/N]" }
            $antwort = Read-Host "Der Quellordner $Quelle wird nicht mehr benoetigt. Loeschen? $hinweis"
            if ($antwort -eq "") { $antwort = $standard }
        }
        if ($antwort -match "^[jJyY]") {
            Set-Location $env:USERPROFILE
            # erst loeschen, wenn dieses Fenster zu ist (das Skript laeuft gerade noch aus dem Ordner)
            Spaeter-Loeschen $QuelleVoll
            Ok "Quellordner wird entfernt, sobald dieses Fenster geschlossen ist: $Quelle"
        } else {
            Info "Quellordner behalten: $Quelle (kann jederzeit geloescht werden)"
        }
    }
}

Write-Host ""
Write-Host "Fertig! Starten ueber das Startmenue oder den Desktop: '$AppName'" -ForegroundColor Cyan
Write-Host "Updates: beim Start automatisch oder Einstellungen -> 'Nach Updates suchen ...'"
Write-Host "Deinstallieren: Einstellungen -> Apps -> '$AppName' (oder $Ziel\deinstallieren.cmd)"
Write-Host ""
Read-Host "Enter zum Schliessen" | Out-Null
