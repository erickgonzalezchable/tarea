"""Pruebas del portal web (requieren Flask). Ejecutar:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MESA_DB", str(Path(tempfile.mkdtemp()) / "test_web.db"))

try:
    from web.app import app
except ModuleNotFoundError:  # Flask no instalado
    app = None

from app import db, logica as lg  # noqa: E402
from config import config as cfg  # noqa: E402

COM = cfg.COMEDORES[0]["nombre"]


@unittest.skipIf(app is None, "Flask no está instalado (pip install -r requirements-web.txt)")
class TestPortalWeb(unittest.TestCase):
    def setUp(self):
        if cfg.DB_PATH.exists():
            cfg.DB_PATH.unlink()
        db.init_db()
        self.c = app.test_client()

    def entrar(self, usuario, password, cliente=None):
        c = cliente or self.c
        return c.post("/login", data={"usuario": usuario, "password": password})

    def donacion_pendiente(self):
        don = lg.login("donante1", "donante123")["id"]
        return lg.registrar_donacion(don, "Pan y tortilla", 20, 8, "Centro", "Calle 1 Norte #20", "", COM)

    def test_registro_donante_y_login(self):
        r = self.c.post("/registro", data={"usuario": "panaderia1", "nombre": "Panadería El Sol",
                                           "telefono": "9611112222", "password": "clave123"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(lg.login("panaderia1", "clave123")["rol"], "DONANTE")
        self.assertEqual(self.entrar("panaderia1", "clave123").status_code, 302)

    def test_registro_valida_datos(self):
        r = self.c.post("/registro", data={"usuario": "ab", "nombre": "X", "telefono": "", "password": "123"})
        self.assertEqual(r.status_code, 200)               # se queda en el formulario con el error
        self.assertIsNone(lg.login("ab", "123"))
        r = self.c.post("/registro", data={"usuario": "donante1", "nombre": "Otro", "telefono": "", "password": "clave123"})
        self.assertIn("ya existe", r.get_data(as_text=True))

    def test_registro_no_crea_otros_roles(self):
        self.c.post("/registro", data={"usuario": "intruso", "nombre": "X", "telefono": "", "password": "clave123",
                                       "rol": "ADMIN"})
        self.assertEqual(lg.login("intruso", "clave123")["rol"], "DONANTE")

    def test_coordinacion_cancela_donacion_de_otro(self):
        did = self.donacion_pendiente()
        self.entrar("admin", "admin123")
        self.assertEqual(self.c.post(f"/donacion/{did}/cancel").status_code, 302)
        self.assertEqual(db.fetch_one("SELECT estado FROM donaciones WHERE id=?", (did,))["estado"], "CANCELADO")

    def test_donante_solo_cancela_las_suyas(self):
        did = self.donacion_pendiente()
        lg.registrar_donante("otrodonante", "Otro", "", "clave123")
        self.entrar("otrodonante", "clave123")
        self.c.post(f"/donacion/{did}/cancel")
        self.assertEqual(db.fetch_one("SELECT estado FROM donaciones WHERE id=?", (did,))["estado"], "PENDIENTE")

    def test_voluntario_no_puede_cancelar(self):
        did = self.donacion_pendiente()
        self.entrar("voluntario1", "mesa123")
        self.assertEqual(self.c.post(f"/donacion/{did}/cancel").status_code, 403)
        self.assertEqual(db.fetch_one("SELECT estado FROM donaciones WHERE id=?", (did,))["estado"], "PENDIENTE")

    def test_boton_cancelar_visible_para_coordinacion(self):
        self.donacion_pendiente()
        self.entrar("admin", "admin123")
        self.assertIn("/cancel", self.c.get("/panel").get_data(as_text=True))

    def test_panel_exige_sesion(self):
        self.assertEqual(self.c.get("/panel").status_code, 302)


if __name__ == "__main__":
    unittest.main()
