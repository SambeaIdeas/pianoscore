# pianoscore

[English](README.md) · **Español**

Convierte **audio en partitura de piano** y **partituras en audio**, en las dos
direcciones y siempre sobre la pieza completa: no recorta ni muestrea trozos.

```
audio (mp3, wav, m4a, ogg, flac, vídeo…)  ──►  PDF + MusicXML + MIDI
MusicXML / MIDI / PDF escaneado           ──►  mp3, wav, flac, ogg
```

Todo funciona en local, sin conexión una vez instalado y sin permisos de root.

---

## Instalación

```bash
./install.sh
```

Descarga, dentro de la propia carpeta del proyecto:

- **uv** y un entorno virtual con Python 3.11 y las librerías de audio
- **PyTorch** (CPU) y el modelo de transcripción de piano (~165 MB, al primer uso)
- **MuseScore 3.6.2** en AppImage, que graba los PDF y sintetiza el audio

Comprueba que todo está en su sitio:

```bash
./pianoscore info
```

Para leer además partituras **escaneadas** en PDF o imagen (Audiveris, ~75 MB;
trae su propio Java dentro, no hace falta instalar ninguno):

```bash
./install.sh --with-omr
```

### Requisitos

Linux con `ffmpeg`, `wget`, `curl` y `dpkg-deb`. El MuseScore incluido solo trae
el plugin `xcb` de Qt, así que necesita un display X: vale X11 o XWayland. En un
servidor sin pantalla, lánzalo con `xvfb-run`.

---

## Ventana

Si prefieres no tocar la terminal:

```bash
./pianoscore-gui
```

También aparece como **pianoscore** en el menú de aplicaciones.

Tiene una pestaña por sentido, botón de examinar, las opciones a la vista
(tempo, compás, figura más corta, separación de manos, limpieza) y un registro
que va mostrando el avance en vivo, con barra de progreso y botón de cancelar.
Al terminar, «Abrir resultado» lanza el PDF y «Abrir carpeta» el directorio.
Arriba a la derecha hay un selector de idioma.

Por dentro llama a la misma orden que la terminal, así que hace exactamente lo
mismo: la ventana nunca se queda congelada mientras el modelo trabaja, y
cancelar mata el proceso de verdad.

---

## Uso

### Audio ➜ partitura

```bash
./pianoscore a2p cancion.mp3
```

Deja en `salida/cancion/`:

| Fichero | Qué es |
|---|---|
| `cancion.pdf` | la partitura grabada, dos pentagramas con llave |
| `cancion.musicxml` | para abrir y editar en MuseScore, Sibelius, Finale, Dorico… |
| `cancion.mid` | el MIDI **fiel**: sin cuantizar, con velocidades y pedal |

El `.mid` conserva el fraseo real tal y como suena; el `.musicxml` y el `.pdf`
son la versión encajada en compases, que es la que se puede leer y tocar.

Opciones útiles:

```bash
./pianoscore a2p cancion.mp3 --bpm 92 --compas 3/4   # si no acierta el pulso
./pianoscore a2p cancion.mp3 --subdivision 2         # redondear a corcheas
./pianoscore a2p cancion.mp3 --corte-manos C4        # fijar la separación de manos
./pianoscore a2p cancion.mp3 --png --audio-prueba    # páginas PNG + audio para comparar
./pianoscore a2p cancion.mp3 --umbral 0.6 --minimo-ms 80   # limpiar grabaciones sucias
./pianoscore a2p cancion.mp3 --titulo "Nocturno" --compositor "Chopin"
```

Cada opción tiene su alias en inglés, por si compartes órdenes: `--tempo`,
`--time-signature`, `--hand-split`, `--title`, `--composer`, `--threshold`,
`--min-ms`, `--check-audio`, `--no-pdf`, `--no-pedal`, `--chunk`, `--overlap` y
`--output`, además de los subcomandos `audio2score` y `score2audio`.

`--umbral` sube la confianza que se le exige al modelo para dar una nota por
buena (0,30 por defecto) y `--minimo-ms` descarta los repiques más cortos que el
valor dado. Los dos solo hacen falta cuando la grabación no es de piano solo:
sobre una banda con voces, por defecto salen cientos de notas que nadie tocó.

`--audio-prueba` sintetiza la partitura resultante: escuchándola junto al
original se oye enseguida qué ha quedado bien y qué no.

### Partitura ➜ audio

