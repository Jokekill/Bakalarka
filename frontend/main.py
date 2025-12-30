import asyncio
import json
import os
from dataclasses import dataclass
from typing import Optional, List, Tuple

import chess
import httpx
from nicegui import ui
from nicegui import events

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
ENGINE_URL = os.getenv('ENGINE_URL', 'http://localhost:8000/analyze')
REQUEST_TIMEOUT_S = float(os.getenv('ENGINE_TIMEOUT', '12'))

# Chessground uses "piece placement FEN" (board FEN), not full FEN.
DEFAULT_PLACEMENT = chess.STARTING_BOARD_FEN  # 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'


def build_full_fen(
    placement: str,
    turn: str,
    castling: str,
    ep: str,
    halfmove: int,
    fullmove: int,
) -> str:
    """Build a full FEN string from Chessground placement FEN and extra fields."""
    turn = (turn or 'w').lower().strip()
    if turn not in ('w', 'b'):
        turn = 'w'
    castling = (castling or '-').strip() or '-'
    ep = (ep or '-').strip() or '-'
    return f'{placement} {turn} {castling} {ep} {halfmove} {fullmove}'


def uci_to_squares(move_uci: str) -> Optional[Tuple[str, str]]:
    if not move_uci or len(move_uci) < 4:
        return None
    return move_uci[:2], move_uci[2:4]


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


class SelfPlayController:
    """Manages a single running self-play task."""
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def stop(self) -> None:
        self._stop.set()

    def _attach_exception_logger(self) -> None:
        """Log exceptions from the background task so they don't show as 'never retrieved'."""
        if not self._task:
            return

        def _cb(t: asyncio.Task) -> None:
            try:
                exc = t.exception()
                if exc:
                    print(f'[self-play] task failed: {exc!r}')
            except asyncio.CancelledError:
                pass

        self._task.add_done_callback(_cb)

    async def start(self, coro) -> None:
        if self.running:
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(coro(self._stop))
        self._attach_exception_logger()


# -----------------------------------------------------------------------------
# UI: load Chessground assets (ESM) and required CSS
# -----------------------------------------------------------------------------
CHESSGROUND_VERSION = os.getenv('CHESSGROUND_VERSION', '8.2.0')

ui.add_head_html(
    f'<link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.base.css">'
)
ui.add_head_html(
    f'<link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.brown.css">'
)
ui.add_head_html(
    f'<link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.cburnett.css">'
)

# Import Chessground as an ES module and expose it globally.
ui.add_head_html(
    f"""
<script type="module">
import {{ Chessground }} from 'https://unpkg.com/chessground@{CHESSGROUND_VERSION}/chessground.js';
window.Chessground = Chessground;
</script>
"""
)

# Styles
ui.add_head_html(
    """
<style>
  .cg-wrapper { width: 520px; max-width: 95vw; }
  .spare-pieces { display: flex; flex-wrap: wrap; gap: 6px; }
  .spare-pieces img { width: 42px; height: 42px; cursor: grab; user-select: none; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
</style>
"""
)

# -----------------------------------------------------------------------------
# Shared state
# -----------------------------------------------------------------------------
engine = EngineClient(ENGINE_URL, REQUEST_TIMEOUT_S)
self_play = SelfPlayController()

editor_placement = DEFAULT_PLACEMENT
game_board = chess.Board()  # python-chess board
score_history: List[int] = []

