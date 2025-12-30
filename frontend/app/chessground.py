import json

import chess
from nicegui import ui

from .config import CHESSGROUND_VERSION


# Chessground uses "piece placement FEN" (board_fen), not full FEN
DEFAULT_PLACEMENT = chess.STARTING_BOARD_FEN

ROLE_MAP = {
    'P': 'pawn', 'N': 'knight', 'B': 'bishop', 'R': 'rook', 'Q': 'queen', 'K': 'king',
}


def piece_svg(color: str, p: str) -> str:
    # Lichess cburnett pieces
    return f'https://lichess1.org/assets/piece/cburnett/{color}{p.lower()}.svg'


def inject_chessground_assets() -> None:
    """Inject Chessground CSS, ESM import, and JS glue into <head>."""
    ui.add_head_html(
        f'<link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.base.css">'
    )
    ui.add_head_html(
        f'<link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.brown.css">'
    )
    ui.add_head_html(
        f'<link rel="stylesheet" href="https://unpkg.com/chessground@{CHESSGROUND_VERSION}/assets/chessground.cburnett.css">'
    )

    # Import Chessground as ESM and expose globally
    ui.add_head_html(
        f"""
<script type="module">
import {{ Chessground }} from 'https://unpkg.com/chessground@{CHESSGROUND_VERSION}/chessground.js';
window.Chessground = Chessground;
</script>
"""
    )

    js_glue = r"""
(function () {
  window.cgInit = function(initialFen) {
    const el = document.getElementById('cg-board');
    if (!el) { console.error('cg-board element not found'); return; }
    if (!window.Chessground) { console.error('Chessground not loaded'); return; }

    const config = {
      fen: initialFen,
      orientation: 'white',
      viewOnly: false,
      movable: { free: true, color: 'both', showDests: false },
      draggable: { enabled: true, showGhost: true, deleteOnDropOff: true },
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
{js_glue}
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
