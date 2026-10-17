"""Linea de comandos / command line: audio <-> piano sheet music."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from . import config
from . import idioma
from .idioma import t

VERSION = "1.1"

# La ventana localiza el resultado leyendo esta marca, no los mensajes: asi
# el texto se puede traducir sin romper nada. Solo se imprime cuando quien
# llama lo pide con PIANOSCORE_MARCAS=1.
MARCA = "@@PIANOSCORE_RESULTADO@@"


def _log(msg=""):
    print(msg, flush=True)


def _marcar(ruta: Path):
    if os.environ.get("PIANOSCORE_MARCAS"):
        print(f"{MARCA}{ruta}", flush=True)


def _nota_a_midi(txt: str) -> int | None:
    txt = (txt or "").strip()
    if not txt or txt.lower() in ("auto", "automatico", "automatic"):
        return None
    if txt.isdigit():
        return int(txt)
    from music21 import note
    return note.Note(txt).pitch.midi


def _parse_compas(txt: str | None):
    if not txt:
        return None
    num, den = txt.split("/")
    return int(num), int(den)


# --------------------------------------------------------------------------
# audio -> partitura
# --------------------------------------------------------------------------
def cmd_audio2partitura(a) -> int:
    from . import partitura as mod_part
    from . import render, ritmo, transcribe

    entrada = Path(a.entrada).expanduser().resolve()
    if not entrada.exists():
        _log(t("no_existe", ruta=entrada))
        return 1

    carpeta = Path(a.salida).expanduser().resolve() if a.salida else \
        config.SALIDA_POR_DEFECTO / entrada.stem
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = entrada.stem
    t0 = time.time()

    _log(t("paso_transcribir", nombre=entrada.name))
    tr = transcribe.transcribir(
        entrada, device=a.device, trozo_seg=a.trozo, solape_seg=a.solape,
        umbral=a.umbral, dur_minima_ms=a.minimo_ms, progreso=_log)
    if not tr.notas:
        _log(t("sin_notas"))
        return 1

    midi_crudo = carpeta / f"{nombre}.mid"
    transcribe.a_midi(tr, midi_crudo, con_pedal=not a.sin_pedal)
    _log(t("midi_fiel", ruta=midi_crudo))

    _log(t("paso_pulso"))
    audio_22k = transcribe.cargar_audio(entrada, sr=22050)
    rejilla = ritmo.construir_rejilla(
        audio_22k, 22050, notas=tr.notas, bpm_fijo=a.bpm,
        compas_fijo=_parse_compas(a.compas))
    _log(t("pulso_info", bpm=rejilla.bpm, ppc=rejilla.pulsos_por_compas))

    _log(t("paso_cuantizar", sub=a.subdivision))
    notas_q, n_compases = ritmo.cuantizar(tr.notas, rejilla, subdivision=a.subdivision)
    _log(t("cuantizar_info", notas=len(notas_q), compases=n_compases))

    _log(t("paso_partitura"))
    den = _parse_compas(a.compas)[1] if a.compas else 4
    score, tonalidad = mod_part.construir_partitura(
        notas_q, ppc=rejilla.pulsos_por_compas, bpm=rejilla.bpm,
        titulo=a.titulo or nombre, compositor=a.compositor,
        subdivision=a.subdivision, corte_manos=_nota_a_midi(a.corte_manos or "auto"),
        denominador_compas=den, n_compases=n_compases,
    )
    if tonalidad is not None:
        _log(t("tonalidad", k=idioma.tonalidad(tonalidad)))
    xml = carpeta / f"{nombre}.musicxml"
    mod_part.escribir_musicxml(score, xml)
    _log(t("musicxml", ruta=xml))

    _log(t("paso_grabar"))
    if not a.sin_pdf:
        try:
            _log(t("pdf", ruta=render.a_pdf(xml, carpeta / f"{nombre}.pdf")))
        except Exception as e:
            _log(t("aviso", msg=t("no_pdf", e=e)))
    if a.png:
        try:
            paginas = render.a_png(xml, carpeta / f"{nombre}.png")
            _log(t("png", n=len(paginas), ruta=carpeta))
        except Exception as e:
            _log(t("aviso", msg=t("no_png", e=e)))
    if a.audio_prueba:
        try:
            dest = carpeta / f"{nombre}_comprobacion.mp3"
            render.a_audio(xml, dest)
            _log(t("audio_prueba", ruta=dest))
        except Exception as e:
            _log(t("aviso", msg=t("no_prueba", e=e)))

    _log(t("listo_carpeta", seg=time.time() - t0, ruta=carpeta))
    _marcar(carpeta)
    return 0


# --------------------------------------------------------------------------
# partitura -> audio
# --------------------------------------------------------------------------
def cmd_partitura2audio(a) -> int:
    from . import render

    entrada = Path(a.entrada).expanduser().resolve()
    if not entrada.exists():
        _log(t("no_existe", ruta=entrada))
        return 1

    if a.salida:
        destino = Path(a.salida).expanduser().resolve()
    else:
        destino = config.SALIDA_POR_DEFECTO / entrada.stem / f"{entrada.stem}.{a.formato}"
    destino.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    _log(t("sonorizando", nombre=entrada.name))
    try:
        res = render.partitura_a_audio(entrada, destino, bpm=a.bpm, progreso=_log)
    except Exception as e:
        _log(t("error", msg=e))
        return 1

    _log(t("listo_fichero", seg=time.time() - t0, ruta=res,
           mb=res.stat().st_size / 1e6))
    if a.tambien_pdf:
        try:
            _log(t("pdf_misma", ruta=render.a_pdf(entrada, destino.with_suffix(".pdf"))))
        except Exception as e:
            _log(t("aviso", msg=t("no_pdf", e=e)))
    _marcar(res)
    return 0


def cmd_info(a) -> int:
    _log(f"pianoscore {VERSION}\n")
    try:
        _log(f"[ok]   {t('info_mscore')} {config.exige_mscore()}")
    except config.FaltaDependencia as e:
        _log(f"[--]   {t('info_mscore')} {e}")
    marca = "ok" if config.SOUNDFONT.exists() else "--"
    _log(f"[{marca}]   {t('info_soundfont')} {config.SOUNDFONT}")
    hay = config.hay_audiveris()
    _log(f"[{'ok' if hay else '--'}]   {t('info_omr')} "
         f"{t('info_instalado') if hay else t('info_no_instalado')}")

    pesos = list((Path.home() / "piano_transcription_inference_data").glob("*.pth"))
    _log(f"[{'ok' if pesos else '--'}]   {t('info_modelo')} "
         f"{pesos[0] if pesos else t('info_modelo_pendiente')}")

    env = config.entorno_mscore()
    _log(t("info_entorno", plat=env.get("QT_QPA_PLATFORM"), disp=env.get("DISPLAY", "-")))
    try:
        import torch
        _log(t("info_torch", v=torch.__version__, h=torch.get_num_threads()))
    except Exception:
        _log(t("info_sin_torch"))
    return 0


# --------------------------------------------------------------------------
EJEMPLOS = """ejemplos / examples:
  pianoscore a2p cancion.mp3
  pianoscore a2p song.mp3 --bpm 92 --compas 3/4 --png --audio-prueba
  pianoscore a2p song.mp3 --umbral 0.6 --minimo-ms 80
  pianoscore p2a partitura.musicxml -o version.mp3
  pianoscore p2a scan.pdf -o scan.wav
  pianoscore info