```bash
./pianoscore p2a partitura.musicxml -o version.mp3
./pianoscore p2a partitura.mid -o version.wav
./pianoscore p2a escaneo.pdf -o escaneo.mp3        # necesita --with-omr
./pianoscore p2a partitura.musicxml --bpm 70       # tocarla más lenta
```

Acepta `.musicxml`, `.xml`, `.mxl`, `.mid`, `.midi`, `.mscz` y, con OMR
instalado, `.pdf`, `.png`, `.jpg`. Con `--tambien-pdf` graba de paso el PDF.

### Idioma

Los mensajes siguen el idioma del sistema. Para forzarlo, `--idioma es` /
`--lang en`, o la variable de entorno `PIANOSCORE_LANG`.

---

## Qué esperar de la calidad

La transcripción usa el modelo CRNN de ByteDance, entrenado sobre MAESTRO y
especializado en piano: detecta ataques, duraciones, intensidades y pedal.

Medido con dos pruebas de ida y vuelta (partitura ➜ audio ➜ partitura), que
están en `ejemplos/`:

| | notas | F1 | ataques | tempo | compás | tonalidad |
|---|---|---|---|---|---|---|
| Pieza a dos manos, 4/4 | 61 → 63 | 98,4 % | ±51 ms | 87,9 (real 88) | 4/4 ✓ | Do M ✓ |
| Vals, 3/4, Mi♭ mayor | 102 → 102 | 99,0 % | ±52 ms | 125,6 (real 126) | 3/4 ✓ | Mi♭ M ✓ |

En sentido contrario, sobre un PDF grabado limpio el OMR recuperó las 106
alturas, los 13 compases, la armadura y el compás sin un solo error. Un escaneo
real, con su grano y su torcedura, da bastante menos.

El MusicXML sale como un único `<part>` con dos pautas: un pentagrama doble de
piano de verdad, con su llave, no dos instrumentos sueltos.

Dónde falla, y qué hacer:

- **Piano solo** es su terreno. Con voz, batería o banda encima la transcripción
  se ensucia bastante: el modelo solo sabe de piano. Subir `--umbral` a 0,5–0,7 y
  poner `--minimo-ms 80` ayuda, pero no se va a inventar una buena partitura a
  partir de una grabación de banda.
- **El compás y el pulso** se estiman del audio. Si la pieza tiene rubato fuerte
  o entra en anacrusa, puede equivocarse: fíjalos con `--bpm` y `--compas`.
- **La separación de manos** es una heurística por registro. Funciona bien cuando
  las manos no se cruzan, pero en texturas donde la melodía baja al registro del
  acompañamiento no hay umbral que acierte del todo. Ajusta con `--corte-manos`,
  o repártelas a mano en MuseScore abriendo el `.musicxml`.
- **La partitura es un punto de partida editable**, no una edición final.

---

## Cómo funciona

**Audio ➜ partitura**, en cinco pasos:

1. `ffmpeg` decodifica a mono 16 kHz. Los audios largos se trocean con solape y
   se vuelven a unir por tiempos absolutos, sin duplicar ni perder notas.
2. El modelo CRNN saca notas con ataque, final, intensidad y pedal.
3. `librosa` detecta el pulso; el compás se decide con las notas ya transcritas,
   no con la energía del audio: el indicio fiable del tiempo fuerte es el
   registro grave, porque el bajo marca el cambio de armonía.
4. Las notas se encajan en la rejilla interpolando contra los pulsos reales, de
   modo que el rubato se absorbe en lugar de desplazar la pieza entera.
5. `music21` reparte las manos, estima la tonalidad y escribe el MusicXML;
   MuseScore lo graba en PDF.

**Partitura ➜ audio**: MuseScore sintetiza con el soundfont MuseScore_General
que trae incluido. Si la entrada es un PDF o una imagen, antes pasa por
Audiveris para reconocer la partitura.

---

## Estructura

```
pianoscore            lanzador de la terminal
pianoscore-gui        lanzador de la ventana
install.sh            instalación sin root (instalar.sh es un enlace a él)
src/pianoscore/
  cli.py              línea de comandos
  gui.py              ventana de escritorio (Tkinter)
  idioma.py           textos en español e inglés
  transcribe.py       audio -> MIDI (modelo CRNN, troceado con solape)
  ritmo.py            pulso, compás y cuantización
  partitura.py        separación de manos y escritura del MusicXML
  render.py           conversiones con MuseScore
  omr.py              lectura de partituras escaneadas
  config.py           rutas y detección de herramientas
ejemplos/             piezas de prueba y scripts de comprobación
salida/               resultados
```
