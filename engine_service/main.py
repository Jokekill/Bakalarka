import os
import shutil
from typing import Optional

import chess
import chess.engine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="r-chess-engine-service")


def resolve_stockfish_path() -> str:
    env_path = os.getenv('STOCKFISH_PATH')
    if env_path:
        return env_path
    return shutil.which('stockfish') or '/usr/games/stockfish'


STOCKFISH_PATH = resolve_stockfish_path()


class AnalysisRequest(BaseModel):
    fen: str = Field(..., description="Full FEN string")
    depth: int = Field(15, ge=1, le=30, description="Search depth (1-30)")
    uci_elo: Optional[int] = Field(None, ge=1350, le=2850, description="Optional Elo limit (if supported)")

    @field_validator('fen')
    @classmethod
    def fen_must_be_non_empty(cls, v: str) -> str:
        v = (v or '').strip()
        if not v:
            raise ValueError('fen must be non-empty')
        return v


class AnalysisResponse(BaseModel):
    best_move: Optional[str]
    score: Optional[int]  # centipawns from White's perspective (mate mapped via mate_score)
    depth: int


@app.on_event("startup")
async def startup_event() -> None:
    if not os.path.exists(STOCKFISH_PATH):
        raise RuntimeError(f"Stockfish not found at: {STOCKFISH_PATH}")


@app.get("/health")
async def health():
    return {"status": "ok", "stockfish_path": STOCKFISH_PATH}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_position(request: AnalysisRequest) -> AnalysisResponse:
    # Validate FEN early so we can return a 400
    try:
        board = chess.Board(request.fen)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {ex}") from ex

    # Start engine per request (black-box / stateless)
    try:
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to start Stockfish: {ex}") from ex

    try:
        if request.uci_elo is not None:
            # Not all Stockfish builds support these options, so we guard it.
            try:
                await engine.configure({"UCI_LimitStrength": True, "UCI_Elo": int(request.uci_elo)})
            except Exception:
                # If unsupported, we simply ignore; depth control remains.
                pass

        limit = chess.engine.Limit(depth=int(request.depth))

        # `analyse` provides score + PV (principal variation); PV[0] is best move
        info = await engine.analyse(board, limit)
        score_obj = info.get("score")
        score = score_obj.white().score(mate_score=100000) if score_obj else None

        pv = info.get("pv") or []
        best_move = pv[0].uci() if pv else None

        # Fallback: if PV missing, ask engine to play a move
        if best_move is None:
            result = await engine.play(board, limit)
            best_move = result.move.uci() if result.move else None

        return AnalysisResponse(best_move=best_move, score=score, depth=int(request.depth))

    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex
    finally:
        try:
            await engine.quit()
        except Exception:
            pass
