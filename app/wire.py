from __future__ import annotations

import json
import time
import uuid
from typing import Any


def _as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        text = content.get("text") or ""
        return text if isinstance(text, str) else ""
    return ""


def _message_from_item(item: Any) -> dict | None:
    if isinstance(item, str):
        return {"role": "user", "content": item}
    if not isinstance(item, dict):
        return None
    role = item.get("role") or ("user" if item.get("type") in {None, "message"} else None)
    if item.get("type") == "message" or role:
        content = _as_text(item.get("content") or item.get("text") or "")
        if role in {"user", "assistant", "system", "developer"} and content:
            return {"role": role, "content": content}
    return None


def parse_turn(body: dict) -> tuple[str, list[dict], str | None, float]:
    raw_input = body.get("input", body.get("messages"))
    instructions = body.get("instructions")
    platform_instructions = instructions.strip() if isinstance(instructions, str) else None

    messages: list[dict] = []
    if isinstance(raw_input, str):
        messages = [{"role": "user", "content": raw_input}]
    elif isinstance(raw_input, list):
        for item in raw_input:
            message = _message_from_item(item)
            if message:
                messages.append(message)
    elif isinstance(raw_input, dict):
        message = _message_from_item(raw_input)
        if message:
            messages = [message]

    notes = [message["content"] for message in messages if message["role"] in {"system", "developer"}]
    if notes:
        extra = "\n".join(notes)
        platform_instructions = f"{platform_instructions}\n{extra}".strip() if platform_instructions else extra

    conversation = [message for message in messages if message["role"] in {"user", "assistant"}]
    user_indexes = [index for index, message in enumerate(conversation) if message["role"] == "user"]
    if not user_indexes:
        return "", [], platform_instructions, _temperature(body)

    current_index = user_indexes[-1]
    question = conversation[current_index]["content"].strip()
    history = conversation[:current_index]
    return question, history, platform_instructions, _temperature(body)


def _temperature(body: dict) -> float:
    raw = body.get("temperature", 0.2)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.2
    return min(max(value, 0.0), 0.4)


def response_payload(text: str, model: str) -> dict:
    response_id = f"resp_{uuid.uuid4().hex}"
    message_id = f"msg_{uuid.uuid4().hex}"
    now = int(time.time())
    return {
        "id": response_id,
        "object": "response",
        "created_at": now,
        "status": "completed",
        "model": model or "cv-jordi",
        "output": [
            {
                "id": message_id,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                        "annotations": [],
                    }
                ],
            }
        ],
        "output_text": text,
    }


def sse(text: str, model: str) -> str:
    payload = response_payload(text, model)
    message = payload["output"][0]
    events = [
        {
            "type": "response.created",
            "response": {**payload, "status": "in_progress", "output": []},
        },
        {
            "type": "response.output_text.delta",
            "item_id": message["id"],
            "output_index": 0,
            "content_index": 0,
            "delta": text,
        },
        {
            "type": "response.output_text.done",
            "item_id": message["id"],
            "output_index": 0,
            "content_index": 0,
            "text": text,
        },
        {"type": "response.completed", "response": payload},
    ]
    lines = []
    for sequence_number, event in enumerate(events):
        event["sequence_number"] = sequence_number
        lines.append(f"event: {event['type']}")
        lines.append(f"data: {json.dumps(event, ensure_ascii=False)}")
        lines.append("")
    lines.append("data: [DONE]")
    lines.append("")
    return "\n".join(lines)


def error_payload(message: str, code: str, error_type: str = "invalid_request_error") -> dict:
    return {"error": {"message": message, "type": error_type, "code": code}}
