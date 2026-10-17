# pianoscore

**English** · [Español](README.es.md)

Turns **audio into piano sheet music** and **sheet music into audio**, both ways,
always over the complete recording — nothing is trimmed or sampled.

```
audio (mp3, wav, m4a, ogg, flac, video…)  ──►  PDF + MusicXML + MIDI
MusicXML / MIDI / scanned PDF             ──►  mp3, wav, flac, ogg
```

Everything runs locally, offline once installed, and without root.

---

## Install

```bash
./install.sh
```

It downloads, inside the project folder:

- **uv** plus a Python 3.11 virtual environment with the audio libraries
- **PyTorch** (CPU) and the piano transcription model (~165 MB, fetched on first use)
- **MuseScore 3.6.2** as an AppImage, which engraves the PDFs and synthesizes audio

Check everything is in place:

```bash
./pianoscore info
```

To also read **scanned** scores from PDF or images (Audiveris, ~75 MB; it bundles
its own Java, so you don't need to install one):

```bash
./install.sh --with-omr
```

### Requirements

Linux with `ffmpeg`, `wget`, `curl` and `dpkg-deb`. The bundled MuseScore only
ships Qt's `xcb` plugin, so it needs an X display — X11 or XWayland is fine. On a
headless server, run it under `xvfb-run`.

---

## Window

If you'd rather not touch the terminal:

```bash
./pianoscore-gui
```

It also shows up as **pianoscore** in the applications menu.

One tab per direction, a browse button, the options in plain sight (tempo, time
signature, shortest value, hand split, cleanup) and a log that streams progress
live, with a progress bar and a cancel button. When it finishes, *Open result*
launches the PDF and *Open folder* the output directory. There is a language
selector in the top-right corner.

Under the hood it calls the same command the terminal does, so both do exactly
the same thing: the window never freezes while the model works, and cancelling
really kills the process.

---

## Usage

### Audio ➜ sheet music

```bash
./pianoscore a2p song.mp3
```

Leaves in `salida/song/`:

| File | What it is |
|---|---|
| `song.pdf` | the engraved score, two staves under a brace |
| `song.musicxml` | to open and edit in MuseScore, Sibelius, Finale, Dorico… |
| `song.mid` | the **faithful** MIDI: unquantized, with velocities and pedal |

The `.mid` keeps the real phrasing as played; the `.musicxml` and `.pdf` are the
version fitted into bars, which is the one you can read and play.

Useful options:

```bash
./pianoscore a2p song.mp3 --bpm 92 --compas 3/4    # when it misreads the beat
./pianoscore a2p song.mp3 --subdivision 2          # round to eighth notes
./pianoscore a2p song.mp3 --corte-manos C4         # fix where the hands split
./pianoscore a2p song.mp3 --png --audio-prueba     # PNG pages + audio to compare
./pianoscore a2p song.mp3 --umbral 0.6 --minimo-ms 80   # clean up messy recordings
./pianoscore a2p song.mp3 --titulo "Nocturne" --compositor "Chopin"
```

Every option has an English alias, so `--tempo`, `--time-signature`,
`--hand-split`, `--title`, `--composer`, `--threshold`, `--min-ms`, `--check-audio`,
`--no-pdf`, `--no-pedal`, `--chunk`, `--overlap` and `--output` all work too, as do
the `audio2score` and `score2audio` subcommands.

`--umbral` raises the confidence the model needs before accepting a note (0.30 by
default) and `--minimo-ms` drops blips shorter than the given value. You only need
them when the recording isn't solo piano: over a band with vocals, the defaults
produce hundreds of notes nobody played.

`--audio-prueba` synthesizes the resulting score, so playing it next to the
original tells you immediately what came out right and what didn't.

### Sheet music ➜ audio

```bash
./pianoscore p2a score.musicxml -o version.mp3
./pianoscore p2a score.mid -o version.wav
./pianoscore p2a scan.pdf -o scan.mp3        # needs --with-omr
./pianoscore p2a score.musicxml --bpm 70     # play it slower
```

Accepts `.musicxml`, `.xml`, `.mxl`, `.mid`, `.midi`, `.mscz` and, with OMR
installed, `.pdf`, `.png`, `.jpg`. Add `--tambien-pdf` / `--also-pdf` to engrave
the PDF along the way.

### Language

Messages follow the system locale. Force one with `--lang en` / `--idioma es`, or
with the `PIANOSCORE_LANG` environment variable.

---

## What to expect from the quality

Transcription uses ByteDance's CRNN model, trained on MAESTRO and specialized in
piano: it detects onsets, durations, velocities and sustain pedal.

Measured on two round trips (score ➜ audio ➜ score), both in `ejemplos/`:

| | notes | F1 | onsets | tempo | meter | key |
|---|---|---|---|---|---|---|
| Two-hand piece, 4/4 | 61 → 63 | 98.4 % | ±51 ms | 87.9 (real 88) | 4/4 ✓ | C major ✓ |
| Waltz, 3/4, E♭ major | 102 → 102 | 99.0 % | ±52 ms | 125.6 (real 126) | 3/4 ✓ | E♭ major ✓ |

The other way round, on a cleanly engraved PDF, OMR recovered all 106 pitches, the
13 bars, the key signature and the time signature without a single error. A real
scan, with its grain and skew, does considerably worse.

The MusicXML comes out as a single `<part>` with two staves: a real piano grand
staff with its brace, not two separate instruments.

Where it falls short, and what to do:

- **Solo piano** is its home ground. With vocals, drums or a band on top the
  transcription gets messy: the model only knows about pianos. Raising `--umbral`
  to 0.5–0.7 and setting `--minimo-ms 80` helps, but it won't invent a good score
  out of a band recording.
- **Beat and meter** are estimated from the audio. Heavy rubato or an upbeat can
  throw it off: pin them down with `--bpm` and `--compas`.
- **Hand separation** is a register heuristic. It works well when the hands don't
  overlap, but where the melody dips into the accompaniment's range no single
  threshold gets it right. Adjust with `--corte-manos`, or split them by hand in
  MuseScore by opening the `.musicxml`.
- **The score is an editable starting point**, not a finished edition.

---

## How it works

**Audio ➜ sheet music**, in five steps:

1. `ffmpeg` decodes to mono 16 kHz. Long recordings are cut into overlapping
   chunks and rejoined by absolute time, with no duplicated or lost notes.
2. The CRNN model returns notes with onset, offset, velocity and pedal.
3. `librosa` detects the beat; the meter is then decided from the transcribed
   notes rather than from audio energy, because the reliable cue for a downbeat
   is the low register — the bass marks the harmony change.
4. Notes are fitted to the grid by interpolating against the real beat times, so
   rubato is absorbed instead of shifting the whole piece.
5. `music21` splits the hands, estimates the key and writes the MusicXML;
   MuseScore engraves the PDF.

**Sheet music ➜ audio**: MuseScore synthesizes with the bundled MuseScore_General
soundfont. If the input is a PDF or an image, it goes through Audiveris first.

---

## Layout

```
pianoscore            terminal launcher
pianoscore-gui        window launcher
install.sh            root-free install (instalar.sh is a symlink to it)
src/pianoscore/
  cli.py              command line
  gui.py              desktop window (Tkinter)
  idioma.py           Spanish and English strings
  transcribe.py       audio -> MIDI (CRNN model, overlapping chunks)
  ritmo.py            beat, meter and quantization
  partitura.py        hand separation and MusicXML writing
  render.py           MuseScore conversions
  omr.py              reading scanned scores
  config.py           paths and tool discovery
ejemplos/             test pieces and check scripts
salida/               results
```
