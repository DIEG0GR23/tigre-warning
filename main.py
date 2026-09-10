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

app = FastAPI(title="Tigre Warning")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CRON_SECRET = os.getenv("CRON_SECRET")

TIGRES_ID = "232"
ZONA_MONTERREY = ZoneInfo("America/Monterrey")


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


def obtener_calendario():
    ahora = datetime.now(timezone.utc)
    fecha_final = ahora + timedelta(days=180)

    rango = (
        ahora.strftime("%Y%m%d")
        + "-"
        + fecha_final.strftime("%Y%m%d")
    )

    url = (
        "https://site.api.espn.com/apis/site/v2/"
        f"sports/soccer/mex.1/scoreboard?dates={rango}&limit=1000"
    )

    try:
        respuesta = requests.get(url, timeout=10)
        respuesta.raise_for_status()
        datos = respuesta.json()

        calendario = []

        for evento in datos.get("events", []):
            competencia = evento["competitions"][0]
            equipos = competencia["competitors"]

            participa_tigres = any(
                equipo["team"]["id"] == TIGRES_ID
                for equipo in equipos
            )

            fecha_utc = datetime.fromisoformat(
                evento["date"].replace("Z", "+00:00")
            )

            if not participa_tigres or fecha_utc <= ahora:
                continue

            local = next(
                equipo["team"]["displayName"]
                for equipo in equipos
                if equipo["homeAway"] == "home"
            )

            visitante = next(
                equipo["team"]["displayName"]
                for equipo in equipos
                if equipo["homeAway"] == "away"
            )

            fecha_local = fecha_utc.astimezone(ZONA_MONTERREY)

            estadio = competencia.get("venue", {}).get(
                "fullName",
                "Por confirmar"
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
                "google_calendar_url": enlace_calendar
            })

        calendario.sort(
            key=lambda partido: partido["orden"]
        )

        return calendario

    except (requests.RequestException, KeyError, ValueError):
        return []


def obtener_proximo_partido():
    calendario = obtener_calendario()

    if calendario:
        return calendario[0]

    return {
        "local": "Tigres UANL",
        "visitante": "Por confirmar",
        "fecha": "Por confirmar",
        "hora": "Por confirmar",
        "estadio": "Por confirmar",
        "google_calendar_url": "#"
    }


def crear_mensaje_discord(partido):
    return (
        "🐯 **¡Mañana juega Tigres!**\n"
        f"⚽ {partido['local']} vs. {partido['visitante']}\n"
        f"📅 {partido['fecha']}\n"
        f"⏰ {partido['hora']}\n"
        f"🏟️ {partido['estadio']}"
    )


def enviar_alerta(mensaje):
    if not WEBHOOK_URL:
        print("No se encontró el webhook.")
        return False

    try:
        respuesta = requests.post(
            WEBHOOK_URL,
            json={"content": mensaje},
            timeout=10
        )

        return respuesta.status_code == 204

    except requests.RequestException:
        return False


@app.get("/api/calendario")
def api_calendario():
    return obtener_calendario()


@app.get("/")
def inicio(request: Request):
    calendario = obtener_calendario()

    if calendario:
        partido = calendario[0]
    else:
        partido = obtener_proximo_partido()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "partido": partido,
            "calendario": calendario
        }
    )
    
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

    mañana = (
        datetime.now(ZONA_MONTERREY).date()
        + timedelta(days=1)
    )

    for partido in calendario:
        fecha_partido = datetime.fromisoformat(
            partido["fecha_local_iso"]
        ).date()

        if fecha_partido == mañana:
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
    {
  
}