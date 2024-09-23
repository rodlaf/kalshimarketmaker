const socket = io();

document.getElementById('startBtn').addEventListener('click', () => {
    fetch('/start', { method: 'POST' })
        .then(response => response.json())
        .then(data => console.log(data));
});

document.getElementById('stopBtn').addEventListener('click', () => {
    fetch('/stop', { method: 'POST' })
        .then(response => response.json())
        .then(data => console.log(data));
});

document.getElementById('configForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const config = {
        api: {},
        market_maker: {}
    };
    for (let [key, value] of formData.entries()) {
        const [section, name] = key.split('.');
        config[section][name] = isNaN(value) ? value : Number(value);
    }
    fetch('/update_config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => console.log(data));
});

socket.on('strategy_data', (data) => {
    document.getElementById('tradeSide').value = data.trade_side;
    document.getElementById('marketTicker').value = data.market_ticker;
    updateOrderBook('buy', data.buy_orders);
    updateOrderBook('sell', data.sell_orders);
    document.getElementById('positionValue').textContent = data.position;
});

socket.on('log', (data) => {
    const logOutput = document.getElementById('logOutput');
    logOutput.textContent += data.message + '\n';
    logOutput.scrollTop = logOutput.scrollHeight;
});

function updateOrderBook(side, orders) {
    const ordersList = document.getElementById(`${side}OrdersList`);
    ordersList.innerHTML = '';
    orders.forEach(order => {
        const li = document.createElement('li');
        li.textContent = `Price: ${order.price}, Size: ${order.size}`;
        ordersList.appendChild(li);
    });
}