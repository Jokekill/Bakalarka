// assets/script.js

// Inicializace Chessground instance
window.cgInit = (fen) => {
    const config = {
        fen: fen,
        viewOnly: false,
        orientation: 'white',
        // Konfigurace pohybu
        movable: {
            color: 'white', // V editoru hýbeme jen bílými
            free: true,     // V editoru můžeme pokládat kamkoliv (validaci dělá Python)
        },
        draggable: {
            showGhost: true,
        },
        // Události
        events: {
            change: () => {
                // Když se změní deska, pošleme nový FEN do Pythonu
                const newFen = window.chessground.getFen();
                emitEvent('fen_update', newFen);
            }
        }
    };
    
    const el = document.getElementById('cg-board');
    if (el) {
        // Uložíme instanci do window pro pozdější přístup
        window.chessground = Chessground(el, config);
    }
};

// Programatické nastavení FENu (např. při startu simulace)
window.cgSetFen = (fen) => {
    if (window.chessground) {
        window.chessground.set({ fen: fen });
    }
};

// Zamčení/Odemčení desky (Simulace vs Editor)
window.cgSetViewOnly = (isViewOnly) => {
    if (window.chessground) {
        window.chessground.set({ 
            viewOnly: isViewOnly,
            movable: { 
                // Pokud je viewOnly, nikdo nemůže hýbat. Jinak jen bílý.
                color: isViewOnly? 'none' : 'white',
                free:!isViewOnly 
            }
        });
    }
};

// Zvýraznění posledního tahu (pro vizuální zpětnou vazbu)
window.cgSetLastMove = (orig, dest) => {
    if (window.chessground) {
        window.chessground.set({
            lastMove: [orig, dest]
        });
    }
};

// Drag and Drop z palety obchodu
window.startDragNewPiece = (color, role, event) => {
    event.preventDefault();
    if (window.chessground) {
        // Voláme interní metodu Chessgroundu pro zahájení dragu z externího zdroje
        window.chessground.dragNewPiece(
            { color: color, role: role },
            event,
            true // force: true
        );
    }
};