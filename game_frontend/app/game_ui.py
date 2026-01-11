import asyncio
import json
from dataclasses import dataclass, field
from typing import List

import chess
import httpx
from nicegui import ui, events

from .config import (
    ENGINE_URL, REQUEST_TIMEOUT_S,
    INITIAL_MONEY, BASE_ENGINE_DEPTH, BASE_ENGINE_TIME,
    DEPTH_COST, TIME_COST, PIECE_COSTS,
    LEVELS, BLACK_BASE_DEPTH, BLACK_DEPTH_PER_LEVEL, MAX_BLACK_DEPTH,
)
from .engine_api import EngineClient, EngineResult
from .chessground import ROLE_MAP, piece_svg


# -------------------------
# State
# -------------------------
@dataclass
class GameState:
    current_level: int = 1
    money: int = INITIAL_MONEY

    # placement FEN (jen rozestavení, bez "w - - 0 1")
    editor_placement: str = "8/8/8/8/8/8/8/8"

    # hráčův engine (upgrady)
    white_depth: int = BASE_ENGINE_DEPTH
    white_time: int = BASE_ENGINE_TIME

    sim_running: bool = False
    ignore_fen_events: bool = False  # <- KLÍČ: ignorovat fen_update při simulaci / programatickém cgSetFen
    moves: List[str] = field(default_factory=list)


# -------------------------
# Helpers
# -------------------------
def _count_piece_cost_from_placement(placement_fen: str) -> int:
    cost = 0
    for ch in placement_fen:
        if ch.isalpha() and ch.isupper():
            cost += PIECE_COSTS.get(ch, 0)
    return cost


def _placement_has_white_piece_on_black_half(placement_fen: str) -> bool:
    ranks = placement_fen.split("/")
    if len(ranks) != 8:
        return False
    # ranks[0..3] jsou řady 8..5 (soupeřova půlka)
    for i in range(0, 4):
        for ch in ranks[i]:
            if ch.isupper():
                return True
    return False


def _placement_has_black_piece_anywhere(placement_fen: str) -> bool:
    for ch in placement_fen:
        if ch.isalpha() and ch.islower():
            return True
    return False


def _parse_and_place(board: chess.Board, placement_fen: str, allow_white: bool, allow_black: bool) -> None:
    """Naparsuje placement FEN a vloží figury na board (ignoruje nepovolené barvy)."""
    ranks = placement_fen.split("/")
    if len(ranks) != 8:
        raise ValueError("Neplatný placement FEN (musí mít 8 řad).")

    for rank_idx, rank_str in enumerate(ranks):
        file_idx = 0
        for ch in rank_str:
            if ch.isdigit():
                file_idx += int(ch)
                continue

            if not ch.isalpha():
                raise ValueError("Neplatný znak v placement FEN.")

            piece = chess.Piece.from_symbol(ch)

            if piece.color == chess.WHITE and not allow_white:
                file_idx += 1
                continue
            if piece.color == chess.BLACK and not allow_black:
                file_idx += 1
                continue

            square = chess.square(file_idx, 7 - rank_idx)  # rank 8..1 -> 7..0
            board.set_piece_at(square, piece)
            file_idx += 1


async def _js(client, code: str) -> None:
    """Spolehlivé volání JS v kontextu konkrétního klienta."""
    try:
        await client.run_javascript(code)
    except Exception as ex:
        print(f"[js] failed: {ex!r}")


