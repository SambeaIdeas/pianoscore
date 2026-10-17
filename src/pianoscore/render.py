"""Conversiones con MuseScore: partitura <-> PDF, PNG, MIDI, audio."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import idioma
from .config import FaltaDependencia, correr_mscore

FORMATOS_AUDIO = {".wav", ".mp3", ".flac", ".ogg"}
FORMATOS_PARTITURA = {".musicxml", ".xml", ".mxl", ".mid", ".midi", ".mscz", ".mscx", ".cap", ".gp", ".gpx"}
FORMATOS_IMAGEN = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def convertir(entrada: Path, destino: Path, timeout: int = 1800) -> Path:
    """Conversion generica de MuseScore, deducida por la extension del destino."""
    entrada, destino = Path(entrada), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    proc = correr_mscore(["-o", str(destino), str(entrada)], timeout=timeout)

    if destino.suffix.lower() == ".png":
        # MuseScore numera las paginas: salida-1.png, salida-2.png...
        paginas = sorted(destino.parent.glob(f"{destino.stem}-*.png"))
        if paginas:
            return paginas[0]

    if not destino.exists():
        detalle = (proc.stderr or proc.stdout or "").strip()[-800:]
        raise FaltaDependencia(idioma.t(
            "mscore_fallo", nombre=destino.name, entrada=entrada, detalle=detalle))
    return destino


def a_pdf(entrada: Path, destino: Path) -> Path:
    return convertir(entrada, destino)


def a_png(entrada: Path, destino: Path) -> list[Path]:
    convertir(entrada, destino)
    paginas = sorted(destino.parent.glob(f"{destino.stem}-*.png"))
    return paginas or ([destino] if destino.exists() else [])


def a_audio(entrada: Path, destino: Path, timeout: int = 3600) -> Path:
    if destino.suffix.lower() not in FORMATOS_AUDIO:
        raise ValueError(idioma.t(
            "formato_audio_malo", ext=destino.suffix,
            lista=", ".join(sorted(FORMATOS_AUDIO))))
    return convertir(entrada, destino, timeout=timeout)


def a_musicxml(entrada: Path, destino: Path) -> Path:
    return convertir(entrada, destino)


def a_midi(entrada: Path, destino: Path) -> Path:
    return convertir(entrada, destino)


def aplicar_tempo(entrada: Path, bpm: float, carpeta_tmp: Path) -> Path:
    """Reescribe la partitura con otro tempo. Si falla, devuelve la original."""
    try:
        from music21 import converter, tempo
        s = converter.parse(str(entrada))
        for marca in list(s.recurse().getElementsByClass(tempo.MetronomeMark)):
            marca.activeSite.remove(marca)
        partes = list(s.parts) if hasattr(s, "parts") and len(s.parts) else [s]
        partes[0].insert(0, tempo.MetronomeMark(number=bpm))
        destino = carpeta_tmp / "con_tempo.musicxml"
        s.write("musicxml", fp=str(destino))
        return destino
    except Exception:
        return entrada


def partitura_a_audio(
    entrada: Path, destino: Path, bpm: float | None = None, progreso=print,
) -> Path:
    """Punto de entrada de la direccion partitura -> audio."""
    entrada, destino = Path(entrada), Path(destino)
    ext = entrada.suffix.lower()

    if ext in FORMATOS_IMAGEN:
        from .omr import leer_partitura_escaneada
        progreso(idioma.t("omr_lanzando"))
        with tempfile.TemporaryDirectory() as tmp:
            xml = leer_partitura_escaneada(entrada, Path(tmp))
            # Audiveris exporta .mxl (MusicXML comprimido en zip). Hay que
            # conservar su extension: con el nombre cambiado a .musicxml,
            # MuseScore intenta leer el zip como XML plano y falla.
            copia = destino.parent / (destino.stem + "_reconocida" + xml.suffix)
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(xml, copia)
            progreso(idioma.t("omr_reconocida", ruta=copia))
            return _sintetizar(copia, destino, bpm, progreso)

    if ext not in FORMATOS_PARTITURA:
        raise ValueError(idioma.t(
            "formato_entrada_malo", ext=ext,
            partituras=", ".join(sorted(FORMATOS_PARTITURA)),
            imagenes=", ".join(sorted(FORMATOS_IMAGEN))))
    return _sintetizar(entrada, destino, bpm, progreso)


def _sintetizar(fuente: Path, destino: Path, bpm: float | None, progreso) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        if bpm:
            progreso(idioma.t("forzando_tempo", bpm=bpm))
            fuente = aplicar_tempo(fuente, bpm, Path(tmp))
        progreso(idioma.t("sintetizando", fmt=destino.suffix.lstrip(".")))
        return a_audio(fuente, destino)
