# Agente de CV — Jordi Adrián Mota Sánchez

Servicio HTTP que responde preguntas sobre mi trayectoria. Lo consume el chat de Banorte: ellos tienen la interfaz, yo expongo `POST /v1/responses` con la forma de Open Responses.

La fuente de hechos es `knowledge/cv.yaml`. El modelo no “sabe” el CV de memoria. En cada turno se eligen secciones de ese archivo y se le pasan como contexto. Si el dato no está, la respuesta lo dice. Si la pregunta mete un hecho que el yaml no sostiene, se corrige la premisa y no se desarrolla.

## Cómo entra una pregunta

1. Banorte manda `POST /v1/responses` (acepto también `/responses` por si registran la URL sin `/v1`).
2. `app/wire.py` saca el último mensaje de usuario, el historial y las instrucciones extra del formulario.
3. `app/policy.py` mira la pregunta. Si es inyección, inventar experiencia, teléfono, sueldo, un hecho falso del CV o algo que no es el perfil, se responde con un texto fijo y Groq no se llama.
4. Si es un saludo (“Hola”, “Buenas tardes”), se responde el saludo del agente. Si llega un saludo pegado a una pregunta, no entra por ahí.
5. `app/retrieve.py` elige las secciones del yaml. Si no hay coincidencia, se abstiene: “No encuentro esa información en el CV; no quiero inventarla.”
6. Si hay secciones, `app/llm.py` llama a Groq. Si Groq falla o se acaba el cupo, se dice que no se pudo generar. No se inventa una respuesta de CV para tapar el error.

El servidor no guarda conversación. Cada request trae la transcripción. Los turnos de usuario que la política habría bloqueado se quitan del historial antes de mandarlos al modelo.

## Stack


| Pieza                      | Qué hace                  | Por qué esta y no otra                                                                                                                                                                                                        |
| -------------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python 3.12                | Runtime de la imagen      | FastAPI y httpx se instalan sin pelea. En mi Mac el intérprete es 3.9; el código arranca igual porque los módulos usan `from __future__ import annotations`.                                                                  |
| FastAPI + Uvicorn          | HTTP, JSON, SSE           | Un POST, un GET de salud y un stream. No hay colas ni workers extra.                                                                                                                                                          |
| PyYAML                     | Carga `knowledge/cv.yaml` | El expediente es texto estructurado, no una base.                                                                                                                                                                             |
| httpx                      | Cliente de Groq           | Una llamada síncrona con timeout de 25 s.                                                                                                                                                                                     |
| Groq, `openai/gpt-oss-20b` | Redacta la respuesta      | OpenAI no da una clave gratis que sirva. En el tier gratis de Groq están el 20B y el 120B. El 20B responde antes; el cupo es 30 req/min, 1000 al día, 8k tokens/min. Eso alcanza para la revisión si no se dispara en ráfaga. |
| Render Free, Docker        | Host público con HTTPS    | El reto no trae servidor. Render construye el `Dockerfile` y da una URL. El plan gratis se duerme a los 15 min sin tráfico.                                                                                                   |
| pytest                     | Contrato y rechazos       | Corre sin Groq. Los 21 casos cubren el body, el stream, el teléfono, la inyección y las premisas falsas.                                                                                                                      |
| `evals/run_eval.py`        | Casos contra el modelo    | 14 preguntas con Groq de verdad. Si no hay clave, se saltan.                                                                                                                                                                  |


## Componentes