# -------------------------
# UI
# -------------------------
def build_ui() -> None:
    state = GameState()
    engine = EngineClient(url=ENGINE_URL, timeout_s=REQUEST_TIMEOUT_S)

    # Widgets (naplníme po vytvoření)
    level_label = None
    money_label = None
    money_left_label = None
    depth_val_label = None
    time_val_label = None
    next_button = None
    reset_button = None
    depth_minus_button = None
    depth_plus_button = None
    time_minus_button = None
    time_plus_button = None
    moves_log = None

    # -------------------------
    # Budget
    # -------------------------
    def total_spent() -> int:
        pieces_cost = _count_piece_cost_from_placement(state.editor_placement)
        depth_upg = max(0, state.white_depth - BASE_ENGINE_DEPTH)
        time_upg = max(0, state.white_time - BASE_ENGINE_TIME)
        return pieces_cost + depth_upg * DEPTH_COST + time_upg * TIME_COST

    def money_left() -> int:
        return state.money - total_spent()

    def sync_labels() -> None:
        nonlocal level_label, money_label, money_left_label, depth_val_label, time_val_label
        if level_label:
            level_label.set_text(f"Úroveň: {state.current_level}")
        if money_label:
            money_label.set_text(f"Peníze: {state.money}")
        if money_left_label:
            money_left_label.set_text(f"Zbývá: {money_left()}")
        if depth_val_label:
            depth_val_label.set_text(f"Hloubka: {state.white_depth}")
        if time_val_label:
            time_val_label.set_text(f"Čas: {state.white_time} s")

    def set_controls_enabled(enabled: bool) -> None:
        disabled = "false" if enabled else "true"
        for btn in (next_button, reset_button, depth_minus_button, depth_plus_button, time_minus_button, time_plus_button):
            if btn:
                btn.props(f"disabled={disabled}")
                btn.update()

    def refresh_affordability() -> None:
        if not depth_plus_button or not time_plus_button:
            return

        if state.sim_running:
            depth_plus_button.props("disabled=true").update()
            time_plus_button.props("disabled=true").update()
            return

        if money_left() < DEPTH_COST or state.white_depth >= 30:
            depth_plus_button.props("disabled=true")
        else:
            depth_plus_button.props("disabled=false")
        depth_plus_button.update()

        if money_left() < TIME_COST:
            time_plus_button.props("disabled=true")
        else:
            time_plus_button.props("disabled=false")
        time_plus_button.update()

    # -------------------------
    # Board FEN (programatic) - KLÍČOVÉ
    # -------------------------
    async def set_board_fen(client, placement_fen: str) -> None:
        """Nastaví šachovnici programově a dočasně ignoruje fen_update validace."""
        state.ignore_fen_events = True
        await _js(client, f"window.cgSetFen({json.dumps(placement_fen)});")
        await asyncio.sleep(0.05)  # nech doběhnout případný fen_update event
        state.ignore_fen_events = False

    async def revert_board(client) -> None:
        state.ignore_fen_events = True
        await _js(client, f"window.cgSetFen({json.dumps(state.editor_placement)});")
        await asyncio.sleep(0.05)
        state.ignore_fen_events = False

    # -------------------------
    # fen_update handler (pouze při "build phase")
    # -------------------------
    async def on_board_change(e: events.GenericEventArguments) -> None:
        # během simulace / programatických změn ignoruj
        if state.sim_running or state.ignore_fen_events:
            return

        client = ui.context.client
        placement = e.args
        if not isinstance(placement, str) or not placement:
            return

        illegal = False

        # pravidla jen pro build phase:
        if _placement_has_black_piece_anywhere(placement):
            illegal = True
            ui.notify("Černé figury nelze umístit v této fázi.", type="warning")

        if _placement_has_white_piece_on_black_half(placement):
            illegal = True
            ui.notify("Nelze umístit bílé figury na soupeřovu polovinu!", type="warning")

        if placement.count("K") > 1:
            illegal = True
            ui.notify("Povoleno je pouze jeden bílý král!", type="warning")

        # budget check
        if not illegal:
            tmp_old = state.editor_placement
            state.editor_placement = placement
            if money_left() < 0:
                illegal = True
                ui.notify("Nemáš dost peněz na tolik figurek / upgradů.", type="warning")
            if illegal:
                state.editor_placement = tmp_old

        if illegal:
            await revert_board(client)
            return

        state.editor_placement = placement
        sync_labels()
        refresh_affordability()

    ui.on("fen_update", on_board_change)

    # -------------------------
    # Actions
    # -------------------------
    async def reset_board() -> None:
        if state.sim_running:
            return
        client = ui.context.client
        state.editor_placement = "8/8/8/8/8/8/8/8"
        sync_labels()
        refresh_affordability()
        await set_board_fen(client, state.editor_placement)

    def adjust_depth(delta: int) -> None:
        if state.sim_running:
            return
        if delta > 0:
            if state.white_depth < 30 and money_left() >= DEPTH_COST:
                state.white_depth += 1
        else:
            if state.white_depth > BASE_ENGINE_DEPTH:
                state.white_depth -= 1
        sync_labels()
        refresh_affordability()

    def adjust_time(delta: int) -> None:
        if state.sim_running:
            return
        if delta > 0:
            if money_left() >= TIME_COST:
                state.white_time += 1
        else:
            if state.white_time > BASE_ENGINE_TIME:
                state.white_time -= 1
        sync_labels()
        refresh_affordability()

    def do_restart() -> None:
        state.current_level = 1
        state.money = INITIAL_MONEY
        state.white_depth = BASE_ENGINE_DEPTH
        state.white_time = BASE_ENGINE_TIME
        state.editor_placement = "8/8/8/8/8/8/8/8"
        state.sim_running = False
        state.ignore_fen_events = False
        sync_labels()
        refresh_affordability()
        if moves_log:
            moves_log.clear()
            moves_log.push("== Restartováno na úroveň 1 ==")
        ui.notify("Hra restartována.", type="positive")

    def show_restart_dialog() -> None:
        with ui.dialog() as dialog:
            with ui.card():
                ui.label("Chcete restartovat hru od 1. úrovně?")
                with ui.row().classes("justify-center gap-2"):
                    ui.button("Restart", on_click=lambda: (dialog.close(), do_restart())).classes("btn-primary")
                    ui.button("Zrušit", on_click=dialog.close).classes("btn-ghost")
        dialog.open()

    def show_loss_dialog() -> None:
        with ui.dialog() as dialog:
            with ui.card():
                ui.label("Počítač vás porazil. Co dál?")
                with ui.row().classes("justify-center gap-2"):
                    ui.button("Restart (lvl 1)", on_click=lambda: (dialog.close(), do_restart())).classes("btn-primary")
                    ui.button("Pokračovat ve volném hraní", on_click=dialog.close).classes("btn-ghost")
        dialog.open()

    def _black_depth_for_level(level: int) -> int:
        return min(MAX_BLACK_DEPTH, BLACK_BASE_DEPTH + (level - 1) * BLACK_DEPTH_PER_LEVEL)

    async def start_next_opponent() -> None:
        if state.sim_running:
            return

        client = ui.context.client

        # validace setupu (build phase)
        if state.editor_placement.count("K") != 1:
            ui.notify("Musíte umístit přesně jednoho bílého krále!", type="negative")
            return
        if money_left() < 0:
            ui.notify("Nemáte dost peněz na aktuální setup.", type="negative")
            return

        level_index = state.current_level - 1
        if level_index < 0 or level_index >= len(LEVELS):
            ui.notify("Konfigurace pro tuto úroveň neexistuje.", type="negative")
            return

        black_fen = LEVELS[level_index]["black_fen"]
        reward = int(LEVELS[level_index].get("reward", 0))

        # složení startovní pozice = white placement + black placement
        try:
            board = chess.Board(fen=None)  # prázdná
            _parse_and_place(board, state.editor_placement, allow_white=True, allow_black=False)
            _parse_and_place(board, black_fen, allow_white=False, allow_black=True)
            board.turn = chess.WHITE
        except Exception as ex:
            ui.notify(f"Chyba při skládání pozice: {ex}", type="negative")
            return

        # lock UI + povolit černé figury a tahy napříč deskou = vypnout validace
        state.sim_running = True
        set_controls_enabled(False)
        await _js(client, "window.cgSetViewOnly(true);")
        await set_board_fen(client, board.board_fen())

        if moves_log:
            moves_log.push(f"--- Simulace úroveň {state.current_level} začíná ---")

        saved_placement = state.editor_placement

        MAX_PLIES = 300
        ply = 0

        try:
            while ply < MAX_PLIES:
                if board.is_game_over(claim_draw=True):
                    break

                if board.turn == chess.WHITE:
                    depth = state.white_depth
                    think_delay = min(1.5, 0.15 + state.white_time * 0.05)
                else:
                    depth = _black_depth_for_level(state.current_level)
                    think_delay = 0.15

                fen = board.fen()

                try:
                    res: EngineResult = await engine.analyze(fen=fen, depth=depth)
                except httpx.TimeoutException:
                    if moves_log:
                        moves_log.push("ERR: Engine timeout – zkus snížit depth.")
                    break
                except Exception as ex:
                    if moves_log:
                        moves_log.push(f"ERR: Engine error: {ex}")
                    break

                if not res.best_move:
                    if moves_log:
                        moves_log.push("ERR: Engine nevrátil tah.")
                    break

                mv = chess.Move.from_uci(res.best_move)
                if mv not in board.legal_moves:
                    if moves_log:
                        moves_log.push(f"ERR: Nelegální tah od enginu: {res.best_move}")
                    break

                board.push(mv)

                orig, dest = res.best_move[:2], res.best_move[2:4]
                await set_board_fen(client, board.board_fen())
                await _js(client, f"window.cgSetLastMove({json.dumps(orig)}, {json.dumps(dest)});")

                if moves_log:
                    just_moved = "Bílý" if board.turn == chess.BLACK else "Černý"
                    moves_log.push(f"{just_moved}: {res.best_move}")

                ply += 1
                await asyncio.sleep(think_delay)

        finally:
            outcome = board.outcome(claim_draw=True)
            player_won = bool(outcome and outcome.winner is True)

            # remíza = nepostupuje
            if outcome is None or outcome.winner is None:
                player_won = False

            if player_won:
                if moves_log:
                    moves_log.push(f"== Výhra! +{reward} peněz ==")
                state.money += reward
                state.current_level += 1
                ui.notify(f"Vyhráno. +{reward} peněz. Úroveň {state.current_level}.", type="positive")
            else:
                if moves_log:
                    result_str = board.result(claim_draw=True)
                    moves_log.push(f"== Prohra / remíza ({result_str}) ==")
                ui.notify("Počítač vás porazil (nebo remíza).", type="warning")
                show_loss_dialog()

            # unlock UI + návrat do build fáze
            state.sim_running = False
            set_controls_enabled(True)
            await _js(client, "window.cgSetViewOnly(false);")

            state.editor_placement = saved_placement
            await set_board_fen(client, saved_placement)

            sync_labels()
            refresh_affordability()

    # -------------------------
    # Layout podle PNG
    # -------------------------
    with ui.header().classes("app-header"):
        ui.label("Chess Rogue like").classes("app-title")
        ui.space()
        ui.button("Restart", on_click=show_restart_dialog).classes("btn-ghost")

    with ui.element("div").classes("app-shell"):
        with ui.element("div").classes("app-grid"):

            # LEFT
            with ui.element("div").classes("left-panel"):
                with ui.card().classes("panel-card"):
                    ui.label("Chess board").classes("card-title")
                    ui.html('<div id="cg-board" class="cg-board"></div>', sanitize=False)

                with ui.card().classes("panel-card mt-3"):
                    ui.label("White pieces for Drag and drop with Prices").classes("text-caption")
                    with ui.row().classes("spare-pieces justify-center"):
                        for p, role in ROLE_MAP.items():
                            ui.image(piece_svg("w", p)) \
                                .classes("spare-piece") \
                                .props("no-spinner") \
                                .on("mousedown", js_handler=f'(e) => window.startDragNewPiece("white", "{role}", e)')

                    reset_button = ui.button("Vymazat desku", on_click=reset_board).classes("btn-ghost w-full mt-2")

            # RIGHT
            with ui.element("div").classes("right-panel"):
                with ui.card().classes("panel-card"):
                    level_label = ui.label(f"Úroveň: {state.current_level}").classes("card-title")
                    money_label = ui.label(f"Peníze: {state.money}").classes("mono")
                    money_left_label = ui.label(f"Zbývá: {money_left()}").classes("mono text-caption")

                with ui.card().classes("panel-card mt-3"):
                    ui.label("Engine upgrade").classes("card-title")

                    with ui.row().classes("items-center justify-between"):
                        depth_val_label = ui.label(f"Hloubka: {state.white_depth}").classes("mono")
                        depth_minus_button = ui.button("-", on_click=lambda: adjust_depth(-1)).classes("btn-ghost")
                        depth_plus_button = ui.button("+", on_click=lambda: adjust_depth(1)).classes("btn-ghost")

                    with ui.row().classes("items-center justify-between mt-2"):
                        time_val_label = ui.label(f"Čas: {state.white_time} s").classes("mono")
                        time_minus_button = ui.button("-", on_click=lambda: adjust_time(-1)).classes("btn-ghost")
                        time_plus_button = ui.button("+", on_click=lambda: adjust_time(1)).classes("btn-ghost")

                with ui.card().classes("panel-card mt-3"):
                    ui.label("FIGHT NEXT OPPONENT").classes("card-title")
                    next_button = ui.button("Další soupeř", on_click=start_next_opponent).classes("btn-primary w-full")
                    moves_log = ui.log(max_lines=200).classes("w-full h-56 mt-2")
                    moves_log.push(f"== Připravte se na úroveň {state.current_level} ==")

    # initial sync
    sync_labels()
    refresh_affordability()