# -----------------------------------------------------------------------------
# JavaScript glue for Chessground + spare pieces + fen_update events
# -----------------------------------------------------------------------------
JS_GLUE = r"""
(function () {
  window.cgInit = function(initialFen) {
    const el = document.getElementById('cg-board');
    if (!el) { console.error('cg-board element not found'); return; }
    if (!window.Chessground) { console.error('Chessground not loaded'); return; }

    const config = {
      fen: initialFen,
      orientation: 'white',
      viewOnly: false,
      movable: {
        free: true,
        color: 'both',
        showDests: false,
      },
      draggable: {
        enabled: true,
        showGhost: true,
        deleteOnDropOff: true,
      },
      premovable: { enabled: false },
      predroppable: { enabled: false },
      events: {
        change: function () {
          try {
            const fen = window.chessgroundInstance.getFen();
            emitEvent('fen_update', fen);
          } catch (e) {
            console.warn('fen_update failed', e);
          }
        }
      }
    };

    window.chessgroundInstance = window.Chessground(el, config);

    // initial push
    try { emitEvent('fen_update', window.chessgroundInstance.getFen()); } catch(e) {}
  };

  window.cgSetFen = function(fen) {
    if (!window.chessgroundInstance) return;
    window.chessgroundInstance.set({ fen: fen });
    try { emitEvent('fen_update', window.chessgroundInstance.getFen()); } catch(e) {}
  };

  window.cgSetViewOnly = function(flag) {
    if (!window.chessgroundInstance) return;
    window.chessgroundInstance.set({ viewOnly: !!flag });
  };

  window.cgToggleOrientation = function() {
    if (!window.chessgroundInstance) return;
    window.chessgroundInstance.toggleOrientation();
  };

  window.cgSetLastMove = function(orig, dest) {
    if (!window.chessgroundInstance) return;
    window.chessgroundInstance.set({ lastMove: [orig, dest] });
  };

  window.startDragNewPiece = function(color, role, event) {
    event.preventDefault();
    if (!window.chessgroundInstance) return;
    window.chessgroundInstance.dragNewPiece({ color: color, role: role }, event, true);
  };
})();
"""

ui.add_head_html(
    f"""
<script>
{JS_GLUE}
</script>
<script>
window.addEventListener('DOMContentLoaded', () => {{
  const initialFen = {json.dumps(DEFAULT_PLACEMENT)};
  const tryInit = () => {{
    if (!window.Chessground) return setTimeout(tryInit, 50);
    if (typeof emitEvent !== 'function') return setTimeout(tryInit, 50);
    if (!document.getElementById('cg-board')) return setTimeout(tryInit, 50);
    try {{
      window.cgInit(initialFen);
    }} catch (e) {{
      console.error('cgInit failed', e);
      setTimeout(tryInit, 200);
    }}
  }};
  tryInit();
}});
</script>
"""
)

# -----------------------------------------------------------------------------
# UI Construction
# -----------------------------------------------------------------------------
ui.page_title('Roguelike Chess – Editor + Engine Service')