| Archivo                                  | Responsabilidad                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/main.py`                            | Arranca FastAPI, carga el CV y el cliente de Groq, escribe en log las claves del body (no el valor de la clave), despacha JSON o SSE.                                                                                                                                                                                                                                                                                                         |
| `app/wire.py`                            | Traduce Open Responses. Acepta `input` como string, lista de mensajes o `content` en partes. Los roles `system` y `developer` no se tratan como pregunta: se juntan con `instructions`. Recorta la temperatura a `[0, 0.4]`. Arma `output` + `output_text` y, si hay stream, los eventos `response.created`, `response.output_text.delta`, `response.output_text.done`, `response.completed` con `sequence_number`.                           |
| `app/agent.py`                           | Ordena el turno: política, saludo, historial limpio, secciones, llamada al modelo. El system prompt obliga a tercera persona, a no completar huecos y a no explicar un hecho que el CV no registra. Las instrucciones de la plataforma se pegan al final, tope 1500 caracteres, y no pueden saltarse esas reglas. Del historial se reenvían los últimos 8 turnos, cada uno recortado a 4000 caracteres.                                       |
| `app/policy.py`                          | Clasifica el texto (y, si viene, un bloque base64 ≥ 24 caracteres decodificado). Devuelve `allow` o un `kind` con mensaje fijo.                                                                                                                                                                                                                                                                                                               |
| `app/retrieve.py`                        | Puntúa secciones. Palabra que está en los keywords de la sección: +3. Palabra que aparece en el texto, con borde de palabra: +1. Eso evita que `java` pegue dentro de `javascript`. Si la pregunta es amplia (“cuéntame”, “hazme un resumen”, “platícame”), se mandan todas las secciones. El historial de usuario entra en la consulta para que un “¿y en ese proyecto?” no pierda el tema. Si el mejor puntaje es 0, no se llama al modelo. |
| `app/knowledge.py`                       | Carga el yaml, aplana espacios y fuerza los keywords a `str` (un `2023` sin comillas en YAML llega como entero y rompe el join).                                                                                                                                                                                                                                                                                                              |
| `app/llm.py`                             | `POST {GROQ_BASE_URL}/chat/completions`. `max_tokens` 500, `reasoning_effort` low. Si Groq responde 400 por ese campo, reintenta sin él. Timeout 25 s. Respuesta vacía = error.                                                                                                                                                                                                                                                               |
| `app/config.py`                          | Lee entorno. Modelo por defecto `openai/gpt-oss-20b`. Base por defecto `https://api.groq.com/openai/v1`.                                                                                                                                                                                                                                                                                                                                      |
| `app/textutil.py`                        | Quita acentos y parte tokens. `jordi`, `tiene` y `tienen` son stopwords: si no, “¿cuántos años tiene?” recuperaba el perfil por la palabra `tiene`.                                                                                                                                                                                                                                                                                           |
| `knowledge/cv.yaml`                      | Persona, siete secciones y un bloque `limits` que el prompt recibe siempre.                                                                                                                                                                                                                                                                                                                                                                   |
| `tests/test_agent.py`                    | Cliente de FastAPI y un LLM falso. No gasta la clave.                                                                                                                                                                                                                                                                                                                                                                                         |
| `evals/cases.json` + `evals/run_eval.py` | Las mismas preguntas contra Groq.                                                                                                                                                                                                                                                                                                                                                                                                             |
| `Dockerfile`                             | `python:3.12-slim`, instala requirements, copia `app/` y `knowledge/`, arranca Uvicorn en `$PORT`.                                                                                                                                                                                                                                                                                                                                            |
| `render.yaml`                            | Web service `cv-jordi`, runtime Docker, plan Free, health check `/health`.                                                                                                                                                                                                                                                                                                                                                                    |


## Contrato HTTP

Al registrar el agente la URL base es la del host más `/v1`. Ellos pegan `/responses`.


| Ruta                 | Uso                                                                     |
| -------------------- | ----------------------------------------------------------------------- |
| `POST /v1/responses` | Turno. Body Open Responses.                                             |
| `POST /responses`    | La misma lógica, por si la base se registra sin `/v1`.                  |
| `GET /health`        | `{"status":"ok"}`. Health check de Render y el ping que evita el sleep. |
| `GET /`              | Nombre y ruta del endpoint.                                             |


En el formulario: API key vacía, modelo vacío, estado de conversación **Reproducir transcripción**, imágenes y archivos apagados. El modelo lo fija `GROQ_MODEL` en el servidor. Si mandan `model` en el body, se ignora.

`input` puede ser un string o una lista de mensajes (`content` string o partes con `text`). Si `stream` es true, la respuesta es `text/event-stream`.

## Despliegue

Render, plan Free, runtime Docker, servicio `cv-agent`. Está descrito en `render.yaml`. URL pública: https://cv-agent-qmvs.onrender.com

El plan Free duerme el proceso a los ~15 minutos sin tráfico. La primera petición después de eso tarda en levantar el contenedor (a veces cerca de un minuto). Las siguientes responden normal.


| Variable           | Dónde                       | Qué es                             |
| ------------------ | --------------------------- | ---------------------------------- |
| `GROQ_API_KEY`     | Panel de Render, no el repo | Clave de console.groq.com.         |
| `GROQ_MODEL`       | `openai/gpt-oss-20b`        | Se puede cambiar sin tocar código. |
| `PYTHONUNBUFFERED` | `1`                         | Logs en tiempo real.               |
| `PORT`             | Lo pone Render              | Uvicorn escucha ahí.               |


El `Dockerfile` copia solo `app/` y `knowledge/`. `.env`, `.venv` y el PDF del CV no salen de la máquina. Durante la evaluación, un monitor a `/health` cada 5 minutos (UptimeRobot o cron-job.org) evita ese arranque en frío.

## Cómo lo corro aquí

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

En `.env` va la clave de Groq. Ese archivo está en `.gitignore`.

```bash
set -a && source .env && set +a
uvicorn app.main:app --reload --port 8000
```

```bash
pytest
python evals/run_eval.py
```

`pytest` cubre, entre otras cosas: body string y lista de mensajes, temperatura recortada a 0.4, SSE con `sequence_number`, “Buenas tardes” como saludo, “hazme un resumen” que sí llega al modelo, teléfono sin los números del PDF, salario, “trabajó en Google”, historial con inyección que no se reenvía, “dejó Rocketel” y “el call center dentro de la UNAM”.

## Qué no hace y qué cambiaría

No persiste logs de las preguntas de Banorte más allá de lo que imprime Uvicorn. No hay métricas ni cola. Si el cupo gratis de Groq se satura, el usuario ve la frase de “no pude generar”; no hay segundo proveedor.

Si el corpus creciera a varios CVs o a documentos largos, ahí sí pondría embeddings. Con una página no.
