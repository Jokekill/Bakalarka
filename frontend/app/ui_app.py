import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional, List

import chess
import httpx
from nicegui import ui, events

from .config import ENGINE_URL, REQUEST_TIMEOUT_S
from .engine_api import EngineClient, EngineResult
from .selfplay import SelfPlayController
from .utils import build_full_fen, uci_to_squares
from .chessground import DEFAULT_PLACEMENT, ROLE_MAP, piece_svg


@dataclass
class AppState:
    editor_placement: str = DEFAULT_PLACEMENT
    game_board: chess.Board = field(default_factory=chess.Board)
    score_history: List[int] = field(default_factory=list)


async def js(client, code: str) -> None:
    """Run JS in the correct browser client context (safe for background tasks)."""
    try:
        await client.run_javascript(code)
    except Exception as ex:
        # client may disconnect; do not crash background tasks
        print(f'[js] failed: {ex!r}')


def build_ui() -> None:
    state = AppState()
    engine = EngineClient(ENGINE_URL, REQUEST_TIMEOUT_S)
    self_play = SelfPlayController()

    # -------------------------
    # Editor helpers (MUST exist before buttons)
    # -------------------------
    async def reset_start() -> None:
        client = ui.context.client
        state.editor_placement = DEFAULT_PLACEMENT
        await js(client, f"window.cgSetFen({json.dumps(DEFAULT_PLACEMENT)});")

    async def reset_empty() -> None:
        client = ui.context.client
        empty = "8/8/8/8/8/8/8/8"
        state.editor_placement = empty
        await js(client, f"window.cgSetFen({json.dumps(empty)});")

    async def flip_board() -> None:
        client = ui.context.client
        await js(client, "window.cgToggleOrientation();")

    # -------------------------
    # Header
    # -------------------------
    with ui.header().classes('app-header'):
        ui.label('Roguelike Chess – Editor + Engine').classes('app-title')
        ui.space()
        ui.label(f'ENGINE: {ENGINE_URL}').classes('app-subtitle mono')

    # -------------------------
    # Main grid (2 columns)
    # -------------------------
    with ui.element('div').classes('app-shell'):
        with ui.element('div').classes('app-grid'):

            # =========================
            # LEFT PANEL (board + palettes only)
            # =========================
            with ui.element('div').classes('left-panel'):
                with ui.card().classes('panel-card'):
                    ui.label('Editor pozice').classes('card-title')

                    # BLACK palette ABOVE the board
                    ui.label('Černé (táhni na šachovnici)').classes('text-caption')
                    with ui.row().classes('spare-pieces justify-center'):
                        for p, role in ROLE_MAP.items():
                            ui.image(piece_svg('b', p)) \
                                .classes('spare-piece') \
                                .props('no-spinner') \
                                .on('mousedown', js_handler=f'(e) => window.startDragNewPiece("black", "{role}", e)')

                    # BOARD
                    ui.html('<div id="cg-board" class="cg-board"></div>', sanitize=False)


                    # WHITE palette BELOW the board
                    ui.label('Bílé (táhni na šachovnici)').classes('text-caption')
                    with ui.row().classes('spare-pieces justify-center'):
                        for p, role in ROLE_MAP.items():
                            ui.image(piece_svg('w', p)) \
                                .classes('spare-piece') \
                                .props('no-spinner') \
                                .on('mousedown', js_handler=f'(e) => window.startDragNewPiece("white", "{role}", e)')

                    # Editor buttons
                    with ui.row().classes('w-full gap-2 mt-3'):
                        ui.button('Základ', on_click=reset_start).classes('btn-ghost')
                        ui.button('Prázdná', on_click=reset_empty).classes('btn-ghost')
                        ui.button('Otočit', on_click=flip_board).classes('btn-ghost')

            # =========================
            # RIGHT PANEL (controls/output)
            # =========================
            with ui.element('div').classes('right-panel'):

                # Engine settings
                with ui.card().classes('panel-card'):
                    ui.label('Nastavení síly (depth)').classes('card-title')

                    white_depth = ui.slider(min=1, max=30, value=15).props('label-always').classes('w-full')
                    black_depth = ui.slider(min=1, max=30, value=15).props('label-always').classes('w-full')
                    analysis_depth = ui.slider(min=1, max=30, value=15).props('label-always').classes('w-full')

                    white_lbl = ui.label('Bílý: 15').classes('mono text-caption')
                    black_lbl = ui.label('Černý: 15').classes('mono text-caption')
                    ana_lbl = ui.label('Jednorázová analýza: 15').classes('mono text-caption')

                    def sync_labels() -> None:
                        white_lbl.set_text(f'Bílý: {int(white_depth.value)}')
                        black_lbl.set_text(f'Černý: {int(black_depth.value)}')
                        ana_lbl.set_text(f'Jednorázová analýza: {int(analysis_depth.value)}')

                    white_depth.on('update:model-value', lambda _: sync_labels())
                    black_depth.on('update:model-value', lambda _: sync_labels())
                    analysis_depth.on('update:model-value', lambda _: sync_labels())
                    sync_labels()

                # Actions + output
                with ui.card().classes('panel-card mt-3'):
                    ui.label('Akce').classes('card-title')

                    best_move_label = ui.label('Best move: –').classes('mono')
                    score_label = ui.label('Score: –').classes('mono')
                    status_right = ui.label('—').classes('mono text-caption')

                    chart = ui.echart({
                        'xAxis': {'type': 'category', 'data': []},
                        'yAxis': {'type': 'value'},
                        'series': [{'data': [], 'type': 'line'}],
                        'tooltip': {'trigger': 'axis'},
                    }).classes('w-full mt-2')

                    moves_log = ui.log(max_lines=300).classes('w-full h-56 mt-2')

                    async def analyze_and_update(client, depth: int, allow_notify: bool) -> Optional[EngineResult]:
                        try:
                            fen = state.game_board.fen()
                        except Exception as ex:
                            if allow_notify:
                                ui.notify(f'Neplatný stav hry: {ex}', type='negative')
                            moves_log.push(f'ERR: Neplatný stav hry: {ex}')
                            return None

                        try:
                            res = await engine.analyze(fen=fen, depth=depth)
                        except httpx.TimeoutException:
                            msg = 'Engine timeout – zkus snížit depth.'
                            if allow_notify:
                                ui.notify(msg, type='negative')
                            moves_log.push(f'ERR: {msg}')
                            return None
                        except httpx.HTTPStatusError as ex:
                            msg = f'Engine HTTP {ex.response.status_code}: {ex.response.text}'
                            if allow_notify:
                                ui.notify(msg, type='negative')
                            moves_log.push(f'ERR: {msg}')
                            return None
                        except Exception as ex:
                            msg = f'Chyba volání enginu: {ex}'
                            if allow_notify:
                                ui.notify(msg, type='negative')
                            moves_log.push(f'ERR: {msg}')
                            return None

                        best_move_label.set_text(f'Best move: {res.best_move}')
                        score_label.set_text(f'Score (cp, z pohledu bílého): {res.score}')
                        status_right.set_text(f'OK (depth={res.depth})')

                        if res.score is not None:
                            state.score_history.append(int(res.score))
                            chart.options['xAxis']['data'] = list(range(1, len(state.score_history) + 1))
                            chart.options['series'][0]['data'] = state.score_history
                            chart.update()

                        if res.best_move:
                            squares = uci_to_squares(res.best_move)
                            if squares:
                                orig, dest = squares
                                await js(client, f"window.cgSetLastMove({json.dumps(orig)}, {json.dumps(dest)});")

                        return res

                    async def analyze_only() -> None:
                        client = ui.context.client
                        await analyze_and_update(client, int(analysis_depth.value), allow_notify=True)

                    async def play_one_best_move() -> None:
                        if self_play.running:
                            ui.notify('Self-play běží. Nejdřív ho zastav.', type='warning')
                            return

                        client = ui.context.client
                        res = await analyze_and_update(client, int(analysis_depth.value), allow_notify=True)
                        if not res or not res.best_move:
                            return

                        try:
                            mv = chess.Move.from_uci(res.best_move)
                            if mv not in state.game_board.legal_moves:
                                ui.notify('Engine vrátil nelegální tah.', type='negative')
                                return
                            state.game_board.push(mv)
                        except Exception as ex:
                            ui.notify(f'Nelze provést tah: {ex}', type='negative')
                            return

                        await js(client, f"window.cgSetFen({json.dumps(state.game_board.board_fen())});")
                        moves_log.push(f'MOVE: {res.best_move}')

                    async def self_play_loop(stop_event: asyncio.Event, client) -> None:
                        await js(client, "window.cgSetViewOnly(true);")
                        moves_log.push('SELF-PLAY: start')

                        try:
                            while not stop_event.is_set():
                                if state.game_board.is_game_over(claim_draw=True):
                                    moves_log.push(f'SELF-PLAY: konec ({state.game_board.result(claim_draw=True)})')
                                    break

                                depth = int(white_depth.value) if state.game_board.turn == chess.WHITE else int(black_depth.value)
                                res = await analyze_and_update(client, depth, allow_notify=False)
                                if not res or not res.best_move:
                                    moves_log.push('SELF-PLAY: stop (engine bez tahu)')
                                    break

                                mv = chess.Move.from_uci(res.best_move)
                                if mv not in state.game_board.legal_moves:
                                    moves_log.push(f'SELF-PLAY: nelegální tah {res.best_move}')
                                    break

                                state.game_board.push(mv)
                                await js(client, f"window.cgSetFen({json.dumps(state.game_board.board_fen())});")
                                moves_log.push(f'SELF-PLAY: {res.best_move}')

                                await asyncio.sleep(0.6)
                        finally:
                            await js(client, "window.cgSetViewOnly(false);")
                            moves_log.push('SELF-PLAY: stop')

                    async def toggle_self_play() -> None:
                        client = ui.context.client

                        if self_play.running:
                            self_play.stop()
                            ui.notify('Zastavuji self-play…', type='warning')
                            return

                        async def runner(stop_event: asyncio.Event) -> None:
                            await self_play_loop(stop_event, client)

                        await self_play.start(runner)
                        ui.notify('Self-play spuštěn.', type='positive')

                    with ui.row().classes('w-full gap-2 mt-2'):
                        ui.button('Analyzovat', on_click=analyze_only).classes('btn-primary grow')
                        ui.button('Zahrát tah', on_click=play_one_best_move).classes('btn-ghost grow')
                        ui.button('Start/Stop self-play', on_click=toggle_self_play).classes('btn-danger grow')

                # FEN applicator - RIGHT COLUMN, BOTTOM, hidden by default
                with ui.card().classes('panel-card mt-3'):
                    with ui.expansion('FEN aplikátor (pokročilé)', value=False).classes('w-full'):
                        turn = ui.radio({'w': 'Bílý na tahu', 'b': 'Černý na tahu'}, value='w').props('inline')
                        castling = ui.input('Rokáda (KQkq / -)', value='-').classes('mono')
                        ep = ui.input('En-passant (e3 / -)', value='-').classes('mono')
                        halfmove = ui.number('Halfmove', value=0, min=0, max=200).classes('w-40')
                        fullmove = ui.number('Fullmove', value=1, min=1, max=999).classes('w-40')

                        fen_preview = ui.label().classes('mono text-caption mt-2')

                        def update_fen_preview() -> str:
                            full_fen = build_full_fen(
                                placement=state.editor_placement,
                                turn=turn.value,
                                castling=castling.value,
                                ep=ep.value,
                                halfmove=int(halfmove.value or 0),
                                fullmove=int(fullmove.value or 1),
                            )
                            fen_preview.set_text(full_fen)
                            return full_fen

                        for c in (turn, castling, ep, halfmove, fullmove):
                            c.on('update:model-value', lambda _: update_fen_preview())

                        def on_fen_update(e: events.GenericEventArguments) -> None:
                            placement = e.args
                            if isinstance(placement, str) and placement:
                                state.editor_placement = placement
                                update_fen_preview()

                        ui.on('fen_update', on_fen_update)
                        update_fen_preview()

                        status_left = ui.label('—').classes('mono text-caption mt-2')

                        def apply_editor_to_game() -> None:
                            full_fen = update_fen_preview()
                            try:
                                state.game_board = chess.Board(full_fen)
                                state.score_history.clear()
                                status_left.set_text('Pozice aplikována do hry.')
                                ui.notify('Pozice aplikována do hry.', type='positive')
                            except Exception as ex:
                                ui.notify(f'Neplatný FEN: {ex}', type='negative')

                        ui.button('Aplikovat editor → hra', on_click=apply_editor_to_game).classes('btn-primary w-full mt-2')
