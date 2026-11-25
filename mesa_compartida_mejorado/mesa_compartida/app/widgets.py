"""Componentes visuales: estilo, tabla con colores por estado y caja de detalle."""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

COLORES = {"PENDIENTE": "#FFF3C4", "ASIGNADO": "#E3F0FF", "EN_CAMINO": "#FFE0B2",
           "ENTREGADO": "#D7F2D7", "INCIDENTE": "#F8D0D0", "CANCELADO": "#E6E6E6", "VENCIDO": "#D9C7E8"}
NOMBRES = {"PENDIENTE": "Pendiente", "ASIGNADO": "Asignado", "EN_CAMINO": "En camino",
           "ENTREGADO": "Entregado", "INCIDENTE": "Incidente", "CANCELADO": "Cancelado", "VENCIDO": "Vencido"}


def formatear(k, v):
    if v is None:
        return ""
    if k in ("valor_estimado", "costo_traslado"):
        return f"${float(v):,.2f}"
    if k == "estado":
        return NOMBRES.get(v, v)
    if k == "estado_vol":
        return str(v).capitalize()
    if k == "refrigerado":
        return "Sí" if v else "No"
    if k == "cantidad_kg":
        return f"{float(v):g} kg"
    if k == "capacidad_kg":
        return f"{v} kg"
    if k == "prioridad":
        return str(v).capitalize()
    if k == "vence_en":
        return str(v)[5:16]
    if k in ("km_total", "km_a_b", "km_b_c"):
        return f"{float(v):.1f} km"
    if k == "creado_en":
        return str(v)[:16]
    return v


def aplicar_estilo(root):
    st = ttk.Style(root)
    try:
        st.theme_use("vista" if "vista" in st.theme_names() else "clam")
    except tk.TclError:
        pass
    for n in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        tkfont.nametofont(n).configure(size=11)
    st.configure("Treeview", rowheight=28)
    st.configure("Treeview.Heading", font=("TkDefaultFont", 11, "bold"))
    st.configure("TButton", padding=(10, 6))
    st.configure("Principal.TButton", font=("TkDefaultFont", 12, "bold"), padding=(14, 8))
    st.configure("Titulo.TLabel", font=("TkDefaultFont", 20, "bold"), foreground="#2E7D32")
    st.configure("Sub.TLabel", foreground="#555555")
    st.configure("Total.TLabel", font=("TkDefaultFont", 18, "bold"))


class DataTable(ttk.Frame):
    """columnas = [(clave, título, ancho)]. Se recarga sin perder la selección."""

    def __init__(self, parent, columnas, on_select=None, height=8):
        super().__init__(parent)
        self.columnas, self.rows, self.on_select = columnas, {}, on_select
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columnas], show="headings",
                                 selectmode="browse", height=height)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        for clave, titulo, ancho in columnas:
            self.tree.heading(clave, text=titulo)
            self.tree.column(clave, width=ancho, minwidth=50, anchor="w")
        for e, color in COLORES.items():
            self.tree.tag_configure(e, background=color)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.on_select and self.on_select())
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def load(self, rows):
        previo = self.selected_id()
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for r in rows:
            iid = str(r["id"])
            self.rows[iid] = r
            tag = r.get("estado") if r.get("estado") in COLORES else None
            self.tree.insert("", "end", iid=iid, tags=(tag,) if tag else (),
                             values=[formatear(k, r.get(k)) for k, _t, _a in self.columnas])
        if previo is not None and str(previo) in self.rows:
            self.tree.selection_set(str(previo))
        if self.on_select:
            self.on_select()

    def selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def selected_row(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None


class CajaTexto(tk.Text):
    def __init__(self, parent, height=8):
        super().__init__(parent, height=height, wrap="word", state="disabled", relief="flat",
                         background="#F1F8E9", padx=10, pady=8)

    def mostrar(self, texto):
        self.config(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", texto)
        self.config(state="disabled")
