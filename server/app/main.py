import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.limits import limiter
from app.routers import anomalies, auth, devices, ingest, metrics, models, pipeline

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(levelname)s:     %(name)s - %(message)s",
)
logger = logging.getLogger("baseline")

os.makedirs(settings.models_dir, exist_ok=True)

app = FastAPI(title="Baseline API")

SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "Referrer-Policy": "no-referrer",
                    "Cache-Control": "no-store"}

app.state.limiter = limiter
limiter.enabled = settings.rate_limits_enabled


@app.exception_handler(RateLimitExceeded)
async def rate_limited(request: Request, exc: RateLimitExceeded):
    # detail-keyed like every other API error (slowapi's stock handler uses
    # {"error": ...}, which the web client's error surface would drop)
    response = JSONResponse(status_code=429,
                            content={"detail": f"Rate limit exceeded: {exc.detail}"})
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit)  # keeps Retry-After
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update(SECURITY_HEADERS)
    return resp


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Never leak stack traces to clients; log them server-side instead.
    # Headers set here directly: this handler runs in the outermost
    # ServerErrorMiddleware, ABOVE the security_headers middleware.
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500,
                        content={"detail": "internal error", "code": "internal_error"},
                        headers=SECURITY_HEADERS)


app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(ingest.router)
app.include_router(metrics.router)
app.include_router(anomalies.router)
app.include_router(pipeline.router)
app.include_router(models.router)

logger.info("baseline api starting — autoencoder=%s models_dir=%s log_level=%s",
            settings.enable_autoencoder, settings.models_dir, settings.log_level)


@app.get("/api/v1/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "db": "error"})
    return {"status": "ok", "db": "ok"}
