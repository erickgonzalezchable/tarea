"""Reglas de negocio: usuarios, donaciones, asignación, estados, incidentes e impacto."""
import secrets
from datetime import datetime, timedelta

from app import calculadora as calc
from app import db
from config import config as cfg

ESTADOS = {"PENDIENTE": "Pendiente", "ASIGNADO": "Asignado", "EN_CAMINO": "En camino", "ENTREGADO": "Entregado",
           "INCIDENTE": "Incidente", "CANCELADO": "Cancelado", "VENCIDO": "Vencido"}
TIPOS_INCIDENTE = ["Alimento en mal estado", "Donante no estaba", "Comedor cerrado", "Dirección incorrecta",
                   "Falla del vehículo", "Otro"]
FMT = "%Y-%m-%d %H:%M:%S"


class ReglaError(Exception):
    """Error de regla de negocio con mensaje entendible."""


def ahora():
    return datetime.now()


# ---------- Usuarios ----------
def login(usuario, password):
    u = db.fetch_one("SELECT * FROM usuarios WHERE usuario=? AND activo=1", (usuario.strip(),))
    return u if u and db.verify_password(password, u["password_hash"]) else None


def _validar_cuenta(usuario, nombre, password):
    if len(usuario.strip()) < 3 or not usuario.strip().isalnum():
        raise ReglaError("El usuario debe tener 3 o más letras/números, sin espacios.")
    if not nombre.strip():
        raise ReglaError("Escribe el nombre completo o del negocio.")
    if len(password) < 6:
        raise ReglaError("La contraseña debe tener al menos 6 caracteres.")


def _telefono_ok(tel):
    t = tel.strip()
    if t and not (t.isdigit() and len(t) == 10):
        raise ReglaError("El teléfono debe tener 10 dígitos.")
    return t


def registrar_donante(usuario, nombre, telefono, password):
    _validar_cuenta(usuario, nombre, password)
    return db.execute("INSERT INTO usuarios(usuario,nombre,telefono,rol,password_hash) VALUES (?,?,?,'DONANTE',?)",
                      (usuario.strip(), nombre.strip(), _telefono_ok(telefono), db.hash_password(password)))


def registrar_voluntario(usuario, nombre, telefono, password, vehiculo, placas, capacidad, refrigerado):
    _validar_cuenta(usuario, nombre, password)
    if int(capacidad) not in cfg.CAPACIDADES_KG:
        raise ReglaError("La capacidad debe ser de 50 o 150 kg.")
    if not vehiculo.strip() or not placas.strip():
        raise ReglaError("Escribe el vehículo y las placas.")
    with db.transaction() as conn:
        uid = conn.execute(
            "INSERT INTO usuarios(usuario,nombre,telefono,rol,password_hash) VALUES (?,?,?,'VOLUNTARIO',?)",
            (usuario.strip(), nombre.strip(), _telefono_ok(telefono), db.hash_password(password))).lastrowid
        conn.execute(
            "INSERT INTO voluntarios(usuario_id,vehiculo,placas,capacidad_kg,refrigerado,codigo_qr) "
            "VALUES (?,?,?,?,?,?)", (uid, vehiculo.strip(), placas.strip().upper(), int(capacidad),
                                     int(bool(refrigerado)), secrets.token_hex(8)))
    return uid


def cambiar_password(usuario_id, actual, nueva):
    u = db.fetch_one("SELECT * FROM usuarios WHERE id=?", (usuario_id,))
    if not u or not db.verify_password(actual, u["password_hash"]):
        raise ReglaError("La contraseña actual no es correcta.")
    if len(nueva) < 6:
        raise ReglaError("La nueva contraseña debe tener al menos 6 caracteres.")
    db.execute("UPDATE usuarios SET password_hash=? WHERE id=?", (db.hash_password(nueva), usuario_id))


# ---------- Donaciones ----------
def cotizar(alimento, kg, horas, zona, comedor):
    """Vista previa del impacto antes de registrar la donación."""
    try:
        kg = float(kg)
    except (TypeError, ValueError):
        raise ReglaError("La cantidad debe ser un número (kg).")
    if not (0 < kg <= max(cfg.CAPACIDADES_KG)):
        raise ReglaError(f"La cantidad debe estar entre 0 y {max(cfg.CAPACIDADES_KG)} kg por donación. "
                         "Si es más, registra varias donaciones.")
    if not all([alimento, zona, comedor]):
        raise ReglaError("Completa todos los datos.")
    km = calc.calcular_km(zona, comedor)
    return {**km, **calc.calcular_impacto(alimento, kg, km["km_total"]), "kg": kg,
            "prioridad": calc.prioridad(int(horas))}


