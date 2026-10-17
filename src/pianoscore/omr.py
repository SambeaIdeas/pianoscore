"""Reconocimiento optico de partituras (PDF o imagen -> MusicXML) con Audiveris."""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import idioma
from .config import FaltaDependencia, ruta_audiveris


def leer_partitura_escaneada(entrada: Path, carpeta_salida: Path, timeout: int = 3600) -> Path:
    binario = ruta_audiveris()
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [str(binario), "-batch", "-export", "-output", str(carpeta_salida), "--", str(entrada)],
        capture_output=True, text=True, timeout=timeout,
    )
    resultados = list(carpeta_salida.rglob("*.mxl")) + list(carpeta_salida.rglob("*.musicxml"))
    if not resultados:
        detalle = (proc.stderr or proc.stdout or "").strip()[-1000:]
        raise FaltaDependencia(idioma.t(
            "omr_fallo", nombre=entrada.name, detalle=detalle))
    return max(resultados, key=lambda p: p.stat().st_size)
