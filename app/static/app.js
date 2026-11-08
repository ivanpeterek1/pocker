const socket = io();
const status = document.getElementById('status');
const playersEl = document.getElementById('players');
const handEl = document.getElementById('hand');
const communityEl = document.getElementById('community');
const potEl = document.getElementById('pot');
const potLargeEl = document.getElementById('potLarge');
const currentBetEl = document.getElementById('currentBet');
const stageEl = document.getElementById('stage');
const playerCountEl = document.getElementById('playerCount');
const controls = document.getElementById('controls');
const messageEl = document.getElementById('message');

let availableActions = [];

function formatCard(card) {
    if (!card) return '<span class="card">?</span>';
    const suitCode = card.slice(-1);
    const valueCode = card.slice(0, -1);
    const suitMap = { H: '♥', D: '♦', C: '♣', S: '♠' };
    const valueMap = { T: '10', J: 'J', Q: 'Q', K: 'K', A: 'A' };
    const suit = suitMap[suitCode] || suitCode;
    const value = valueMap[valueCode] || valueCode;
    const red = ['H', 'D'].includes(suitCode);
    return `<span class="card ${red ? 'red' : ''}">${value}${suit}</span>`;
}

function renderFaceDownCards(count) {
    return Array.from({ length: count }, () => '<span class="card back">♠</span>').join('');
}

function seatPositions(count) {
    const positions = [
        { left: '50%', top: '2%' },
        { left: '82%', top: '18%' },
        { left: '82%', top: '62%' },
        { left: '50%', top: '82%' },
        { left: '18%', top: '62%' },
        { left: '18%', top: '18%' },
        { left: '68%', top: '8%' },
        { left: '32%', top: '8%' }
    ];
    return positions.slice(0, count);
}

document.getElementById('joinBtn').addEventListener('click', () => {
    const name = document.getElementById('name').value.trim() || 'Player';
    socket.emit('join_game', { name });
});

document.getElementById('startBtn').addEventListener('click', () => {
    socket.emit('start_game');
});

document.querySelectorAll('[data-action]').forEach(button => {
    button.addEventListener('click', () => {
        const action = button.dataset.action;
        const amount = Number(document.getElementById('amount').value || 0);
        socket.emit('player_action', { action, amount });
    });
});

socket.on('connect', () => {
    status.textContent = 'Connected';
    status.style.color = '#6fe38b';
    status.style.borderColor = 'rgba(111, 227, 139, 0.35)';
    status.style.background = 'rgba(111, 227, 139, 0.12)';
});

socket.on('disconnect', () => {
    status.textContent = 'Disconnected';
    status.style.color = '#ff7d7d';
    status.style.background = 'rgba(255, 125, 125, 0.12)';
    status.style.borderColor = 'rgba(255, 125, 125, 0.35)';
});

socket.on('table_state', state => {
    const myPlayer = state.players.find(p => p.sid === socket.id) || null;
    potEl.textContent = state.pot;
    potLargeEl.textContent = state.pot;
    currentBetEl.textContent = state.current_bet;
    stageEl.textContent = state.stage || 'Waiting';
    playerCountEl.textContent = state.players.length;
    messageEl.textContent = state.last_message || 'Ready.';

    communityEl.innerHTML = state.community.length
        ? state.community.map(card => formatCard(card)).join('')
        : '<span style="color:#b8d5bf; opacity:0.8;">No community cards yet</span>';

    if (myPlayer) {
        handEl.innerHTML = (myPlayer.hand || []).length
            ? (myPlayer.hand || []).map(card => formatCard(card)).join('')
            : '<span style="color:#b8d5bf; opacity:0.8;">No cards yet</span>';
    } else {
        handEl.innerHTML = '<span style="color:#b8d5bf; opacity:0.8;">Join the table to receive cards</span>';
    }

    const currentTurnSid = state.turn_order && state.turn_order.length ? state.turn_order[state.turn_index % state.turn_order.length] : null;
    const seats = seatPositions(state.players.length);
    const sortedPlayers = [...state.players].sort((a, b) => a.seat - b.seat);

    document.getElementById('tableSeats').innerHTML = sortedPlayers.map((player, index) => {
        const isYou = player.sid === socket.id;
        const isTurn = currentTurnSid === player.sid;
        const loadedCards = isYou && (player.hand || []).length
            ? (player.hand || []).map(card => formatCard(card)).join('')
            : renderFaceDownCards(2);
        const style = `left:${seats[index].left}; top:${seats[index].top}; transform: translate(-50%, 0);`;

        return `
            <div class="seat ${isTurn ? 'active' : ''}" style="${style}">
                <div class="seat-name">${isYou ? 'You' : player.name}</div>
                <div class="seat-cards">${loadedCards}</div>
                <div class="seat-meta">${player.chips} chips · ${player.bet} bet<br>${player.folded ? 'Folded' : player.all_in ? 'All-in' : 'Active'}</div>
            </div>
        `;
    }).join('');

    playersEl.innerHTML = sortedPlayers.map(player => {
        const isYou = player.sid === socket.id;
        const isTurn = currentTurnSid === player.sid;
        const visibleHand = isYou && (player.hand || []).length ? player.hand : [];
        const handCards = visibleHand.map(card => formatCard(card)).join('') || renderFaceDownCards(2);
        return `
            <div class="player ${isYou ? 'you' : ''} ${isTurn ? 'active' : ''}">
                <div class="player-head">
                    <div class="avatar">${(player.name || 'P').charAt(0).toUpperCase()}</div>
                    <div class="player-name">${isYou ? 'You' : player.name}</div>
                    ${isTurn ? '<span style="font-size:0.75rem; color:#f7c66b; font-weight:700;">TURN</span>' : ''}
                </div>
                <div class="player-meta">
                    Chips: ${player.chips}<br>
                    Bet: ${player.bet}<br>
                    ${player.folded ? 'Folded' : player.all_in ? 'All-in' : 'Active'}
                </div>
                <div class="player-hand">${handCards}</div>
            </div>
        `;
    }).join('');
});

socket.on('request_action', data => {
    availableActions = data.options || [];
    controls.style.display = 'block';
    const buttons = document.querySelectorAll('[data-action]');
    buttons.forEach(btn => {
        const allowed = !availableActions.length || availableActions.includes(btn.dataset.action);
        btn.disabled = !allowed;
        btn.style.opacity = allowed ? '1' : '0.45';
    });
    messageEl.textContent = data.message || 'Your turn.';
});
