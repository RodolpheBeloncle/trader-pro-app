"""FastAPI backend for stock analyzer"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from analyzer import analyze_stock, analyze_batch, export_to_csv
from markets import MARKETS, get_market_tickers, get_all_markets
from saxo_routes import router as saxo_router

app = FastAPI(
    title="Stock Analyzer API",
    description="Multi-period stock analysis for identifying resilient stocks",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for parallel analysis
executor = ThreadPoolExecutor(max_workers=5)

# Include Saxo routes
app.include_router(saxo_router)


class TickerRequest(BaseModel):
    ticker: str


class BatchRequest(BaseModel):
    tickers: List[str]


class StockResult(BaseModel):
    ticker: str
    name: Optional[str] = None
    currency: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[int] = None
    current_price: Optional[float] = None
    perf_3m: Optional[float] = None
    perf_6m: Optional[float] = None
    perf_1y: Optional[float] = None
    perf_3y: Optional[float] = None
    perf_5y: Optional[float] = None
    volatility: Optional[float] = None
    dividend_yield: Optional[float] = None
    is_resilient: Optional[bool] = None
    chart_data: Optional[List[dict]] = None
    last_updated: Optional[str] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "ok",
        "message": "Stock Analyzer API is running",
        "version": "1.0.0"
    }


@app.post("/api/analyze", response_model=StockResult)
async def analyze_single(request: TickerRequest):
    """Analyze a single stock ticker"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, analyze_stock, request.ticker.upper())
    return result


@app.post("/api/analyze-batch")
async def analyze_multiple(request: BatchRequest):
    """Analyze multiple stock tickers"""
    loop = asyncio.get_event_loop()

    # Process tickers in parallel using thread pool
    tasks = [
        loop.run_in_executor(executor, analyze_stock, ticker.upper())
        for ticker in request.tickers
    ]
    results = await asyncio.gather(*tasks)

    return {
        "results": results,
        "total": len(results),
        "resilient_count": sum(1 for r in results if r.get('is_resilient', False))
    }


@app.get("/api/markets")
async def get_markets():
    """Get all available market presets grouped by type"""
    return {
        "markets": [
            {
                "id": k,
                "name": v["name"],
                "type": v.get("type", "stocks"),
                "count": len(v["tickers"])
            }
            for k, v in MARKETS.items()
        ]
    }


@app.get("/api/markets/{market}")
async def get_market(market: str, limit: int = 10, offset: int = 0):
    """Get tickers for a specific market with pagination"""
    market = market.lower()
    if market not in MARKETS:
        raise HTTPException(status_code=404, detail=f"Market '{market}' not found")

    all_tickers = MARKETS[market]["tickers"]
    paginated_tickers = all_tickers[offset:offset + limit]

    return {
        "market": market,
        "name": MARKETS[market]["name"],
        "tickers": paginated_tickers,
        "total": len(all_tickers),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(all_tickers)
    }


@app.post("/api/export/csv")
async def export_csv(request: BatchRequest):
    """Export analysis results as CSV"""
    loop = asyncio.get_event_loop()

    # Analyze stocks first
    tasks = [
        loop.run_in_executor(executor, analyze_stock, ticker.upper())
        for ticker in request.tickers
    ]
    results = await asyncio.gather(*tasks)

    # Convert to CSV
    csv_content = export_to_csv(results)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=stock_analysis.csv"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
