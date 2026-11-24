from fastapi import FastAPI

from atlas_ml_platform.api.router import api_router
from atlas_ml_platform.config import Settings, get_settings
from atlas_ml_platform.core.errors import register_exception_handlers
from atlas_ml_platform.core.lifespan import lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="Production-grade ML Model Serving Platform",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.state.settings = settings

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api/v1")

    return app
