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
API = f"https://api.github.com/repos/{REPO}"
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
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "willhaben-agent-updater"}
    tok = os.environ.get("GITHUB_TOKEN")             # optional, z.B. für private Repos
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout, **kw)
    except requests.RequestException as e:
        raise UpdateFehler(f"GitHub nicht erreichbar ({type(e).__name__})") from e
    if r.status_code == 404:
        raise UpdateFehler("Repository nicht gefunden (privat oder umbenannt?)")
    if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
        raise UpdateFehler("GitHub-Abfragelimit erreicht – bitte in einer Stunde erneut versuchen")
    if r.status_code >= 400:
        raise UpdateFehler(f"GitHub-Fehler {r.status_code}")
    return r


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


def remote_stand(timeout: float = 8) -> Stand:
    r = _get(f"{API}/commits/{BRANCH}", timeout)
    d = r.json()
    sha = d["sha"]
    c = d.get("commit", {})
    basis = _remote_text("VERSION", timeout).strip() or "1.0"
    # letzte Stelle = Commits seit der letzten Änderung der VERSION-Datei
    rv = _get(f"{API}/commits", timeout, params={"sha": BRANCH, "path": "VERSION", "per_page": 1}).json()
    if rv:
        v_sha = rv[0]["sha"]
        nummer = 0 if v_sha == sha else _get(f"{API}/compare/{v_sha}...{sha}", timeout).json().get("ahead_by", 0)
    else:
        r2 = _get(f"{API}/commits", timeout, params={"sha": BRANCH, "per_page": 1})
        m = re.search(r'[?&]page=(\d+)>; rel="last"', r2.headers.get("Link", ""))
        nummer = int(m.group(1)) if m else len(r2.json())
    return Stand(sha, nummer, c.get("committer", {}).get("date", ""), (c.get("message") or "").split("\n")[0], basis)


def _remote_text(pfad: str, timeout: float = 8) -> str:
    """Inhalt einer Datei im Repo (Stand main) über die GitHub-API."""
    import base64
    d = _get(f"{API}/contents/{pfad}", timeout, params={"ref": BRANCH}).json()
    return base64.b64decode(d.get("content", "")).decode("utf-8", "replace")


def verlauf(anzahl: int = 12, timeout: float = 8) -> list[dict]:
    """Versionsverlauf aus CHANGELOG.md auf GitHub: [{version, datum, punkte: [...]}], neueste zuerst."""
    eintraege, aktuell = [], None
    for zeile in _remote_text("CHANGELOG.md", timeout).splitlines():
        m = re.match(r"^##\s+v?(\d+\.\d+\.\d+)\s*(?:[–—-]\s*(.+))?$", zeile.strip())
        if m:
            aktuell = {"version": m.group(1), "datum": (m.group(2) or "").strip(), "punkte": []}
            eintraege.append(aktuell)
        elif aktuell and zeile.strip().startswith(("- ", "* ")):
            aktuell["punkte"].append(zeile.strip()[2:].strip())
        elif aktuell and aktuell["punkte"] and zeile.startswith("  ") and zeile.strip():
            aktuell["punkte"][-1] += " " + zeile.strip()
    return eintraege[:anzahl]


def pruefen(app_dir: Path = APP_DIR, timeout: float = 8) -> UpdateInfo:
    """Vergleicht den installierten Stand mit GitHub. Wirft keine Fehler (siehe .fehler)."""
    basis = basis_version(app_dir)
    lokal = lokaler_stand(app_dir)
    info = UpdateInfo(lokal, None, basis)
    try:
        info.remote = remote_stand(timeout)
        if lokal.sha == info.remote.sha:
            lokal.nummer = info.remote.nummer
            return info
        if not lokal.sha:
            info.neuer = True
            info.aenderungen = [info.remote.nachricht]
            return info
        r = None
        for versuch in range(2):          # direkt nach einem Push kennt GitHub den Vergleich manchmal kurz noch nicht
            try:
                r = _get(f"{API}/compare/{lokal.sha}...{info.remote.sha}", timeout)
                break
            except UpdateFehler as e:
                if "nicht gefunden" not in str(e):
                    raise
                if versuch == 0:
                    time.sleep(2)
        if r is None:
            if lokal.nummer is not None and info.remote.nummer and lokal.nummer < info.remote.nummer:
                info.neuer = True              # anhand der Versionsnummer entscheiden
                info.aenderungen = [info.remote.nachricht]
            else:
                info.fehler = (f"Der installierte Stand {lokal.kurz} ist nicht auf GitHub – vermutlich eine lokale, "
                               "noch nicht gepushte Entwicklungsversion. Kein Update nötig.")
            return info
        cmp = r.json()
        behind = cmp.get("ahead_by", 0)              # remote ist so viele Commits voraus
        if lokal.nummer is None and lokal.basis == info.remote.basis and cmp.get("behind_by", 0) == 0:
            lokal.nummer = info.remote.nummer - behind if info.remote.nummer >= behind else None
        info.neuer = behind > 0
        info.aenderungen = [((c.get("commit") or {}).get("message") or "").split("\n")[0]
                            for c in reversed(cmp.get("commits", []))]
    except UpdateFehler as e:
        info.fehler = str(e)
    except Exception as e:  # z.B. lokaler Commit existiert auf GitHub nicht (lokale Entwicklung)
        info.fehler = f"Vergleich nicht möglich ({type(e).__name__})"
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
    a = ap.parse_args()
    if a.status:
        _status_schreiben(APP_DIR, Stand(a.status[0], int(a.status[1]) if a.status[1].isdigit() else None),
                          laufzeit_dateien(APP_DIR))
    if a.aufraeumen:
        aufraeumen(APP_DIR)
        alte_menueeintraege_entfernen()
