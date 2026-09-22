import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


load_dotenv()


# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

app = FastAPI(title="Tigre Warning")

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(directory="templates")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CRON_SECRET = os.getenv("CRON_SECRET")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

ZONA_MONTERREY = ZoneInfo("America/Monterrey")

API_FOOTBALL_URL = (
    "https://v3.football.api-sports.io"
)

HEADERS_API = {
    "x-apisports-key": API_FOOTBALL_KEY or ""
}

# Guarda el ID mientras la aplicación esté activa.
TIGRES_ID_CACHE = None


# --------------------------------------------------
# GOOGLE CALENDAR
# --------------------------------------------------

def crear_enlace_google_calendar(
    local,
    visitante,
    fecha_local,
    estadio
):
    final_partido = fecha_local + timedelta(hours=2)

    parametros = {
        "action": "TEMPLATE",
        "text": f"{local} vs. {visitante}",
        "dates": (
            f"{fecha_local.strftime('%Y%m%dT%H%M%S')}/"
            f"{final_partido.strftime('%Y%m%dT%H%M%S')}"
        ),
        "ctz": "America/Monterrey",
        "location": estadio,
        "details": (
            "Partido de Tigres UANL.\n"
            "Horario sujeto a cambios."
        )
    }

    return (
        "https://calendar.google.com/calendar/render?"
        + urlencode(parametros)
    )


# --------------------------------------------------
# PETICIONES A API-FOOTBALL
# --------------------------------------------------

def solicitar_api(ruta, parametros=None):
    if not API_FOOTBALL_KEY:
        print(
            "ERROR: No se encontró API_FOOTBALL_KEY."
        )
        return None

    url = API_FOOTBALL_URL + ruta

    try:
        respuesta = requests.get(
            url,
            headers=HEADERS_API,
            params=parametros,
            timeout=15
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        errores = datos.get("errors")

        if errores:
            print(
                "ERROR DE API-FOOTBALL:",
                errores
            )
            return None

        return datos

    except requests.RequestException as error:
        print(
            "ERROR DE CONEXIÓN CON API-FOOTBALL:",
            repr(error)
        )
        return None

    except ValueError as error:
        print(
            "ERROR AL LEER API-FOOTBALL:",
            repr(error)
        )
        return None


# --------------------------------------------------
# BUSCAR ID DE TIGRES
# --------------------------------------------------

def obtener_id_tigres():
    global TIGRES_ID_CACHE

    if TIGRES_ID_CACHE:
        return TIGRES_ID_CACHE

    datos = solicitar_api(
        "/teams",
        {
            "search": "Tigres UANL"
        }
    )

    if not datos:
        return None

    resultados = datos.get("response", [])

    for resultado in resultados:
        equipo = resultado.get("team", {})

        nombre = equipo.get("name", "")
        pais = equipo.get("country", "")

        if (
            "tigres" in nombre.lower()
            and pais.lower() == "mexico"
        ):
            TIGRES_ID_CACHE = equipo.get("id")

            print(
                "ID DE TIGRES ENCONTRADO:",
                TIGRES_ID_CACHE
            )

            return TIGRES_ID_CACHE

    print(
        "ERROR: No se encontró Tigres UANL "
        "en API-Football."
    )

    return None


# --------------------------------------------------
# OBTENER CALENDARIO
# --------------------------------------------------

def obtener_calendario():
    tigres_id = obtener_id_tigres()

    if not tigres_id:
        return []

    datos = solicitar_api(
        "/fixtures",
        {
            "team": tigres_id,
            "next": 20,
            "timezone": "America/Monterrey"
        }
    )

    if not datos:
        return []

    ahora = datetime.now(timezone.utc)
    fecha_final = ahora + timedelta(days=180)

    calendario = []

    for evento in datos.get("response", []):
        try:
            fixture = evento.get("fixture", {})
            equipos = evento.get("teams", {})

            fecha_texto = fixture.get("date")

            if not fecha_texto:
                continue

            fecha_utc = datetime.fromisoformat(
                fecha_texto.replace("Z", "+00:00")
            ).astimezone(timezone.utc)

            if fecha_utc <= ahora:
                continue

            if fecha_utc > fecha_final:
                continue

            local_datos = equipos.get("home", {})
            visitante_datos = equipos.get("away", {})

            local = local_datos.get(
                "name",
                "Por confirmar"
            )

            visitante = visitante_datos.get(
                "name",
                "Por confirmar"
            )

            logo_local = local_datos.get("logo")
            logo_visitante = visitante_datos.get("logo")

            fecha_local = fecha_utc.astimezone(
                ZONA_MONTERREY
            )

            venue = fixture.get("venue") or {}

            estadio = (
                venue.get("name")
                or "Por confirmar"
            )

            enlace_calendar = crear_enlace_google_calendar(
                local,
                visitante,
                fecha_local,
                estadio
            )

            calendario.append({
                "local": local,
                "visitante": visitante,
                "fecha": fecha_local.strftime("%d/%m/%Y"),
                "hora": fecha_local.strftime("%I:%M %p"),
                "estadio": estadio,
                "orden": fecha_utc.isoformat(),
                "fecha_local_iso": fecha_local.isoformat(),
                "google_calendar_url": enlace_calendar,
                "logo_local": logo_local,
                "logo_visitante": logo_visitante
            })

        except (
            KeyError,
            ValueError,
            TypeError
        ) as error:
            print(
                "ERROR AL PROCESAR PARTIDO:",
                repr(error)
            )

    calendario.sort(
        key=lambda partido: partido["orden"]
    )

    print(
        f"PARTIDOS ENCONTRADOS: {len(calendario)}"
    )

    return calendario


# --------------------------------------------------
# PRÓXIMO PARTIDO
# --------------------------------------------------

def partido_por_confirmar():
    return {
        "local": "Tigres UANL",
        "visitante": "Por confirmar",
        "fecha": "Por confirmar",
        "hora": "Por confirmar",
        "estadio": "Por confirmar",
        "google_calendar_url": "#",
        "logo_local": None,
        "logo_visitante": None,
        "fecha_local_iso": None
    }


def obtener_proximo_partido():
    calendario = obtener_calendario()

    if calendario:
        return calendario[0]

    return partido_por_confirmar()


# --------------------------------------------------
# DISCORD
# --------------------------------------------------

def crear_mensaje_discord(partido):
    return (
        "🐯 **¡Mañana juega Tigres!**\n"
        f"⚽ {partido['local']} vs. "
        f"{partido['visitante']}\n"
        f"📅 {partido['fecha']}\n"
        f"⏰ {partido['hora']}\n"
        f"🏟️ {partido['estadio']}"
    )


def enviar_alerta(mensaje):
    if not WEBHOOK_URL:
        print(
            "ERROR: No se encontró "
            "DISCORD_WEBHOOK_URL."
        )
        return False

    try:
        respuesta = requests.post(
            WEBHOOK_URL,
            json={"content": mensaje},
            timeout=10
        )

        if respuesta.status_code in (200, 204):
            return True

        print(
            "ERROR DE DISCORD:",
            respuesta.status_code,
            respuesta.text
        )

        return False

    except requests.RequestException as error:
        print(
            "ERROR AL CONECTAR CON DISCORD:",
            repr(error)
        )
        return False


# --------------------------------------------------
# PÁGINA PRINCIPAL
# --------------------------------------------------

@app.get("/")
def inicio(request: Request):
    calendario = obtener_calendario()

    partido = (
        calendario[0]
        if calendario
        else partido_por_confirmar()
    )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "partido": partido,
            "calendario": calendario
        }
    )