"""


def _preparar_idioma(argv) -> None:
    """Resuelve el idioma antes de construir el parser.

    Los textos de ayuda de argparse se fijan al crear el parser, asi que el
    idioma tiene que estar decidido antes: se busca --idioma/--lang a mano.
    """
    from . import idioma

    elegido = None
    for i, arg in enumerate(argv):
        if arg in ("--idioma", "--lang") and i + 1 < len(argv):
            elegido = argv[i + 1]
        elif arg.startswith(("--idioma=", "--lang=")):
            elegido = arg.split("=", 1)[1]
    idioma.fijar(elegido)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _preparar_idioma(argv)

    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--idioma", "--lang", dest="idioma", choices=["es", "en"],
                       help=t("ayuda_idioma"))

    p = argparse.ArgumentParser(
        prog="pianoscore", description=t("ayuda_prog"),
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EJEMPLOS)
    p.add_argument("--version", action="version", version=f"pianoscore {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a2p = sub.add_parser("audio2partitura", aliases=["a2p", "audio2score"],
                         parents=[comun], help=t("ayuda_a2p"))
    a2p.add_argument("entrada", help=t("ayuda_entrada_audio"))
    a2p.add_argument("-o", "--salida", "--output", help=t("ayuda_salida_dir"))
    a2p.add_argument("--bpm", "--tempo", type=float, help=t("ayuda_bpm"))
    a2p.add_argument("--compas", "--time-signature", help=t("ayuda_compas"))
    a2p.add_argument("--subdivision", type=int, default=4, help=t("ayuda_subdivision"))
    a2p.add_argument("--corte-manos", "--hand-split", default="auto",
                     help=t("ayuda_corte"))
    a2p.add_argument("--titulo", "--title", help=t("ayuda_titulo"))
    a2p.add_argument("--compositor", "--composer", default="",
                     help=t("ayuda_compositor"))
    a2p.add_argument("--png", action="store_true", help=t("ayuda_png"))
    a2p.add_argument("--audio-prueba", "--check-audio", action="store_true",
                     dest="audio_prueba", help=t("ayuda_audio_prueba"))
    a2p.add_argument("--umbral", "--threshold", type=float, help=t("ayuda_umbral"))
    a2p.add_argument("--minimo-ms", "--min-ms", type=float, default=0.0,
                     dest="minimo_ms", help=t("ayuda_minimo"))
    a2p.add_argument("--sin-pdf", "--no-pdf", action="store_true", dest="sin_pdf",
                     help=t("ayuda_sin_pdf"))
    a2p.add_argument("--sin-pedal", "--no-pedal", action="store_true",
                     dest="sin_pedal", help=t("ayuda_sin_pedal"))
    a2p.add_argument("--trozo", "--chunk", type=float, default=600.0,
                     help=t("ayuda_trozo"))
    a2p.add_argument("--solape", "--overlap", type=float, default=10.0,
                     help=t("ayuda_solape"))
    a2p.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    a2p.set_defaults(func=cmd_audio2partitura)

    p2a = sub.add_parser("partitura2audio", aliases=["p2a", "score2audio"],
                         parents=[comun], help=t("ayuda_p2a"))
    p2a.add_argument("entrada", help=t("ayuda_entrada_part"))
    p2a.add_argument("-o", "--salida", "--output", help=t("ayuda_salida_fich"))
    p2a.add_argument("--formato", "--format", default="mp3",
                     choices=["mp3", "wav", "flac", "ogg"], help=t("ayuda_formato"))
    p2a.add_argument("--bpm", "--tempo", type=float, help=t("ayuda_bpm2"))
    p2a.add_argument("--tambien-pdf", "--also-pdf", action="store_true",
                     dest="tambien_pdf", help=t("ayuda_tambien_pdf"))
    p2a.set_defaults(func=cmd_partitura2audio)

    inf = sub.add_parser("info", parents=[comun], help=t("ayuda_info"))
    inf.set_defaults(func=cmd_info)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except KeyboardInterrupt:
        _log(t("interrumpido"))
        return 130
    except BrokenPipeError:
        # Pasa al canalizar la salida a algo que la corta, como `| head`.
        # Sin esto Python imprime un traceback al cerrar stdout.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except Exception:
            pass
        return 0
    except config.FaltaDependencia as e:
        _log("\n" + t("error", msg=e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
