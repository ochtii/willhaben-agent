"""Update-Funktion: prüft auf GitHub, ob eine neuere Version vorliegt, und installiert sie.

Versionsnummer: <VERSION-Datei>.<Commits seit der letzten Änderung der VERSION-Datei>, z.B. 1.1.3.
Ändert sich VERSION (z.B. auf 1.2), beginnt die letzte Stelle wieder bei 0; danach erhöht sie sich bei
jedem Commit/Push automatisch.

Installationsarten:
  * Git-Klon      -> `git pull --ff-only` (lokale Änderungen werden NICHT überschrieben)
  * ZIP/Kopie     -> neueste Version als ZIP von GitHub laden und Dateien ersetzen
Danach werden die Python-Pakete aus requirements.txt aktualisiert.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import requests

import plattform

REPO = "ochtii/willhaben-agent"
BRANCH = "main"
REPO_URL = f"https://github.com/{REPO}"
APP_DIR = Path(__file__).resolve().parent
STATUS_DATEI = ".installed_version.json"      # nicht im Repo (siehe .gitignore)
MANIFEST = "laufzeit-dateien.txt"             # welche Dateien eine Installation braucht
# Im Installationsordner nie anfassen (Laufzeit-Umgebung, Startskripte, Update-Status)
PAKETE_AUSSTEHEND = ".pakete_ausstehend"     # Windows: Pakete beim nächsten Start aktualisieren
GESCHUETZT = {".venv", ".git", STATUS_DATEI, PAKETE_AUSSTEHEND, "__pycache__",
              "willhaben-agent", "willhaben-agent-cli",                       # Linux-Startskripte
              "willhaben-agent.cmd", "willhaben-agent-cli.cmd",               # Windows-Startskripte
              "deinstallieren.cmd", "deinstallieren.ps1"}                     # Windows-Deinstallation


class UpdateFehler(Exception):
    pass


@dataclass
class Stand:
    sha: str = ""
    nummer: int | None = None          # Commits seit der letzten Änderung der VERSION-Datei
    datum: str = ""
    nachricht: str = ""
    basis: str = ""                    # Inhalt der VERSION-Datei, z.B. "1.1"

    def version(self, basis: str | None = None) -> str:
        b = self.basis or basis or "1.0"
        return f"{b}.{self.nummer}" if self.nummer is not None else f"{b}.?"

    @property
    def kurz(self) -> str:
        return self.sha[:7] if self.sha else "unbekannt"


@dataclass
class UpdateInfo:
    lokal: Stand
    remote: Stand | None
    basis: str
    neuer: bool = False
    aenderungen: list[str] = field(default_factory=list)   # Commit-Nachrichten (neueste zuerst)
    fehler: str = ""

    @property
    def version_lokal(self) -> str:
        return self.lokal.version(self.basis)

    @property
    def version_remote(self) -> str:
        return self.remote.version(self.basis) if self.remote else "?"


# --------------------------------------------------------------------------- Hilfen

def basis_version(app_dir: Path = APP_DIR) -> str:
    try:
        return (app_dir / "VERSION").read_text().strip() or "1.0"
    except OSError:
        return "1.0"


def _git(app_dir: Path, *args, timeout=60) -> str:
    r = subprocess.run(["git", "-C", str(app_dir), *args], capture_output=True, text=True, timeout=timeout,
                       **plattform.OHNE_FENSTER)
    if r.returncode != 0:
        raise UpdateFehler((r.stderr or r.stdout).strip() or f"git {' '.join(args)} fehlgeschlagen")
    return r.stdout.strip()


def ist_git(app_dir: Path = APP_DIR) -> bool:
    if not (app_dir / ".git").exists() or not shutil.which("git"):
        return False
    try:
        _git(app_dir, "rev-parse", "HEAD", timeout=10)
        return True
    except (UpdateFehler, OSError, subprocess.SubprocessError):
        return False


def laufzeit_dateien(ordner: Path) -> list[str] | None:
    """Liste der benötigten Dateien aus laufzeit-dateien.txt (None, wenn die Liste fehlt)."""
    try:
        zeilen = (ordner / MANIFEST).read_text().splitlines()
    except OSError:
        return None
    out = []
    for z in zeilen:
        z = z.strip()
        if z and not z.startswith("#") and ".." not in z and not z.startswith("/"):
            out.append(z)
    return out


def aufraeumen(app_dir: Path = APP_DIR, erlaubt: set[str] | None = None, log=print) -> list[str]:
    """Entfernt im Installationsordner alles, was nicht zum Betrieb/Update gebraucht wird.
    Nie in einem Git-Klon (Entwicklung) – dort wird nichts gelöscht."""
    if (app_dir / ".git").exists():
        return []
    if erlaubt is None:
        liste = laufzeit_dateien(app_dir)
        if not liste:
            return []                      # ohne Liste lieber nichts löschen
        erlaubt = set(liste)
    entfernt = []
    for p in sorted(app_dir.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        rel = p.relative_to(app_dir).as_posix()
        if rel.split("/")[0] in GESCHUETZT:
            continue
        if p.is_dir():
            if not any(p.iterdir()):
                p.rmdir()
            continue
        if rel not in erlaubt:
            p.unlink()
            entfernt.append(rel)
    if entfernt:
        log(f"🧹 {len(entfernt)} nicht benötigte Dateien entfernt: {', '.join(entfernt[:8])}"
            + (" …" if len(entfernt) > 8 else ""))
    return entfernt


def alte_menueeintraege_entfernen(log=print) -> list[str]:
    """Entfernt Startmenü-Einträge früherer Versionen (z.B. den zweiten Eintrag „… (mit Terminal)“)."""
    if plattform.IST_WINDOWS:
        return []
    apps = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
    entfernt = []
    for name in ("willhaben-agent-terminal.desktop",):
        p = apps / name
        if p.is_file() and "willhaben" in p.read_text(errors="ignore").lower():
            p.unlink()
            entfernt.append(name)
    if entfernt:
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", str(apps)], capture_output=True, timeout=30)
        log("🧹 Doppelten Startmenü-Eintrag entfernt: " + ", ".join(entfernt))
    return entfernt


def _status_lesen(app_dir: Path) -> dict:
    try:
        return json.loads((app_dir / STATUS_DATEI).read_text())
    except (OSError, ValueError):
        return {}


def _status_schreiben(app_dir: Path, stand: Stand, dateien: list[str] | None = None):
    data = {"sha": stand.sha, "nummer": stand.nummer, "datum": stand.datum, "aktualisiert": time.time()}
    if dateien is not None:
        data["dateien"] = sorted(dateien)
    (app_dir / STATUS_DATEI).write_text(json.dumps(data, indent=1))


def _get(url: str, timeout: float, **kw) -> requests.Response:
    """HTTP-Abruf ohne GitHub-API (die erlaubt ohne Anmeldung nur 60 Abfragen pro Stunde)."""
    headers = {"User-Agent": "git/2.45.0 willhaben-agent-updater"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, **kw)
    except requests.RequestException as e:
        raise UpdateFehler(f"GitHub nicht erreichbar ({type(e).__name__})") from e
    if r.status_code == 404:
        raise UpdateFehler("Repository oder Datei nicht gefunden (privat oder umbenannt?)")
    if r.status_code == 429:
        raise UpdateFehler("GitHub meldet zu viele Anfragen – bitte in ein paar Minuten erneut versuchen")
    if r.status_code >= 400:
        raise UpdateFehler(f"GitHub-Fehler {r.status_code}")
    return r


def _version_tupel(v: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return None


def _changelog_lesen(text: str) -> list[dict]:
    """CHANGELOG.md -> [{version, datum, punkte: [...]}], neueste zuerst."""
    eintraege, aktuell = [], None
    for zeile in text.splitlines():
        m = re.match(r"^##\s+v?(\d+\.\d+\.\d+)\s*(?:[–—-]\s*(.+))?$", zeile.strip())
        if m:
            aktuell = {"version": m.group(1), "datum": (m.group(2) or "").strip(), "punkte": []}
            eintraege.append(aktuell)
        elif aktuell and zeile.strip().startswith(("- ", "* ")):
            aktuell["punkte"].append(zeile.strip()[2:].strip())
        elif aktuell and aktuell["punkte"] and zeile.startswith("  ") and zeile.strip():
            aktuell["punkte"][-1] += " " + zeile.strip()
    return eintraege


# --------------------------------------------------------------------------- Stände

def lokaler_stand(app_dir: Path = APP_DIR) -> Stand:
    """Installierter Stand: aus Git (bevorzugt) oder aus der Statusdatei des letzten Updates."""
    if ist_git(app_dir):
        try:
            sha = _git(app_dir, "rev-parse", "HEAD", timeout=10)
            nummer = None
            if _git(app_dir, "rev-parse", "--is-shallow-repository", timeout=10) == "false":
                v_commit = _git(app_dir, "log", "-1", "--format=%H", "--", "VERSION", timeout=10)
                nummer = int(_git(app_dir, "rev-list", "--count", f"{v_commit}..HEAD" if v_commit else "HEAD",
                                  timeout=10))
            else:
                st = _status_lesen(app_dir)
                nummer = st.get("nummer") if st.get("sha") == sha else None
            msg = _git(app_dir, "log", "-1", "--format=%s", timeout=10)
            datum = _git(app_dir, "log", "-1", "--format=%cI", timeout=10)
            return Stand(sha, nummer, datum, msg, basis_version(app_dir))
        except (UpdateFehler, ValueError, OSError, subprocess.SubprocessError):
            pass
    st = _status_lesen(app_dir)
    return Stand(st.get("sha", ""), st.get("nummer"), st.get("datum", ""), "", basis_version(app_dir))


def remote_sha(timeout: float = 8) -> str:
    """Neuester Commit auf GitHub – über das Git-Protokoll (wie git pull), nicht über die limitierte API."""
    r = _get(f"{REPO_URL}.git/info/refs", timeout, params={"service": "git-upload-pack"})
    m = re.search(rb"([0-9a-f]{40}) refs/heads/" + BRANCH.encode() + rb"\n", r.content)
    if not m:
        raise UpdateFehler("Stand auf GitHub nicht lesbar")
    return m.group(1).decode()


def _remote_text(pfad: str, timeout: float = 8, ref: str = BRANCH) -> str:
    """Inhalt einer Datei im Repo über raw.githubusercontent.com (ohne API-Limit)."""
    r = _get(f"https://raw.githubusercontent.com/{REPO}/{ref}/{pfad}", timeout)
    r.encoding = "utf-8"
    return r.text


def remote_stand(timeout: float = 8, sha: str | None = None) -> tuple[Stand, list[dict]]:
    """Stand auf GitHub: Commit per Git-Protokoll, Versionsnummer und Änderungen aus CHANGELOG.md dieses Commits.
    Die oberste Changelog-Überschrift ist laut Projektregel genau die Version dieses Commits."""
    sha = sha or remote_sha(timeout)
    basis = _remote_text("VERSION", timeout, sha).strip() or "1.0"
    eintraege = _changelog_lesen(_remote_text("CHANGELOG.md", timeout, sha))
    nummer, datum, nachricht = None, "", ""
    if eintraege:
        oben = eintraege[0]
        teile = oben["version"].rsplit(".", 1)
        if teile[0] == basis:
            nummer = int(teile[1])
        datum = oben["datum"]
        nachricht = oben["punkte"][0] if oben["punkte"] else ""
    return Stand(sha, nummer, datum, nachricht, basis), eintraege


def status_vom_server(app_dir: Path = APP_DIR, timeout: float = 8) -> bool:
    """Für ZIP-Installationen ohne Git: Entsprechen die installierten Programmdateien dem neuesten Stand auf GitHub,
    wird dieser Stand (Commit + Versionsnummer) gemerkt. Sonst bleibt der Stand unbekannt."""
    stand, _ = remote_stand(timeout)
    for datei in ("gui.py", "updater.py", "providers.py", "VERSION"):
        lokal = (app_dir / datei).read_bytes().replace(b"\r\n", b"\n") if (app_dir / datei).exists() else None
        if lokal is None or lokal != _remote_text(datei, timeout, stand.sha).encode("utf-8").replace(b"\r\n", b"\n"):
            return False
    _status_schreiben(app_dir, stand, laufzeit_dateien(app_dir))
    return True


def verlauf(anzahl: int = 12, timeout: float = 8) -> list[dict]:
    """Versionsverlauf aus CHANGELOG.md auf GitHub: [{version, datum, punkte: [...]}], neueste zuerst."""
    return _changelog_lesen(_remote_text("CHANGELOG.md", timeout))[:anzahl]


def pruefen(app_dir: Path = APP_DIR, timeout: float = 8) -> UpdateInfo:
    """Vergleicht den installierten Stand mit GitHub. Wirft keine Fehler (siehe .fehler).

    Nutzt keine GitHub-API (60 Abfragen/Stunde ohne Anmeldung), sondern das Git-Protokoll und
    raw.githubusercontent.com – beides ohne dieses Limit."""
    basis = basis_version(app_dir)
    lokal = lokaler_stand(app_dir)
    info = UpdateInfo(lokal, None, basis)
    try:
        info.remote, eintraege = remote_stand(timeout)
        if lokal.sha == info.remote.sha:
            if info.remote.nummer is not None:
                lokal.nummer = info.remote.nummer
            return info
        v_lokal = _version_tupel(info.version_lokal) if lokal.nummer is not None else None
        v_remote = _version_tupel(info.version_remote) if info.remote.nummer is not None else None
        if lokal.sha and ist_git(app_dir):
            try:                       # Git-Klon: liegt der GitHub-Stand schon in der eigenen Historie?
                _git(app_dir, "merge-base", "--is-ancestor", info.remote.sha, "HEAD", timeout=10)
                return info            # ja -> lokale (Entwicklungs-)Version ist gleich oder neuer
            except (UpdateFehler, OSError, subprocess.SubprocessError):
                pass                   # nein oder unbekannt (noch nicht geholt)
        if v_lokal and v_remote:
            info.neuer = v_remote > v_lokal
            if not info.neuer:
                return info            # lokale Version ist gleich oder neuer – kein Update nötig
        else:
            info.neuer = True          # Version unbekannt, aber anderer Stand auf GitHub
        if info.neuer:
            for e in eintraege:
                v = _version_tupel(e["version"])
                if v_lokal and v and v <= v_lokal:
                    break
                info.aenderungen += [f"v{e['version']}: {p}" for p in e["punkte"]]
            if not info.aenderungen and info.remote.nachricht:
                info.aenderungen = [info.remote.nachricht]
    except UpdateFehler as e:
        info.fehler = str(e)
    except Exception as e:
        info.fehler = f"Update-Prüfung nicht möglich ({type(e).__name__})"
    return info


# --------------------------------------------------------------------------- Installation

def _pakete(app_dir: Path, log):
    req = app_dir / "requirements.txt"
    if not req.exists():
        return
    if plattform.IST_WINDOWS:
        # Windows sperrt Dateien geladener Pakete -> erst beim nächsten Start (vor dem Laden) aktualisieren
        (app_dir / PAKETE_AUSSTEHEND).write_text("1")
        log("Python-Pakete werden beim nächsten Start aktualisiert")
        return
    log("Python-Pakete werden aktualisiert …")
    r = subprocess.run([plattform.python_konsole(), "-m", "pip", "install", "-q", "-r", str(req)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        log("⚠ Pakete konnten nicht aktualisiert werden: " + (r.stderr or r.stdout).strip()[-300:])
    else:
        log("✔ Python-Pakete aktuell")


def _update_git(app_dir: Path, ziel: Stand, log):
    geaendert = [z for z in _git(app_dir, "status", "--porcelain", "--untracked-files=no").splitlines() if z.strip()]
    if geaendert:
        raise UpdateFehler("Es gibt lokale Änderungen an Programmdateien – Update abgebrochen, damit nichts "
                           "verloren geht:\n  " + "\n  ".join(geaendert[:8])
                           + "\nÄnderungen sichern (git stash) oder verwerfen und erneut versuchen.")
    log("Lade Änderungen von GitHub (git pull) …")
    _git(app_dir, "pull", "--ff-only", "origin", BRANCH, timeout=300)
    neu = _git(app_dir, "rev-parse", "HEAD")
    _status_schreiben(app_dir, Stand(neu, ziel.nummer if neu == ziel.sha else None, ziel.datum))
    log(f"✔ Auf Stand {neu[:7]}")


def _update_zip(app_dir: Path, ziel: Stand, log):
    log("Lade neueste Version als ZIP von GitHub …")
    url = f"https://codeload.github.com/{REPO}/zip/{ziel.sha or 'refs/heads/' + BRANCH}"
    try:
        r = requests.get(url, timeout=120, headers={"User-Agent": "willhaben-agent-updater"})
        r.raise_for_status()
    except requests.RequestException as e:
        raise UpdateFehler(f"Download fehlgeschlagen ({e})") from e
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(tmp)
        wurzel = next(Path(tmp).iterdir())                     # <repo>-<sha>/
        liste = laufzeit_dateien(wurzel)
        if liste:      # nur die Dateien übernehmen, die laut neuer Version zum Betrieb nötig sind
            neue = [rel for rel in liste if (wurzel / rel).is_file()]
        else:          # ältere Version ohne Liste: alles übernehmen
            neue = [p.relative_to(wurzel).as_posix() for p in wurzel.rglob("*") if p.is_file()]
        alte = set(_status_lesen(app_dir).get("dateien", []))
        for rel in neue:
            if rel.split("/")[0] in GESCHUETZT:
                continue
            ziel_pfad = app_dir / rel
            ziel_pfad.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wurzel / rel, ziel_pfad)
        if liste:
            aufraeumen(app_dir, set(neue), log)
        else:
            for rel in alte - set(neue):                       # auf GitHub gelöschte Dateien entfernen
                if rel.split("/")[0] not in GESCHUETZT and (app_dir / rel).is_file():
                    (app_dir / rel).unlink()
    _status_schreiben(app_dir, ziel, neue)
    log(f"✔ {len(neue)} Dateien aktualisiert")


def installieren(info: UpdateInfo, app_dir: Path = APP_DIR, log=print) -> str:
    """Installiert den Stand info.remote. Gibt die neue Versionsnummer zurück."""
    if not info.remote:
        raise UpdateFehler(info.fehler or "Kein Update-Stand bekannt")
    if ist_git(app_dir):
        _update_git(app_dir, info.remote, log)
    else:
        _update_zip(app_dir, info.remote, log)
    _pakete(app_dir, log)
    return info.remote.version(basis_version(app_dir))


def neu_starten():
    """Startet das laufende Programm mit denselben Argumenten neu."""
    plattform.neu_starten()


def ausstehende_pakete_installieren(app_dir: Path = APP_DIR) -> bool:
    """Nach einem Update unter Windows: requirements.txt installieren, bevor Pakete geladen werden."""
    marke = app_dir / PAKETE_AUSSTEHEND
    if not marke.exists():
        return False
    req = app_dir / "requirements.txt"
    r = subprocess.run([plattform.python_konsole(), "-m", "pip", "install", "-q", "-r", str(req)],
                       capture_output=True, text=True, timeout=900, **plattform.OHNE_FENSTER)
    if r.returncode == 0:
        marke.unlink(missing_ok=True)
    return r.returncode == 0


def version_text(app_dir: Path = APP_DIR) -> str:
    st = lokaler_stand(app_dir)
    return st.version(basis_version(app_dir))


if __name__ == "__main__":
    # Hilfsbefehle für install.sh / install.ps1
    import argparse
    ap = argparse.ArgumentParser(description="Hilfsbefehle für den Installer")
    ap.add_argument("--aufraeumen", action="store_true", help="nicht benötigte Dateien im Installationsordner entfernen")
    ap.add_argument("--status", nargs=2, metavar=("SHA", "NUMMER"), help="installierten Stand merken")
    ap.add_argument("--status-vom-server", action="store_true",
                    help="ZIP-Installation ohne Git: Stand von GitHub übernehmen, wenn die Dateien übereinstimmen")
    a = ap.parse_args()
    if a.status_vom_server and not _status_lesen(APP_DIR).get("sha"):
        try:
            print("Stand:", "erkannt" if status_vom_server() else "nicht eindeutig (wird beim ersten Update gesetzt)")
        except Exception as e:                       # offline o.ä. – kein Problem, nur ohne Versionsnummer
            print(f"Stand nicht ermittelbar ({type(e).__name__})")
    if a.status:
        _status_schreiben(APP_DIR, Stand(a.status[0], int(a.status[1]) if a.status[1].isdigit() else None),
                          laufzeit_dateien(APP_DIR))
    if a.aufraeumen:
        aufraeumen(APP_DIR)
        alte_menueeintraege_entfernen()
