from pathlib import Path

from nicegui import ui, app

from app.config import HOST, PORT
from app.chessground import inject_chessground_assets
from app.ui_app import build_ui


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / 'app' / 'assets'

# Serve local static assets (CSS)
app.add_static_files('/static', str(ASSETS_DIR))
ui.add_head_html('<link rel="stylesheet" href="/static/styles.css">')

# Chessground + JS glue (must be in <head>)
inject_chessground_assets()

# Build the page
build_ui()

ui.run(host=HOST, port=PORT)
