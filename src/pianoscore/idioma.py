"""Textos en español e inglés / Spanish and English strings.

El idioma sale de la variable PIANOSCORE_LANG si está puesta y, si no, de la
configuración regional del sistema; cualquier cosa que no empiece por "es"
cae en inglés.

The language comes from PIANOSCORE_LANG when set, otherwise from the system
locale; anything that does not start with "es" falls back to English.
"""
from __future__ import annotations

import os

IDIOMAS = ("es", "en")
_actual: str | None = None


def detectar() -> str:
    forzado = os.environ.get("PIANOSCORE_LANG", "").strip().lower()
    if forzado[:2] in IDIOMAS:
        return forzado[:2]
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        valor = os.environ.get(var, "").strip().lower()
        if valor:
            return "es" if valor.startswith("es") else "en"
    return "en"


def actual() -> str:
    global _actual
    if _actual is None:
        _actual = detectar()
    return _actual


def fijar(codigo: str | None) -> str:
    global _actual
    if codigo and codigo[:2].lower() in IDIOMAS:
        _actual = codigo[:2].lower()
    else:
        _actual = detectar()
    return _actual


_NOTAS_ES = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa",
             "G": "Sol", "A": "La", "B": "Si"}


def tonalidad(k) -> str:
    """Nombra una tonalidad de music21 en el idioma activo.

    music21 siempre la escribe a la inglesa ("E- major"); en español se
    espera "Mi bemol mayor".
    """
    if k is None:
        return "?"
    if actual() != "es":
        return str(k)
    try:
        nombre = _NOTAS_ES.get(k.tonic.step, k.tonic.step)
        alt = k.tonic.name[1:]
        if alt:
            nombre += " bemol" * alt.count("-") + " sostenido" * alt.count("#")
        return f"{nombre} {'mayor' if k.mode == 'major' else 'menor'}"
    except Exception:
        return str(k)


def t(clave: str, **kw) -> str:
    """Devuelve el texto de `clave` en el idioma activo, formateado con kw."""
    par = TEXTOS.get(clave)
    if par is None:
        return clave
    texto = par.get(actual()) or par.get("en") or clave
    return texto.format(**kw) if kw else texto


