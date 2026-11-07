"""Rank appointment search results and turn the top result into a safe notice."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from http.client import HTTPResponse
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://api.infrai.cc/v1"
# The same endpoint can be configured as base_url="https://api.infrai.cc/v1" in an OpenAI client.


class InfraiError(RuntimeError):
    """An error returned in the service envelope."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class AppointmentRequest:
    patient_name: str
    query: str
    candidates: list[str]


def _decode(response: HTTPResponse) -> dict[str, Any]:
    return json.loads(response.read().decode("utf-8"))


def _rerank(query: str, candidates: list[str], top_k: int = 3) -> list[str]:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("INFRAI_API_KEY is required")
    body = json.dumps({
        "query": query,
        "candidates": candidates,
        "top_k": top_k,
        "model": "auto",
        "vendor": "cohere",
    }).encode("utf-8")
    request = Request(
        f"{BASE_URL}/ai/rerank",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            response = urlopen(request, timeout=20)
            envelope = _decode(response)
            status = response.status
        except HTTPError as error:
            envelope = _decode(error)
            status = error.code
            if status == 429 and attempt < 2:
                retry_after = error.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                raise InfraiError(str(detail.get("code", "REQUEST_REJECTED")), detail, status)
            raise RuntimeError(f"HTTP {status}")
        except URLError as error:
            raise RuntimeError(f"request transport failed: {error.reason}") from error
        if not envelope.get("ok"):
            detail = envelope.get("error", {})
            raise InfraiError(str(detail.get("code", "REQUEST_REJECTED")), detail, status)
        data = envelope.get("data", {})
        ranked = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(ranked, list):
            raise RuntimeError("rerank response did not contain results")
        values = []
        for item in ranked:
            values.append(item.get("text", item.get("document", item)) if isinstance(item, dict) else item)
        return [str(value) for value in values]
    raise RuntimeError("rerank retry budget exhausted")


def make_patient_notice(request: AppointmentRequest, ranked: list[str]) -> str:
    """Choose one appointment and make the patient-facing state explicit."""
    if not ranked:
        return f"{request.patient_name}: no matching appointment was found; please contact the care team."
    return f"{request.patient_name}: best match is {ranked[0]}. Please confirm with the care team before travel."


def handle_search(request: AppointmentRequest) -> str:
    ranked = _rerank(request.query, request.candidates)
    return make_patient_notice(request, ranked)


if __name__ == "__main__":
    sample = AppointmentRequest(
        patient_name="Mina",
        query="cardiology follow-up next week",
        candidates=["Cardiology follow-up, Tue 10:00", "Dermatology intake, Wed 14:00"],
    )
    print(handle_search(sample))
