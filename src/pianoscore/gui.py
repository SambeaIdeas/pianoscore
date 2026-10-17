"""Ventana de escritorio / desktop window for pianoscore.

Envuelve la misma linea de comandos: lanza `pianoscore.cli` como subproceso y
va volcando su salida en el registro segun llega. Hacerlo por subproceso, y no
importando el modulo, tiene dos ventajas: la ventana nunca se congela mientras
el modelo trabaja (son minutos de CPU) y el boton de cancelar puede matar el
proceso de verdad.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import config, idioma
from .cli import MARCA
from .idioma import t

RAIZ = config.RAIZ
PYTHON = RAIZ / ".venv" / "bin" / "python"

EXT_AUDIO = "*.mp3 *.wav *.flac *.m4a *.ogg *.opus *.aac *.wma *.mp4 *.mkv"
EXT_PARTITURA = "*.musicxml *.xml *.mxl *.mid *.midi *.mscz"
EXT_ESCANEADA = "*.pdf *.png *.jpg *.jpeg *.tif *.tiff"

# (clave del texto, valor que recibe --subdivision)
SUBDIVISIONES = [("v_corcheas", 2), ("v_semicorcheas", 4),
                 ("v_tresillos", 3), ("v_fusas", 8)]
COMPASES_FIJOS = ["4/4", "3/4", "2/4", "6/8", "2/2", "5/4"]


class App(ttk.Frame):
    def __init__(self, raiz: tk.Tk):
        super().__init__(raiz, padding=12)
        self.raiz = raiz
        self.proceso: subprocess.Popen | None = None
        self.cola: queue.Queue[str | None] = queue.Queue()
        self.ultimo_resultado: Path | None = None
        self.cancelado = False

        # Las variables viven fuera de los widgets para que un cambio de
        # idioma pueda rehacer la ventana sin perder lo que haya escrito.
        self.idioma_var = tk.StringVar(value=idioma.actual())
        self.a_entrada = tk.StringVar()
        self.a_titulo = tk.StringVar()
        self.a_compositor = tk.StringVar()
        self.a_bpm = tk.StringVar()
        self.a_compas = tk.StringVar()
        self.a_subdiv = tk.StringVar()
        self.a_corte = tk.StringVar(value="auto")
        self.a_umbral = tk.StringVar()
        self.a_minimo = tk.StringVar(value="0")
        self.a_png = tk.BooleanVar(value=False)
        self.a_prueba = tk.BooleanVar(value=True)
        self.a_sin_pedal = tk.BooleanVar(value=False)
        self.p_entrada = tk.StringVar()
        self.p_formato = tk.StringVar(value="mp3")
        self.p_bpm = tk.StringVar()
        self.p_pdf = tk.BooleanVar(value=False)

        self.grid(sticky="nsew")
        raiz.columnconfigure(0, weight=1)
        raiz.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._construir()
        self._temporizador = self.after(100, self._vaciar_cola)

    def destroy(self):
        # Sin cancelarlo, el temporizador se dispara con la ventana ya
        # destruida y Tk escupe "invalid command name" al cerrar.
        if getattr(self, "_temporizador", None):
            try:
                self.after_cancel(self._temporizador)
            except tk.TclError:
                pass
            self._temporizador = None
        super().destroy()

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def _construir(self):
        # Valores traducidos de los desplegables.
        self.a_compas.set(t("v_automatico"))
        self.a_subdiv.set(t("v_semicorcheas"))

        cabecera = ttk.Frame(self)
        cabecera.grid(row=0, column=0, sticky="ew")
        cabecera.columnconfigure(0, weight=1)
        ttk.Label(cabecera, text="Idioma / Language").grid(row=0, column=1, padx=(0, 6))
        combo = ttk.Combobox(cabecera, textvariable=self.idioma_var, width=10,
                             state="readonly",
                             values=["español", "English"])
        combo.set("español" if idioma.actual() == "es" else "English")
        combo.grid(row=0, column=2)
        combo.bind("<<ComboboxSelected>>", self._cambiar_idioma)
        self.combo_idioma = combo

        self.pestanas = ttk.Notebook(self)
        self.pestanas.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.pestanas.add(self._pestana_a2p(), text=t("v_pest_a2p"))
        self.pestanas.add(self._pestana_p2a(), text=t("v_pest_p2a"))

        registro = ttk.LabelFrame(self, text=t("v_progreso"), padding=8)
        registro.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        registro.columnconfigure(0, weight=1)
        registro.rowconfigure(0, weight=1)
        self.texto = tk.Text(registro, height=10, wrap="word", state="disabled",
                             font=("monospace", 9), relief="flat",
                             background="#1e1e1e", foreground="#d4d4d4")
        self.texto.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(registro, orient="vertical", command=self.texto.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.texto.configure(yscrollcommand=barra.set)
        self._pista()

        self.progreso = ttk.Progressbar(self, mode="determinate", maximum=5)
        self.progreso.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        pie = ttk.Frame(self)
        pie.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        pie.columnconfigure(0, weight=1)
        self.estado = ttk.Label(pie, text=t("v_listo"))
        self.estado.grid(row=0, column=0, sticky="w")
        self.btn_carpeta = ttk.Button(pie, text=t("v_abrir_carpeta"), state="disabled",
                                      command=self._abrir_carpeta)
        self.btn_carpeta.grid(row=0, column=1, padx=4)
        self.btn_abrir = ttk.Button(pie, text=t("v_abrir_resultado"), state="disabled",
                                    command=self._abrir_resultado)
        self.btn_abrir.grid(row=0, column=2, padx=4)
        self.btn_cancelar = ttk.Button(pie, text=t("v_cancelar"), state="disabled",
                                       command=self._cancelar)
        self.btn_cancelar.grid(row=0, column=3, padx=4)

    def _cambiar_idioma(self, _evento=None):
        idioma.fijar("es" if self.combo_idioma.get() == "español" else "en")
        for hijo in list(self.children.values()):
            hijo.destroy()
        self._construir()

    def _fila_fichero(self, padre, fila, variable, tipos, etiqueta):
        ttk.Label(padre, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=4)
        ttk.Entry(padre, textvariable=variable).grid(row=fila, column=1, columnspan=3,
                                                     sticky="ew", padx=6)

        def elegir():
            r = filedialog.askopenfilename(title=etiqueta, filetypes=tipos,
                                           initialdir=str(Path.home()))
            if r:
                variable.set(r)

        ttk.Button(padre, text=t("v_examinar"), command=elegir).grid(row=fila, column=4)

    # ------------------------------------------------------------------
    def _pestana_a2p(self):
        m = ttk.Frame(self.pestanas, padding=12)
        m.columnconfigure(1, weight=1)
        m.columnconfigure(3, weight=1)

        self._fila_fichero(m, 0, self.a_entrada,
                           [(t("v_filtro_audio"), EXT_AUDIO),
                            (t("v_filtro_todos"), "*.*")], t("v_audio"))
        ttk.Separator(m, orient="horizontal").grid(row=1, column=0, columnspan=5,
                                                   sticky="ew", pady=10)

        ttk.Label(m, text=t("v_titulo_campo")).grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(m, textvariable=self.a_titulo).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Label(m, text=t("v_autor")).grid(row=2, column=2, sticky="e", padx=(12, 0))
        ttk.Entry(m, textvariable=self.a_compositor).grid(row=2, column=3,
                                                          sticky="ew", padx=6)

        ttk.Label(m, text=t("v_tempo")).grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(m, textvariable=self.a_bpm, width=10).grid(row=3, column=1,
                                                             sticky="w", padx=6)
        ttk.Label(m, text=t("v_compas")).grid(row=3, column=2, sticky="e", padx=(12, 0))
        ttk.Combobox(m, textvariable=self.a_compas, width=14, state="readonly",
                     values=[t("v_automatico"), *COMPASES_FIJOS]
                     ).grid(row=3, column=3, sticky="w", padx=6)

        ttk.Label(m, text=t("v_figura")).grid(row=4, column=0, sticky="w", pady=3)
        ttk.Combobox(m, textvariable=self.a_subdiv, width=20, state="readonly",
                     values=[t(k) for k, _ in SUBDIVISIONES]
                     ).grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(m, text=t("v_separar")).grid(row=4, column=2, sticky="e", padx=(12, 0))
        ttk.Entry(m, textvariable=self.a_corte, width=12).grid(row=4, column=3,
                                                               sticky="w", padx=6)

        limpieza = ttk.LabelFrame(m, text=t("v_limpieza"), padding=8)
        limpieza.grid(row=5, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        ttk.Label(limpieza, text=t("v_confianza")).grid(row=0, column=0, sticky="w")
        ttk.Entry(limpieza, textvariable=self.a_umbral, width=8).grid(row=0, column=1,
                                                                      padx=6)
        ttk.Label(limpieza, text=t("v_vacio")).grid(row=0, column=2, sticky="w")
        ttk.Label(limpieza, text=t("v_descartar")).grid(row=0, column=3, sticky="e",
                                                        padx=(16, 0))
        ttk.Entry(limpieza, textvariable=self.a_minimo, width=8).grid(row=0, column=4,
                                                                      padx=6)
        ttk.Label(limpieza, text="ms").grid(row=0, column=5, sticky="w")

        extras = ttk.Frame(m)
        extras.grid(row=6, column=0, columnspan=5, sticky="w", pady=(10, 0))
        ttk.Checkbutton(extras, text=t("v_png"), variable=self.a_png
                        ).grid(row=0, column=0, padx=(0, 16))
        ttk.Checkbutton(extras, text=t("v_comprobacion"), variable=self.a_prueba
                        ).grid(row=0, column=1, padx=(0, 16))
        ttk.Checkbutton(extras, text=t("v_sin_pedal"), variable=self.a_sin_pedal
                        ).grid(row=0, column=2)

        self.btn_a2p = ttk.Button(m, text=t("v_btn_a2p"), command=self._lanzar_a2p)
        self.btn_a2p.grid(row=7, column=0, columnspan=5, sticky="ew", pady=(14, 0))
        return m

    def _pestana_p2a(self):
        m = ttk.Frame(self.pestanas, padding=12)
        m.columnconfigure(1, weight=1)
        m.columnconfigure(3, weight=1)

        self._fila_fichero(m, 0, self.p_entrada,
                           [(t("v_filtro_part"), EXT_PARTITURA),
                            (t("v_filtro_escan"), EXT_ESCANEADA),
                            (t("v_filtro_todos"), "*.*")], t("v_partitura"))
        ttk.Separator(m, orient="horizontal").grid(row=1, column=0, columnspan=5,
                                                   sticky="ew", pady=10)

        ttk.Label(m, text=t("v_formato")).grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(m, textvariable=self.p_formato, width=10, state="readonly",
                     values=["mp3", "wav", "flac", "ogg"]).grid(row=2, column=1,
                                                                sticky="w", padx=6)
        ttk.Label(m, text=t("v_tempo")).grid(row=2, column=2, sticky="e", padx=(12, 0))
        ttk.Entry(m, textvariable=self.p_bpm, width=10).grid(row=2, column=3,
                                                             sticky="w", padx=6)

        ttk.Checkbutton(m, text=t("v_tambien_pdf"), variable=self.p_pdf
                        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(10, 0))
        ttk.Label(m, foreground="#888", wraplength=640, justify="left",
                  text=t("v_aviso_omr")).grid(row=4, column=0, columnspan=5,
                                              sticky="w", pady=(10, 0))

        self.btn_p2a = ttk.Button(m, text=t("v_btn_p2a"), command=self._lanzar_p2a)
        self.btn_p2a.grid(row=5, column=0, columnspan=5, sticky="ew", pady=(14, 0))
        return m

    # ------------------------------------------------------------------
    # Lanzamiento
    # ------------------------------------------------------------------
    def _lanzar_a2p(self):
        entrada = self.a_entrada.get().strip()
        if not entrada or not Path(entrada).exists():
            messagebox.showwarning(t("v_falta_audio"), t("v_falta_audio_msg"))
            return

        args = ["a2p", entrada]
        if self.a_titulo.get().strip():
            args += ["--titulo", self.a_titulo.get().strip()]
        if self.a_compositor.get().strip():
            args += ["--compositor", self.a_compositor.get().strip()]
        if self.a_bpm.get().strip():
            args += ["--bpm", self.a_bpm.get().strip()]
        if self.a_compas.get() != t("v_automatico"):
            args += ["--compas", self.a_compas.get()]
        elegido = self.a_subdiv.get()
        sub = next((v for k, v in SUBDIVISIONES if t(k) == elegido), 4)
        args += ["--subdivision", str(sub)]
        corte = self.a_corte.get().strip()
        if corte and corte.lower() not in ("auto", "automatic", "automático"):
            args += ["--corte-manos", corte]
        if self.a_umbral.get().strip():
            args += ["--umbral", self.a_umbral.get().strip()]
        if self.a_minimo.get().strip() not in ("", "0"):
            args += ["--minimo-ms", self.a_minimo.get().strip()]
        if self.a_png.get():
            args.append("--png")
        if self.a_prueba.get():
            args.append("--audio-prueba")
        if self.a_sin_pedal.get():
            args.append("--sin-pedal")

        self._ejecutar(args, t("v_transcribiendo"))

    def _lanzar_p2a(self):
        entrada = self.p_entrada.get().strip()
        if not entrada or not Path(entrada).exists():
            messagebox.showwarning(t("v_falta_part"), t("v_falta_part_msg"))
            return
        args = ["p2a", entrada, "--formato", self.p_formato.get()]
        if self.p_bpm.get().strip():
            args += ["--bpm", self.p_bpm.get().strip()]
        if self.p_pdf.get():
            args.append("--tambien-pdf")
        self._ejecutar(args, t("v_convirtiendo"))

    def _ejecutar(self, args, mensaje):
        if self.proceso is not None:
            return
        self._limpiar_registro()
        self.ultimo_resultado = None
        self.cancelado = False
        self.progreso.configure(value=0)
        self.estado.configure(text=mensaje)
        for b in (self.btn_a2p, self.btn_p2a, self.btn_carpeta, self.btn_abrir):
            b.configure(state="disabled")
        self.btn_cancelar.configure(state="normal")

        entorno = dict(os.environ)
        entorno["PYTHONPATH"] = str(RAIZ / "src") + os.pathsep + entorno.get("PYTHONPATH", "")
        entorno["PYTHONUNBUFFERED"] = "1"
        entorno["PIANOSCORE_LANG"] = idioma.actual()
        entorno["PIANOSCORE_MARCAS"] = "1"

        self.proceso = subprocess.Popen(
            [str(PYTHON), "-u", "-m", "pianoscore.cli", *args],
            cwd=str(RAIZ), env=entorno, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        threading.Thread(target=self._leer_salida, daemon=True).start()

    def _leer_salida(self):
        proc = self.proceso
        if proc is None or proc.stdout is None:
            return
        for linea in proc.stdout:
            self.cola.put(linea.rstrip("\n"))
        proc.wait()
        self.cola.put(None)

    # ------------------------------------------------------------------
    def _vaciar_cola(self):
        try:
            while True:
                linea = self.cola.get_nowait()
                if linea is None:
                    self._terminado()
                else:
                    self._anotar(linea)
        except queue.Empty:
            pass
        self._temporizador = self.after(100, self._vaciar_cola)

    def _anotar(self, linea: str):
        # La ruta del resultado llega en una marca aparte, no en el texto:
        # asi los mensajes se traducen sin romper la deteccion.
        if linea.startswith(MARCA):
            ruta = Path(linea[len(MARCA):].strip())
            if ruta.exists():
                self.ultimo_resultado = ruta
            return
        # Las lineas "[3/5] ..." mueven la barra de progreso.
        if linea.startswith("[") and "/" in linea[:6]:
            try:
                self.progreso.configure(value=int(linea[1:linea.index("/")]))
            except ValueError:
                pass
        self.texto.configure(state="normal")
        self.texto.insert("end", linea + "\n")
        self.texto.see("end")
        self.texto.configure(state="disabled")

    def _terminado(self):
        codigo = self.proceso.returncode if self.proceso else 1
        self.proceso = None
        self.btn_cancelar.configure(state="disabled")
        self.btn_a2p.configure(state="normal")
        self.btn_p2a.configure(state="normal")
        if self.cancelado:
            # Matarlo nosotros devuelve un codigo negativo: eso no es un fallo.
            self.cancelado = False
            self.progreso.configure(value=0)
            self.estado.configure(text=t("v_cancelado"))
            return
        if codigo == 0:
            self.progreso.configure(value=5)
            self.estado.configure(text=t("v_terminado"))
            if self.ultimo_resultado:
                self.btn_carpeta.configure(state="normal")
                self.btn_abrir.configure(state="normal")
        else:
            self.progreso.configure(value=0)
            self.estado.configure(text=t("v_con_error", c=codigo))

    def _cancelar(self):
        if self.proceso:
            self.cancelado = True
            self.proceso.terminate()
            self.estado.configure(text=t("v_cancelando"))

    def _limpiar_registro(self):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.configure(state="disabled")

    def _pista(self):
        self.texto.configure(state="normal")
        self.texto.insert("end", t("v_pista"))
        self.texto.configure(state="disabled")

    def _abrir(self, ruta: Path):
        subprocess.Popen(["xdg-open", str(ruta)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _abrir_carpeta(self):
        if self.ultimo_resultado:
            r = self.ultimo_resultado
            self._abrir(r if r.is_dir() else r.parent)

    def _abrir_resultado(self):
        if not self.ultimo_resultado:
            return
        r = self.ultimo_resultado
        if r.is_dir():
            # Tras una transcripcion lo que se quiere ver es el PDF.
            pdfs = sorted(r.glob("*.pdf"))
            r = pdfs[0] if pdfs else r
        self._abrir(r)


def main() -> int:
    raiz = tk.Tk()
    raiz.title(t("v_titulo"))
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(raiz)
    # La geometria se fija despues de montar el contenido: puesta antes, Tk
    # la reemplaza por el tamano que piden los widgets y la ventana sale
    # mucho mas alta de lo necesario.
    raiz.update_idletasks()
    raiz.minsize(840, 600)
    raiz.geometry("920x690")
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
