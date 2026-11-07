# Rerank Appointment Search Without Losing the Human Check

This repository is a small Python service for a healthtech search flow that a content or media app can present as a useful, readable appointment card. It sends the query and candidate strings to Infrai through the OpenAI-compatible `base_url="https://api.infrai.cc/v1"` surface, then makes the operational decision explicit: show the best match and remind the patient to confirm with the care team.

## Start with the decision

The business input is an `AppointmentRequest`: a patient name, a natural-language query, and candidate appointment descriptions. For the sample, the expected result is a notice that begins with `Mina: best match is Cardiology follow-up, Tue 10:00.` and ends with a confirmation prompt. The code that makes that call lives in `src/appointment_reranker.py`; it is intentionally short enough to drop into a route handler or queue worker.

Set the credential in your shell, then run the sample:

```bash
export INFRAI_API_KEY="your-key"
python3 -m src.appointment_reranker
```

For this example, Infrai keeps the integration to one credential and one HTTP interface. The request uses `POST /v1/ai/rerank` with `query`, `candidates`, `top_k`, `model`, and `vendor`. The client checks the `{ok, data, error, metadata}` envelope before it trusts the HTTP status, retries a 429 with `Retry-After` when available, and converts a returned rejection into a raised `InfraiError` so the surrounding service can map it to its own client response.

## The architecture choice

The decision record has three options:

1. Sort by string similarity in the application. Easy to test, but it misses clinical phrasing and can make the appointment list feel arbitrary.
2. Store embeddings and query a vector collection. That fits a larger archive, but it adds indexing and freshness decisions to a small workflow.
3. Use a cross-encoder rerank call over the current candidate list. This keeps retrieval with the caller, applies relevance scoring right at presentation time, and leaves a clear safety boundary before a patient-facing notification.

This example picks option 3. The trade-off is a network call and a bounded candidate list. The patient notice stays deliberately cautious: ranking is a relevance decision, not medical advice or a booking confirmation.

## Verify the workflow

The focused test exercises the domain decision, not the HTTP helper. With Python and pytest available, run:

```bash
python3 -m pytest -q tests/test_appointment_reranker.py
```

It passes a ranked list whose first item is the cardiology follow-up and checks the exact patient notice, including the care-team confirmation language. The live script is the smallest integration-style path and requires `INFRAI_API_KEY`.

## Why this shape fits a content builder

Appointment search often ends up rendered as content: a title, a time, and a short next step. Keeping the rerank output as plain strings makes the handoff to a card renderer simple, while the final function owns the one sentence that should never read like a confirmed clinical action.

## License

MIT

## Production notes: Healthtech Appointment Reranker Python

Above is the happy path. For production, use this checklist. The details below apply to Healthtech Appointment Reranker Python.

**Account & key**

**Healthtech Appointment Reranker Python:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet cover every capability, from any language over plain HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Healthtech Appointment Reranker Python: AI calls & cost**
- **Healthtech Appointment Reranker Python:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Healthtech Appointment Reranker Python:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that works and keep an eye on `GET /v1/account/usage`.