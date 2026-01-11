"""
game_logic.py
Spravuje stav hry, ekonomiku a validaci šachovnice.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import chess
from levels_config import LEVELS, PIECE_COSTS

@dataclass
class GameState:
    money: int = 20  # Startovní kapitál
    player_depth: int = 1
    player_time: float = 1.0  # Vizuální stat, ovlivňuje rychlost smyčky
    current_level_idx: int = 0
    
    # FEN reprezentující rozmístění hráčových (bílých) figur v editoru
    # Výchozí stav: jen bílý král na E1
    editor_fen: str = "8/8/8/8/8/8/8/4K3 w - - 0 1" 
    
    in_simulation: bool = False
    logs: List[str] = field(default_factory=list)

    def get_current_level_config(self):
        """Vrátí konfiguraci pro aktuální level."""
        if self.current_level_idx < len(LEVELS):
            return LEVELS[self.current_level_idx]
        return LEVELS[-1] # Fallback na poslední level (endgame)

    def calculate_board_cost(self, fen: str) -> int:
        """Vypočítá celkovou cenu bílých figur na šachovnici."""
        board = chess.Board(fen)
        cost = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == chess.WHITE:
                # Král je zdarma/povinný, nepočítáme ho do ceny nákupu
                if piece.piece_type!= chess.KING:
                    symbol = piece.symbol().lower()
                    cost += PIECE_COSTS.get(symbol, 0)
        return cost

    def validate_setup(self, fen: str) -> Tuple[bool, str]:
        """
        Ověří, zda je rozestavení validní pro start hry:
        1. Přesně jeden bílý Král.
        2. Figury pouze na řadách 1-4 (polovina hráče).
        3. Cena armády <= Peníze hráče.
        """
        board = chess.Board(fen)
        
        # 1. Kontrola Krále
        kings = board.pieces(chess.KING, chess.WHITE)
        if len(kings)!= 1:
            return False, "Musíš mít na šachovnici přesně jednoho krále!"

        # 2. Kontrola Rozpočtu
        cost = self.calculate_board_cost(fen)
        if cost > self.money:
            return False, f"Nedostatek peněz! Cena armády: {cost}, Máš: {self.money}"

        # 3. Kontrola Zón (Pouze řady 1-4 pro Bílé)
        # Ve standardním indexování jsou řady 0-7. Bílé pole je 0-3.
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == chess.WHITE:
                if chess.square_rank(square) > 3: 
                    return False, "Své figury můžeš stavět jen na svou polovinu (první 4 řady)!"

        return True, "OK"

    def merge_fens_for_simulation(self, white_fen: str, black_fen: str) -> str:
        """
        Spojí hráčovy bílé figury s levelovými černými figurami.
        white_fen: Z editoru (obsahuje bílé figury, prázdno u černých)
        black_fen: Z konfigu (obsahuje černé figury, prázdno u bílých)
        """
        board_w = chess.Board(white_fen)
        board_b = chess.Board(black_fen)
        
        # Vytvoříme čistou desku
        final_board = chess.Board(None) 
        
        # Umístíme bílé figury
        for square in chess.SQUARES:
            p = board_w.piece_at(square)
            if p and p.color == chess.WHITE:
                final_board.set_piece_at(square, p)
                
        # Umístíme černé figury
        for square in chess.SQUARES:
            p = board_b.piece_at(square)
            if p and p.color == chess.BLACK:
                final_board.set_piece_at(square, p)
        
        # Nastavíme tah na Bílého
        final_board.turn = chess.WHITE
        return final_board.fen()

    def log(self, message: str):
        """Přidá zprávu do logu a omezí historii."""
        self.logs.insert(0, message)
        if len(self.logs) > 50:
            self.logs.pop()

    def reset_to_level_1(self):
        """Kompletní restart hry."""
        self.money = 20
        self.player_depth = 1
        self.player_time = 1.0
        self.current_level_idx = 0
        # Reset na základního krále
        self.editor_fen = "8/8/8/8/8/8/8/4K3 w - - 0 1"
        self.log("Hra restartována. Jsi zpět na úrovni 1.")

# Globální instance stavu (pro zjednodušení v rámci single-client Dockeru)
state = GameState()