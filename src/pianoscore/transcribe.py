"""Audio -> MIDI. Transcripcion de piano con el modelo CRNN de ByteDance.

Procesa el audio ENTERO. Los ficheros largos se trocean con solape para no
agotar la memoria, y los trozos se vuelven a unir respetando los tiempos
absolutos.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import idioma

SAMPLE_RATE = 16000  # el modelo esta entrenado a 16 kHz


@dataclass
class Nota:
    pitch: int
    onset: float
    offset: float
    velocity: int


@dataclass
class Pedal:
    onset: float
    offset: float


@dataclass
class Transcripcion:
    notas: list[Nota]
    pedales: list[Pedal]
    duracion: float


def cargar_audio(ruta: Path, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Decodifica cualquier formato a mono/16 kHz pasando por ffmpeg.

    Es mas fiable que librosa a secas para mp3, m4a, ogg, opus o video.
    """
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "entrada.wav"
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(ruta),
             "-ac", "1", "-ar", str(sr), "-f", "wav", str(wav)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not wav.exists():
            raise RuntimeError(idioma.t("ffmpeg_fallo", ruta=ruta,
                                        detalle=proc.stderr.strip()))
        import soundfile as sf
        audio, _ = sf.read(str(wav), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return np.ascontiguousarray(audio, dtype=np.float32)


def _modelo(device: str = "cpu", umbral: float | None = None):
    from piano_transcription_inference import PianoTranscription

    m = PianoTranscription(device=device)
    if umbral is not None:
        # El modelo lee estos umbrales al transcribir, asi que se pueden
        # subir despues de construirlo. Subirlos exige mas confianza para dar
        # una nota por buena: es la via para limpiar grabaciones que no son
        # de piano solo, donde el modelo se inventa notas a partir de voces,
        # platillos o metales.
        m.onset_threshold = float(umbral)
        m.frame_threshold = float(min(umbral, 0.3))
    return m


def transcribir(
    ruta_audio: Path,
    device: str = "cpu",
    trozo_seg: float = 600.0,
    solape_seg: float = 10.0,
    umbral: float | None = None,
    dur_minima_ms: float = 0.0,
    progreso=print,
) -> Transcripcion:
    audio = cargar_audio(ruta_audio)
    duracion = len(audio) / SAMPLE_RATE
    progreso(idioma.t("audio_info", min=duracion / 60, seg=duracion, sr=SAMPLE_RATE))

    modelo = _modelo(device, umbral)
    if umbral is not None:
        progreso(idioma.t("umbral_info", u=umbral))

    notas: list[Nota] = []
    pedales: list[Pedal] = []

    if duracion <= trozo_seg:
        tramos = [(0.0, duracion)]
    else:
        paso = trozo_seg - solape_seg
        inicios = np.arange(0.0, duracion, paso)
        tramos = [(float(t0), float(min(t0 + trozo_seg, duracion))) for t0 in inicios]
        tramos = [t for t in tramos if t[1] - t[0] > 1.0]

    for i, (t0, t1) in enumerate(tramos):
        if len(tramos) > 1:
            progreso(idioma.t("tramo", i=i + 1, n=len(tramos),
                              a=t0 / 60, b=t1 / 60))
        seg = audio[int(t0 * SAMPLE_RATE): int(t1 * SAMPLE_RATE)]
        res = modelo.transcribe(seg, None)

        # Zona "util" del tramo: descarta medio solape por cada lado para que
        # las notas del borde no se dupliquen ni se corten dos veces.
        ini_util = t0 + (solape_seg / 2 if i > 0 else 0.0)
        fin_util = t1 - (solape_seg / 2 if i < len(tramos) - 1 else 0.0)

        for ev in res["est_note_events"]:
            on = t0 + float(ev["onset_time"])
            if not (ini_util <= on < fin_util):
                continue
            notas.append(Nota(
                pitch=int(ev["midi_note"]),
                onset=on,
                offset=t0 + float(ev["offset_time"]),
                velocity=int(np.clip(ev.get("velocity", 80), 1, 127)),
            ))
        for ev in res["est_pedal_events"]:
            on = t0 + float(ev["onset_time"])
            if not (ini_util <= on < fin_util):
                continue
            pedales.append(Pedal(onset=on, offset=t0 + float(ev["offset_time"])))

    if dur_minima_ms > 0:
        antes = len(notas)
        minimo = dur_minima_ms / 1000.0
        notas = [n for n in notas if (n.offset - n.onset) >= minimo]
        if antes != len(notas):
            progreso(idioma.t("descartadas", n=antes - len(notas),
                              ms=dur_minima_ms))

    notas.sort(key=lambda n: (n.onset, n.pitch))
    pedales.sort(key=lambda p: p.onset)
    progreso(idioma.t("notas_detectadas", notas=len(notas), pedales=len(pedales)))
    return Transcripcion(notas=notas, pedales=pedales, duracion=duracion)


def a_midi(tr: Transcripcion, destino: Path, bpm: float = 120.0, con_pedal: bool = True) -> Path:
    """Escribe el MIDI tal cual suena (sin cuantizar): la version fiel."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=0, name="Piano")
    for n in tr.notas:
        fin = max(n.offset, n.onset + 0.02)
        inst.notes.append(pretty_midi.Note(
            velocity=n.velocity, pitch=n.pitch, start=n.onset, end=fin))
    if con_pedal:
        for p in tr.pedales:
            inst.control_changes.append(pretty_midi.ControlChange(64, 127, p.onset))
            inst.control_changes.append(pretty_midi.ControlChange(64, 0, max(p.offset, p.onset + 0.05)))
    pm.instruments.append(inst)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(destino))
    return destino