def registrar_donacion(donante_id, alimento, kg, horas, zona, direccion, observaciones, comedor):
    if len(direccion.strip()) < 5:
        raise ReglaError("Escribe la dirección o referencias del lugar de recolección.")
    c = cotizar(alimento, kg, horas, zona, comedor)
    vence = (ahora() + timedelta(hours=int(horas))).strftime(FMT)
    return db.execute(
        "INSERT INTO donaciones(donante_id,alimento,cantidad_kg,requiere_frio,horas_limite,vence_en,prioridad,zona,"
        "direccion,observaciones,comedor,km_a_b,km_b_c,km_total,raciones,valor_estimado,costo_traslado) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (donante_id, alimento, c["kg"], c["requiere_frio"], int(horas), vence, c["prioridad"], zona,
         direccion.strip(), observaciones.strip(), comedor, c["km_a_b"], c["km_b_c"], c["km_total"],
         c["raciones"], c["valor_estimado"], c["costo_traslado"]))


def marcar_vencidas():
    """Las donaciones que nadie recogió a tiempo pasan a VENCIDO (no se pueden asignar)."""
    with db.transaction() as conn:
        cur = conn.execute("UPDATE donaciones SET estado='VENCIDO' WHERE estado='PENDIENTE' AND vence_en < ?",
                           (ahora().strftime(FMT),))
        return cur.rowcount


def _donacion(did):
    d = db.fetch_one("SELECT * FROM donaciones WHERE id=?", (did,))
    if not d:
        raise ReglaError("La donación no existe.")
    return d


def voluntarios_con_carga():
    return db.fetch_all(
        "SELECT v.id, u.nombre, v.vehiculo, v.placas, v.capacidad_kg, v.refrigerado, v.estado, v.codigo_qr, "
        "(SELECT COUNT(*) FROM donaciones d WHERE d.voluntario_id=v.id AND d.estado IN "
        "('ASIGNADO','EN_CAMINO','INCIDENTE')) AS carga FROM voluntarios v JOIN usuarios u ON u.id=v.usuario_id "
        "ORDER BY u.nombre")


def asignar(did):
    """Voluntario ACTIVO con capacidad, con refrigeración si hace falta y menos entregas en curso."""
    marcar_vencidas()
    d = _donacion(did)
    if d["estado"] == "VENCIDO":
        raise ReglaError("Esta donación ya venció; el alimento no se puede recoger.")
    if d["estado"] != "PENDIENTE":
        raise ReglaError("Solo se pueden asignar donaciones pendientes.")
    cand = [v for v in voluntarios_con_carga() if v["estado"] == "ACTIVO"
            and v["capacidad_kg"] >= d["cantidad_kg"] and (v["refrigerado"] or not d["requiere_frio"])]
    if not cand:
        extra = " con refrigeración" if d["requiere_frio"] else ""
        raise ReglaError(f"No hay voluntarios activos{extra} con capacidad para {d['cantidad_kg']:g} kg.")
    elegido = min(cand, key=lambda v: (v["carga"], v["id"]))
    db.execute("UPDATE donaciones SET voluntario_id=?, estado='ASIGNADO' WHERE id=?", (elegido["id"], did))
    return elegido


def _cambiar(did, permitidos, nuevo, voluntario_id):
    d = _donacion(did)
    if d["voluntario_id"] != voluntario_id:
        raise ReglaError("Esta donación no está asignada a ti.")
    if d["estado"] not in permitidos:
        raise ReglaError(f"No se puede pasar de '{ESTADOS[d['estado']]}' a '{ESTADOS[nuevo]}'.")
    db.execute("UPDATE donaciones SET estado=? WHERE id=?", (nuevo, did))


def iniciar(did, voluntario_id):
    _cambiar(did, ("ASIGNADO", "INCIDENTE"), "EN_CAMINO", voluntario_id)


def marcar_entregada(did, voluntario_id):
    _cambiar(did, ("EN_CAMINO",), "ENTREGADO", voluntario_id)


def cancelar(did, donante_id=None):
    d = _donacion(did)
    if donante_id is not None and d["donante_id"] != donante_id:
        raise ReglaError("Solo puedes cancelar tus propias donaciones.")
    if d["estado"] in ("ENTREGADO", "CANCELADO", "EN_CAMINO", "VENCIDO"):
        raise ReglaError(f"No se puede cancelar una donación '{ESTADOS[d['estado']]}'.")
    db.execute("UPDATE donaciones SET estado='CANCELADO' WHERE id=?", (did,))


