"""Distancias (sin internet) e impacto estimado de cada donación."""
import math

from config import config as cfg


def haversine_km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def buscar(lista, nombre):
    for p in lista:
        if p["nombre"] == nombre:
            return p
    raise ValueError(f"No existe '{nombre}' en el catálogo.")


def km_ruta(a, b):
    return round(haversine_km(a["lat"], a["lng"], b["lat"], b["lng"]) * cfg.FACTOR_RUTA, 1)


def calcular_km(zona, comedor):
    """Centro de acopio -> donante -> comedor."""
    z, c = buscar(cfg.ZONAS, zona), buscar(cfg.COMEDORES, comedor)
    a_b, b_c = km_ruta(cfg.BASE, z), km_ruta(z, c)
    return {"km_a_b": a_b, "km_b_c": b_c, "km_total": round(a_b + b_c, 1)}


def calcular_impacto(alimento, kg, km_total):
    frio, raciones_kg, valor_kg = cfg.ALIMENTOS[alimento]
    return {
        "requiere_frio": int(frio),
        "raciones": int(kg * raciones_kg),
        "valor_estimado": round(kg * valor_kg, 2),
        "costo_traslado": round(km_total / cfg.KM_POR_LITRO * cfg.GASOLINA_PRECIO, 2),
    }


def prioridad(horas_limite):
    return "ALTA" if horas_limite <= cfg.URGENTE_HORAS else "NORMAL"