TEXTOS: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- común
    "no_existe": {
        "es": "ERROR: no existe {ruta}",
        "en": "ERROR: {ruta} does not exist",
    },
    "error": {"es": "ERROR: {msg}", "en": "ERROR: {msg}"},
    "aviso": {"es": "  AVISO: {msg}", "en": "  WARNING: {msg}"},
    "interrumpido": {"es": "\nInterrumpido.", "en": "\nInterrupted."},

    # --------------------------------------------------- audio -> partitura
    "paso_transcribir": {
        "es": "[1/5] Transcribiendo el audio completo  ({nombre})",
        "en": "[1/5] Transcribing the whole recording  ({nombre})",
    },
    "audio_info": {
        "es": "  audio: {min:.1f} min ({seg:.1f} s) a {sr} Hz mono",
        "en": "  audio: {min:.1f} min ({seg:.1f} s) at {sr} Hz mono",
    },
    "umbral_info": {
        "es": "  umbral de deteccion: {u:.2f} (por defecto 0.30)",
        "en": "  detection threshold: {u:.2f} (default 0.30)",
    },
    "tramo": {
        "es": "  tramo {i}/{n}  [{a:.1f}-{b:.1f} min]",
        "en": "  chunk {i}/{n}  [{a:.1f}-{b:.1f} min]",
    },
    "notas_detectadas": {
        "es": "  {notas} notas, {pedales} pedaleos",
        "en": "  {notas} notes, {pedales} pedal marks",
    },
    "descartadas": {
        "es": "  descartadas {n} notas de menos de {ms:g} ms",
        "en": "  dropped {n} notes shorter than {ms:g} ms",
    },
    "sin_notas": {
        "es": "ERROR: no se detecto ninguna nota de piano en el audio.",
        "en": "ERROR: no piano notes were detected in the recording.",
    },
    "midi_fiel": {
        "es": "  MIDI fiel (sin cuantizar): {ruta}",
        "en": "  Faithful MIDI (unquantized): {ruta}",
    },
    "paso_pulso": {
        "es": "[2/5] Detectando pulso y compas",
        "en": "[2/5] Detecting beat and time signature",
    },
    "pulso_info": {
        "es": "  tempo ~{bpm:.1f} BPM, {ppc} pulsos por compas",
        "en": "  tempo ~{bpm:.1f} BPM, {ppc} beats per bar",
    },
    "paso_cuantizar": {
        "es": "[3/5] Cuantizando a 1/{sub} de pulso",
        "en": "[3/5] Quantizing to 1/{sub} of a beat",
    },
    "cuantizar_info": {
        "es": "  {notas} notas en {compases} compases",
        "en": "  {notas} notes across {compases} bars",
    },
    "paso_partitura": {
        "es": "[4/5] Escribiendo la partitura a dos pentagramas",
        "en": "[4/5] Writing the two-stave score",
    },
    "tonalidad": {
        "es": "  tonalidad estimada: {k}",
        "en": "  estimated key: {k}",
    },
    "musicxml": {"es": "  MusicXML: {ruta}", "en": "  MusicXML: {ruta}"},
    "paso_grabar": {
        "es": "[5/5] Grabando la partitura",
        "en": "[5/5] Engraving the score",
    },
    "pdf": {"es": "  PDF: {ruta}", "en": "  PDF: {ruta}"},
    "png": {
        "es": "  PNG: {n} pagina(s) en {ruta}",
        "en": "  PNG: {n} page(s) in {ruta}",
    },
    "audio_prueba": {
        "es": "  Audio de la partitura (para comparar): {ruta}",
        "en": "  Audio of the score (to compare): {ruta}",
    },
    "no_pdf": {
        "es": "no se pudo generar el PDF ({e})",
        "en": "could not produce the PDF ({e})",
    },
    "no_png": {
        "es": "no se pudo generar el PNG ({e})",
        "en": "could not produce the PNG ({e})",
    },
    "no_prueba": {
        "es": "no se pudo sintetizar la comprobacion ({e})",
        "en": "could not synthesize the check audio ({e})",
    },
    "listo_carpeta": {
        "es": "\nListo en {seg:.0f} s. Resultados en: {ruta}",
        "en": "\nDone in {seg:.0f} s. Results in: {ruta}",
    },

    # --------------------------------------------------- partitura -> audio
    "sonorizando": {"es": "Sonorizando {nombre}", "en": "Rendering {nombre}"},
    "omr_lanzando": {
        "es": "  partitura escaneada: lanzando reconocimiento optico (OMR)...",
        "en": "  scanned score: running optical music recognition (OMR)...",
    },
    "omr_reconocida": {
        "es": "  partitura reconocida: {ruta}",
        "en": "  recognized score: {ruta}",
    },
    "forzando_tempo": {
        "es": "  forzando tempo a {bpm:g} BPM",
        "en": "  forcing tempo to {bpm:g} BPM",
    },
    "sintetizando": {
        "es": "  sintetizando a {fmt}...",
        "en": "  synthesizing to {fmt}...",
    },
    "listo_fichero": {
        "es": "\nListo en {seg:.0f} s: {ruta}  ({mb:.1f} MB)",
        "en": "\nDone in {seg:.0f} s: {ruta}  ({mb:.1f} MB)",
    },
    "pdf_misma": {
        "es": "PDF de la misma partitura: {ruta}",
        "en": "PDF of the same score: {ruta}",
    },

    # ------------------------------------------------------------- errores
    "falta_mscore": {
        "es": ("No encuentro MuseScore.\nEsperaba: {ruta}\n"
               "Ejecuta ./instalar.sh para descargarlo (no hace falta root)."),
        "en": ("MuseScore not found.\nExpected at: {ruta}\n"
               "Run ./install.sh to download it (no root needed)."),
    },
    "falta_audiveris": {
        "es": ("Audiveris no esta instalado; hace falta para leer partituras en "
               "PDF o imagen.\nInstalalo con: ./instalar.sh --con-omr\n"
               "Alternativa sin OMR: exporta la partitura a MusicXML o MIDI y "
               "pasa ese fichero."),
        "en": ("Audiveris is not installed; it is needed to read scores from PDF "
               "or images.\nInstall it with: ./install.sh --with-omr\n"
               "Without OMR: export the score to MusicXML or MIDI and pass that "
               "file instead."),
    },
    "mscore_fallo": {
        "es": "MuseScore no pudo generar {nombre}.\nEntrada: {entrada}\n{detalle}",
        "en": "MuseScore could not produce {nombre}.\nInput: {entrada}\n{detalle}",
    },
    "formato_audio_malo": {
        "es": "Formato de audio no soportado: {ext}. Usa uno de: {lista}",
        "en": "Unsupported audio format: {ext}. Use one of: {lista}",
    },
    "formato_entrada_malo": {
        "es": ("No se que hacer con '{ext}'.\nPartituras: {partituras}\n"
               "Escaneadas: {imagenes}"),
        "en": ("Don't know what to do with '{ext}'.\nScores: {partituras}\n"
               "Scanned: {imagenes}"),
    },
    "omr_fallo": {
        "es": ("Audiveris no pudo extraer la partitura de {nombre}.\n{detalle}\n"
               "Los escaneos borrosos o con poca resolucion suelen fallar: "
               "prueba con 300 dpi."),
        "en": ("Audiveris could not extract the score from {nombre}.\n{detalle}\n"
               "Blurry or low-resolution scans usually fail: try 300 dpi."),
    },
    "ffmpeg_fallo": {
        "es": "ffmpeg no pudo leer {ruta}:\n{detalle}",
        "en": "ffmpeg could not read {ruta}:\n{detalle}",
    },

    # ---------------------------------------------------------------- info
    "info_mscore": {"es": "MuseScore       ", "en": "MuseScore       "},
    "info_soundfont": {"es": "Soundfont       ", "en": "Soundfont       "},
    "info_omr": {"es": "Audiveris (OMR) ", "en": "Audiveris (OMR) "},
    "info_modelo": {"es": "Modelo CRNN     ", "en": "CRNN model      "},
    "info_instalado": {"es": "instalado", "en": "installed"},
    "info_no_instalado": {
        "es": "no instalado -> ./instalar.sh --con-omr",
        "en": "not installed -> ./install.sh --with-omr",
    },
    "info_modelo_pendiente": {
        "es": "se descargara en el primer uso (~165 MB)",
        "en": "will download on first use (~165 MB)",
    },
    "info_entorno": {
        "es": "\nMuseScore se ejecutara con QT_QPA_PLATFORM={plat} DISPLAY={disp}",
        "en": "\nMuseScore will run with QT_QPA_PLATFORM={plat} DISPLAY={disp}",
    },
    "info_torch": {
        "es": "torch {v}  (hilos: {h})",
        "en": "torch {v}  (threads: {h})",
    },
    "info_sin_torch": {"es": "torch no disponible", "en": "torch unavailable"},

    # ----------------------------------------------------------- ayuda CLI
    "ayuda_prog": {
        "es": "Convierte audio en partitura de piano y partituras en audio.",
        "en": "Turns audio into piano sheet music, and sheet music into audio.",
    },
    "ayuda_a2p": {
        "es": "audio (mp3/wav/...) -> partitura PDF + MusicXML + MIDI",
        "en": "audio (mp3/wav/...) -> PDF + MusicXML + MIDI score",
    },
    "ayuda_p2a": {
        "es": "MusicXML/MIDI/PDF escaneado -> audio",
        "en": "MusicXML/MIDI/scanned PDF -> audio",
    },
    "ayuda_info": {
        "es": "comprobar que todo esta instalado",
        "en": "check that everything is installed",
    },
    "ayuda_entrada_audio": {
        "es": "fichero de audio (se transcribe entero)",
        "en": "audio file (transcribed in full)",
    },
    "ayuda_entrada_part": {
        "es": "partitura: .musicxml .xml .mxl .mid, o .pdf/.png escaneado",
        "en": "score: .musicxml .xml .mxl .mid, or a scanned .pdf/.png",
    },
    "ayuda_salida_dir": {
        "es": "carpeta de resultados",
        "en": "output folder",
    },
    "ayuda_salida_fich": {
        "es": "fichero de audio de salida",
        "en": "output audio file",
    },
    "ayuda_bpm": {
        "es": "fijar el tempo en vez de detectarlo",
        "en": "set the tempo instead of detecting it",
    },
    "ayuda_bpm2": {"es": "forzar otro tempo", "en": "force a different tempo"},
    "ayuda_compas": {
        "es": "fijar el compas, por ejemplo 4/4 o 3/4",
        "en": "set the time signature, e.g. 4/4 or 3/4",
    },
    "ayuda_subdivision": {
        "es": ("figura mas corta por pulso: 2=corcheas, 4=semicorcheas "
               "(por defecto 4)"),
        "en": ("shortest value per beat: 2=eighths, 4=sixteenths (default 4)"),
    },
    "ayuda_corte": {
        "es": "altura que separa las manos: auto, o una nota como C4 / 60",
        "en": "pitch that splits the hands: auto, or a note like C4 / 60",
    },
    "ayuda_titulo": {"es": "titulo de la partitura", "en": "score title"},
    "ayuda_compositor": {
        "es": "autor que aparece en la partitura",
        "en": "composer shown on the score",
    },
    "ayuda_png": {
        "es": "exportar tambien las paginas en PNG",
        "en": "also export the pages as PNG",
    },
    "ayuda_audio_prueba": {
        "es": "sintetizar la partitura resultante para comparar con el original",
        "en": "synthesize the resulting score to compare with the original",
    },
    "ayuda_sin_pdf": {"es": "no generar PDF", "en": "skip the PDF"},
    "ayuda_sin_pedal": {
        "es": "no escribir el pedal en el MIDI",
        "en": "do not write pedal into the MIDI",
    },
    "ayuda_umbral": {
        "es": ("confianza minima para dar una nota por buena (0-1, por defecto "
               "0.30). Subirlo a 0.5-0.7 limpia grabaciones que no son de piano "
               "solo"),
        "en": ("minimum confidence to accept a note (0-1, default 0.30). Raise it "
               "to 0.5-0.7 to clean up recordings that are not solo piano"),
    },
    "ayuda_minimo": {
        "es": ("descartar notas mas cortas que esto en milisegundos (prueba 80 si "
               "salen muchos repiques sueltos)"),
        "en": ("drop notes shorter than this in milliseconds (try 80 if you get "
               "lots of stray blips)"),
    },
    "ayuda_trozo": {
        "es": "segundos por tramo en audios largos (por defecto 600)",
        "en": "seconds per chunk for long recordings (default 600)",
    },
    "ayuda_solape": {
        "es": "solape entre tramos en segundos",
        "en": "overlap between chunks, in seconds",
    },
    "ayuda_formato": {
        "es": "formato si no se indica -o (por defecto mp3)",
        "en": "format when -o is omitted (default mp3)",
    },
    "ayuda_tambien_pdf": {
        "es": "grabar ademas el PDF",
        "en": "also engrave the PDF",
    },
    "ayuda_idioma": {
        "es": "idioma de los mensajes: es o en (por defecto, el del sistema)",
        "en": "message language: es or en (default: the system's)",
    },

    # ------------------------------------------------------------- ventana
    "v_titulo": {
        "es": "pianoscore - audio y partituras de piano",
        "en": "pianoscore - piano audio and sheet music",
    },
    "v_pest_a2p": {
        "es": "   Audio  ->  Partitura   ",
        "en": "   Audio  ->  Sheet music   ",
    },
    "v_pest_p2a": {
        "es": "   Partitura  ->  Audio   ",
        "en": "   Sheet music  ->  Audio   ",
    },
    "v_audio": {"es": "Audio", "en": "Audio"},
    "v_partitura": {"es": "Partitura", "en": "Score"},
    "v_examinar": {"es": "Examinar...", "en": "Browse..."},
    "v_titulo_campo": {"es": "Título", "en": "Title"},
    "v_autor": {"es": "Autor", "en": "Composer"},
    "v_tempo": {"es": "Tempo (BPM)", "en": "Tempo (BPM)"},
    "v_compas": {"es": "Compás", "en": "Time signature"},
    "v_automatico": {"es": "automático", "en": "automatic"},
    "v_figura": {"es": "Figura más corta", "en": "Shortest value"},
    "v_separar": {"es": "Separar manos en", "en": "Split hands at"},
    "v_limpieza": {
        "es": "Limpieza (útil si la grabación no es de piano solo)",
        "en": "Cleanup (useful when the recording is not solo piano)",
    },
    "v_confianza": {"es": "Confianza mínima (0-1)", "en": "Minimum confidence (0-1)"},
    "v_vacio": {"es": "vacío = 0.30", "en": "empty = 0.30"},
    "v_descartar": {"es": "Descartar notas de menos de", "en": "Drop notes shorter than"},
    "v_png": {"es": "Páginas en PNG", "en": "Pages as PNG"},
    "v_comprobacion": {"es": "Audio de comprobación", "en": "Check audio"},
    "v_sin_pedal": {"es": "Sin pedal", "en": "No pedal"},
    "v_btn_a2p": {"es": "Transcribir a partitura", "en": "Transcribe to sheet music"},
    "v_btn_p2a": {"es": "Convertir a audio", "en": "Convert to audio"},
    "v_formato": {"es": "Formato", "en": "Format"},
    "v_tambien_pdf": {
        "es": "Grabar además el PDF de la partitura",
        "en": "Also engrave the score as PDF",
    },
    "v_aviso_omr": {
        "es": ("Acepta MusicXML, MIDI y ficheros de MuseScore. Para un PDF o una "
               "imagen escaneada hace falta Audiveris, que se instala aparte con "
               "./instalar.sh --con-omr."),
        "en": ("Accepts MusicXML, MIDI and MuseScore files. A scanned PDF or image "
               "needs Audiveris, installed separately with "
               "./install.sh --with-omr."),
    },
    "v_progreso": {"es": "Progreso", "en": "Progress"},
    "v_listo": {"es": "Listo.", "en": "Ready."},
    "v_abrir_carpeta": {"es": "Abrir carpeta", "en": "Open folder"},
    "v_abrir_resultado": {"es": "Abrir resultado", "en": "Open result"},
    "v_cancelar": {"es": "Cancelar", "en": "Cancel"},
    "v_transcribiendo": {"es": "Transcribiendo...", "en": "Transcribing..."},
    "v_convirtiendo": {"es": "Convirtiendo...", "en": "Converting..."},
    "v_cancelando": {"es": "Cancelando...", "en": "Cancelling..."},
    "v_cancelado": {"es": "Cancelado.", "en": "Cancelled."},
    "v_terminado": {"es": "Terminado.", "en": "Finished."},
    "v_con_error": {
        "es": "Terminó con error (código {c}).",
        "en": "Finished with an error (code {c}).",
    },
    "v_falta_audio": {"es": "Falta el audio", "en": "No audio selected"},
    "v_falta_audio_msg": {
        "es": "Elige un fichero de audio.",
        "en": "Choose an audio file.",
    },
    "v_falta_part": {"es": "Falta la partitura", "en": "No score selected"},
    "v_falta_part_msg": {
        "es": "Elige un fichero de partitura.",
        "en": "Choose a score file.",
    },
    "v_filtro_audio": {"es": "Audio", "en": "Audio"},
    "v_filtro_part": {"es": "Partituras", "en": "Scores"},
    "v_filtro_escan": {"es": "Partituras escaneadas", "en": "Scanned scores"},
    "v_filtro_todos": {"es": "Todos", "en": "All files"},
    "v_corcheas": {"es": "corcheas", "en": "eighths"},
    "v_semicorcheas": {"es": "semicorcheas", "en": "sixteenths"},
    "v_tresillos": {"es": "tresillos de corchea", "en": "eighth triplets"},
    "v_fusas": {"es": "fusas", "en": "thirty-seconds"},
    "v_pista": {
        "es": ("  Elige un fichero arriba y pulsa el boton.\n\n"
               "  Audio -> Partitura deja un PDF, un MusicXML editable y un MIDI\n"
               "  en salida/<nombre>/. Transcribe la grabacion entera; cuenta con\n"
               "  cerca de un minuto de CPU por cada minuto de audio.\n\n"
               "  El modelo entiende piano solo. Con voz, bateria o banda encima\n"
               "  la partitura sale sucia: ahi ayuda subir la confianza minima a\n"
               "  0.5-0.7 y descartar las notas de menos de 80 ms.\n"),
        "en": ("  Pick a file above and press the button.\n\n"
               "  Audio -> Sheet music leaves a PDF, an editable MusicXML and a\n"
               "  MIDI in salida/<name>/. It transcribes the whole recording;\n"
               "  budget about a minute of CPU per minute of audio.\n\n"
               "  The model only understands solo piano. With vocals, drums or a\n"
               "  band on top the score comes out messy: raising the minimum\n"
               "  confidence to 0.5-0.7 and dropping notes under 80 ms helps.\n"),
    },
}
