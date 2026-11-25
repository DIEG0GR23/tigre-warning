"""Utilidades de formato compartidas por el calendario varonil y femenil."""

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

MESES_CORTOS = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def es_tigres(nombre):
    return "tigres" in (nombre or "").lower()


def fecha_corta(fecha):
    """26/09/2026 -> 'Sáb 26 sep'."""
    return (
        f"{DIAS[fecha.weekday()]} {fecha.day} "
        f"{MESES_CORTOS[fecha.month - 1]}"
    )


def nombre_mes(fecha):
    """'Septiembre 2026'."""
    return f"{MESES[fecha.month - 1]} {fecha.year}"


def resultado_tigres(partido):
    """Regresa 'G', 'E' o 'P' desde el punto de vista de Tigres."""
    try:
        goles_local = int(partido.get("marcador_local"))
        goles_visitante = int(partido.get("marcador_visitante"))
    except (TypeError, ValueError):
        return None

    if goles_local == goles_visitante:
        return "E"

    gana_local = goles_local > goles_visitante

    return "G" if gana_local == partido.get("es_local") else "P"


def completar_partido(partido, fecha_local):
    """Agrega los campos de presentación que usa la plantilla."""
    partido["es_local"] = es_tigres(partido.get("local"))
    partido["fecha_corta"] = fecha_corta(fecha_local)
    partido["mes"] = nombre_mes(fecha_local)

    if partido.get("marcador_local") is not None:
        partido["resultado"] = resultado_tigres(partido)

    return partido
