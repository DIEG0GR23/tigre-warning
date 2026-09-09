import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests


TIGRES_ID = "232"

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

respuesta = requests.get(url, timeout=10)

print("Código:", respuesta.status_code)

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
    print("No se encontraron próximos partidos de Tigres.")

else:
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

    print("------------------------")
    print("Local:", local)
    print("Visitante:", visitante)
    print("Fecha:", fecha_local.strftime("%d/%m/%Y"))
    print("Hora:", fecha_local.strftime("%I:%M %p"))
    print("Estadio:", estadio)