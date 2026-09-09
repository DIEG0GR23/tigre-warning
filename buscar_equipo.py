import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("FOOTBALL_API_KEY")

url = "https://v3.football.api-sports.io/teams"

headers = {
    "x-apisports-key": api_key
}

parametros = {
    "search": "Tigres"
}

respuesta = requests.get(
    url,
    headers=headers,
    params=parametros,
    timeout=10
)

datos = respuesta.json()

print("Código:", respuesta.status_code)

if datos.get("errors"):
    print("Error:", datos["errors"])
else:
    for resultado in datos.get("response", []):
        equipo = resultado["team"]

        print("----------------")
        print("ID:", equipo["id"])
        print("Nombre:", equipo["name"])
        print("País:", equipo["country"])