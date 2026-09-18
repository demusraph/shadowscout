<div align="center">

# ⚡ ShadowScout

**Autonomous Hidden API Reverse-Engineering & High-Speed Scraper Synthesizer**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Playwright](https://img.shields.io/badge/Engine-Playwright%20CDP-orange.svg)](https://playwright.dev/)
[![Pydantic V2](https://img.shields.io/badge/Validation-Pydantic%20V2-e92063.svg)](https://docs.pydantic.dev/)
[![MCP Ready](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple.svg)](https://modelcontextprotocol.io/)

*Browse once. Discover hidden backend APIs. Generate standalone, zero-browser Python scrapers that run 100x faster.*

---

</div>

## 📌 Why ShadowScout?

Traditional AI web scraping tools (`Browser-Use`, `Skyvern`, `Crawl4AI`) fall into two traps:
1. **DOM Parsing & Markdown Scraping**: Flaky, breaks when CSS classes change, and requires feeding 50k+ tokens into LLMs.
2. **Visual Browsing Agents**: Expensive (\$0.05 – \$0.20 per navigation) and painfully slow (3–15 seconds per page).

Modern dynamic web applications (Next.js, React, Nuxt) already fetch their structured data through **clean backend JSON REST / GraphQL endpoints**. 

**ShadowScout** acts as your autonomous reverse-engineer:
1. Navigates the target website once using Playwright to trigger dynamic client-side queries.
2. Intercepts network traffic via Chrome DevTools Protocol (CDP) and drops 95%+ telemetry/ad noise (GA4, Sentry, Datadog, TikTok).
3. Ranks endpoints using a **Tabular Data Density Heuristic**.
4. Performs **Ablative Header Pruning** to strip tracking headers and isolate essential auth tokens (`Bearer`, `X-CSRF-Token`).
5. Synthesizes a standalone, fully-typed `httpx` Python scraper (`scraper.py`) and an **OpenAPI 3.1** specification.
6. Runs a **Subprocess Self-Verification Gate** to guarantee the generated code is 100% runnable.

```
                    ┌──────────────────────────────────────────────┐
                    │ Target URL (e.g. Dynamic SPA Store / Portal) │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │ 1. Intercept & Filter Noise (Playwright/CDP) │
                    │    - Drops GA4, Datadog, Sentry, Meta Pixel  │
                    │    - Captures raw XHR/Fetch JSON streams     │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │ 2. Tabular Density Scorer & Parameter Fuzzer │
                    │    - Ranks JSON arrays by key entropy & size │
                    │    - Tests header ablation via httpx         │
                    │    - Detects pagination (page, offset, cursor)│
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │ 3. Code Synthesizer & Verification Gate      │
                    │    - Generates Pydantic V2 data model        │
                    │    - Synthesizes async standalone scraper.py │
                    │    - Exports OpenAPI 3.1 specification       │
                    │    - Runs subprocess test to verify 200 OK   │
                    └──────────────────────────────────────────────┘
```

---

## ⚡ Comparison: ShadowScout vs Existing Tools

| Feature | `Browser-Use` / `Skyvern` | `Crawl4AI` / `Firecrawl` | `ShadowScout` |
|---|---|---|---|
| **Production Execution** | Requires Full Browser | Requires Headless Chrome | **Zero Browser (`httpx` only)** |
| **Request Latency** | 3,000ms – 15,000ms | 1,000ms – 4,000ms | **10ms – 50ms per request** |
| **Token Cost per Scraping Run** | Very High (\$0.05 - \$0.50/page) | Medium (Markdown context) | **Zero (Code generated once)** |
| **Resilience to UI Redesigns** | Fragile (breaks on layout drift) | Fragile (breaks on CSS shifts) | **Immune (Target backend API)** |
| **Deliverable** | Chatbot / Agent log | Markdown / Raw HTML | **Standalone `.py` + `openapi.json`** |

---

## 🚀 Quickstart

### 1. Installation

```bash
pip install shadowscout
# or using uv
uv add shadowscout
```

Install Playwright browser binaries:
```bash
playwright install chromium
```

### 2. Instant Zero-Config Demo (10 Seconds)

Test ShadowScout immediately against an embedded local dynamic SPA e-commerce store with built-in pagination and fake analytics tracking:

```bash
shadowscout demo
```

You'll watch ShadowScout:
- Launch the mock SPA store.
- Sniff network requests and drop Google Analytics tracking pings.
- Isolate the `/api/v1/products` JSON endpoint with score `95.0/100`.
- Prune unnecessary browser headers down to minimal viable request.
- Infer a Pydantic V2 `ScrapedItem` model.
- Synthesize `demo_scraper.py` and run a subprocess self-verification test.

### 3. Sniff Any Dynamic Website

```bash
shadowscout sniff https://target-store.com/catalog -o get_catalog.py --openapi openapi.json
```

Options:
- `-o, --output`: Output file path for synthesized Python scraper (default: `scraper.py`).
- `--openapi`: Path to export standard OpenAPI 3.1 specification (e.g. `openapi.json`).
- `-t, --time`: Observation & scrolling time in seconds (default: `4`).
- `--headless / --no-headless`: Run browser with or without UI window.
- `--verify / --no-verify`: Run automated subprocess verification test (default: enabled).

### 4. Running the Synthesized Scraper

The generated script is 100% standalone and requires only `httpx` and `pydantic`:

```bash
# Scrape 5 pages and export to JSONL
python scraper.py --pages 5 -o data.jsonl

# Scrape and export directly to CSV
python scraper.py --pages 10 -o catalog.csv

# Verify single page test
python scraper.py --test-run
```

---

## 🔌 Model Context Protocol (MCP) Server

ShadowScout includes a native MCP server for integration with **Claude Desktop**, **Cursor**, or **Antigravity IDE**:

Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "shadowscout": {
      "command": "uv",
      "args": ["run", "--package", "shadowscout", "shadowscout", "mcp"]
    }
  }
}
```

Available MCP Tools:
- `mcp_sniff_url`: Intercepts traffic and returns ranked candidate endpoints.
- `mcp_generate_scraper`: Executes end-to-end pipeline and returns verified Python code + OpenAPI spec.

---

## 🧪 Architecture & Project Structure

```text
shadowscout/
├── src/shadowscout/
│   ├── cli.py                  # Typer entrypoint (sniff, demo, mcp)
│   ├── models.py               # Strongly-typed Pydantic V2 domain models
│   ├── interceptor/
│   │   ├── browser.py          # Playwright stealth driver with user simulation
│   │   ├── filters.py          # Deterministic filter for 50+ ad/telemetry SDKs
│   │   └── har_stream.py       # Streaming network capture buffer
│   ├── analyzer/
│   │   └── scorer.py           # Tabular Data Density heuristic scoring
│   ├── fuzzer/
│   │   ├── header_pruner.py    # Ablative header testing for minimal viable cURL
│   │   └── pagination.py       # Parameter discovery & batch limit fuzzing
│   ├── codegen/
│   │   ├── schema_inferrer.py  # Pydantic V2 model inference from samples
│   │   ├── template_engine.py  # Standalone async httpx scraper generator
│   │   └── openapi_exporter.py # OpenAPI 3.1 specification exporter
│   ├── cli/
│   │   ├── console.py          # Rich terminal dashboards & badges
│   │   ├── validator.py        # Subprocess self-verification test gate
│   │   └── mock_server.py      # Embedded FastAPI SPA & paginated API server
│   └── mcp/
│       └── server.py           # Model Context Protocol tools implementation
├── tests/                      # Pytest suite with 100% passing test coverage
├── pyproject.toml              # Modern packaging configuration
└── README.md
```

---

## 📄 License

Distributed under the **Apache 2.0 License**. See `LICENSE` for more information.
