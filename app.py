from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import threading
import mm
import yaml
import logging
import os
from dotenv import load_dotenv

app = Flask(__name__)
socketio = SocketIO(app)

# Setup logging
class SocketIOHandler(logging.Handler):
    def __init__(self, socketio):
        super().__init__()
        self.socketio = socketio

    def emit(self, record):
        log_entry = self.format(record)
        self.socketio.emit('log', {'message': log_entry})

logger = logging.getLogger()
logger.setLevel(logging.INFO)
socketio_handler = SocketIOHandler(socketio)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
socketio_handler.setFormatter(formatter)
logger.addHandler(socketio_handler)

# Load default configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)['default']

strategy = None

@app.route('/')
def index():
    return render_template('index.html', config=config)

@app.route('/start', methods=['POST'])
def start_strategy():
    global strategy
    if strategy is None:
        load_dotenv()
        api = mm.create_api(config['api'], logger)
        strategy = mm.create_market_maker(config['market_maker'], api, logger)
        threading.Thread(target=strategy.run, args=(config['market_maker'].get('dt', 1.0),), daemon=True).start()
        logger.info("Strategy started")
        return jsonify({"status": "started"})
    return jsonify({"status": "already running"})

@app.route('/stop', methods=['POST'])
def stop_strategy():
    global strategy
    if strategy:
        strategy.stop()
        strategy = None
        logger.info("Strategy stopped")
        return jsonify({"status": "stopped"})
    return jsonify({"status": "not running"})

@app.route('/update_config', methods=['POST'])
def update_config():
    global config
    new_config = request.json
    config['api'].update(new_config.get('api', {}))
    config['market_maker'].update(new_config.get('market_maker', {}))
    logger.info("Configuration updated")
    return jsonify({"status": "config updated"})

@socketio.on('connect')
def handle_connect():
    if strategy:
        emit_strategy_data()

def emit_strategy_data():
    if strategy:
        socketio.emit('strategy_data', {
            'trade_side': strategy.trade_side,
            'market_ticker': strategy.api.market_ticker,
            'buy_orders': strategy.api.get_orders(),
            'sell_orders': strategy.api.get_orders(),
            'position': strategy.api.get_position()
        })

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8080)