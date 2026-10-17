"""Comprueba la ventana: los dos idiomas, el cambio en caliente, la deteccion
del resultado por marca y que cancelar mata de verdad el subproceso."""
import os
import pathlib
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from pianoscore import idioma  # noqa: E402
from pianoscore.gui import App  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parents[1]
AUDIO_LARGO = "/home/lucas/Escritorio/Trabajos Liceo/Sambea Anclada.mp3"
PARTITURA = RAIZ / "ejemplos" / "vals_mib.mid"


def bombear(app, raiz, segundos):
    fin = time.time() + segundos
    while app.proceso is not None and time.time() < fin:
        raiz.update()
        time.sleep(0.05)
    raiz.update()


print("=== 1. la ventana se construye en los dos idiomas ===")
for codigo in ("es", "en"):
    os.environ["PIANOSCORE_LANG"] = codigo
    idioma.fijar(codigo)
    r = tk.Tk()
    ttk.Style().theme_use("clam")
    a = App(r)
    r.update()
    print(f"  {codigo}: {[a.pestanas.tab(i, 'text').strip() for i in range(2)]}"
          f"  boton={a.btn_a2p.cget('text')!r}  estado={a.estado.cget('text')!r}")
    r.destroy()

print("\n=== 2. cambio de idioma en caliente, conservando lo escrito ===")
idioma.fijar("es")
r = tk.Tk()
ttk.Style().theme_use("clam")
a = App(r)
r.update()
a.a_titulo.set("Mi pieza")
a.a_umbral.set("0.55")
print(f"  antes : {a.btn_a2p.cget('text')!r}  titulo={a.a_titulo.get()!r}")
a.combo_idioma.set("English")
a._cambiar_idioma()
r.update()
print(f"  despues: {a.btn_a2p.cget('text')!r}  titulo={a.a_titulo.get()!r} "
      f"umbral={a.a_umbral.get()!r}")

print("\n=== 3. ejecucion real: deteccion del resultado por marca ===")
a.p_entrada.set(str(PARTITURA))
a.p_formato.set("mp3")
a._lanzar_p2a()
bombear(a, r, 180)
registro = a.texto.get("1.0", "end")
print(f"  estado        : {a.estado.cget('text')}")
print(f"  resultado     : {a.ultimo_resultado}")
print(f"  existe        : {a.ultimo_resultado.exists() if a.ultimo_resultado else False}")
print(f"  marca oculta  : {'@@PIANOSCORE' not in registro}")
print(f"  registro en en: {'Rendering' in registro or 'Done in' in registro}")
r.destroy()

print("\n=== 4. cancelar mata el subproceso ===")
idioma.fijar("es")
r = tk.Tk()
ttk.Style().theme_use("clam")
a = App(r)
r.update()
a.a_entrada.set(AUDIO_LARGO)
a._lanzar_a2p()
pid = a.proceso.pid
fin = time.time() + 6
while time.time() < fin:
    r.update()
    time.sleep(0.05)
a._cancelar()
bombear(a, r, 25)
vivo = subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode == 0
print(f"  estado   : {a.estado.cget('text')}")
print(f"  sigue vivo: {vivo}")
r.destroy()
