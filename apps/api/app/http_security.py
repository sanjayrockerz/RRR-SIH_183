import re
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def request_id(request: Request) -> str:
    value = request.headers.get("X-Request-ID", "")
    return value if _REQUEST_ID.fullmatch(value) else str(uuid4())


def error_payload(request: Request, status_code: int, detail: object, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": detail if isinstance(detail, str) else "Request validation failed",
                "request_id": getattr(request.state, "request_id", None),
            },
            # Keep detail for existing clients while they migrate to the envelope.
            "detail": detail,
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )


def validation_detail(exc: RequestValidationError) -> list[dict[str, object]]:
    return [
        {"location": list(error.get("loc", [])), "message": error.get("msg", "Invalid value"), "type": error.get("type", "value_error")}
        for error in exc.errors()
    ]
