"""
main.py
Vstupní bod pro Player Frontend.
Orchestruje životní cyklus aplikace, routování a simulační smyčky.
"""
from nicegui import ui, app
import asyncio
import chess
from pathlib import Path

# Lokální importy
from game_logic import state
from levels_config import UPGRADE_COST_DEPTH, UPGRADE_COST_TIME, LEVELS
from ui_components import build_shop_palette, build_stats_panel, build_logs_panel, build_level_info
from api_client import EngineClient

# --- Konfigurace Statických Souborů ---
BASE_DIR = Path(__file__).resolve().parent

# Načtení externích CSS/JS pro Chessground (pomocí unpkg CDN)
ui.add_head_html(f'<link rel="stylesheet" href="https://unpkg.com/chessground@8.2.0/assets/chessground.base.css">')
ui.add_head_html(f'<link rel="stylesheet" href="https://unpkg.com/chessground@8.2.0/assets/chessground.brown.css">')
ui.add_head_html(f'<link rel="stylesheet" href="https://unpkg.com/chessground@8.2.0/assets/chessground.cburnett.css">')
ui.add_head_html(f'<script src="https://unpkg.com/chessground@8.2.0/dist/chessground.js"></script>')

# Servírování lokálních assets (figury, skript) na cestě /static
app.add_static_files('/static', BASE_DIR / 'assets')

# Injektáž našeho vlastního JS lepidla
with open(BASE_DIR / 'assets' / 'script.js') as f:
    ui.add_head_html(f'<script>{f.read()}</script>')

# Inicializace klienta API
engine_client = EngineClient()

# --- Handlery Událostí ---

async def handle_fen_update(e):
    """Voláno JS, když hráč v editoru pohne figurou."""
    if state.in_simulation: return # Ignorovat během simulace
    state.editor_fen = e.args

def upgrade_depth():
    """Handler pro nákup hloubky."""
    if state.money >= UPGRADE_COST_DEPTH:
        state.money -= UPGRADE_COST_DEPTH
        state.player_depth += 1
        state.log(f"UPGRADE: Hloubka zvýšena na {state.player_depth}")

def upgrade_time():
    """Handler pro nákup času (zpomalení simulace)."""
    if state.money >= UPGRADE_COST_TIME:
        state.money -= UPGRADE_COST_TIME
        state.player_time += 0.5
        state.log(f"UPGRADE: Čas na přemýšlení zvýšen (+0.5s)")

def reset_game():
    """Restartuje hru na úroveň 1."""
    state.reset_to_level_1()
    ui.run_javascript(f"cgSetFen('{state.editor_fen}')")
    ui.run_javascript("cgSetViewOnly(false)")
    state.in_simulation = False
    ui.notify("Hra byla restartována.", type='info')

async def start_simulation():
    """Hlavní smyčka hry (The Game Loop)."""
    
    # 1. Validace setupu
    is_valid, msg = state.validate_setup(state.editor_fen)
    if not is_valid:
        ui.notify(msg, type='negative', position='center')
        return

    # 2. Uzamčení UI
    state.in_simulation = True
    ui.run_javascript("cgSetViewOnly(true)") # JS zamkne desku
    state.log("--- SIMULACE ZAHÁJENA ---")
    
    # 3. Sloučení desek (Hráč + Level)
    level_cfg = state.get_current_level_config()
    game_fen = state.merge_fens_for_simulation(state.editor_fen, level_cfg['fen'])
    board = chess.Board(game_fen)
    
    # Zobrazení sloučené desky
    ui.run_javascript(f"cgSetFen('{board.fen()}')")
    
    # 4. Smyčka tahů
    while not board.is_game_over():
        # Určení kdo je na tahu
        is_white = board.turn == chess.WHITE
        # Bílý = Hráč (jeho depth), Černý = Level (enemy_depth)
        current_depth = state.player_depth if is_white else level_cfg['enemy_depth']
        player_name = "VÁŠ ENGINE" if is_white else f"SOUPEŘ (Lvl {level_cfg['enemy_depth']})"
        
        # Umělé zpoždění pro simulaci "přemýšlení" a napětí (Player Time upgrade)
        # Pokud hraje hráč, použije se jeho 'player_time', pokud soupeř, fixní čas.
        wait_time = state.player_time if is_white else 1.0
        await asyncio.sleep(wait_time) 
        
        # Dotaz na Backend
        result = await engine_client.analyze(board.fen(), current_depth)
        
        if not result.best_move:
            state.log(f"{player_name} nemůže najít tah (Pravděpodobně Mat/Pat).")
            break
            
        # Aplikace tahu
        move = chess.Move.from_uci(result.best_move)
        board.push(move)
        
        # Aktualizace UI
        ui.run_javascript(f"cgSetFen('{board.fen()}')")
        # Zvýraznění tahu (from -> to)
        ui.run_javascript(f"cgSetLastMove('{move.from_square}', '{move.to_square}')") 
        state.log(f"{player_name}: {result.best_move} (Eval: {result.score})")

    # 5. Vyhodnocení výsledku
    outcome = board.outcome()
    
    # Logika pro "Free Play": Pokud vyhraju poslední level, co se stane?
    # Zde: Zůstávám na posledním levelu nebo se level nezvyšuje.
    
    if outcome and outcome.winner == chess.WHITE:
        # VÍTĚZSTVÍ HRÁČE
        reward = level_cfg['reward']
        state.money += reward
        state.log(f"VÍTĚZSTVÍ! Získáno ${reward}.")
        ui.notify(f"BITVA VYHRÁNA! +${reward}", type='positive', position='center', close_button="OK")
        
        # Posun na další level, pokud existuje
        if state.current_level_idx < len(LEVELS) - 1:
            state.current_level_idx += 1
            state.log(f"Postupuješ na úroveň {state.current_level_idx + 1}")
        else:
            state.log("GRATULACE! Porazil jsi finálního bosse!")
            ui.notify("HRA DOHRÁNA! Můžeš pokračovat ve volném hraní.", type='positive', timeout=0, close_button="Super")

    else:
        # PROHRA nebo REMÍZA
        state.log("PORÁŽKA (nebo Pat). Úroveň zůstává.")
        ui.notify("Porážka. Zkus upravit armádu a zkus to znovu.", type='negative', position='center', close_button="Zkusit znovu")
        # Level se nezvyšuje, peníze se nepřičítají.

    # 6. Odemčení UI pro další kolo
    state.in_simulation = False
    
    # Návrat do editoru: Resetujeme desku na stav, jak si ho hráč postavil (editor_fen)
    # Tím umožníme "postavit figury znovu" (resp. upravit ty stávající)
    ui.run_javascript(f"cgSetFen('{state.editor_fen}')")
    ui.run_javascript("cgSetViewOnly(false)")
    state.log("--- EDITAČNÍ MÓD ---")


