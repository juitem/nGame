import eventlet
# To resolve bug on a specific version
# This typically means that you attempted to use functionality that needed
# the current application. To solve this, set up an application context
# with app.app_context(). See the documentation for more information.
# An exception was thrown while monkey_patching for eventlet. to fix this error make sure you run eventlet.monkey_patch() before importing any other modules.
# Traceback (most recent call last):
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

import random

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins='*')

names = []
winner = ''
spinning = False
spin_count = 0

# 회전 제어용
spin_task = None
slowdown_mode = False


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('update_names')
def handle_update_names(data):
    global names, winner, spinning, spin_task, slowdown_mode
    names = [n.strip() for n in data['names'].split(',') if n.strip()]
    winner = ''
    spinning = False
    slowdown_mode = False
    if spin_task:
        spin_task.kill()
        spin_task = None
    emit('sync_state', get_state(), broadcast=True)

@socketio.on('start_spin')
def handle_start_spin():
    global spinning, spin_count, winner, spin_task, slowdown_mode
    if spinning or not names:
        return
    spinning = True
    winner = ''
    spin_count += 1
    slowdown_mode = False
    emit('sync_state', get_state(), broadcast=True)
    # spin_task는 멈춤 버튼에서 제어
    spin_task = eventlet.spawn(spin_forever)

def spin_forever():
    # 아무 일 없이 계속 대기, 멈춤 명령 대기
    while spinning:
        eventlet.sleep(0.1)

@socketio.on('stop_immediate')
def handle_stop_immediate():
    global spinning, winner, spin_task, slowdown_mode
    if spinning:
        spinning = False
        slowdown_mode = False
        if names:
            winner = random.choice(names)
        else:
            winner = ''
        if spin_task:
            spin_task.kill()
        emit('sync_state', get_state(), broadcast=True)

@socketio.on('stop_slowdown')
def handle_stop_slowdown():
    global spinning, winner, spin_task, slowdown_mode
    if spinning and not slowdown_mode:
        slowdown_mode = True
        # 5초간 감속 후 멈춤
        eventlet.spawn(slowdown_and_stop)

def slowdown_and_stop():
    global spinning, winner, spin_task, slowdown_mode
    eventlet.sleep(5)
    if spinning:
        spinning = False
        slowdown_mode = False
        if names:
            winner = random.choice(names)
        else:
            winner = ''
        if spin_task:
            spin_task.kill()
        socketio.emit('sync_state', get_state(), broadcast=True)

def get_state():
    return {
        'names': names,
        'winner': winner,
        'spinning': spinning,
        'spin_count': spin_count,
        'slowdown_mode': slowdown_mode
    }

@socketio.on('connect')
def handle_connect():
    emit('sync_state', get_state())

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
