#!/usr/bin/env python3
"""
FastAPI server for competitor post pipeline.
Deploy on Railway with cron trigger.

Usage:
    uvicorn execution.api_server:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /health          - Health check
    POST /run-pipeline    - Trigger pipeline manually
    GET  /cache-stats     - View profile cache stats
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Import pipeline
from execution.competitor_post_pipeline import (
    run_full_pipeline,
    load_profile_cache,
    PROFILE_CACHE_FILE
)


# =============================================================================
# MODELS
# =============================================================================

class PipelineRequest(BaseModel):
    keywords: str = "ceos"
    days_back: int = 7
    min_reactions: int = 50
    countries: list[str] = ["United States", "Canada"]
    list_id: int = 480247
    dry_run: bool = False
    skip_icp: bool = False
    skip_validation: bool = False


class PipelineStatus(BaseModel):
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results: Optional[dict] = None
    error: Optional[str] = None


# =============================================================================
# STATE
# =============================================================================

pipeline_status = PipelineStatus(status="idle")
pipeline_lock = asyncio.Lock()


# =============================================================================
# BACKGROUND TASK
# =============================================================================

def run_pipeline_task(request: PipelineRequest):
    """Run pipeline in background thread."""
    global pipeline_status

    pipeline_status.status = "running"
    pipeline_status.started_at = datetime.now().isoformat()
    pipeline_status.completed_at = None
    pipeline_status.results = None
    pipeline_status.error = None

    try:
        results = run_full_pipeline(
            keywords=request.keywords,
            days_back=request.days_back,
            min_reactions=request.min_reactions,
            allowed_countries=request.countries,
            heyreach_list_id=request.list_id,
            dry_run=request.dry_run,
            skip_icp=request.skip_icp,
            skip_validation=request.skip_validation
        )

        pipeline_status.status = "completed"
        pipeline_status.completed_at = datetime.now().isoformat()
        pipeline_status.results = results

    except Exception as e:
        pipeline_status.status = "failed"
        pipeline_status.completed_at = datetime.now().isoformat()
        pipeline_status.error = str(e)


# =============================================================================
# APP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # Ensure .tmp dir exists
    os.makedirs(".tmp", exist_ok=True)
    yield


app = FastAPI(
    title="Competitor Post Pipeline API",
    description="API for running LinkedIn competitor post lead generation pipeline",
    version="1.0.0",
    lifespan=lifespan
)


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/status")
async def get_status():
    """Get current pipeline status."""
    return pipeline_status


@app.get("/cache-stats")
async def cache_stats():
    """Get profile cache statistics."""
    cache = load_profile_cache()
    return {
        "total_cached_profiles": len(cache),
        "cache_file": PROFILE_CACHE_FILE,
        "cache_exists": os.path.exists(PROFILE_CACHE_FILE),
        "cache_size_bytes": os.path.getsize(PROFILE_CACHE_FILE) if os.path.exists(PROFILE_CACHE_FILE) else 0
    }


@app.post("/run-pipeline")
async def trigger_pipeline(
    request: PipelineRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger the competitor post pipeline.

    This endpoint is designed to be called by Railway Cron.
    Configure cron schedule in railway.json or Railway dashboard.
    """
    global pipeline_status

    async with pipeline_lock:
        if pipeline_status.status == "running":
            raise HTTPException(
                status_code=409,
                detail="Pipeline already running"
            )

        # Start pipeline in background
        background_tasks.add_task(run_pipeline_task, request)

        return {
            "message": "Pipeline started",
            "request": request.model_dump(),
            "started_at": datetime.now().isoformat()
        }


@app.post("/run-pipeline/cron")
async def trigger_pipeline_cron(background_tasks: BackgroundTasks):
    """
    Simplified endpoint for cron - uses default settings.

    Configure in Railway:
    - Cron schedule: "0 9 * * *" (daily at 9am UTC)
    - HTTP method: POST
    - URL: https://your-app.railway.app/run-pipeline/cron
    """
    request = PipelineRequest()  # Use defaults
    return await trigger_pipeline(request, background_tasks)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
