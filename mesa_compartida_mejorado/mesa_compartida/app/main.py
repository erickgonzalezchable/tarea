"""Mesa Compartida — pantallas (login, donante, voluntario, coordinación)."""
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, logica as lg  # noqa: E402
from app.widgets import CajaTexto, DataTable, aplicar_estilo  # noqa: E402
from config import config as cfg  # noqa: E402

REFRESCO_MS = 5000
COLS = [("id", "N.º", 50), ("alimento", "Alimento", 190), ("cantidad_kg", "Cantidad", 80), ("zona", "Zona", 100),
        ("prioridad", "Prioridad", 80), ("vence_en", "Recoger antes de", 120), ("estado", "Estado", 90)]


def error(ex):
    messagebox.showerror(cfg.APP_NAME, ex.args[0] if isinstance(ex, lg.ReglaError) else db.friendly_error(ex))


def formulario(parent, titulo, campos, texto_boton, accion, extra=None):
    """Ventana de captura simple. campos=[(etiqueta, clave, oculto)]; accion(dict) debe guardar o lanzar error."""
    d = tk.Toplevel(parent)
    d.title(titulo)
    d.transient(parent)
    v = {k: tk.StringVar() for _t, k, _o in campos}
    for i, (txt, k, oculto) in enumerate(campos):
        ttk.Label(d, text=txt).grid(row=i, column=0, sticky="w", padx=8, pady=3)
        ttk.Entry(d, textvariable=v[k], width=30, show="*" if oculto else "").grid(row=i, column=1, padx=8)
    n = len(campos)
    if extra:
        extra(d, v, n)
        n += 2

    def guardar():
        try:
            accion({k: x.get() for k, x in v.items()})
            d.destroy()
        except Exception as ex:
            error(ex)
    ttk.Button(d, text=texto_boton, command=guardar).grid(row=n, column=1, sticky="e", padx=8, pady=8)


