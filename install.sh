#!/usr/bin/env bash
# Instalacion completa sin permisos de root / full install without root.
#
#   ./install.sh                nucleo / core (audio <-> sheet music)
#   ./install.sh --with-omr     + lectura de partituras escaneadas (PDF/imagen)
#                                 + reading scanned scores (PDF/image)
#
# Alias aceptados / accepted aliases: --con-omr = --with-omr
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

# Mensajes en el idioma del sistema / messages in the system language.
case "${PIANOSCORE_LANG:-${LC_ALL:-${LANG:-en}}}" in
  es*) ES=1 ;;
  *)   ES=0 ;;
esac
msg() { if [ "$ES" = 1 ]; then echo "$1"; else echo "$2"; fi; }

CON_OMR=0
for arg in "$@"; do
  case "$arg" in
    --con-omr|--with-omr) CON_OMR=1 ;;
    -h|--help|--ayuda)
      msg "Uso: ./install.sh [--with-omr]" "Usage: ./install.sh [--with-omr]"
      exit 0 ;;
  esac
done

msg "==> 1/4  uv (gestor de paquetes de Python)" "==> 1/4  uv (Python package manager)"
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

msg "==> 2/4  entorno virtual y dependencias" "==> 2/4  virtual environment and dependencies"
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python --index-url https://download.pytorch.org/whl/cpu torch
uv pip install --python .venv/bin/python \
  "numpy<2" librosa soundfile pretty_midi mido music21 piano_transcription_inference scipy

msg "==> 3/4  MuseScore (graba partituras y sintetiza audio)" \
    "==> 3/4  MuseScore (engraves scores and synthesizes audio)"
mkdir -p tools && cd tools
if [ ! -x squashfs-root/bin/mscore-portable ]; then
  URL=$(curl -s https://api.github.com/repos/musescore/MuseScore/releases/tags/v3.6.2 \
        | grep -o 'https://[^"]*x86_64.AppImage' | head -1)
  wget -q --show-progress -O MuseScore.AppImage "$URL"
  chmod +x MuseScore.AppImage
  ./MuseScore.AppImage --appimage-extract >/dev/null
fi
cd "$RAIZ"

if [ "$CON_OMR" = "1" ]; then
  msg "==> 4/4  Audiveris (lectura de partituras escaneadas)" \
      "==> 4/4  Audiveris (reading scanned scores)"
  # El .deb de Audiveris trae su propio runtime de Java dentro, asi que no
  # hace falta instalar un JDK aparte.
  # Audiveris' .deb bundles its own Java runtime, so no separate JDK is needed.
  if [ ! -x tools/audiveris/bin/Audiveris ]; then
    VER=$(. /etc/os-release 2>/dev/null; echo "${VERSION_ID:-22.04}")
    case "$VER" in
      24.*|25.*|26.*) SERIE=ubuntu24.04 ;;
      *)              SERIE=ubuntu22.04 ;;
    esac
    DEB=$(curl -s https://api.github.com/repos/Audiveris/audiveris/releases/latest \
          | grep -o "https://[^\"]*${SERIE}[^\"]*\.deb" | head -1)
    if [ -z "$DEB" ]; then
      DEB=$(curl -s https://api.github.com/repos/Audiveris/audiveris/releases/latest \
            | grep -o 'https://[^"]*\.deb' | head -1)
    fi
    if [ -n "$DEB" ]; then
      echo "    $(basename "$DEB")"
      wget -q --show-progress -O /tmp/audiveris.deb "$DEB"
      rm -rf tools/audiveris_raw && mkdir -p tools/audiveris_raw
      dpkg-deb -x /tmp/audiveris.deb tools/audiveris_raw
      rm -f /tmp/audiveris.deb
      if [ -d tools/audiveris_raw/opt/audiveris ]; then
        rm -rf tools/audiveris
        mv tools/audiveris_raw/opt/audiveris tools/audiveris
      fi
      rm -rf tools/audiveris_raw
    fi
  fi
  if [ -f tools/audiveris/bin/Audiveris ]; then
    chmod +x tools/audiveris/bin/Audiveris
    msg "    Audiveris listo." "    Audiveris ready."
  else
    msg "    AVISO: no se pudo instalar Audiveris automaticamente." \
        "    WARNING: could not install Audiveris automatically."
    msg "    El nucleo funciona igual; solo quedan fuera los PDF escaneados." \
        "    The core still works; only scanned PDFs are left out."
  fi
else
  msg "==> 4/4  OMR omitido (usa --with-omr para leer partituras escaneadas)" \
      "==> 4/4  OMR skipped (use --with-omr to read scanned scores)"
fi

echo
msg "Instalacion terminada. Comprueba con:" "Installation finished. Check it with:"
echo "  $RAIZ/pianoscore info"