# --------------------------------------------------
# API DEL CALENDARIO
# --------------------------------------------------

@app.get("/api/calendario")
def api_calendario():
    return obtener_calendario()


# --------------------------------------------------
# PRUEBA DE DISCORD
# --------------------------------------------------

@app.get("/probar-alerta")
def probar_alerta():
    partido = obtener_proximo_partido()
    mensaje = crear_mensaje_discord(partido)

    enviado = enviar_alerta(mensaje)

    print(
        "ALERTA DE PRUEBA:",
        "ENVIADA" if enviado else "FALLÓ"
    )

    return RedirectResponse(
        url="/",
        status_code=303
    )


# --------------------------------------------------
# ALERTA AUTOMÁTICA
# --------------------------------------------------

@app.get("/api/cron/alerta")
def alerta_automatica(
    authorization: str | None = Header(default=None)
):
    if (
        not CRON_SECRET
        or authorization != f"Bearer {CRON_SECRET}"
    ):
        raise HTTPException(
            status_code=401,
            detail="No autorizado"
        )

    calendario = obtener_calendario()

    if not calendario:
        return {
            "ok": True,
            "mensaje": "No hay partidos próximos."
        }

    manana = (
        datetime.now(ZONA_MONTERREY).date()
        + timedelta(days=1)
    )

    for partido in calendario:
        fecha_local_iso = partido.get(
            "fecha_local_iso"
        )

        if not fecha_local_iso:
            continue

        fecha_partido = datetime.fromisoformat(
            fecha_local_iso
        ).date()

        if fecha_partido == manana:
            mensaje = crear_mensaje_discord(partido)
            enviado = enviar_alerta(mensaje)

            return {
                "ok": enviado,
                "mensaje": (
                    "Alerta enviada."
                    if enviado
                    else "No se pudo enviar la alerta."
                )
            }

    return {
        "ok": True,
        "mensaje": "Tigres no juega mañana."
    }