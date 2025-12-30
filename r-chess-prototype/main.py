import asyncio
import chess
import chess.engine
import chess.svg
from nicegui import ui, app

# Cesta k Stockfish binárce (nainstalováno v Dockerfile)
STOCKFISH_PATH = "/usr/games/stockfish"

# --- TŘÍDA PRO OVLÁDÁNÍ ENGINU ---
class ChessBot:
    def __init__(self, name, color_name):
        self.name = name
        self.color_name = color_name # Pro výpis v UI
        self.engine = None
        self.transport = None
        self.elo = 1350
        self.depth = 15

    async def start(self):
        """Nastartuje proces enginu."""
        if not self.engine:
            try:
                self.transport, self.engine = await chess.engine.popen_uci(STOCKFISH_PATH)
                await self.update_settings()
            except Exception as e:
                print(f"Chyba při startu enginu {self.name}: {e}")

    async def update_settings(self):
        """Aplikuje Elo a omezí sílu enginu."""
        if self.engine:
            await self.engine.configure({
                "UCI_LimitStrength": True,
                "UCI_Elo": self.elo
            })

    async def get_move(self, board):
        """Vypočítá nejlepší tah."""
        if not self.engine: await self.start()
        # Časový limit 0.1s pro rychlou odezvu v UI, hloubka omezena
        result = await self.engine.play(board, chess.engine.Limit(time=0.1, depth=self.depth))
        return result.move

    async def stop(self):
        if self.engine:
            await self.engine.quit()

# --- GLOBÁLNÍ STAV ---
board = chess.Board()
white_bot = ChessBot("White Bot", "Bílý")
black_bot = ChessBot("Black Bot", "Černý")
is_running = False

# --- UI LOGIKA ---
async def refresh_board():
    """Aktualizuje SVG šachovnice a popisky."""
    # Vykreslení šachovnice s posledním tahem
    content = chess.svg.board(
        board=board, 
        lastmove=board.peek() if board.move_stack else None,
        size=600
    )
    board_ui.content = content
    
    # Textové statistiky
    fen_label.text = board.fen()
    
    # Poslední tah do logu
    if board.move_stack:
        move = board.peek()
        # Určení kdo táhl (teď je na tahu ten druhý, takže táhl ten předchozí)
        who = "Černý" if board.turn == chess.WHITE else "Bílý"
        pgn_log.push(f"{board.fullmove_number}. {who}: {move.uci()} (Elo {white_bot.elo if who=='Bílý' else black_bot.elo})")

async def self_play_step():
    """Jeden krok herní smyčky."""
    global is_running
    if not is_running or board.is_game_over():
        if board.is_game_over():
            is_running = False
            ui.notify(f"Konec hry: {board.result()}", type='positive', close_button=True)
            btn_start.text = "Start Self-Play"
            btn_start.props('color=green')
        return

    # 1. Kdo je na tahu?
    active_bot = white_bot if board.turn == chess.WHITE else black_bot
    
    # 2. Získání tahu
    try:
        move = await active_bot.get_move(board)
        if move:
            board.push(move)
            await refresh_board()
    except Exception as e:
        ui.notify(f"Chyba enginu: {e}", type='negative')
        is_running = False
        return

    # 3. Naplánování dalšího kroku (smyčka)
    if is_running:
        ui.timer(0.5, self_play_step, once=True)

def toggle_simulation():
    """Tlačítko Start/Stop."""
    global is_running
    if is_running:
        is_running = False
        btn_start.text = "Start Self-Play"
        btn_start.props('color=green')
    else:
        is_running = True
        btn_start.text = "Stop Self-Play"
        btn_start.props('color=red')
        self_play_step() # Spustí první krok

def reset_game():
    global is_running
    is_running = False
    board.reset()
    btn_start.text = "Start Self-Play"
    btn_start.props('color=green')
    pgn_log.clear()
    # Nutné zabalit do tasku, protože voláme async funkci z synchronního handleru
    asyncio.create_task(refresh_board())

async def update_elo(bot, val):
    bot.elo = val
    await bot.update_settings()
    ui.notify(f"{bot.color_name} síla změněna: Elo {val}")

# --- STARTUP / SHUTDOWN ---
@app.on_startup
async def startup():
    await white_bot.start()
    await black_bot.start()

@app.on_shutdown
async def shutdown():
    await white_bot.stop()
    await black_bot.stop()

# --- VZHLED STRÁNKY ---
@ui.page('/')
async def index():
    ui.query('body').style('margin: 0; padding: 0; background-color: #e0e0e0;')

    with ui.row().classes('w-full h-screen no-wrap'):
        
        # LEVÝ PANEL - Šachovnice
        with ui.card().classes('w-2/3 h-full flex justify-center items-center bg-gray-200 square-0'):
            global board_ui
            # OPRAVA ZDE: Přidáno sanitize=False, které vyžaduje NiceGUI 3.0+
            board_ui = ui.html(chess.svg.board(board, size=600), sanitize=False)

        # PRAVÝ PANEL - Admin
        with ui.column().classes('w-1/3 h-full p-6 bg-white shadow-xl scroll-y'):
            ui.label("♟️ Chess Proto Admin").classes('text-2xl font-bold mb-4')
            
            # Statistiky
            with ui.card().classes('w-full bg-blue-50 p-3 mb-4'):
                ui.label("Stav hry").classes('font-bold text-blue-800')
                global fen_label
                ui.label("FEN:").classes('text-xs font-bold text-gray-500')
                fen_label = ui.label(board.fen()).classes('text-[10px] break-all font-mono leading-tight')

            # Nastavení Enginů
            with ui.card().classes('w-full p-4 border-l-8 border-blue-500 mb-4'):
                ui.label("⚙️ Nastavení Síly (Stockfish)").classes('text-lg font-bold mb-2')
                
                ui.label('Bílý Elo:').classes('font-bold text-gray-700')
                ui.slider(min=500, max=3000, value=1350, step=50, 
                          on_change=lambda e: update_elo(white_bot, e.value)) \
                 .props('label-always color=blue')
                
                ui.separator().classes('my-2')
                
                ui.label('Černý Elo:').classes('font-bold text-gray-700')
                ui.slider(min=500, max=3000, value=1350, step=50, 
                          on_change=lambda e: update_elo(black_bot, e.value)) \
                 .props('label-always color=red')

            # Ovládání
            with ui.row().classes('w-full gap-2 mb-4'):
                global btn_start
                btn_start = ui.button('Start Self-Play', on_click=toggle_simulation) \
                 .classes('flex-grow').props('color=green icon=play_arrow')
                
                ui.button('Reset', on_click=reset_game) \
                 .classes('flex-grow').props('color=grey icon=refresh outline')

            # Log
            ui.label("Historie tahů:").classes('font-bold')
            global pgn_log
            pgn_log = ui.log().classes('w-full h-64 bg-black text-green-400 font-mono text-xs p-2 rounded')

ui.run(title='Chess Roguelike', port=8080)