from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class EngineResult:
    best_move: Optional[str]
    score: Optional[int]
    depth: int


class EngineClient:
    def __init__(self, url: str, timeout_s: float) -> None:
        self.url = url
        self.timeout_s = timeout_s

    async def analyze(self, fen: str, depth: int) -> EngineResult:
        payload = {'fen': fen, 'depth': depth}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.post(self.url, json=payload)
            r.raise_for_status()
            data = r.json()
        return EngineResult(
            best_move=data.get('best_move'),
            score=data.get('score'),
            depth=int(data.get('depth', depth)),
        )
