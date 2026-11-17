"""Deployment entry point for the Destination Finder FastAPI application.

Run from the project root with:
    uvicorn main:app --host 0.0.0.0 --port $PORT

Required environment variables:
    API_KEY: secret API key (exempt from the configured rate limits)
    PUB_KEY: public/shared API key (subject to the configured rate limits)

Importing this module does not train the model, modify project files, create
directories, or start a server. Uvicorn manages the server lifecycle.
"""

# third party
from fastapi.responses import RedirectResponse

# my files
from api.api import app


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect visitors to the existing website entry point."""
    return RedirectResponse(url="/website/", status_code=307)


# Uvicorn target: main:app
