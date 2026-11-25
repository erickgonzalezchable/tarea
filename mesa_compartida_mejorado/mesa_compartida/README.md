# Mesa Compartida

Rescate de **alimentos excedentes**: restaurantes, panaderías y tiendas registran lo que les sobra, la coordinación asigna a un
voluntario con vehículo y este lo lleva a un comedor comunitario o casa hogar de Tuxtla Gutiérrez, Chiapas.

Proyecto de Taller de Investigación II · TecNM Campus Tuxtla Gutiérrez.

## Estado del proyecto

| Parte | Tecnología | Estado |
|---|---|---|
| **Etapa 1 – Prototipo de escritorio** | Python + Tkinter + SQLite | Realizada |
| **Etapa 2 – Portal web** | Python + Flask (plantillas HTML/CSS) | **En avance**: versión local sobre SQLite. Falta migrar a MySQL/PostgreSQL, mapas, QR e historial con filtros |

La Etapa 2 se plantea como **portal web** (no como API REST): el servidor Flask genera las páginas y ambas versiones comparten
las mismas reglas de negocio (`app/logica.py`) y la misma base de datos.

## Abrirlo

Requisitos: Python 3.10 o superior.

**Escritorio**
- Windows: doble clic en `iniciar.bat`.
- Linux: instala Tkinter una vez (`sudo apt install python3-tk` en Debian/Ubuntu/Mint; `sudo dnf install python3-tkinter` en Fedora;
  `sudo pacman -S tk` en Arch) y ejecuta `./iniciar.sh` (o `python3 -m app.main`). Si no abre: `chmod +x iniciar.sh`.

**Portal web local**
- Ubuntu: `sudo apt install python3 python3-venv`, luego `chmod +x iniciar_web.sh && ./iniciar_web.sh`.
- Manual: `pip install -r requirements-web.txt` y `python -m web.app`.
- Abre <http://127.0.0.1:5000>. Solo escucha en tu equipo (127.0.0.1).

La base (`data/mesa_compartida.db`) se crea sola con datos de prueba. Escritorio y web pueden usar la misma base.

## Cuentas de prueba (cámbialas con "Cambiar contraseña")
| Rol | Usuario | Contraseña |
|---|---|---|
| Coordinación | admin | admin123 |
| Voluntario | voluntario1 | mesa123 |
| Donante | donante1 | donante123 |

## Qué hace

- **Cuentas y roles:** coordinación, voluntario y donante, con contraseñas PBKDF2. Los **donantes se registran solos**
  (escritorio y web); la coordinación da de alta a los voluntarios con su vehículo.
- **Donación:** alimento, kg, horas disponibles para recogerlo, zona, dirección, observaciones y comedor. Calcula raciones,
  valor rescatado, km y prioridad (alta si quedan 4 h o menos). Funciona **sin internet**.
- **Vencimiento automático:** lo que nadie recoge a tiempo pasa a "Vencido" y ya no se puede asignar.
- **Asignación:** voluntario activo con capacidad suficiente (50/150 kg), con refrigeración si el alimento la requiere y con menos
  entregas en curso. Lo pendiente y urgente aparece primero.
- **Estados:** Pendiente → Asignado → En camino → Entregado, más Incidente, Cancelado y Vencido. Reporte de incidentes.
- **Cancelación:** el donante cancela sus propias donaciones y la coordinación puede cancelar cualquiera (en escritorio y en web).
  El voluntario no cancela.
- **Panel de impacto (coordinación):** entregas, kg rescatados, raciones, valor, donantes y kg vencidos.
- **Administración de voluntarios:** activar, suspender o dar de baja.

## Alcance y límites actuales

- Las distancias son una **estimación** (Haversine × factor de ruta 1.30) con coordenadas de ejemplo de zonas y comedores. El enlace
  "Abrir mapa" del portal abre Google Maps en otra pestaña, pero el sistema **no** calcula rutas viales reales.
- El código QR del voluntario está generado y guardado, pero todavía no se muestra ni se lee.
- No hay historial con filtros; alimentos, comedores y zonas se editan en `config/config.py`, no desde pantalla.
- El portal web usa SQLite. MySQL/PostgreSQL forma parte de la Etapa 2 y **aún no está implementado**.
- Aún no se ha probado con usuarios reales de la organización.
- Para publicarlo en internet faltan: dominio y hosting, HTTPS, llave secreta propia (`MESA_SECRET_KEY`), protección CSRF,
  servidor WSGI y pruebas de despliegue. **No publiques las cuentas de prueba.**

## Configurar (config/config.py)
Alimentos (refrigeración, raciones y valor por kg), horas límite, gasolina, comedores y zonas (coordenadas de ejemplo de Tuxtla).

## Pruebas
`python -m unittest discover -s tests -v`  (29 pruebas: 21 de reglas de negocio y 8 del portal web; las del portal se omiten si
Flask no está instalado).

## Estructura
```
app/main.py         pantallas de escritorio  |  app/logica.py    reglas de negocio (compartidas)
app/calculadora.py  rutas e impacto          |  app/db.py        SQLite y contraseñas
app/widgets.py      tablas y estilo          |  config/config.py catálogos
web/app.py          portal web (Flask)       |  web/templates/   páginas HTML
web/static/         estilos                  |  database/*.sql   esquema
tests/              pruebas funcionales      |
```
