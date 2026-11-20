# standard library
import os
from pathlib import Path
from typing import Annotated

# third party
from beartype import beartype
from fastapi import (
    Depends,
    FastAPI, 
    Header, 
    HTTPException,
    Request,
)
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# my files
from api.parse_response import UserResponse
from model import predict


SEC_KEY: str = os.environ["API_KEY"]
PUB_KEY: str = os.environ["PUB_KEY"]
KEYS: set[str] = {SEC_KEY, PUB_KEY}


@beartype
def get_api_key(request: Request) -> str:
    key = request.headers.get("X-Api-Key", "")
    return key


@beartype
def is_unlimited(request: Request) ->  bool:
    supplied_key: str = get_api_key(request)
    return supplied_key == SEC_KEY


@beartype
def verify_api_key(
    key: Annotated[
        str | None, 
        Header(alias="X-Api-Key"),
    ] = None,
) -> str:
    if key is None or key not in KEYS:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    return key


limiter = Limiter(
    key_func=get_api_key,
    default_limits=[],
    headers_enabled=True,
)

app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

@app.post("/recommend-destination")
@limiter.limit(
    "100/day",
    exempt_when=is_unlimited,
)
@limiter.limit(
    "15/hour",
    exempt_when=is_unlimited,
)
async def recommend_destination(
    request: Request,
    user_answer: UserResponse,
    x_api_key: Annotated[str, Depends(verify_api_key)],
) -> dict[str, list[str]]:

    return {
        "recommended-destination": predict(user_answer.to_tensor())
    }
    

WEBSITE_DIR: Path = Path(__file__).resolve().parent.parent / "website"

app.mount("/website", StaticFiles(directory=WEBSITE_DIR, html=True), name="website")
