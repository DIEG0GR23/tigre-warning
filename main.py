import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


load_dotenv()

app = FastAPI(title="Tigre Warning")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
TIGRES_ID = "232"


def obtener_proximo_partido():
    ahora = datetime.now(timezone.utc)
    fecha_final = ahora + timedelta(days=120)

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

        proximos = []

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

            if participa_tigres and fecha_utc > ahora:
                proximos.append((fecha_utc, evento))

        if not proximos:
            return {
                "local": "Tigres UANL",
                "visitante": "Por confirmar",
                "fecha": "Por confirmar",
                "hora": "Por confirmar",
                "estadio": "Por confirmar"
            }

        proximos.sort(key=lambda elemento: elemento[0])

        fecha_utc, evento = proximos[0]
        competencia = evento["competitions"][0]
        equipos = competencia["competitors"]

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

        fecha_local = fecha_utc.astimezone(
            ZoneInfo("America/Monterrey")
        )

        estadio = competencia.get("venue", {}).get(
            "fullName",
            "Por confirmar"
        )

        return {
            "local": local,
            "visitante": visitante,
            "fecha": fecha_local.strftime("%d/%m/%Y"),
            "hora": fecha_local.strftime("%I:%M %p"),
            "estadio": estadio
        }

    except (requests.RequestException, KeyError, ValueError):
        return {
            "local": "Tigres UANL",
            "visitante": "No disponible",
            "fecha": "No disponible",
            "hora": "No disponible",
            "estadio": "No disponible"
        }
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

            fecha_local = fecha_utc.astimezone(
                ZoneInfo("America/Monterrey")
            )

            estadio = competencia.get("venue", {}).get(
                "fullName",
                "Por confirmar"
            )

            calendario.append({
                "local": local,
                "visitante": visitante,
                "fecha": fecha_local.strftime("%d/%m/%Y"),
                "hora": fecha_local.strftime("%I:%M %p"),
                "estadio": estadio,
                "orden": fecha_utc.isoformat()
            })

        calendario.sort(
            key=lambda partido: partido["orden"]
        )

        return calendario

    except (requests.RequestException, KeyError, ValueError):
        return []

def enviar_alerta(mensaje):
    if not WEBHOOK_URL:
        print("No se encontró el webhook.")
        return False

    respuesta = requests.post(
        WEBHOOK_URL,
        json={"content": mensaje},
        timeout=10
    )

    return respuesta.status_code == 204


@app.get("/api/calendario")
def api_calendario():
    return obtener_calendario()


@app.get("/")
def inicio(request: Request):
    partido = obtener_proximo_partido()
    calendario = obtener_calendario()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "partido": partido,
            "calendario": calendario
        }
    )


@app.get("/probar-alerta")
def probar_alerta():
    partido = obtener_proximo_partido()
    

    mensaje = (
        "🐯 **Próximo partido de Tigres**\n"
        f"⚽ {partido['local']} vs. {partido['visitante']}\n"
        f"📅 {partido['fecha']}\n"
        f"⏰ {partido['hora']}\n"
        f"🏟️ {partido['estadio']}"
    )
    

    enviar_alerta(mensaje)
    

    return RedirectResponse(url="/")