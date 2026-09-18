from __future__ import annotations

import asyncio
import threading
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="ShadowScout Mock SPA Server")

# 50 realistic mock product records
MOCK_PRODUCTS = [
    {
        "id": i,
        "name": f"Enterprise AI Node {i:02d}",
        "price": round(199.99 + (i * 12.5), 2),
        "sku": f"SKU-NODE-{i:03d}",
        "category": "Compute" if i % 2 == 0 else "Storage",
        "rating": round(4.0 + (i % 10) * 0.1, 1),
        "stock": 10 + (i * 3),
        "is_active": True,
    }
    for i in range(1, 51)
]

HTML_SPA_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Modern Tech Hardware Catalog</title>
    <!-- Fake Analytics script to test noise filtering -->
    <script src="https://www.google-analytics.com/analytics.js" async></script>
    <style>
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1.5rem; margin-top: 1.5rem; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.25rem; }
        .price { color: #38bdf8; font-weight: bold; font-size: 1.2rem; }
        button { background: #0284c7; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 6px; cursor: pointer; margin-top: 2rem; font-weight: bold; }
        button:hover { background: #0369a1; }
    </style>
</head>
<body>
    <h1>Catalog SPA Demo</h1>
    <p>Dynamic catalog powered by client-side asynchronous fetch calls.</p>
    <div id="products-container" class="grid"></div>
    <div style="text-align: center;">
        <button id="load-more-btn" onclick="fetchNextPage()">Load More Items</button>
    </div>

    <script>
        let currentPage = 1;
        async function loadProducts(page) {
            try {
                const res = await fetch(`/api/v1/products?page=${page}&limit=6`);
                const data = await res.json();
                const container = document.getElementById('products-container');
                data.items.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'card';
                    card.innerHTML = `
                        <h3>${item.name}</h3>
                        <p class="price">$${item.price.toFixed(2)}</p>
                        <p style="color: #94a3b8; font-size: 0.9rem;">SKU: ${item.sku} | Rating: ${item.rating}/5.0</p>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error("Fetch failed", err);
            }
        }

        function fetchNextPage() {
            currentPage += 1;
            loadProducts(currentPage);
        }

        // Initial fetch on page load
        window.addEventListener('DOMContentLoaded', () => loadProducts(1));
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_spa_page():
    return HTML_SPA_CONTENT


@app.get("/api/v1/products")
async def get_products_api(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
):
    start = (page - 1) * limit
    end = start + limit
    items = MOCK_PRODUCTS[start:end]

    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": len(MOCK_PRODUCTS),
        "total_pages": (len(MOCK_PRODUCTS) + limit - 1) // limit,
        "items": items,
    }


class MockServerManager:
    """Helper to run the mock SPA server in a background thread for demos or tests."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.server: Optional[uvicorn.Server] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> str:
        config = uvicorn.Config(app=app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)

        def run_srv():
            asyncio.run(self.server.serve())

        self.thread = threading.Thread(target=run_srv, daemon=True)
        self.thread.start()
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self.server:
            self.server.should_exit = True
