"""Fake Claude Messages API responses, shared by the client and publisher tests."""

import json

import httpx2

FIELDS = {
    "title": "1997 Toyota RAV4: The Compact SUV That Started a Whole Segment",
    "content": "<p>The <strong>1997 Toyota RAV4</strong> is a compact SUV.</p>",
    "seo_title": "1997 Toyota RAV4 Review and Buyer's Guide",
    "seo_description": "Everything to know before buying a 1997 Toyota RAV4.",
    "seo_keywords": ["used toyota rav4", "1997 rav4"],
}
UNSET = object()


def message(
    fields=FIELDS,
    *,
    text=UNSET,
    blocks_before=(),
    stop_reason="end_turn",
    input_tokens=1234,
    output_tokens=567,
    cache_creation_input_tokens=0,
    cache_read_input_tokens=0,
    iterations=None,
    model="claude-haiku-4-5",
):
    content = list(blocks_before)
    if text is not None:
        content.append({"type": "text", "text": json.dumps(fields) if text is UNSET else text})
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
    }
    if iterations is not None:
        usage["iterations"] = iterations
    body = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage,
    }
    return httpx2.Response(200, json=body, headers={"request-id": "req_abc"})


def api_error(status, error_type, text="Something went wrong.", headers=None):
    body = {"type": "error", "error": {"type": error_type, "message": text}, "request_id": "req_err"}
    return httpx2.Response(status, json=body, headers={"request-id": "req_bad", **(headers or {})})
