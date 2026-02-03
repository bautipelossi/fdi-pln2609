# app.py
from fastapi import FastAPI
from pydantic import BaseModel
import requests
import json

# =========================================================
# CONFIGURACIÓN
# =========================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
BUTLER_CARTA_URL = "http://147.96.81.252:8000/carta"
MODEL = "mistral"

app = FastAPI(title="Agente 51")

# =========================================================
# MODELO DE ESTADO 
# =========================================================

class ButlerState(BaseModel):
    Alias: list[str] | None = None
    Recursos: dict
    Objetivo: dict
    Buzon: dict | None = None

# =========================================================
# PROMPT PARA EL LLM
# =========================================================

def construir_prompt(estado: ButlerState) -> str:
    return f"""
Eres un agente autónomo en un sistema de intercambio de recursos.

REGLAS OBLIGATORIAS:
- No puedes acceder a cuentas de otros agentes.
- No puedes inventar recursos.
- Solo puedes interactuar enviando cartas.
- Si no hay ninguna acción válida, debes esperar.

ESTADO ACTUAL:

Recursos disponibles:
{json.dumps(estado.Recursos, indent=2)}

Objetivo a cumplir:
{json.dumps(estado.Objetivo, indent=2)}

Buzón de mensajes:
{json.dumps(estado.Buzon or {}, indent=2)}

INSTRUCCIONES:
Debes devolver UNA sola acción en formato JSON estricto.
NO escribas texto adicional.
NO expliques tu razonamiento.

Acciones posibles:

1) Esperar:
{{"accion": "esperar"}}

2) Pedir recursos:
{{"accion": "pedir", "recurso": "<nombre>", "cantidad": <numero>}}

3) Ofrecer intercambio:
{{"accion": "ofrecer", "ofrezco": {{...}}, "pido": {{...}}}}

Devuelve SOLO el JSON.
"""

# =========================================================
# CONSULTA A OLLAMA
# =========================================================

def consultar_ollama(prompt: str) -> dict:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    ).json()

    texto = response.get("response", "").strip()

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        # fallback seguro
        return {"accion": "esperar"}

# =========================================================
# ENVÍO DE CARTAS A BUTLER
# =========================================================

def enviar_carta(alias: str, mensaje: str):
    requests.post(
        BUTLER_CARTA_URL,
        json={
            "alias": alias,
            "mensaje": mensaje
        }
    )

# =========================================================
# EJECUCIÓN DE LA DECISIÓN
# =========================================================

def ejecutar_decision(decision: dict, alias: str):
    accion = decision.get("accion")

    if accion == "esperar":
        return {"estado": "esperando"}

    if accion == "pedir":
        recurso = decision.get("recurso")
        cantidad = decision.get("cantidad")

        if recurso and cantidad:
            mensaje = f"Necesito {cantidad} unidades de {recurso}"
            enviar_carta(alias, mensaje)
            return {"estado": "pedido_enviado"}

    if accion == "ofrecer":
        ofrezco = decision.get("ofrezco", {})
        pido = decision.get("pido", {})

        mensaje = f"OFREZCO {ofrezco} A CAMBIO DE {pido}"
        enviar_carta(alias, mensaje)
        return {"estado": "oferta_enviada"}

    return {"estado": "esperando"}

# =========================================================
# ENDPOINT PRINCIPAL (BUTLER LLAMA ACÁ)
# =========================================================

@app.post("/generate")
def generate(estado: ButlerState):
    alias = estado.Alias[0] if estado.Alias else "agente"

    prompt = construir_prompt(estado)
    decision = consultar_ollama(prompt)
    resultado = ejecutar_decision(decision, alias)

    return {
        "decision": decision,
        "resultado": resultado
    }
