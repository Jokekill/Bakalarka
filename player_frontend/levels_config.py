"""
levels_config.py
Definuje progresi obtížnosti pro Roguelike Chess.
Každá úroveň specifikuje:
- fen: Startovní pozice ČERNÝCH figur (Bílé staví hráč).
- reward: Zlato získané za vítězství.
- enemy_depth: Inteligence nepřátelského enginu.
"""

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

# Ceník figur pro nákup v obchodě
PIECE_COSTS = {
    'p': 1,  # Pěšec
    'n': 3,  # Jezdec
    'b': 3,  # Střelec
    'r': 5,  # Věž
    'q': 9,  # Dáma
    'k': 0   # Král (Povinný, zdarma v rámci základního vybavení)
}

# Ceny upgradů
UPGRADE_COST_DEPTH = 15  # Cena za zvýšení hloubky o 1
UPGRADE_COST_TIME = 10   # Cena za "čas" (simulovanou rozvahu)