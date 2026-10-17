"""Thin HTTP adapter. The same service is used by the CLI and Python callers."""

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .service import PromotionService, RecommendationRequest


def create_app(artifact_path: str | Path = "artifacts/model.json") -> FastAPI:
    service = PromotionService(artifact_path)
    app = FastAPI(title="Stories promotion opportunities", version="0.1.0",
                  description="Historical compatibility and conditional offer economics. Test requests interactively at /docs.")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": service.bundle["selected_model"], "schema_version": 1}

    @app.get("/options")
    def options() -> dict:
        return service.options()

    @app.post("/recommend")
    def recommend(request: RecommendationRequest) -> dict:
        try:
            return service.recommend(request)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return app
