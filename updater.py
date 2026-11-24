"""Update-Funktion: prüft auf GitHub, ob eine neuere Version vorliegt, und installiert sie.

Versionsnummer: <VERSION-Datei>.<Anzahl Commits auf main>, z.B. 1.0.12.
Die letzte Stelle erhöht sich dadurch bei jedem Commit/Push automatisch.

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

REPO = "ochtii/willhaben-agent"
BRANCH = "main"
API = f"https://api.github.com/repos/{REPO}"
REPO_URL = f"https://github.com/{REPO}"
APP_DIR = Path(__file__).resolve().parent
STATUS_DATEI = ".installed_version.json"      # nicht im Repo (siehe .gitignore)
MANIFEST = "laufzeit-dateien.txt"             # welche Dateien eine Installation braucht
# Im Installationsordner nie anfassen (Laufzeit-Umgebung, Startskripte, Update-Status)
GESCHUETZT = {".venv", ".git", STATUS_DATEI, "willhaben-agent", "willhaben-agent-cli", "__pycache__"}


class UpdateFehler(Exception):
    pass


@dataclass
class Stand:
    sha: str = ""
    nummer: int | None = None          # Anzahl Commits bis zu diesem Stand
    datum: str = ""
    nachricht: str = ""

    def version(self, basis: str) -> str:
        return f"{basis}.{self.nummer}" if self.nummer is not None else f"{basis}.?"

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
    r = subprocess.run(["git", "-C", str(app_dir), *args], capture_output=True, text=True, timeout=timeout)
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
                nummer = int(_git(app_dir, "rev-list", "--count", "HEAD", timeout=10))
            else:
                st = _status_lesen(app_dir)
                nummer = st.get("nummer") if st.get("sha") == sha else None
            msg = _git(app_dir, "log", "-1", "--format=%s", timeout=10)
            datum = _git(app_dir, "log", "-1", "--format=%cI", timeout=10)
            return Stand(sha, nummer, datum, msg)
        except (UpdateFehler, ValueError, OSError, subprocess.SubprocessError):
            pass
    st = _status_lesen(app_dir)
    return Stand(st.get("sha", ""), st.get("nummer"), st.get("datum", ""))


def remote_stand(timeout: float = 8) -> Stand:
    r = _get(f"{API}/commits/{BRANCH}", timeout)
    d = r.json()
    sha = d["sha"]
    c = d.get("commit", {})
    # Anzahl Commits: Seitenzahl der letzten Seite bei 1 Commit pro Seite
    r2 = _get(f"{API}/commits", timeout, params={"sha": BRANCH, "per_page": 1})
    m = re.search(r'[?&]page=(\d+)>; rel="last"', r2.headers.get("Link", ""))
    nummer = int(m.group(1)) if m else len(r2.json())
    return Stand(sha, nummer, c.get("committer", {}).get("date", ""), (c.get("message") or "").split("\n")[0])


def verlauf(anzahl: int = 12, timeout: float = 8) -> list[dict]:
    """Die letzten Versionen auf GitHub: [{version, sha, datum, nachricht}], neueste zuerst."""
    basis = basis_version()
    r = _get(f"{API}/commits", timeout, params={"sha": BRANCH, "per_page": 1})
    m = re.search(r'[?&]page=(\d+)>; rel="last"', r.headers.get("Link", ""))
    gesamt = int(m.group(1)) if m else len(r.json())
    r = _get(f"{API}/commits", timeout, params={"sha": BRANCH, "per_page": anzahl})
    out = []
    for i, c in enumerate(r.json()):
        info = c.get("commit", {})
        out.append({"version": f"{basis}.{gesamt - i}", "sha": c.get("sha", "")[:7],
                    "datum": (info.get("committer", {}).get("date") or "")[:10],
                    "nachricht": (info.get("message") or "").split("\n")[0]})
    return out


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
        if lokal.nummer is None:
            lokal.nummer = info.remote.nummer - behind if cmp.get("behind_by", 0) == 0 else None
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
    log("Python-Pakete werden aktualisiert …")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
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
    os.execv(sys.executable, [sys.executable] + sys.argv)


def version_text(app_dir: Path = APP_DIR) -> str:
    st = lokaler_stand(app_dir)
    return st.version(basis_version(app_dir))


if __name__ == "__main__":
    # Hilfsbefehle für install.sh
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
