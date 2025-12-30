from typing import Optional, Tuple


def build_full_fen(
    placement: str,
    turn: str,
    castling: str,
    ep: str,
    halfmove: int,
    fullmove: int,
) -> str:
    """Build a full FEN string from Chessground placement FEN and extra fields."""
    turn = (turn or 'w').lower().strip()
    if turn not in ('w', 'b'):
        turn = 'w'

    castling = (castling or '-').strip() or '-'
    ep = (ep or '-').strip() or '-'

    return f'{placement} {turn} {castling} {ep} {halfmove} {fullmove}'


def uci_to_squares(move_uci: str) -> Optional[Tuple[str, str]]:
    if not move_uci or len(move_uci) < 4:
        return None
    return move_uci[:2], move_uci[2:4]
