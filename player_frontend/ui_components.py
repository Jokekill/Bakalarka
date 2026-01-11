"""
ui_components.py
Obsahuje konstrukční funkce pro UI komponenty (NiceGUI).
"""
from nicegui import ui
from game_logic import state, PIECE_COSTS
from levels_config import UPGRADE_COST_DEPTH, UPGRADE_COST_TIME

# Mapování pro assets (role -> název souboru)
ROLE_MAP = {
    'p': 'pawn',
    'n': 'knight',
    'b': 'bishop',
    'r': 'rook',
    'q': 'queen',
    # Král není v obchodě k nákupu, ale potřebujeme mapování pro případné vykreslení
}

def piece_svg(color: str, role: str) -> str:
    """Vrátí cestu k SVG souboru figury."""
    # Předpokládáme, že assets jsou servírovány na /static/
    # Formát souborů: wP.svg, bK.svg atd. (standard Cburnett set)
    c_prefix = 'w' if color == 'white' else 'b'
    role_map_rev = {'pawn': 'P', 'knight': 'N', 'bishop': 'B', 'rook': 'R', 'queen': 'Q', 'king': 'K'}
    # Získání jednopísmenného kódu
    code = role_map_rev.get(role, 'P') 
    filename = f"{c_prefix}{code}.svg"
    return f"/static/pieces/{filename}"

def build_shop_palette():
    """Vykreslí řadu nakupovatelných figur."""
    # Kontejner obchodu
    with ui.row().classes('w-full justify-center gap-4 p-4 bg-slate-800 rounded-lg shadow-inner border border-slate-700'):
        for code, cost in PIECE_COSTS.items():
            if code == 'k': continue # Krále nelze koupit
            
            role = ROLE_MAP[code]
            
            # Kartička figury
            with ui.column().classes('items-center cursor-pointer transform hover:scale-110 transition duration-200'):
                # Cena
                ui.label(f"${cost}").classes('text-yellow-400 font-bold text-lg')
                
                # HTML element pro obrázek, který má navázaný onmousedown event pro start dragu
                # Používáme ui.html, abychom mohli vložit surový JS handler
                ui.html(f'''
                    <div onmousedown="window.startDragNewPiece('white', '{role}', event)" 
                         style="width: 60px; height: 60px; background-image: url('{piece_svg('white', role)}'); background-size: cover; cursor: grab;">
                    </div>
                ''')

def build_stats_panel(on_upgrade_depth, on_upgrade_time):
    """Vykreslí panel statistik a tlačítek pro vylepšení."""
    with ui.card().classes('w-full bg-slate-900 text-white border border-slate-700'):
        ui.label("VELITELSKÝ PULT").classes('text-xl font-bold text-center w-full mb-2 tracking-wider')
        
        with ui.grid(columns=2).classes('w-full gap-4'):
            # Peníze
            with ui.column().classes('col-span-2 items-center bg-slate-800 p-2 rounded'):
                ui.label("Dostupné Zdroje").classes('text-gray-400 text-xs uppercase')
                ui.label().bind_text_from(state, 'money', lambda m: f"${m}").classes('text-yellow-400 font-bold text-3xl')
            
            # Depth Upgrade
            with ui.column().classes('col-span-2 border-t border-slate-700 pt-4'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label("Hloubka Výpočtu").classes('font-bold text-indigo-300')
                    ui.label().bind_text_from(state, 'player_depth', lambda d: f"Lvl {d}")
                
                # Tlačítko je disabled, pokud nemáme peníze nebo běží simulace
                ui.button(f"Vylepšit (${UPGRADE_COST_DEPTH})", on_click=on_upgrade_depth) \
                   .props('color=indigo size=md icon=upgrade w-full') \
                   .classes('mt-1') \
                   .bind_enabled_from(state, 'money', lambda m: m >= UPGRADE_COST_DEPTH and not state.in_simulation)

            # Time Upgrade
            with ui.column().classes('col-span-2 border-t border-slate-700 pt-4'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label("Čas na Tah").classes('font-bold text-teal-300')
                    ui.label().bind_text_from(state, 'player_time', lambda t: f"{t:.1f}s")
                
                ui.button(f"Vylepšit (${UPGRADE_COST_TIME})", on_click=on_upgrade_time) \
                   .props('color=teal size=md icon=timer w-full') \
                   .classes('mt-1') \
                   .bind_enabled_from(state, 'money', lambda m: m >= UPGRADE_COST_TIME and not state.in_simulation)

def build_logs_panel():
    """Vykreslí rolovací log hry."""
    with ui.card().classes('w-full h-48 bg-black text-green-400 overflow-y-auto p-2 font-mono text-xs border border-slate-700'):
        # Jednoduchý bind textu s joinem pro zobrazení seznamu logů
        ui.label().bind_text_from(state, 'logs', lambda l: '\n'.join(l)).style('white-space: pre-wrap;')

def build_level_info():
    """Informační lišta o aktuálním levelu."""
    with ui.row().classes('w-full justify-between items-center bg-gradient-to-r from-red-900 to-slate-900 p-3 rounded-lg text-white mb-4 shadow-md'):
        with ui.column().classes('gap-0'):
            ui.label().bind_text_from(state, 'current_level_idx', lambda i: f"SOUPEŘ: ÚROVEŇ {i+1}").classes('font-bold text-sm text-red-300')
            # Dynamické načítání jména levelu
            ui.label().bind_text_from(state, 'current_level_idx', 
                lambda i: state.get_current_level_config()['name']).classes('text-xl font-black')
        
        with ui.column().classes('items-end gap-0'):
            ui.label("ODMĚNA").classes('text-xs text-gray-400')
            ui.label().bind_text_from(state, 'current_level_idx', 
                lambda i: f"+${state.get_current_level_config()['reward']}").classes('text-yellow-400 font-bold text-xl')