from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent import Agent
from app.config import load_settings
from app.knowledge import load_curriculum
from app.llm import GroqClient
from app.wire import error_payload, parse_turn, response_payload, sse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cv-agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    cv = load_curriculum(settings.cv_path)
    app.state.settings = settings
    app.state.agent = Agent(
        cv,
        GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_base_url),
    )
    log.info("cv loaded sections=%s model=%s", [section.id for section in cv.sections], settings.groq_model)
    yield


app = FastAPI(title="Agente de CV de Jordi", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {
        "name": "Agente de CV de Jordi Adrián Mota Sánchez",
        "open_responses": "/v1/responses",
    }


def _authorized(request: Request) -> bool:
    expected = request.app.state.settings.agent_api_key
    if not expected:
        return True
    header = request.headers.get("authorization", "")
    return header == f"Bearer {expected}"


async def _create_response(request: Request):
    if not _authorized(request):
        return JSONResponse(error_payload("API key inválida.", "invalid_api_key"), status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(error_payload("El body no es JSON.", "invalid_json"), status_code=400)
    if not isinstance(body, dict):
        return JSONResponse(error_payload("El body debe ser un objeto.", "invalid_json"), status_code=400)

    question, history, instructions, temperature = parse_turn(body)
    log.info(
        "turn keys=%s input_type=%s history=%s stream=%s model_field=%s auth=%s",
        sorted(body.keys()),
        type(body.get("input")).__name__,
        len(history),
        bool(body.get("stream")),
        body.get("model"),
        bool(request.headers.get("authorization")),
    )
    if request.app.state.settings.log_bodies:
        preview = question.replace("\n", " ")[:240]
        log.info("question_preview=%s", preview)

    if not question:
        return JSONResponse(error_payload("Falta el mensaje de usuario en input.", "missing_input"), status_code=400)

    answer = request.app.state.agent.reply(question, history, instructions, temperature)
    log.info("path=%s sections=%s", answer.path, answer.sections)
    model_name = answer.model or request.app.state.settings.groq_model
    if body.get("stream") is True:
        return StreamingResponse(iter([sse(answer.text, model_name)]), media_type="text/event-stream")
    return JSONResponse(response_payload(answer.text, model_name))


@app.post("/v1/responses")
async def responses(request: Request):
    return await _create_response(request)


@app.post("/responses")
async def responses_without_prefix(request: Request):
    return await _create_response(request)


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception):
    log.exception("unhandled error: %s", exc)
    return JSONResponse(
        error_payload("Error interno del agente.", "internal_error", "server_error"),
        status_code=500,
    )
