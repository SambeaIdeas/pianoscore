"""Pulso, compas y cuantizacion.

La transcripcion sale con tiempos libres (en segundos). Para escribir una
partitura legible hay que encajarla en una rejilla metrica: detectar el pulso
del audio, decidir donde cae el primer tiempo de cada compas y redondear
cada nota a la subdivision mas cercana.

Interpolar contra los pulsos REALES (no contra un tempo fijo) hace que el
rubato se absorba en la rejilla en vez de desplazar toda la pieza.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Rejilla:
    tiempos_pulso: np.ndarray   # instantes (s) de cada pulso
    bpm: float
    pulsos_por_compas: int
    indice_primer_tiempo: int   # que pulso es el primer tiempo de un compas


def estimar_pulso(audio: np.ndarray, sr: int, bpm_fijo: float | None = None) -> tuple[np.ndarray, float]:
    import librosa

    if bpm_fijo:
        dur = len(audio) / sr
        periodo = 60.0 / bpm_fijo
        onsets = librosa.onset.onset_detect(y=audio, sr=sr, units="time")
        inicio = float(onsets[0]) if len(onsets) else 0.0
        inicio -= periodo * np.floor(inicio / periodo)
        return np.arange(inicio, dur + periodo, periodo), float(bpm_fijo)

    tempo, pulsos = librosa.beat.beat_track(y=audio, sr=sr, units="time", trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    if len(pulsos) < 4:  # audio muy corto o sin pulso claro
        dur = max(len(audio) / sr, 1.0)
        tempo = tempo or 100.0
        periodo = 60.0 / tempo
        pulsos = np.arange(0.0, dur + periodo, periodo)
    pulsos = np.asarray(pulsos, dtype=float)

    # El tempo que devuelve librosa y el que describe la rejilla de pulsos
    # pueden no coincidir. Lo que se escribe en la partitura tiene que ser el
    # de la rejilla, porque es contra ella contra la que se cuantizan las
    # notas: si no, la partitura suena a otra velocidad que el original.
    #
    # Se usa una media recortada en vez de la mediana: los instantes de pulso
    # vienen redondeados a los frames de librosa (~23 ms), asi que la mediana
    # se queda pegada a ese redondeo mientras que promediar lo compensa. El
    # recorte descarta los saltos de cuando el detector se salta un pulso.
    if len(pulsos) >= 3:
        difs = np.diff(pulsos)
        med = float(np.median(difs))
        buenos = difs[np.abs(difs - med) <= 0.25 * med] if med > 0 else difs
        if len(buenos) and buenos.mean() > 0:
            tempo = 60.0 / float(buenos.mean())
    elif len(pulsos) == 2 and pulsos[1] > pulsos[0]:
        tempo = 60.0 / float(pulsos[1] - pulsos[0])
    return pulsos, tempo


def _acento_por_pulso(notas, pulsos: np.ndarray) -> np.ndarray:
    """Cuanto "pesa" cada pulso, a partir de las notas ya transcritas.

    El indicio mas fiable del primer tiempo en piano es el REGISTRO GRAVE: el
    bajo marca el cambio de armonia. La densidad de notas se usa solo como
    apoyo, con poco peso, porque en muchos acompanamientos (un vals tipico)
    el tiempo fuerte lleva una sola nota y los debiles acordes enteros: si se
    le diera peso alto, el detector elegiria el compas equivocado.
    """
    n = len(pulsos)
    cuenta = np.zeros(n)
    grave = np.full(n, np.nan)
    duracion = np.zeros(n)
    for nota in notas:
        i = int(np.argmin(np.abs(pulsos - nota.onset)))
        cuenta[i] += 1
        grave[i] = nota.pitch if np.isnan(grave[i]) else min(grave[i], nota.pitch)
        duracion[i] = max(duracion[i], nota.offset - nota.onset)

    if np.isnan(grave).all():
        grave = np.zeros(n)
    else:
        grave = np.nan_to_num(grave, nan=float(np.nanmean(grave)))

    def z(v):
        return (v - v.mean()) / (v.std() + 1e-9)

    return 1.0 * z(-grave) + 0.3 * z(cuenta) + 0.3 * z(duracion)


def _acento_por_energia(audio: np.ndarray, sr: int, pulsos: np.ndarray) -> np.ndarray:
    """Alternativa cuando no hay notas: fuerza de ataque del audio."""
    import librosa

    env = librosa.onset.onset_strength(y=audio, sr=sr)
    t = librosa.times_like(env, sr=sr)
    f = np.interp(pulsos, t, env, left=0.0, right=0.0)
    return (f - f.mean()) / (f.std() + 1e-9)


def estimar_compas(
    acento: np.ndarray, candidatos=(3, 4), sesgo_4: float = 1.05
) -> tuple[int, int]:
    """Elige pulsos-por-compas y en que pulso empieza el compas.

    Para cada agrupacion se busca el desfase que mas separa los tiempos
    fuertes del resto. Ante un empate se prefiere 4/4, que es mucho mas
    frecuente que 3/4.
    """
    resultados: dict[int, tuple[float, int]] = {}
    for n in candidatos:
        if len(acento) < n * 2:
            continue
        mejor, mejor_fase = -1e9, 0
        for fase in range(n):
            fuertes = acento[fase::n]
            debiles = np.delete(acento, np.arange(fase, len(acento), n))
            if len(fuertes) == 0 or len(debiles) == 0:
                continue
            contraste = float(fuertes.mean() - debiles.mean())
            if contraste > mejor:
                mejor, mejor_fase = contraste, fase
        resultados[n] = (mejor, mejor_fase)

    if not resultados:
        return 4, 0
    if 4 in resultados and 3 in resultados:
        elegido = 4 if resultados[4][0] >= resultados[3][0] * sesgo_4 else 3
    else:
        elegido = max(resultados, key=lambda k: resultados[k][0])
    return elegido, resultados[elegido][1]


def construir_rejilla(
    audio: np.ndarray, sr: int, notas=None, bpm_fijo: float | None = None,
    compas_fijo: tuple[int, int] | None = None,
) -> Rejilla:
    pulsos, bpm = estimar_pulso(audio, sr, bpm_fijo)

    if notas:
        acento = _acento_por_pulso(notas, pulsos)
    else:
        acento = _acento_por_energia(audio, sr, pulsos)

    if compas_fijo:
        num, den = compas_fijo
        ppc = num if den == 4 else max(1, round(num * 4 / den))
        _, fase = estimar_compas(acento, candidatos=(ppc,))
    else:
        ppc, fase = estimar_compas(acento)

    return Rejilla(tiempos_pulso=pulsos, bpm=bpm, pulsos_por_compas=ppc,
                   indice_primer_tiempo=fase)


def segundos_a_pulsos(t: np.ndarray, pulsos: np.ndarray) -> np.ndarray:
    """Convierte segundos a posicion en pulsos (puede ser fraccionaria).

    Fuera del rango detectado se extrapola con el tempo local de los extremos.
    """
    t = np.asarray(t, dtype=float)
    idx = np.arange(len(pulsos), dtype=float)
    fuera_izq = t < pulsos[0]
    fuera_der = t > pulsos[-1]
    out = np.interp(t, pulsos, idx)
    if len(pulsos) >= 2:
        p_ini = pulsos[1] - pulsos[0]
        p_fin = pulsos[-1] - pulsos[-2]
        if p_ini > 0:
            out[fuera_izq] = (t[fuera_izq] - pulsos[0]) / p_ini
        if p_fin > 0:
            out[fuera_der] = (len(pulsos) - 1) + (t[fuera_der] - pulsos[-1]) / p_fin
    return out


@dataclass
class NotaCuantizada:
    pitch: int
    inicio: float      # en negras (quarterLength), ya desplazado al compas 1
    duracion: float
    velocity: int


def cuantizar(
    notas, rejilla: Rejilla, subdivision: int = 4,
    dur_minima_pulsos: float | None = None,
) -> tuple[list[NotaCuantizada], int]:
    """Encaja las notas en la rejilla. Devuelve las notas y el numero de compases."""
    if not notas:
        return [], 0

    onsets = np.array([n.onset for n in notas])
    offsets = np.array([n.offset for n in notas])
    p_on = segundos_a_pulsos(onsets, rejilla.tiempos_pulso)
    p_off = segundos_a_pulsos(offsets, rejilla.tiempos_pulso)

    paso = 1.0 / subdivision
    # La figura mas corta es la propia subdivision pedida: fijar aqui un
    # minimo mayor haria inutil un --subdivision fino.
    minima = paso if dur_minima_pulsos is None else max(paso, dur_minima_pulsos)
    q_on = np.round(p_on / paso) * paso
    q_off = np.round(p_off / paso) * paso
    q_dur = np.maximum(q_off - q_on, minima)

    ppc = rejilla.pulsos_por_compas
    # Origen = primer tiempo fuerte, retrocedido en compases enteros hasta
    # cubrir la nota mas temprana. Asi el compas 1 empieza en una barra real.
    d0 = float(rejilla.indice_primer_tiempo)
    mas_temprana = float(q_on.min())
    compases_antes = int(np.ceil(max(0.0, d0 - mas_temprana) / ppc))
    origen = d0 - compases_antes * ppc

    cuantizadas = [
        NotaCuantizada(pitch=n.pitch, inicio=float(on - origen),
                       duracion=float(d), velocity=n.velocity)
        for n, on, d in zip(notas, q_on, q_dur)
    ]

    # Quita duplicados exactos (misma altura y mismo golpe): se queda el mas largo.
    vistos: dict[tuple[int, float], NotaCuantizada] = {}
    for nc in cuantizadas:
        clave = (nc.pitch, round(nc.inicio, 4))
        previa = vistos.get(clave)
        if previa is None or nc.duracion > previa.duracion:
            vistos[clave] = nc
    cuantizadas = sorted(vistos.values(), key=lambda x: (x.inicio, x.pitch))

    final = max(nc.inicio + nc.duracion for nc in cuantizadas)
    n_compases = int(np.ceil(final / ppc))
    return cuantizadas, n_compases
