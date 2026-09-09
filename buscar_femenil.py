import requests


url = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/soccer/mex.w.1/scoreboard"
    "?dates=20260921"
)
respuesta = requests.get(url, timeout=10)

print("Código:", respuesta.status_code)

respuesta.raise_for_status()
datos = respuesta.json()

equipos_encontrados = {}

for evento in datos.get("events", []):
    competencia = evento["competitions"][0]

    for participante in competencia["competitors"]:
        equipo = participante["team"]
        nombre = equipo["displayName"]

        if "tigres" in nombre.lower():
            equipos_encontrados[equipo["id"]] = nombre

for identificador, nombre in equipos_encontrados.items():
    print("----------------")
    print("ID:", identificador)
    print("Nombre:", nombre)

if not equipos_encontrados:
    print("No se encontró Tigres Femenil.")