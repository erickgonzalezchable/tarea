"""Pruebas funcionales (sin interfaz). Ejecutar:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MESA_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")

from app import calculadora as calc, db, logica as lg  # noqa: E402
from config import config as cfg  # noqa: E402

PAN, LACTEO = "Pan y tortilla", "Lácteos y huevo"
COM = cfg.COMEDORES[0]["nombre"]


class Base(unittest.TestCase):
    def setUp(self):
        if cfg.DB_PATH.exists():
            cfg.DB_PATH.unlink()
        db.init_db()
        self.don = lg.login("donante1", "donante123")["id"]
        self.vol = lg.voluntario_de_usuario(lg.login("voluntario1", "mesa123")["id"])["id"]  # 150 kg, con frío

    def nueva(self, alimento=PAN, kg=20, horas=8):
        return lg.registrar_donacion(self.don, alimento, kg, horas, "Centro", "Calle 1 Norte #20", "", COM)


class TestCalculo(unittest.TestCase):
    def test_distancia_cero(self):
        self.assertEqual(calc.haversine_km(16.7, -93.1, 16.7, -93.1), 0)

    def test_impacto(self):
        i = calc.calcular_impacto(PAN, 10, 11)
        self.assertEqual(i["raciones"], 50)
        self.assertEqual(i["valor_estimado"], 350)
        self.assertAlmostEqual(i["costo_traslado"], 24.5)
        self.assertEqual(i["requiere_frio"], 0)

    def test_frio_y_prioridad(self):
        self.assertEqual(calc.calcular_impacto(LACTEO, 1, 1)["requiere_frio"], 1)
        self.assertEqual(calc.prioridad(2), "ALTA")
        self.assertEqual(calc.prioridad(24), "NORMAL")

    def test_catalogo_invalido(self):
        with self.assertRaises(ValueError):
            calc.calcular_km("Marte", COM)


class TestUsuarios(Base):
    def test_login_mal(self):
        self.assertIsNone(lg.login("admin", "mala"))

    def test_hash(self):
        self.assertNotIn("admin123", db.fetch_one("SELECT password_hash h FROM usuarios WHERE usuario='admin'")["h"])

    def test_duplicado(self):
        with self.assertRaises(Exception) as cm:
            lg.registrar_donante("donante1", "X", "", "abcdef")
        self.assertIn("ya existe", db.friendly_error(cm.exception))

    def test_validaciones(self):
        for args in (("ab", "X", "", "abcdef"), ("nuevo1", "X", "123", "abcdef"), ("nuevo1", "X", "", "123")):
            with self.assertRaises(lg.ReglaError):
                lg.registrar_donante(*args)

    def test_voluntario_atomico(self):
        lg.registrar_voluntario("vol2", "Ana", "", "abcdef", "Auto", "xyz-1", 50, False)
        with self.assertRaises(Exception):
            lg.registrar_voluntario("vol3", "Luis", "", "abcdef", "Auto", "XYZ-1", 50, False)
        self.assertIsNone(db.fetch_one("SELECT 1 FROM usuarios WHERE usuario='vol3'"))


class TestFlujo(Base):
    def test_flujo_completo(self):
        d = self.nueva()
        lg.asignar(d)
        lg.iniciar(d, self.vol)
        lg.marcar_entregada(d, self.vol)
        i = lg.impacto()
        self.assertEqual((i["entregas"], i["kg"], i["raciones"]), (1, 20, 100))

    def test_cantidad_invalida(self):
        for kg in (0, -5, "abc", 500):
            with self.assertRaises(lg.ReglaError):
                self.nueva(kg=kg)

    def test_refrigeracion_requerida(self):
        lg.cambiar_estado_voluntario(self.vol, "SUSPENDIDO")
        lg.registrar_voluntario("vol2", "Ana", "", "abcdef", "Auto", "AAA-1", 50, False)
        with self.assertRaises(lg.ReglaError):
            lg.asignar(self.nueva(LACTEO, 10))       # solo hay voluntario sin frío
        self.assertEqual(lg.asignar(self.nueva(PAN, 10))["nombre"], "Ana")

    def test_capacidad(self):
        lg.registrar_voluntario("vol2", "Ana", "", "abcdef", "Auto", "AAA-1", 50, True)
        self.assertEqual(lg.asignar(self.nueva(PAN, 100))["id"], self.vol)

    def test_balanceo_de_carga(self):
        lg.registrar_voluntario("vol2", "Ana", "", "abcdef", "Auto", "AAA-1", 150, True)
        self.assertNotEqual(lg.asignar(self.nueva())["id"], lg.asignar(self.nueva())["id"])

    def test_vencida_no_se_asigna(self):
        d = self.nueva()
        pasado = (lg.ahora() - timedelta(hours=1)).strftime(lg.FMT)
        db.execute("UPDATE donaciones SET vence_en=? WHERE id=?", (pasado, d))
        with self.assertRaises(lg.ReglaError):
            lg.asignar(d)
        self.assertEqual(lg.impacto()["vencidas_kg"], 20)

    def test_estado_invalido(self):
        d = self.nueva()
        lg.asignar(d)
        with self.assertRaises(lg.ReglaError):
            lg.marcar_entregada(d, self.vol)

    def test_incidente_y_reanudar(self):
        d = self.nueva()
        lg.asignar(d)
        lg.reportar_incidente(d, self.vol, "Comedor cerrado", "sin personal")
        self.assertEqual(len(lg.incidentes_de(d)), 1)
        lg.iniciar(d, self.vol)

    def test_cancelar_y_permisos(self):
        d = self.nueva()
        with self.assertRaises(lg.ReglaError):
            lg.cancelar(d, donante_id=999)
        lg.cancelar(d, self.don)
        with self.assertRaises(lg.ReglaError):
            lg.asignar(d)

    def test_voluntario_ajeno(self):
        d = self.nueva()
        lg.asignar(d)
        with self.assertRaises(lg.ReglaError):
            lg.iniciar(d, 999)

    def test_urgentes_primero(self):
        a, b = self.nueva(horas=24), self.nueva(horas=2)
        self.assertEqual(lg.todas_las_donaciones()[0]["id"], b)

    def test_detalle(self):
        self.nueva()
        self.assertIn("raciones", lg.detalle_texto(lg.todas_las_donaciones()[0]))


if __name__ == "__main__":
    unittest.main()
