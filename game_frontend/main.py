from pathlib import Path
from nicegui import ui, app
from app.config import HOST, PORT
from app.chessground import inject_chessground_assets
from app.game_ui import build_ui

# Serve static files (CSS and piece SVGs) from the assets directory
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / 'app' / 'assets'
app.add_static_files('/static', str(ASSETS_DIR))
ui.add_head_html('<link rel="stylesheet" href="/static/styles.css">')

# Inject Chessground CSS/JS and set up JS helper functions for the chessboard
inject_chessground_assets()

# Build and display the UI for the game
build_ui()

# Run the NiceGUI app on configured host/port
ui.run(host=HOST, port=PORT)
