import logging
import os
from dataclasses import asdict

import sys

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from assistant.ai.domain import AIResponse
from assistant.ai.embedders.transformers import TransformersEmbedder
from assistant.ai.providers.transformers import TransformersProvider

sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__))))

from models import embedder_models, provider_models


app_log_path = os.getenv("GPU_SERVICE_APP_LOG", "app.log")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(app_log_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EmbeddingRequest(BaseModel):
    model: str
    texts: List[str]


class Message(BaseModel):
    role: str
    content: str


class DialogRequest(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: int = 1024
    json_format: bool = False



embedders = {}
providers = {}


# @asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App is starting.")
    for model in embedder_models:
        try:
            embedders[model.lower()] = TransformersEmbedder(model)
        except Exception as e:
            logger.exception(f"Failed to load embedder {model}: {e}")
    for model in provider_models:
        try:
            providers[model.lower()] = TransformersProvider(model)
        except Exception as e:
            logger.exception(f"Failed to load provider {model}: {e}")
    logger.info("App initialized.")
    yield

app = FastAPI(lifespan=lifespan)


@app.post("/embeddings/")
async def get_embeddings(request: EmbeddingRequest):
    model = request.model.lower()
    if model not in embedders:
        raise HTTPException(status_code=400, detail="Model is not supported")
    try:
        embedder = embedders[model]
        embeddings = await embedder.embeddings(request.texts)
        return {"embeddings": embeddings}
    except Exception as e:
        logger.exception(f"Failed to get response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dialog/")
async def get_response(request: DialogRequest):
    model = request.model.lower()
    if model not in providers:
        raise HTTPException(status_code=400, detail="Model is not supported")
    try:
        provider = providers[model]
        response: AIResponse = await provider.get_response(
            messages=[
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ],
            max_tokens=request.max_tokens,
            json_format=request.json_format,
        )
        return {"response": asdict(response)}
    except Exception as e:
        logger.exception(f"Failed to get response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

