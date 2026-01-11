"""
api_client.py
Zajišťuje HTTP komunikaci s mikroslužbou šachového enginu.
"""
import httpx
from dataclasses import dataclass
from typing import Optional
import os

# Získání URL backendu z proměnných prostředí, fallback na localhost pro lokální vývoj
ENGINE_URL = os.getenv('ENGINE_URL', 'http://backend:8000/analyze')

@dataclass
class EngineResult:
    """Datová třída pro typovanou odpověď z enginu."""
    best_move: Optional[str]
    score: Optional[int]
    depth: int

class EngineClient:
    def __init__(self, url: str = ENGINE_URL, timeout_s: float = 30.0):
        self.url = url
        self.timeout_s = timeout_s

    async def analyze(self, fen: str, depth: int) -> EngineResult:
        """
        Odesílá pozici (FEN) na backend a získává nejlepší tah.
        Poznámka: Backend podporuje pouze parametr 'depth'.
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {"fen": fen, "depth": depth}
                response = await client.post(
                    self.url, 
                    json=payload, 
                    timeout=self.timeout_s
                )
                response.raise_for_status()
                data = response.json()
                
                return EngineResult(
                    best_move=data.get("best_move"),
                    score=data.get("score"),
                    depth=data.get("depth", depth)
                )
        except Exception as e:
            print(f"Chyba Enginu: {e}")
            # V případě chyby vracíme bezpečný default, aby aplikace nespadla
            return EngineResult(best_move=None, score=0, depth=0)