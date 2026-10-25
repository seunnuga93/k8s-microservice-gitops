"""Inventory API: a small service used to demonstrate the deployment pipeline."""

import os
import time
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

APP_VERSION = os.getenv("APP_VERSION", "dev")

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=0)


class Item(ItemIn):
    id: int


app = FastAPI(title="inventory-api", version=APP_VERSION)

# In-memory store keeps the demo dependency-free. Swap for a database in real use.
_items: Dict[int, Item] = {}
_next_id = 1


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    # Use the route template, not the raw path, so /items/1 and /items/2 share a label.
    route = request.scope.get("route")
    path = route.path if route else "unmatched"
    LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    return response


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    return {"status": "ready", "version": APP_VERSION}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/items", response_model=List[Item])
def list_items() -> List[Item]:
    return list(_items.values())


@app.post("/items", response_model=Item, status_code=201)
def create_item(payload: ItemIn) -> Item:
    global _next_id
    item = Item(id=_next_id, **payload.model_dump())
    _items[item.id] = item
    _next_id += 1
    return item


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    if item_id not in _items:
        raise HTTPException(status_code=404, detail="item not found")
    return _items[item_id]


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int) -> Response:
    if _items.pop(item_id, None) is None:
        raise HTTPException(status_code=404, detail="item not found")
    return Response(status_code=204)
