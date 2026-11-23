import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings

    logger.info("Starting %s in %s mode", settings.APP_NAME, settings.APP_ENV)

    try:
        yield

    finally:
        logger.info("Shutting down %s", settings.APP_NAME)
