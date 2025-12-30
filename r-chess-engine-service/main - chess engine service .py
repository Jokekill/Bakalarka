from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chess.engine
import os

app = FastAPI(title="Chess Engine Microservice")

# Cesta k Stockfishi uvnitř kontejneru (nastavíme v Dockerfile)
STOCKFISH_PATH = "/usr/local/bin/stockfish"


class AnalysisRequest(BaseModel):
    fen: str
    depth: int = 15  # Defaultní hloubka prohledávání


@app.on_event("startup")
async def startup_event():
    """Ověříme, že Stockfish je dostupný při startu."""
    if not os.path.exists(STOCKFISH_PATH):
        raise RuntimeError(f"Stockfish nebyl nalezen na cestě: {STOCKFISH_PATH}")


@app.post("/analyze")
async def analyze_position(request: AnalysisRequest):
    """
    Přijme FEN, spustí Stockfish analýzu a vrátí výsledek.
    Toto odpovídá tvému požadavku na black-box izolaci[cite: 208].
    """
    transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)

    try:
        board = chess.Board(request.fen)

        # Analýza pozice - limitujeme hloubkou (nebo časem)
        info = await engine.analyse(board, chess.engine.Limit(depth=request.depth))

        # Získání nejlepšího tahu
        result = await engine.play(board, chess.engine.Limit(depth=request.depth))

        return {
            "best_move": result.move.uci() if result.move else None,
            "score": info.get("score").white().score() if info.get("score") else None,
            "depth": request.depth
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await engine.quit()