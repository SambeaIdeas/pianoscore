"""Comprueba la separacion de manos contra la verdad conocida de las piezas de prueba."""
import pathlib
import sys

import pretty_midi

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from pianoscore import partitura as mp  # noqa: E402
from pianoscore import ritmo, transcribe  # noqa: E402

CASOS = [
    ("VALS", "salida/vals_mib/vals_mib.mid", "ejemplos/vals_mib.mp3",
     "izq = bajo 32-46 + acordes 55-68 | der = melodia 63-75"),
    ("PIEZA", "salida/pieza_prueba/pieza_prueba.mid", "ejemplos/pieza_prueba.mp3",
     "izq = 36-55 | der = 62-76"),
]


class _N:
    pass


def cargar(midi, mp3):
    pm = pretty_midi.PrettyMIDI(midi)
    notas = []
    for x in pm.instruments[0].notes:
        o = _N()
        o.onset, o.offset, o.pitch, o.velocity = x.start, x.end, x.pitch, x.velocity
        notas.append(o)
    audio = transcribe.cargar_audio(pathlib.Path(mp3), sr=22050)
    rej = ritmo.construir_rejilla(audio, 22050, notas=notas)
    nq, _ = ritmo.cuantizar(notas, rej, subdivision=4)
    return nq, rej.pulsos_por_compas


for nombre, midi, mp3, verdad in CASOS:
    nq, ppc = cargar(midi, mp3)
    corte, _ = mp._linea_de_corte(nq, ppc)
    der, izq = mp.separar_manos(nq, ppc)
    print(f"\n{nombre}   ({verdad})")
    print(f"  corte medio {corte.mean():.1f} (min {corte.min():.1f}, max {corte.max():.1f})")
    for etiqueta, grupo in (("derecha  ", der), ("izquierda", izq)):
        if grupo:
            print(f"  {etiqueta} {len(grupo):3d} notas, rango "
                  f"{min(n.pitch for n in grupo)}-{max(n.pitch for n in grupo)}")
        else:
            print(f"  {etiqueta}   0 notas")
