"""Notas cuantizadas -> partitura de piano (dos pentagramas) en MusicXML."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DO_CENTRAL = 60


def _linea_de_corte(notas, ppc: int, suavizado_compases: float = 1.0,
                    sigma: float = 8.0) -> tuple[np.ndarray, float]:
    """Estima, pulso a pulso, la altura que separa las dos manos.

    En cada instante se mira donde quedan los huecos entre las alturas que
    suenan y se elige uno como frontera. No vale quedarse con el hueco mas
    ancho a secas: en una textura de melodia con acompanamiento el hueco
    mayor suele estar entre el bajo y todo lo demas, y entonces la izquierda
    se queda solo con el bajo mientras los acordes se van a la derecha. Por
    eso cada hueco se pondera segun su cercania al centro del registro que
    esta sonando: se busca un hueco ancho, pero en el medio.

    La ventana es de un pulso para no mezclar el bajo del primer tiempo con
    los acordes de los tiempos debiles; el suavizado posterior es el que
    evita que la frontera salte de compas en compas.
    """
    if not notas:
        return np.array([DO_CENTRAL], dtype=float), 0.0

    fin = max(n.inicio + n.duracion for n in notas)
    paso = 1.0  # un valor por pulso
    rejilla = np.arange(0.0, fin + paso, paso)
    corte = np.full(len(rejilla), float(DO_CENTRAL))

    ventana = 1.0
    inicios = np.array([n.inicio for n in notas])
    finales = np.array([n.inicio + n.duracion for n in notas])
    alturas = np.array([n.pitch for n in notas], dtype=float)

    for i, t in enumerate(rejilla):
        sonando = alturas[(inicios < t + ventana) & (finales > t - ventana)]
        if len(sonando) == 0:
            corte[i] = np.nan
            continue
        u = np.unique(sonando)
        if len(u) == 1:
            corte[i] = u[0] + 0.5 if u[0] < DO_CENTRAL else u[0] - 0.5
            continue
        centro_registro = float(np.median(sonando))
        huecos = np.diff(u)
        centros = u[:-1] + huecos / 2.0
        peso = np.exp(-((centros - centro_registro) ** 2) / (2.0 * sigma ** 2))
        corte[i] = float(centros[int(np.argmax(huecos * peso))])

    # Rellena huecos (silencios) y suaviza.
    idx = np.arange(len(corte))
    validos = ~np.isnan(corte)
    if validos.any():
        corte = np.interp(idx, idx[validos], corte[validos])
    else:
        corte[:] = DO_CENTRAL

    n_suave = max(1, int(suavizado_compases * ppc / paso))
    if n_suave > 1:
        nucleo = np.ones(n_suave) / n_suave
        corte = np.convolve(np.pad(corte, (n_suave, n_suave), mode="edge"), nucleo, mode="same")[n_suave:-n_suave]

    return np.clip(corte, 43.0, 79.0), paso


def separar_manos(notas, ppc: int, corte_fijo: int | None = None):
    """Reparte las notas entre pentagrama superior (derecha) e inferior (izquierda)."""
    if corte_fijo is not None:
        der = [n for n in notas if n.pitch >= corte_fijo]
        izq = [n for n in notas if n.pitch < corte_fijo]
        return der, izq

    corte, paso = _linea_de_corte(notas, ppc)
    der, izq = [], []
    for n in notas:
        i = int(min(max(n.inicio / paso, 0), len(corte) - 1))
        (der if n.pitch >= corte[i] else izq).append(n)
    return der, izq


def _acordes_por_golpe(notas, paso: float = 0.25, dur_maxima: float = 8.0,
                       truncar: bool = True):
    """Agrupa las notas que atacan a la vez y recorta solapes dentro del pentagrama.

    Las duraciones se anclan a la rejilla: sin esto aparecen figuras absurdas
    (fusas sueltas) que no se pueden leer ni tocar.
    """
    por_inicio: dict[float, list] = {}
    for n in notas:
        por_inicio.setdefault(round(n.inicio, 4), []).append(n)
    golpes = sorted(por_inicio.items())

    grupos = []
    for i, (inicio, grupo) in enumerate(golpes):
        dur = max(n.duracion for n in grupo)
        if truncar and i + 1 < len(golpes):
            dur = min(dur, golpes[i + 1][0] - inicio)
        dur = min(max(dur, paso), dur_maxima)
        dur = float(max(paso, round(dur / paso) * paso))
        grupos.append((inicio, dur, grupo))
    return grupos


def _deletrear(midi: int, usar_bemoles: bool):
    """Escribe la altura con la alteracion que toca en la tonalidad.

    music21 crea Note(60) con un becuadro EXPLICITO, que al exportar sale
    dibujado en cada nota y ensucia la partitura: hay que quitarlo y dejar
    que makeNotation ponga solo los que hacen falta.
    """
    from music21 import pitch as m21pitch

    pp = m21pitch.Pitch(midi)
    if usar_bemoles and pp.accidental is not None and pp.accidental.name == "sharp":
        pp = pp.getEnharmonic()
    if pp.accidental is not None and pp.accidental.name == "natural":
        pp.accidental = None
    return pp


def construir_partitura(
    notas, ppc: int, bpm: float, titulo: str = "Transcripcion",
    compositor: str = "", subdivision: int = 4, corte_manos: int | None = None,
    denominador_compas: int = 4, n_compases: int = 0,
):
    """Devuelve un music21.stream.Score con dos pentagramas unidos por llave."""
    from music21 import (chord, clef, duration, instrument, key, layout,
                         metadata, meter, note, stream, tempo)

    der, izq = separar_manos(notas, ppc, corte_manos)

    score = stream.Score()
    score.metadata = metadata.Metadata()
    score.metadata.title = titulo
    score.metadata.composer = compositor or " "

    # Tonalidad estimada sobre todas las notas.
    tonalidad = None
    try:
        aux = stream.Stream()
        for n in notas:
            aux.insert(n.inicio, note.Note(n.pitch, quarterLength=max(n.duracion, 0.25)))
        tonalidad = aux.analyze("key")
    except Exception:
        tonalidad = None

    # Las tonalidades con bemoles se escriben con bemoles, no con sostenidos.
    usar_bemoles = bool(tonalidad is not None and tonalidad.sharps < 0)

    numerador = ppc if denominador_compas == 4 else int(round(ppc * denominador_compas / 4))
    firma = f"{numerador}/{denominador_compas}"

    pentagramas = []
    # Los dos PartStaff se exportan fundidos en un unico <part> de MusicXML
    # con dos pautas, que es el pentagrama doble de piano de verdad. El
    # nombre del primero es el que acaba nombrando la parte entera, asi que
    # va "Piano" y no el de una mano.
    for notas_mano, clave, nombre in (
        (der, clef.TrebleClef(), "Piano"),
        (izq, clef.BassClef(), "Piano"),
    ):
        p = stream.PartStaff()
        p.partName = nombre
        p.partAbbreviation = "Pno."
        p.insert(0, instrument.Piano())
        p.insert(0, clave)
        if tonalidad is not None:
            p.insert(0, key.KeySignature(tonalidad.sharps))
        p.insert(0, meter.TimeSignature(firma))

        for inicio, dur, grupo in _acordes_por_golpe(notas_mano, paso=1.0 / subdivision):
            alturas = sorted({n.pitch for n in grupo})
            vel = int(np.mean([n.velocity for n in grupo]))
            escritas = [_deletrear(m, usar_bemoles) for m in alturas]
            if len(escritas) == 1:
                el = note.Note(escritas[0])
            else:
                el = chord.Chord(escritas)
            el.duration = duration.Duration(quarterLength=dur)
            el.volume.velocity = vel
            p.insert(inicio, el)

        pentagramas.append(p)

    pentagramas[0].insert(0, tempo.MetronomeMark(number=round(bpm)))

    # Longitud comun: los dos pentagramas deben acabar en la misma barra, y
    # todo compas tiene que estar completo o la partitura no es valida.
    if n_compases:
        longitud = float(n_compases * ppc)
    else:
        longitud = max((n.inicio + n.duracion for n in notas), default=float(ppc))
        longitud = float(np.ceil(longitud / ppc) * ppc)

    for p in pentagramas:
        try:
            p.makeRests(refStreamOrTimeRange=[0.0, longitud], fillGaps=True,
                        inPlace=True, hideRests=False)
        except Exception:
            try:
                p.makeRests(fillGaps=True, inPlace=True)
            except Exception:
                pass
        try:
            p.makeNotation(inPlace=True)
        except Exception:
            pass
        score.insert(0, p)

    grupo = layout.StaffGroup(pentagramas, name="Piano", abbreviation="Pno.",
                              symbol="brace")
    grupo.barTogether = True
    score.insert(0, grupo)
    return score, tonalidad


def escribir_musicxml(score, destino):
    from music21 import converter  # noqa: F401
    destino.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(destino))
    return destino
