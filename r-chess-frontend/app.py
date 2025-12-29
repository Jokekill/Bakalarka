import os  # Nutné přidat import na začátek souboru, pokud tam není
import streamlit as st
import chess
import chess.svg
import requests
import base64

# Konfigurace - adresa naší Engine služby
# Pozor: 'chess-engine' bude název kontejneru v síti Dockeru (vysvětlím níže)
ENGINE_API_URL = os.getenv("ENGINE_API_URL", "http://r-chess-engine:8000/analyze")

st.set_page_config(page_title="Chess Roguelike")

st.title("♟️ Chess Roguelike - Prototype")

# 1. Inicializace stavu hry (Session State)
if 'board' not in st.session_state:
    st.session_state.board = chess.Board()
if 'last_analysis' not in st.session_state:
    st.session_state.last_analysis = None

# Funkce pro zobrazení šachovnice
def render_board(board):
    board_svg = chess.svg.board(board=board)
    b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
    html = f'<img src="data:image/svg+xml;base64,{b64}" width="400" />'
    st.write(html, unsafe_allow_html=True)

# 2. Layout - Levý sloupec hra, Pravý sloupec info
col1, col2 = st.columns([1, 1])

with col1:
    render_board(st.session_state.board)
    
    # Vstup pro tah hráče (UCI formát, např. e2e4)
    move_input = st.text_input("Zadej tah (např. e2e4):")
    
    if st.button("Zahrát tah"):
        try:
            move = chess.Move.from_uci(move_input)
            if move in st.session_state.board.legal_moves:
                st.session_state.board.push(move)
                st.success(f"Tah {move_input} zahrán.")
                st.rerun() # Refresh stránky
            else:
                st.error("Neplatný tah!")
        except ValueError:
            st.error("Špatný formát tahu. Použij UCI (např. e2e4).")

with col2:
    st.subheader("Analýza Enginu (Stockfish)")
    
    if st.button("Požádat o radu (API call)"):
        # Zde voláme tvůj druhý kontejner!
        payload = {
            "fen": st.session_state.board.fen(),
            "depth": 15
        }
        try:
            response = requests.post(ENGINE_API_URL, json=payload)
            if response.status_code == 200:
                data = response.json()
                st.session_state.last_analysis = data
            else:
                st.error(f"Chyba API: {response.status_code}")
        except Exception as e:
            st.error(f"Nelze se spojit s enginem: {e}")

    # Zobrazení výsledků analýzy
    if st.session_state.last_analysis:
        data = st.session_state.last_analysis
        st.info(f"Doporučený tah: **{data.get('best_move')}**")
        st.write(f"Skóre: {data.get('score')}")
        st.json(data)

    if st.button("Reset hry"):
        st.session_state.board = chess.Board()
        st.session_state.last_analysis = None
        st.rerun()