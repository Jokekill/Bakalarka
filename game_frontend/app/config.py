import os

# Engine service endpoint and timeout
ENGINE_URL = os.getenv('ENGINE_URL', 'http://localhost:8000/analyze')
REQUEST_TIMEOUT_S = float(os.getenv('ENGINE_TIMEOUT', '12'))

# Chessground library version (for injecting correct CDN URLs)
CHESSGROUND_VERSION = os.getenv('CHESSGROUND_VERSION', '8.2.0')

# Host and port for the NiceGUI app
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8081'))

# Game settings
INITIAL_MONEY = 10  # Starting budget for level 1
BASE_ENGINE_DEPTH = 3  # Base depth (free) for player's engine
BASE_ENGINE_TIME = 0   # Base time (free seconds) for player's engine
DEPTH_COST = 1  # Cost in money per +1 depth
TIME_COST = 1   # Cost in money per +1 second of think time

# Piece costs (uppercase for white pieces)
PIECE_COSTS = {
    'P': 1,   # Pawn
    'N': 3,   # Knight (Jezdec)
    'B': 3,   # Bishop (Střelec)
    'R': 5,   # Rook (Věž)
    'Q': 9,   # Queen (Dáma)
    'K': 0,   # King (Král must be placed, but no cost)
}

# Configuration for enemy setups per level
LEVELS = [
    # Each level defines black’s initial pieces (placement FEN for black side) and reward money for winning.
    # White's half (ranks 1-4) is empty in these strings; black's half (ranks 5-8) contains the pieces.
    {
        "black_fen": "4k3/8/8/8/8/8/8/8",  # Level 1: Black has only a King at e8
        "reward": 5
    },
    {
        "black_fen": "4k3/p2p2p1/8/8/8/8/8/8",  # Level 2: Black King + 3 pawns (at a7, d7, g7)
        "reward": 5
    },
    {
        "black_fen": "2b1k3/p1p2p2/8/8/8/8/8/8",  # Level 3: Black King+Bishop (c8) + pawns at a7,c7,f7
        "reward": 7
    },
    {
        "black_fen": "r1b1k3/p1p2p1p/8/8/8/8/8/8",  # Level 4: Black King + Bishop + Rook + pawns (a7,c7,f7,h7)
        "reward": 7
    },
    {
        "black_fen": "rnbqkbnr/pppppppp/8/8/8/8/8/8",  # Level 5: Full black starting lineup (final boss)
        "reward": 15
    }
    # More levels can be added here if needed.
]

# (Optional) Black engine settings: we will use a fixed moderate depth for black which can scale with level.
# If desired, we could also incorporate UCI ELO to make early levels play weaker moves.
BLACK_BASE_DEPTH = 5        # base depth for black engine
BLACK_DEPTH_PER_LEVEL = 1   # increment black engine depth each level (e.g., level1 depth5, lvl2 depth6, etc.)
MAX_BLACK_DEPTH = 15        # cap for black engine depth
