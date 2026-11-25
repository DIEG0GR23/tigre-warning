"""Calendario de Tigres Femenil usando la API pública de ESPN.

No requiere API key. Fuente:
https://site.api.espn.com/apis/site/v2/sports/soccer/mex.w.1/teams/22413/schedule
"""

import time
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

from formato import completar_partido


ZONA_MONTERREY = ZoneInfo("America/Monterrey")

# ID de Tigres UANL Femenil en ESPN (liga mex.w.1).
TIGRES_FEMENIL_ID = "22413"

ESPN_CALENDARIO_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/soccer/mex.w.1/teams/"
    f"{TIGRES_FEMENIL_ID}/schedule"
)

# Evita consultar ESPN en cada visita (segundos).
DURACION_CACHE = 15 * 60
_cache = {"momento": 0, "datos": None}

TRADUCCION_FASES = {
    "Quarterfinals": "Cuartos de final",
    "Semifinals": "Semifinales",
    "Final": "Final",
    "Torneo Apertura": "Apertura",
    "Torneo Clausura": "Clausura",
}


# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------

def _traducir_fase(nombre):
    if not nombre:
        return ""

    for ingles, espanol in TRADUCCION_FASES.items():
        nombre = nombre.replace(ingles, espanol)

    return nombre


def _logo(equipo):
    logos = equipo.get("logos") or []

    if logos and logos[0].get("href"):
        return logos[0]["href"]

    return equipo.get("logo")


def _marcador(competidor):
    marcador = competidor.get("score")

    if isinstance(marcador, dict):
        return marcador.get("displayValue")

    return marcador


def _enlace_google_calendar(local, visitante, fecha_local, estadio):
    final_partido = fecha_local + timedelta(hours=2)

    parametros = {
        "action": "TEMPLATE",
        "text": f"{local} vs. {visitante} (Femenil)",
        "dates": (
            f"{fecha_local.strftime('%Y%m%dT%H%M%S')}/"
            f"{final_partido.strftime('%Y%m%dT%H%M%S')}"
        ),
        "ctz": "America/Monterrey",
        "location": estadio,
        "details": (
            "Partido de Tigres UANL Femenil.\n"
            "Horario sujeto a cambios."
        ),
    }

    return (
        "https://calendar.google.com/calendar/render?"
        + urlencode(parametros)
    )


# --------------------------------------------------
# PETICIÓN A ESPN
# --------------------------------------------------

def _solicitar_espn(parametros=None):
    try:
        respuesta = requests.get(
            ESPN_CALENDARIO_URL,
            params=parametros,
            timeout=10,
        )
        respuesta.raise_for_status()
        return respuesta.json().get("events", [])

    except (requests.RequestException, ValueError) as error:
        print("ERROR AL CONSULTAR ESPN (FEMENIL):", repr(error))
        return None


def _convertir_evento(evento):
    competencia = (evento.get("competitions") or [{}])[0]
    competidores = competencia.get("competitors", [])

    local = next(
        (c for c in competidores if c.get("homeAway") == "home"),
        None,
    )
    visitante = next(
        (c for c in competidores if c.get("homeAway") == "away"),
        None,
    )

    if not local or not visitante or not evento.get("date"):
        return None

    fecha_utc = datetime.fromisoformat(
        evento["date"].replace("Z", "+00:00")
    )
    fecha_local = fecha_utc.astimezone(ZONA_MONTERREY)

    estado = (
        competencia.get("status", {})
        .get("type", {})
        .get("state")
    ) or (
        evento.get("status", {})
        .get("type", {})
        .get("state")
    )

    nombre_local = local["team"].get("displayName", "Por confirmar")
    nombre_visitante = visitante["team"].get(
        "displayName", "Por confirmar"
    )
    estadio = (
        competencia.get("venue", {}).get("fullName")
        or "Por confirmar"
    )

    return completar_partido({
        "local": nombre_local,
        "visitante": nombre_visitante,
        "fecha": fecha_local.strftime("%d/%m/%Y"),
        "hora": fecha_local.strftime("%I:%M %p"),
        "estadio": estadio,
        "orden": fecha_local.isoformat(),
        "fecha_local_iso": fecha_local.isoformat(),
        "logo_local": _logo(local["team"]),
        "logo_visitante": _logo(visitante["team"]),
        "fase": _traducir_fase(
            evento.get("seasonType", {}).get("name")
        ),
        "estado": estado,
        "marcador_local": _marcador(local),
        "marcador_visitante": _marcador(visitante),
        "google_calendar_url": _enlace_google_calendar(
            nombre_local,
            nombre_visitante,
            fecha_local,
            estadio,
        ),
    }, fecha_local)


# --------------------------------------------------
# CALENDARIO FEMENIL
# --------------------------------------------------

def obtener_datos_femenil():
    """Regresa {"proximos": [...], "resultados": [...]}.

    - proximos: partidos que aún no se juegan (más cercano primero).
    - resultados: últimos partidos jugados (más reciente primero).
    """
    ahora_segundos = time.time()

    if (
        _cache["datos"] is not None
        and ahora_segundos - _cache["momento"] < DURACION_CACHE
    ):
        return _cache["datos"]

    # fixture=true trae los partidos por jugar;
    # sin parámetro trae los ya jugados de la temporada.
    eventos_proximos = _solicitar_espn({"fixture": "true"})
    eventos_jugados = _solicitar_espn()

    if eventos_proximos is None and eventos_jugados is None:
        # ESPN no respondió: usamos lo último guardado si existe.
        return _cache["datos"] or {"proximos": [], "resultados": []}

    ahora = datetime.now(ZONA_MONTERREY)
    partidos = {}

    for evento in (eventos_proximos or []) + (eventos_jugados or []):
        partido = _convertir_evento(evento)

        if partido:
            partidos[evento.get("id") or partido["orden"]] = partido

    proximos = sorted(
        (
            p for p in partidos.values()
            if p["estado"] != "post"
            and datetime.fromisoformat(p["fecha_local_iso"])
            > ahora - timedelta(hours=2)
        ),
        key=lambda p: p["orden"],
    )

    resultados = sorted(
        (p for p in partidos.values() if p["estado"] == "post"),
        key=lambda p: p["orden"],
        reverse=True,
    )[:5]

    datos = {"proximos": proximos, "resultados": resultados}

    _cache["momento"] = ahora_segundos
    _cache["datos"] = datos

    return datos
