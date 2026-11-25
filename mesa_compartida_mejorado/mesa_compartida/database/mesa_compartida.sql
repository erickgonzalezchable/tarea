PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    telefono TEXT,
    rol TEXT NOT NULL CHECK (rol IN ('ADMIN','VOLUNTARIO','DONANTE')),
    password_hash TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS voluntarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL UNIQUE REFERENCES usuarios(id),
    vehiculo TEXT NOT NULL,
    placas TEXT NOT NULL UNIQUE,
    capacidad_kg INTEGER NOT NULL CHECK (capacidad_kg IN (50,150)),
    refrigerado INTEGER NOT NULL DEFAULT 0 CHECK (refrigerado IN (0,1)),
    estado TEXT NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','SUSPENDIDO','BAJA')),
    codigo_qr TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS donaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donante_id INTEGER NOT NULL REFERENCES usuarios(id),
    voluntario_id INTEGER REFERENCES voluntarios(id),
    alimento TEXT NOT NULL,
    cantidad_kg REAL NOT NULL CHECK (cantidad_kg > 0),
    requiere_frio INTEGER NOT NULL,
    horas_limite INTEGER NOT NULL,
    vence_en TEXT NOT NULL,
    prioridad TEXT NOT NULL CHECK (prioridad IN ('ALTA','NORMAL')),
    zona TEXT NOT NULL,
    direccion TEXT NOT NULL,
    observaciones TEXT,
    comedor TEXT NOT NULL,
    km_a_b REAL NOT NULL,
    km_b_c REAL NOT NULL,
    km_total REAL NOT NULL,
    raciones INTEGER NOT NULL,
    valor_estimado REAL NOT NULL,
    costo_traslado REAL NOT NULL,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE','ASIGNADO','EN_CAMINO','ENTREGADO','INCIDENTE','CANCELADO','VENCIDO')),
    creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS incidentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donacion_id INTEGER NOT NULL REFERENCES donaciones(id),
    tipo TEXT NOT NULL,
    descripcion TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS ix_don_estado ON donaciones(estado);
CREATE INDEX IF NOT EXISTS ix_don_vol ON donaciones(voluntario_id);
