const logsContainer = document.getElementById('logs');
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/ws/logs`;
let socket;

// 1. Text/token filter matching logic for specific industrial keywords
const INDUSTRIAL_KEYWORDS = [
    /^[A-Z0-9-]{5,}$/, // Likely MPNs
    'Siemens', 'Schneider', 'ABB', 'Rockwell', 'Honeywell', // Brands
    /\d+V/, /\d+kV/, /\d+mV/, /\d+Hz/ // Voltages and Frequency
];

function matchesFilter(message) {
    const lowerMsg = message.toLowerCase();
    return INDUSTRIAL_KEYWORDS.some(keyword => {
        if (typeof keyword === 'string') {
            return lowerMsg.includes(keyword.toLowerCase());
        }
        return keyword.test(message);
    });
}

function connect() {
    socket = new WebSocket(wsUrl);

    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        // 2. UI rendering logic that intercepts and filters logs
        if (!matchesFilter(data.message)) {
            return;
        }

        const entry = document.createElement('div');
        entry.className = `log-entry ${data.level.toLowerCase()}`;
        
        const time = new Date().toLocaleTimeString();
        
        entry.innerHTML = `
            <span class="time">[${time}]</span>
            <span class="level">${data.level}</span>
            <span class="message">${data.message}</span>
`;
        
        logsContainer.appendChild(entry);

        // 3. Buffer management mechanism (limit to 500 rows)
        while (logsContainer.children.length > 500) {
            logsContainer.removeChild(logsContainer.firstChild);
        }
        
        logsContainer.scrollTop = logsContainer.scrollHeight;
    };

    socket.onclose = function() {
        setTimeout(connect, 3000);
    };

    socket.onerror = function(err) {
        socket.close();
    };
}

connect();