class Vista(ttk.Frame):
    def __init__(self, app, usuario, subtitulo):
        super().__init__(app.root, padding=14)
        self.app, self.u = app, usuario
        cab = ttk.Frame(self)
        cab.pack(fill="x")
        ttk.Label(cab, text=f"🍽 {cfg.APP_NAME}", style="Titulo.TLabel").pack(side="left")
        ttk.Button(cab, text="Salir", command=app.mostrar_login).pack(side="right")
        ttk.Button(cab, text="Cambiar contraseña", command=self.cambiar_pw).pack(side="right", padx=6)
        ttk.Label(self, text=f"{usuario['nombre']} — {subtitulo}", style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        self._job = self.after(REFRESCO_MS, self._auto)

    def _auto(self):
        try:
            self.refrescar()
        finally:
            self._job = self.after(REFRESCO_MS, self._auto)

    def destroy(self):
        self.after_cancel(self._job)
        super().destroy()

    def cambiar_pw(self):
        a = simpledialog.askstring(cfg.APP_NAME, "Contraseña actual:", show="*", parent=self)
        n = a and simpledialog.askstring(cfg.APP_NAME, "Nueva contraseña (mínimo 6):", show="*", parent=self)
        if n:
            try:
                lg.cambiar_password(self.u["id"], a, n)
                messagebox.showinfo(cfg.APP_NAME, "Contraseña actualizada.")
            except Exception as ex:
                error(ex)

    def abrir_mapa(self):
        d = getattr(self, "tabla", None) and self.tabla.selected_row()
        if not d:
            return messagebox.showinfo(cfg.APP_NAME, "Selecciona una donación en la tabla.")
        import urllib.parse
        import webbrowser
        orig = urllib.parse.quote(f"{d['direccion']}, {d['zona']}, Tuxtla Gutiérrez, Chiapas")
        dest = urllib.parse.quote(f"{d['comedor']}, Tuxtla Gutiérrez, Chiapas")
        webbrowser.open(f"https://www.google.com/maps/dir/?api=1&origin={orig}&destination={dest}")


# ------------------------------------------------------------------ DONANTE
class VistaDonante(Vista):
    def __init__(self, app, u):
        super().__init__(app, u, "Donante")
        f = ttk.LabelFrame(self, text="Registrar alimento excedente", padding=10)
        f.pack(fill="x")
        self.v = {k: tk.StringVar() for k in ("alimento", "kg", "horas", "zona", "comedor", "dir", "obs")}
        self.v["kg"].set("10")
        campos = [("Alimento", "alimento", list(cfg.ALIMENTOS)), ("Horas para recogerlo", "horas", cfg.HORAS_LIMITE),
                  ("Zona", "zona", [z["nombre"] for z in cfg.ZONAS]),
                  ("Comedor destino", "comedor", [c["nombre"] for c in cfg.COMEDORES])]
        for i, (txt, k, vals) in enumerate(campos):
            ttk.Label(f, text=txt).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=4, pady=3)
            cb = ttk.Combobox(f, textvariable=self.v[k], values=vals, state="readonly", width=30)
            cb.grid(row=i // 2, column=(i % 2) * 2 + 1, padx=4, pady=3)
            cb.current(0)
            cb.bind("<<ComboboxSelected>>", lambda _e: self.cotizar(True))
        ttk.Label(f, text="Cantidad (kg)").grid(row=2, column=0, sticky="w", padx=4)
        ttk.Entry(f, textvariable=self.v["kg"], width=10).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(f, text="Dirección / referencias").grid(row=3, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(f, textvariable=self.v["dir"], width=60).grid(row=3, column=1, columnspan=3, sticky="we", padx=4)
        ttk.Label(f, text="Observaciones").grid(row=4, column=0, sticky="w", padx=4)
        ttk.Entry(f, textvariable=self.v["obs"], width=60).grid(row=4, column=1, columnspan=3, sticky="we", padx=4)
        self.total = ttk.Label(f, text="", style="Sub.TLabel")
        self.total.grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=6)
        ttk.Button(f, text="Ver impacto", command=self.cotizar).grid(row=5, column=2, sticky="e")
        ttk.Button(f, text="Registrar donación", style="Principal.TButton", command=self.registrar).grid(row=5, column=3, padx=6)
        ttk.Label(self, text="Mis donaciones").pack(anchor="w", pady=(10, 2))
        self.tabla = DataTable(self, COLS, self.sel, height=6)
        self.tabla.pack(fill="both", expand=True)
        self.det = CajaTexto(self, 8)
        self.det.pack(fill="x", pady=6)
        bar_d = ttk.Frame(self)
        bar_d.pack(fill="x")
        ttk.Button(bar_d, text="🗺 Ver ruta en Google Maps", command=self.abrir_mapa).pack(side="left")
        ttk.Button(bar_d, text="Cancelar donación", command=self.cancelar).pack(side="right")
        self.cotizar(True)
        self.refrescar()

    def _args(self):
        v = self.v
        return v["alimento"].get(), v["kg"].get(), v["horas"].get(), v["zona"].get(), v["comedor"].get()

    def cotizar(self, silencioso=False):
        try:
            c = lg.cotizar(*self._args())
            self.total.config(text=f"≈ {c['raciones']} raciones · ${c['valor_estimado']:,.2f} rescatados · "
                                   f"{c['km_total']:.1f} km · prioridad {c['prioridad'].lower()}")
        except Exception as ex:
            if not silencioso:
                error(ex)

    def registrar(self):
        v = self.v
        try:
            did = lg.registrar_donacion(self.u["id"], v["alimento"].get(), v["kg"].get(), v["horas"].get(),
                                        v["zona"].get(), v["dir"].get(), v["obs"].get(), v["comedor"].get())
        except Exception as ex:
            return error(ex)
        v["dir"].set("")
        v["obs"].set("")
        messagebox.showinfo(cfg.APP_NAME, f"Donación #{did} registrada. ¡Gracias! Coordinación asignará un voluntario.")
        self.refrescar()

    def cancelar(self):
        d = self.tabla.selected_row()
        if d and messagebox.askyesno(cfg.APP_NAME, f"¿Cancelar la donación #{d['id']}?"):
            try:
                lg.cancelar(d["id"], self.u["id"])
            except Exception as ex:
                error(ex)
            self.refrescar()

    def sel(self):
        d = self.tabla.selected_row()
        self.det.mostrar(lg.detalle_texto(d) if d else "Selecciona una donación para ver el detalle.")

    def refrescar(self):
        lg.marcar_vencidas()
        self.tabla.load(lg.donaciones_de_donante(self.u["id"]))


# ------------------------------------------------------------------ VOLUNTARIO
class VistaVoluntario(Vista):
    def __init__(self, app, u):
        self.vol = lg.voluntario_de_usuario(u["id"])
        super().__init__(app, u, f"Voluntario · {self.vol['vehiculo']} ({self.vol['placas']}) · "
                                 f"{self.vol['capacidad_kg']} kg · {'con' if self.vol['refrigerado'] else 'sin'} refrigeración")
        ttk.Label(self, text=f"Tu código QR: {self.vol['codigo_qr']}", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(self, text="Mis recolecciones asignadas").pack(anchor="w", pady=(8, 2))
        self.tabla = DataTable(self, COLS, self.sel, height=8)
        self.tabla.pack(fill="both", expand=True)
        self.det = CajaTexto(self, 9)
        self.det.pack(fill="x", pady=6)
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Iniciar recolección", style="Principal.TButton",
                   command=lambda: self.accion(lg.iniciar)).pack(side="left")
        ttk.Button(bar, text="Marcar entregada", style="Principal.TButton",
                   command=lambda: self.accion(lg.marcar_entregada)).pack(side="left", padx=6)
        ttk.Button(bar, text="Reportar incidente", command=self.incidente).pack(side="left")
        ttk.Button(bar, text="🗺 Ver ruta en Google Maps", command=self.abrir_mapa).pack(side="right")
        self.refrescar()

    def _sel(self):
        d = self.tabla.selected_row()
        if not d:
            messagebox.showinfo(cfg.APP_NAME, "Selecciona una recolección.")
        return d

    def accion(self, fn):
        d = self._sel()
        if d:
            try:
                fn(d["id"], self.vol["id"])
            except Exception as ex:
                error(ex)
            self.refrescar()

    def incidente(self):
        d = self._sel()
        if not d:
            return

        def extra(win, v, n):
            v["tipo"] = tk.StringVar(value=lg.TIPOS_INCIDENTE[0])
            ttk.Label(win, text="Tipo").grid(row=n, column=0, sticky="w", padx=8, pady=3)
            ttk.Combobox(win, textvariable=v["tipo"], values=lg.TIPOS_INCIDENTE, state="readonly",
                         width=28).grid(row=n, column=1, padx=8)

        def guardar(x):
            lg.reportar_incidente(d["id"], self.vol["id"], x["tipo"], x["descripcion"])
            self.refrescar()
        formulario(self, "Reportar incidente", [("Descripción", "descripcion", False)], "Enviar reporte", guardar, extra)

    def sel(self):
        d = self.tabla.selected_row()
        self.det.mostrar(lg.detalle_texto(d) if d else "Selecciona una recolección para ver el detalle.")

    def refrescar(self):
        self.tabla.load(lg.donaciones_de_voluntario(self.vol["id"]))


# ------------------------------------------------------------------ COORDINACIÓN
class VistaAdmin(Vista):
    def __init__(self, app, u):
        super().__init__(app, u, "Coordinación")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        p1 = ttk.Frame(nb, padding=8)
        nb.add(p1, text="Donaciones")
        cols = COLS[:4] + [("donante", "Donante", 130), ("voluntario", "Voluntario", 120)] + COLS[4:]
        self.tabla = DataTable(p1, cols, self.sel, height=9)
        self.tabla.pack(fill="both", expand=True)
        self.det = CajaTexto(p1, 9)
        self.det.pack(fill="x", pady=6)
        b = ttk.Frame(p1)
        b.pack(fill="x")
        ttk.Button(b, text="Asignar voluntario", style="Principal.TButton", command=self.asignar).pack(side="left")
        ttk.Button(b, text="Cancelar donación", command=self.cancelar).pack(side="left", padx=6)
        ttk.Button(b, text="🗺 Ver ruta en Google Maps", command=self.abrir_mapa).pack(side="right")

        p2 = ttk.Frame(nb, padding=8)
        nb.add(p2, text="Voluntarios")
        self.t_vol = DataTable(p2, [("id", "N.º", 50), ("nombre", "Nombre", 160), ("vehiculo", "Vehículo", 170),
                                    ("placas", "Placas", 90), ("capacidad_kg", "Capacidad", 80),
                                    ("refrigerado", "Refrigerado", 90), ("estado", "Estado", 90),
                                    ("carga", "En curso", 70)], height=9)
        self.t_vol.pack(fill="both", expand=True)
        b2 = ttk.Frame(p2)
        b2.pack(fill="x", pady=6)
        ttk.Button(b2, text="Registrar voluntario", style="Principal.TButton", command=self.nuevo_voluntario).pack(side="left")
        for txt, est in (("Suspender", "SUSPENDIDO"), ("Reactivar", "ACTIVO"), ("Dar de baja", "BAJA")):
            ttk.Button(b2, text=txt, command=lambda e=est: self.estado_voluntario(e)).pack(side="left", padx=4)

        p3 = ttk.Frame(nb, padding=20)
        nb.add(p3, text="Impacto")
        self.imp = ttk.Label(p3, text="", font=("TkDefaultFont", 16), justify="left")
        self.imp.pack(anchor="w")
        self.refrescar()

    def sel(self):
        d = self.tabla.selected_row()
        self.det.mostrar(lg.detalle_texto(d) if d else "Selecciona una donación.")

    def asignar(self):
        d = self.tabla.selected_row()
        if not d:
            return messagebox.showinfo(cfg.APP_NAME, "Selecciona una donación.")
        try:
            v = lg.asignar(d["id"])
            messagebox.showinfo(cfg.APP_NAME, f"Asignada a {v['nombre']} ({v['placas']}).")
        except Exception as ex:
            error(ex)
        self.refrescar()

    def cancelar(self):
        d = self.tabla.selected_row()
        if d and messagebox.askyesno(cfg.APP_NAME, f"¿Cancelar la donación #{d['id']}?"):
            try:
                lg.cancelar(d["id"])
            except Exception as ex:
                error(ex)
            self.refrescar()

    def estado_voluntario(self, estado):
        v = self.t_vol.selected_row()
        if v:
            lg.cambiar_estado_voluntario(v["id"], estado)
            self.refrescar()

    def nuevo_voluntario(self):
        def extra(win, v, n):
            v["cap"], v["frio"] = tk.StringVar(value=str(cfg.CAPACIDADES_KG[0])), tk.IntVar()
            ttk.Label(win, text="Capacidad (kg)").grid(row=n, column=0, sticky="w", padx=8)
            ttk.Combobox(win, textvariable=v["cap"], values=list(cfg.CAPACIDADES_KG), state="readonly",
                         width=8).grid(row=n, column=1, sticky="w", padx=8)
            ttk.Checkbutton(win, text="Vehículo con refrigeración", variable=v["frio"]).grid(row=n + 1, column=1, sticky="w", padx=8)

        def guardar(x):
            lg.registrar_voluntario(x["usuario"], x["nombre"], x["telefono"], x["password"], x["vehiculo"],
                                    x["placas"], x["cap"], bool(int(x["frio"])))
            self.refrescar()
        formulario(self, "Registrar voluntario",
                   [("Usuario", "usuario", False), ("Nombre completo", "nombre", False),
                    ("Teléfono (10 dígitos)", "telefono", False), ("Contraseña", "password", True),
                    ("Vehículo", "vehiculo", False), ("Placas", "placas", False)], "Guardar", guardar, extra)

    def refrescar(self):
        self.tabla.load(lg.todas_las_donaciones())
        self.t_vol.load(lg.voluntarios_con_carga())
        i = lg.impacto()
        self.imp.config(text=(f"Entregas completadas: {i['entregas']}\nAlimento rescatado: {i['kg']:g} kg\n"
                              f"Raciones servidas: {i['raciones']}\nValor rescatado: ${i['valor']:,.2f}\n"
                              f"Donantes activos: {i['donantes']}\n\nAlimento que venció sin recogerse: {i['vencidas_kg']:g} kg"))


# ------------------------------------------------------------------ APLICACIÓN
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(cfg.APP_NAME)
        self.root.geometry("1000x720")
        aplicar_estilo(self.root)
        self.vista = None
        self.mostrar_login()

    def _poner(self, vista):
        if self.vista:
            self.vista.destroy()
        self.vista = vista
        vista.pack(fill="both", expand=True)

    def mostrar_login(self):
        f = ttk.Frame(self.root, padding=40)
        ttk.Label(f, text=f"🍽 {cfg.APP_NAME}", style="Titulo.TLabel").pack(pady=(60, 4))
        ttk.Label(f, text="Rescate de alimentos excedentes para comedores comunitarios", style="Sub.TLabel").pack(pady=(0, 20))
        usuario, pw = tk.StringVar(), tk.StringVar()
        ttk.Label(f, text="Usuario").pack()
        e = ttk.Entry(f, textvariable=usuario, width=28)
        e.pack(pady=4)
        ttk.Label(f, text="Contraseña").pack()
        p = ttk.Entry(f, textvariable=pw, show="*", width=28)
        p.pack(pady=4)

        def entrar(_e=None):
            u = lg.login(usuario.get(), pw.get())
            if not u:
                return messagebox.showerror(cfg.APP_NAME, "Usuario o contraseña incorrectos.")
            vista = {"ADMIN": VistaAdmin, "VOLUNTARIO": VistaVoluntario, "DONANTE": VistaDonante}[u["rol"]]
            self._poner(vista(self, u))
        ttk.Button(f, text="Entrar", style="Principal.TButton", command=entrar).pack(pady=10)
        ttk.Button(f, text="Registrarme como donante", command=self.registro).pack()
        p.bind("<Return>", entrar)
        e.focus()
        self._poner(f)

    def registro(self):
        formulario(self.root, "Registro de donante",
                   [("Usuario", "usuario", False), ("Nombre o negocio", "nombre", False),
                    ("Teléfono (10 dígitos)", "telefono", False), ("Contraseña", "password", True)],
                   "Crear cuenta", lambda x: (lg.registrar_donante(x["usuario"], x["nombre"], x["telefono"], x["password"]),
                                              messagebox.showinfo(cfg.APP_NAME, "Cuenta creada. Ya puedes iniciar sesión.")))

    def run(self):
        self.root.mainloop()


def main():
    db.init_db()
    App().run()


if __name__ == "__main__":
    main()
