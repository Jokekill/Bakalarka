# game_frontend/app/chessground.py
import json
from nicegui import ui
from .config import CHESSGROUND_VERSION

# placement FEN (pouze rozestavení figur) – prázdná šachovnice
DEFAULT_PLACEMENT = "8/8/8/8/8/8/8/8"

# mapování na chessground role
ROLE_MAP = {
    "P": "pawn",
    "N": "knight",
    "B": "bishop",
    "R": "rook",
    "Q": "queen",
    "K": "king",
}

def piece_svg(color: str, piece: str) -> str:
    # očekává soubory ve /static: wP.svg, bK.svg, ...
    return f"/static/{color}{piece}.svg"

def inject_chessground_assets() -> None:
    """Vloží Chessground CSS/JS + pomocné JS funkce (cgInit, cgSetFen, cgSetViewOnly...)."""

    ui.add_head_html(f"""
    <link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.base.css">
    <link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.brown.css">
    <link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.cburnett.css">
    """)

    ui.add_head_html(f"""
    <script type="module">
      import {{ Chessground }} from 'https://unpkg.com/chessground@{CHESSGROUND_VERSION}/chessground.js';
      window.Chessground = Chessground;
    </script>
    """)

    # JS glue: stejné API jako v admin frontendu
    ui.add_head_html(r"""
    <script>
      (function () {
        function safeEmitFen() {
          try {
            const fen = window.chessgroundInstance?.getFen?.();
            if (fen) emitEvent('fen_update', fen);
          } catch (e) {}
        }

        window.cgInit = function(initialFen) {
          const el = document.getElementById('cg-board');
          if (!el || !window.Chessground) return;

          const config = {
            fen: initialFen,
            orientation: 'white',
            viewOnly: false,
            movable: { free: true, color: 'both', showDests: false },
            draggable: { enabled: true, showGhost: true, deleteOnDropOff: true },
            premovable: { enabled: false },
            predroppable: { enabled: false },
            events: { change: safeEmitFen }
          };

          window.chessgroundInstance = window.Chessground(el, config);
          safeEmitFen();
        };

        window.cgSetFen = function(fen) {
          if (!window.chessgroundInstance) return;
          window.chessgroundInstance.set({ fen: fen });
          safeEmitFen();
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
    </script>
    """)

    # init po načtení DOM + NiceGUI emitEvent
    ui.add_head_html(f"""
    <script>
      window.addEventListener('DOMContentLoaded', () => {{
        const initialFen = {json.dumps(DEFAULT_PLACEMENT)};
        const tryInit = () => {{
          if (!window.Chessground || typeof emitEvent !== 'function' || !document.getElementById('cg-board')) {{
            return setTimeout(tryInit, 50);
          }}
          try {{ window.cgInit(initialFen); }}
          catch(e) {{ setTimeout(tryInit, 200); }}
        }};
        tryInit();
      }});
    </script>
    """)
