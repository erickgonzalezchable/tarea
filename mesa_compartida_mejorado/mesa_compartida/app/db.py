"""Acceso a datos con SQLite (incluido en Python) y contraseñas protegidas."""
import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager

from config import config as cfg

ITERACIONES = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    d = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${salt.hex()}${d.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _a, it, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, AttributeError):
        return False


def get_connection():
    cfg.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cfg.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(sql, params=()):
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def fetch_one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    with transaction() as conn:
        return conn.execute(sql, params).lastrowid


def friendly_error(ex: Exception) -> str:
    if isinstance(ex, sqlite3.IntegrityError):
        m = str(ex)
        if "usuarios.usuario" in m:
            return "Ese nombre de usuario ya existe. Elige otro."
        if "voluntarios.placas" in m:
            return "Esas placas ya están registradas."
        return "Los datos no son válidos o ya existen."
    return str(ex)


def init_db():
    """Crea la base si no existe y la actualiza si viene de una versión anterior."""
    conn = get_connection()
    try:
        conn.executescript(cfg.SCHEMA_PATH.read_text(encoding="utf-8"))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        # Aquí se agregarían migraciones: if version < 2: conn.execute("ALTER TABLE ...")
        if version < cfg.SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {cfg.SCHEMA_VERSION}")
        hay = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        if not hay:
            _datos_demo(conn)
        conn.commit()
    finally:
        conn.close()


def _datos_demo(conn):
    for usuario, nombre, tel, rol, pw in [
        ("admin", "Rosa Pérez", "", "ADMIN", "admin123"),
        ("voluntario1", "Marcos Díaz", "9611234567", "VOLUNTARIO", "mesa123"),
        ("donante1", "Restaurante La Milpa", "9617654321", "DONANTE", "donante123"),
    ]:
        cur = conn.execute("INSERT INTO usuarios(usuario,nombre,telefono,rol,password_hash) VALUES (?,?,?,?,?)",
                           (usuario, nombre, tel, rol, hash_password(pw)))
        if rol == "VOLUNTARIO":
            conn.execute(
                "INSERT INTO voluntarios(usuario_id,vehiculo,placas,capacidad_kg,refrigerado,codigo_qr) "
                "VALUES (?,?,?,?,?,?)", (cur.lastrowid, "Camioneta Estaquitas", "CHS-123-A", 150, 1,
                                         secrets.token_hex(8)))