with ui.row().classes('w-full items-start gap-6'):
    # Left: board + palette + editor controls
    with ui.column().classes('cg-wrapper gap-3'):
        ui.label('Editor pozice (Chessground)').classes('text-h6')

        ui.html('<div id="cg-board" style="width: 520px; height: 520px;"></div>', sanitize=False)

        ui.label('Paleta figur (drag-and-drop na šachovnici)').classes('text-subtitle2')
        role_map = {
            'P': 'pawn', 'N': 'knight', 'B': 'bishop', 'R': 'rook', 'Q': 'queen', 'K': 'king',
        }

        def piece_svg(color: str, p: str) -> str:
            return f'https://lichess1.org/assets/piece/cburnett/{color}{p.lower()}.svg'

        with ui.row().classes('w-full'):
            with ui.column().classes('gap-2'):
                ui.label('Bílé')
                with ui.row().classes('spare-pieces'):
                    for p, role in role_map.items():
                        ui.image(piece_svg('w', p)).on(
                            'mousedown',
                            js_handler=f'(e) => window.startDragNewPiece("white", "{role}", e)',
                        )
            with ui.column().classes('gap-2'):
                ui.label('Černé')
                with ui.row().classes('spare-pieces'):
                    for p, role in role_map.items():
                        ui.image(piece_svg('b', p)).on(
                            'mousedown',
                            js_handler=f'(e) => window.startDragNewPiece("black", "{role}", e)',
                        )

        with ui.row().classes('w-full items-center gap-2'):
            ui.button('Základní pozice', on_click=lambda: ui.run_javascript(
                f"window.cgSetFen({json.dumps(DEFAULT_PLACEMENT)});"
            ))
            ui.button('Prázdná šachovnice', on_click=lambda: ui.run_javascript(
                "window.cgSetFen('8/8/8/8/8/8/8/8');"
            ))
            ui.button('Otočit desku', on_click=lambda: ui.run_javascript("window.cgToggleOrientation();"))

        ui.separator()

        ui.label('Parametry FEN (doplní se k editoru pro analýzu)').classes('text-subtitle2')

        turn = ui.radio({'w': 'Bílý na tahu', 'b': 'Černý na tahu'}, value='w').props('inline')
        castling = ui.input('Rokáda (např. KQkq nebo -)', value='-').classes('mono')
        ep = ui.input('En-passant (např. e3 nebo -)', value='-').classes('mono')
        halfmove = ui.number('Halfmove', value=0, min=0, max=200).classes('w-40')
        fullmove = ui.number('Fullmove', value=1, min=1, max=999).classes('w-40')

        fen_preview = ui.label().classes('mono text-caption')

        def update_fen_preview() -> None:
            full_fen = build_full_fen(
                placement=editor_placement,
                turn=turn.value,
                castling=castling.value,
                ep=ep.value,
                halfmove=int(halfmove.value or 0),
                fullmove=int(fullmove.value or 1),
            )
            fen_preview.set_text(full_fen)

        turn.on('update:model-value', lambda _: update_fen_preview())
        castling.on('update:model-value', lambda _: update_fen_preview())
        ep.on('update:model-value', lambda _: update_fen_preview())
        halfmove.on('update:model-value', lambda _: update_fen_preview())
        fullmove.on('update:model-value', lambda _: update_fen_preview())

        def on_fen_update(e: events.GenericEventArguments) -> None:
            global editor_placement
            placement = e.args
            if isinstance(placement, str) and placement:
                editor_placement = placement
                update_fen_preview()

        ui.on('fen_update', on_fen_update)

        ui.separator()

        status_label = ui.label(f'ENGINE_URL: {ENGINE_URL}').classes('text-caption mono')

        def apply_editor_to_game() -> None:
            global game_board, score_history
            full_fen = build_full_fen(
                placement=editor_placement,
                turn=turn.value,
                castling=castling.value,
                ep=ep.value,
                halfmove=int(halfmove.value or 0),
                fullmove=int(fullmove.value or 1),
            )
            try:
                game_board = chess.Board(full_fen)
            except Exception as ex:
                ui.notify(f'Neplatný FEN pro python-chess: {ex}', type='negative')
                return

            score_history = []
            status_label.set_text('Pozice aplikována do hry. Připraveno na analýzu / self-play.')
            ui.notify('Pozice aplikována do hry.', type='positive')

        ui.button('Aplikovat editor → hra', on_click=apply_editor_to_game).classes('w-full')

    # Right: analysis and self-play controls / output
    with ui.column().classes('grow gap-3'):
        ui.label('Analýza & Self-play').classes('text-h6')

        with ui.card().classes('w-full'):
            ui.label('Nastavení enginu').classes('text-subtitle2')

            white_depth = ui.slider(min=1, max=30, value=15).props('label-always').classes('w-full')
            white_depth_label = ui.label('Hloubka – bílý: 15')

            black_depth = ui.slider(min=1, max=30, value=15).props('label-always').classes('w-full')
            black_depth_label = ui.label('Hloubka – černý: 15')

            analysis_depth = ui.slider(min=1, max=30, value=15).props('label-always').classes('w-full')
            analysis_depth_label = ui.label('Hloubka – jednorázová analýza: 15')

            def sync_labels() -> None:
                white_depth_label.set_text(f'Hloubka – bílý: {int(white_depth.value)}')
                black_depth_label.set_text(f'Hloubka – černý: {int(black_depth.value)}')
                analysis_depth_label.set_text(f'Hloubka – jednorázová analýza: {int(analysis_depth.value)}')

            white_depth.on('update:model-value', lambda _: sync_labels())
            black_depth.on('update:model-value', lambda _: sync_labels())
            analysis_depth.on('update:model-value', lambda _: sync_labels())
            sync_labels()

        best_move_label = ui.label('Best move: –').classes('mono')
        score_label = ui.label('Score: –').classes('mono')

        chart = ui.echart({
            'xAxis': {'type': 'category', 'data': []},
            'yAxis': {'type': 'value'},
            'series': [{'data': [], 'type': 'line'}],
            'tooltip': {'trigger': 'axis'},
        }).classes('w-full')

        moves_log = ui.log(max_lines=200).classes('w-full h-64')

        async def js(client, code: str) -> None:
            """Run JS in the correct browser client context (safe for background tasks)."""
            try:
                await client.run_javascript(code)
            except Exception as ex:
                # Don't crash background tasks because of transient client disconnects
                print(f'[js] failed: {ex!r}')

        async def call_engine_and_update(client, depth: int) -> Optional[EngineResult]:
            try:
                fen = game_board.fen()
            except Exception as ex:
                ui.notify(f'Neplatný stav hry: {ex}', type='negative')
                return None

            try:
                res = await engine.analyze(fen=fen, depth=depth)
            except httpx.TimeoutException:
                ui.notify('Engine neodpovídá (timeout). Zkuste snížit hloubku.', type='negative')
                return None
            except httpx.HTTPStatusError as ex:
                detail = ex.response.text
                ui.notify(f'Chyba enginu: HTTP {ex.response.status_code} – {detail}', type='negative')
                return None
            except Exception as ex:
                ui.notify(f'Chyba při volání enginu: {ex}', type='negative')
                return None

            best_move_label.set_text(f'Best move: {res.best_move}')
            score_label.set_text(f'Score (cp, z pohledu bílého): {res.score}')
            status_label.set_text(f'Analýza OK (depth={res.depth})')

            if res.score is not None:
                score_history.append(int(res.score))
                chart.options['xAxis']['data'] = list(range(1, len(score_history) + 1))
                chart.options['series'][0]['data'] = score_history
                chart.update()

            if res.best_move:
                squares = uci_to_squares(res.best_move)
                if squares:
                    orig, dest = squares
                    await js(client, f"window.cgSetLastMove({json.dumps(orig)}, {json.dumps(dest)});")

            return res

        async def play_one_best_move() -> None:
            if self_play.running:
                ui.notify('Self-play běží. Nejdřív ho zastav.', type='warning')
                return

            client = ui.context.client
            depth = int(analysis_depth.value)
            res = await call_engine_and_update(client, depth)
            if not res or not res.best_move:
                return

            try:
                mv = chess.Move.from_uci(res.best_move)
                if mv not in game_board.legal_moves:
                    ui.notify('Engine vrátil nelegální tah pro danou pozici.', type='negative')
                    return
                game_board.push(mv)
            except Exception as ex:
                ui.notify(f'Nelze provést tah: {ex}', type='negative')
                return

            await js(client, f"window.cgSetFen({json.dumps(game_board.board_fen())});")
            moves_log.push(f'MOVE: {res.best_move} | FEN: {game_board.fen()}')

        async def analyze_only() -> None:
            client = ui.context.client
            depth = int(analysis_depth.value)
            await call_engine_and_update(client, depth)

        async def self_play_loop(stop_event: asyncio.Event, client) -> None:
            await js(client, "window.cgSetViewOnly(true);")
            moves_log.push('SELF-PLAY: start')

            try:
                while not stop_event.is_set():
                    if game_board.is_game_over(claim_draw=True):
                        moves_log.push(f'SELF-PLAY: konec ({game_board.result(claim_draw=True)})')
                        break

                    depth = int(white_depth.value) if game_board.turn == chess.WHITE else int(black_depth.value)
                    res = await call_engine_and_update(client, depth)
                    if not res or not res.best_move:
                        moves_log.push('SELF-PLAY: engine nevrátil tah, stop')
                        break

                    mv = chess.Move.from_uci(res.best_move)
                    if mv not in game_board.legal_moves:
                        moves_log.push(f'SELF-PLAY: nelegální tah {res.best_move}, stop')
                        break

                    game_board.push(mv)
                    await js(client, f"window.cgSetFen({json.dumps(game_board.board_fen())});")
                    moves_log.push(f'SELF-PLAY: {res.best_move}')

                    await asyncio.sleep(0.7)
            finally:
                await js(client, "window.cgSetViewOnly(false);")
                moves_log.push('SELF-PLAY: stop')

        async def toggle_self_play() -> None:
            client = ui.context.client

            if self_play.running:
                self_play.stop()
                ui.notify('Zastavuji self-play…', type='warning')
                return

            async def _runner(stop_event: asyncio.Event) -> None:
                await self_play_loop(stop_event, client)

            await self_play.start(_runner)
            ui.notify('Self-play spuštěn.', type='positive')

        with ui.row().classes('w-full gap-2'):
            ui.button('Analyzovat', on_click=analyze_only).classes('grow')
            ui.button('Zahrát nejlepší tah', on_click=play_one_best_move).classes('grow')
            ui.button('Start/Stop self-play', on_click=toggle_self_play).classes('grow')

ui.run(host='0.0.0.0', port=int(os.getenv('PORT', '8080')))