def reportar_incidente(did, voluntario_id, tipo, descripcion=""):
    d = _donacion(did)
    if d["voluntario_id"] != voluntario_id:
        raise ReglaError("Esta donación no está asignada a ti.")
    if d["estado"] not in ("ASIGNADO", "EN_CAMINO"):
        raise ReglaError("Solo se reportan incidentes en donaciones asignadas o en camino.")
    with db.transaction() as conn:
        conn.execute("INSERT INTO incidentes(donacion_id,tipo,descripcion) VALUES (?,?,?)",
                     (did, tipo, descripcion.strip()))
        conn.execute("UPDATE donaciones SET estado='INCIDENTE' WHERE id=?", (did,))


def cambiar_estado_voluntario(vid, estado):
    if estado not in ("ACTIVO", "SUSPENDIDO", "BAJA"):
        raise ReglaError("Estado no válido.")
    db.execute("UPDATE voluntarios SET estado=? WHERE id=?", (estado, vid))


# ---------- Consultas ----------
_SEL = ("SELECT d.*, c.nombre AS donante, c.telefono AS tel_donante, u.nombre AS voluntario, v.placas "
        "FROM donaciones d JOIN usuarios c ON c.id=d.donante_id "
        "LEFT JOIN voluntarios v ON v.id=d.voluntario_id LEFT JOIN usuarios u ON u.id=v.usuario_id ")


def donaciones_de_donante(uid):
    return db.fetch_all(_SEL + "WHERE d.donante_id=? ORDER BY d.id DESC", (uid,))


def donaciones_de_voluntario(vid):
    return db.fetch_all(_SEL + "WHERE d.voluntario_id=? ORDER BY d.id DESC", (vid,))


def todas_las_donaciones():
    """Urgentes y pendientes primero."""
    marcar_vencidas()
    return db.fetch_all(_SEL + "ORDER BY (d.estado='PENDIENTE') DESC, (d.prioridad='ALTA') DESC, d.vence_en, d.id")


def voluntario_de_usuario(uid):
    return db.fetch_one("SELECT * FROM voluntarios WHERE usuario_id=?", (uid,))


def incidentes_de(did):
    return db.fetch_all("SELECT * FROM incidentes WHERE donacion_id=? ORDER BY id", (did,))


def impacto():
    """Totales de lo efectivamente entregado."""
    r = db.fetch_one(
        "SELECT COUNT(*) AS entregas, COALESCE(SUM(cantidad_kg),0) AS kg, COALESCE(SUM(raciones),0) AS raciones, "
        "COALESCE(SUM(valor_estimado),0) AS valor, COUNT(DISTINCT donante_id) AS donantes "
        "FROM donaciones WHERE estado='ENTREGADO'")
    r["vencidas_kg"] = db.fetch_one(
        "SELECT COALESCE(SUM(cantidad_kg),0) AS k FROM donaciones WHERE estado='VENCIDO'")["k"]
    return r


def detalle_texto(d):
    t = (f"Donación #{d['id']} — {ESTADOS[d['estado']]}  (prioridad {d['prioridad'].lower()})\n"
         f"Alimento: {d['alimento']}  |  {d['cantidad_kg']:g} kg  |  {'Requiere refrigeración' if d['requiere_frio'] else 'Sin refrigeración'}\n"
         f"Recoger en: {d['zona']} — {d['direccion']}  |  Antes de: {d['vence_en'][:16]}\n"
         f"Donante: {d.get('donante', '')} {d.get('tel_donante') or ''}\n"
         f"Voluntario: {d.get('voluntario') or 'sin asignar'}  |  Entregar en: {d['comedor']}\n"
         f"Ruta: {d['km_a_b']:.1f} + {d['km_b_c']:.1f} = {d['km_total']:.1f} km  |  Gasolina aprox.: ${d['costo_traslado']:,.2f}\n"
         f"Impacto: {d['raciones']} raciones  |  Valor rescatado: ${d['valor_estimado']:,.2f}")
    if d.get("observaciones"):
        t += f"\nObservaciones: {d['observaciones']}"
    for i in incidentes_de(d["id"]):
        t += f"\n⚠ Incidente ({i['creado_en'][:16]}): {i['tipo']} {i['descripcion'] or ''}"
    return t
