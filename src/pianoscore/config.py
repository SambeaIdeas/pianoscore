"""Rutas y descubrimiento de herramientas externas."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

from . import idioma

RAIZ = Path(__file__).resolve().parents[2]
TOOLS = RAIZ / "tools"
SALIDA_POR_DEFECTO = RAIZ / "salida"

# Binario de MuseScore extraido del AppImage (ver instalar.sh).
MSCORE = TOOLS / "squashfs-root" / "bin" / "mscore-portable"
SOUNDFONT = TOOLS / "squashfs-root" / "share" / "mscore-portable-3.6" / "sound" / "MuseScore_General.sf3"

# Audiveris (OMR) es opcional: solo hace falta para leer partituras en PDF/imagen.
AUDIVERIS = TOOLS / "audiveris" / "bin" / "Audiveris"


class FaltaDependencia(RuntimeError):
    pass


def _display_disponible() -> str | None:
    """MuseScore 3 solo trae el plugin Qt 'xcb', asi que necesita un display X.

    Devuelve el valor de DISPLAY que se puede usar, o None.
    """
    actual = os.environ.get("DISPLAY")
    if actual:
        n = actual.lstrip(":").split(".")[0]
        if Path(f"/tmp/.X11-unix/X{n}").exists():
            return actual
    for sock in sorted(glob.glob("/tmp/.X11-unix/X*")):
        return ":" + Path(sock).name[1:]
    return None


def entorno_mscore() -> dict:
    env = dict(os.environ)
    env.setdefault("HOME", str(Path.home()))
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    display = _display_disponible()
    if display:
        env["DISPLAY"] = display
        env["QT_QPA_PLATFORM"] = "xcb"
    else:
        env["QT_QPA_PLATFORM"] = "offscreen"
    # Silencia avisos de Qt que no aportan nada en modo lote.
    env.setdefault("QT_LOGGING_RULES", "*.debug=false;qt.qpa.*=false")
    return env


def exige_mscore() -> Path:
    if MSCORE.exists():
        return MSCORE
    for nombre in ("mscore", "musescore", "mscore3", "musescore3", "mscore4", "musescore4"):
        hallado = shutil.which(nombre)
        if hallado:
            return Path(hallado)
    raise FaltaDependencia(idioma.t("falta_mscore", ruta=MSCORE))


def correr_mscore(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    binario = exige_mscore()
    proc = subprocess.run(
        [str(binario), *args],
        env=entorno_mscore(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc


def hay_audiveris() -> bool:
    return AUDIVERIS.exists() or shutil.which("audiveris") is not None


def ruta_audiveris() -> Path:
    if AUDIVERIS.exists():
        return AUDIVERIS
    hallado = shutil.which("audiveris")
    if hallado:
        return Path(hallado)
    raise FaltaDependencia(idioma.t("falta_audiveris"))