# --- Hlavní Layout Stránky ---

@ui.page('/')
def index():
    # Registrace listeneru pro update FENu z JS
    ui.on('fen_update', handle_fen_update)

    with ui.column().classes('w-full min-h-screen bg-slate-900 text-white p-4 font-sans'):
        
        # Hlavička
        with ui.row().classes('w-full justify-between items-center mb-6 border-b border-slate-700 pb-4'):
            with ui.row().classes('items-center gap-4'):
                ui.icon('psychology').classes('text-4xl text-indigo-500')
                ui.label("ROGUELIKE CHESS").classes('text-3xl font-black tracking-widest text-indigo-400')
            
            ui.button("Restartovat Kampaň", on_click=reset_game, color='red') \
               .props('outline icon=restart_alt') \
               .classes('hover:bg-red-900')

        # Hlavní Grid Obsahu
        with ui.grid(columns=12).classes('w-full gap-6 max-w-7xl mx-auto'):
            
            # LEVÝ SLOUPEC: Deska & Obchod (span 8)
            with ui.column().classes('col-span-12 lg:col-span-8'):
                
                # Info o soupeři
                build_level_info()
                
                # Kontejner desky
                # ID 'cg-board' je klíčové pro naše JS
                with ui.card().classes('w-full aspect-square bg-slate-800 p-1 shadow-2xl border border-slate-600'):
                    ui.element('div').props('id=cg-board').classes('w-full h-full rounded')

                # Obchod
                ui.label("ARMÁDNÍ SKLAD").classes('mt-6 text-gray-400 font-bold tracking-widest text-sm')
                build_shop_palette()

            # PRAVÝ SLOUPEC: Statistiky & Ovládání (span 4)
            with ui.column().classes('col-span-12 lg:col-span-4 gap-6'):
                
                # Statistiky
                build_stats_panel(upgrade_depth, upgrade_time)
                
                # Hlavní Akční Tlačítko
                # Zobrazuje se jen pokud nejsme v simulaci (nebo je disabled)
                with ui.row().classes('w-full'):
                    btn = ui.button("ZAHÁJIT BITVU", on_click=start_simulation) \
                       .classes('w-full py-6 text-xl font-black shadow-[0_0_20px_rgba(0,255,0,0.3)] hover:shadow-[0_0_30px_rgba(0,255,0,0.5)] transition duration-300') \
                       .props('color=green icon=swords')
                    
                    # Bindujeme enabled stav
                    btn.bind_enabled_from(state, 'in_simulation', backward=lambda x: not x)

                # Logy
                with ui.column().classes('w-full gap-1'):
                    ui.label("Záznam Operací").classes('text-gray-400 font-bold text-xs uppercase')
                    build_logs_panel()

                # Nápověda
                with ui.expansion("Taktická Příručka", icon='help').classes('w-full bg-slate-800 text-sm border border-slate-700 rounded'):
                    ui.markdown("""
                    **Ceník Jednotek:**
                    - ♟️ Pěšec: $1
                    - ♞ Jezdec / ♝ Střelec: $3
                    - ♜ Věž: $5
                    - ♛ Dáma: $9
                    - ♚ Král: Zdarma (Musíš mít 1)
                    
                    **Pravidla Mise:**
                    1. Rozmísti armádu na prvních 4 řadách.
                    2. Investuj do **Hloubky** (inteligence) a **Času** (rozvaha).
                    3. Poraz soupeře, získej zlato, postup na další úroveň.
                    """)

    # Inicializace desky při načtení stránky (JS volání)
    ui.run_javascript(f"window.cgInit('{state.editor_fen}')")

# Spuštění serveru
ui.run(title="Roguelike Chess", dark=True, port=8080)