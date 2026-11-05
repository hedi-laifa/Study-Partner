"""FastAPI application entrypoint for Study Partner AI."""
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.auth_middleware import AuthIdentityMiddleware
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, logger
from app.db.session import get_engine
from app.models import Base


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize database tables on startup when the database is reachable."""
    try:
        Base.metadata.create_all(bind=get_engine())
    except Exception as exc:
        logger.warning(f"Startup schema check skipped or deferred: {exc}")
    yield


def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    configure_logging()

    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.APP_DEBUG,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(AuthIdentityMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "HTTP request processed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)
    if settings.API_V1_PREFIX != "/api":
        application.include_router(api_router, prefix="/api", include_in_schema=False)

    @application.get("/", tags=["Root"])
    def root() -> dict[str, str]:
        """Root welcome endpoint."""
        return {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
            "ready": f"{settings.API_V1_PREFIX}/health/ready",
        }

    return application


app = create_application()
