import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import random
import math


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins='*')

DEFAULT_NAMES = ["1", "2", "3", "4", "5", "6","7","8","9","10"]
names = list(DEFAULT_NAMES)
winner = ''
spinning = False
spin_count = 0
slowdown_mode = False

angle = 0.0
speed = 37.0
min_speed = 0.005
slowdown_start = None
slowdown_duration = 7.0
last_update_time = None

base_speed = 37.0

cumulative_winners = []

decel_angle0 = 0.0
decel_time0 = 0.0
decel_speed0 = 5.0

shuffle_on = False

common_memo = "1,2"
shared_text = "2,3"

anim_task = None


def get_winner_index(angle, names):
    N = len(names)
    if N == 0:
        return None
    arc = 2 * math.pi / N
    pointer_angle = -1*angle % (2 * math.pi)
    idx = int((pointer_angle ) // arc) % N
    return idx

def get_state():
    return {
        'names': names,
        'winner': winner,
        'spinning': spinning,
        'spin_count': spin_count,
        'slowdown_mode': slowdown_mode,
        'angle': angle,
        'speed': speed,
        'base_speed': base_speed,
        'slowdown_start': slowdown_start,
        'slowdown_duration': slowdown_duration,
        'last_update_time': last_update_time,
        'cumulative_winners': cumulative_winners,
        'decel_angle0': decel_angle0,
        'decel_time0': decel_time0,
        'decel_speed0': decel_speed0,
        'min_speed': min_speed,
        'shuffle_on': shuffle_on,
        'common_memo': common_memo,
        "shared_text" : shared_text,
    }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('update_common_memo')
def handle_update_common_memo(data):
    global common_memo
    txt = data.get('common_memo', '')
    common_memo = txt
    socketio.emit('sync_state', get_state(), room=None)

@socketio.on('update_text')
def handle_update_text(data):
    global shared_text
    shared_text = data.get('shared_text', '')
    socketio.emit('sync_state', get_state(), room=None)



@socketio.on('update_names')
def handle_update_names(data):
    global names, winner, spinning, slowdown_mode, angle, speed, slowdown_start, anim_task, last_update_time, cumulative_winners
    global decel_angle0, decel_time0, decel_speed0
    names = [n.strip() for n in data['names'].split(',') if n.strip()]
    winner = ''
    spinning = False
    slowdown_mode = False
    angle = 0.0
    speed = base_speed
    slowdown_start = None
    last_update_time = time.time()
    cumulative_winners = []
    decel_angle0 = 0.0
    decel_time0 = 0.0
    decel_speed0 = base_speed
    if anim_task:
        anim_task.kill()
        anim_task = None
    socketio.emit('sync_state', get_state(), room=None)

@socketio.on('set_base_speed')
def handle_set_base_speed(data):
    global base_speed
    try:
        base_speed = float(data.get('base_speed', 5.0))
        if base_speed < 0.1:
            base_speed = 0.1
        elif base_speed > 100:
            base_speed = 100
    except Exception:
        base_speed = 5.0
    socketio.emit('sync_state', get_state(), room=None)

@socketio.on('shuffle_names')
def handle_shuffle_names():
    global names
    random.shuffle(names)
    socketio.emit('sync_state', get_state(), room=None)

@socketio.on('set_shuffle_on')
def handle_set_shuffle_on(data):
    global shuffle_on
    shuffle_on = bool(data.get('shuffle_on', False))
    socketio.emit('sync_state', get_state(), room=None)

@socketio.on('start_spin')
def handle_start_spin():
    global spinning, spin_count, winner, slowdown_mode, angle, speed, slowdown_start, anim_task, last_update_time, shuffle_on
    global decel_angle0, decel_time0, decel_speed0
    if spinning or not names:
        return
    spinning = True
    winner = ''
    spin_count += 1
    slowdown_mode = False
    angle = 0.0
    speed = base_speed
    slowdown_start = None
    last_update_time = time.time()
    decel_angle0 = 0.0
    decel_time0 = 0.0
    decel_speed0 = base_speed
    shuffle_on = False
    socketio.emit('sync_state', get_state(), room=None)
    if anim_task:
        anim_task.kill()
    anim_task = eventlet.spawn(animate_wheel)

@socketio.on('stop_slowdown')
def handle_stop_slowdown():
    global slowdown_mode, slowdown_start, decel_angle0, decel_time0, decel_speed0
    if spinning and not slowdown_mode:
        slowdown_mode = True
        slowdown_start = time.time()
        decel_angle0 = angle
        decel_time0 = slowdown_start
        decel_speed0 = speed
        socketio.emit('sync_state', get_state(), room=None)

@socketio.on('stop_immediate')
def handle_stop_immediate():
    global spinning, winner, slowdown_mode, angle, speed, slowdown_start, anim_task, last_update_time, cumulative_winners
    if spinning:
        spinning = False
        slowdown_mode = False
        speed = base_speed
        slowdown_start = None
        idx = get_winner_index(angle, names)
        winner = names[idx] if idx is not None else ''
        cumulative_winners.append({'round': spin_count, 'winner': winner})
        last_update_time = time.time()
        if anim_task:
            anim_task.kill()
            anim_task = None
        socketio.emit('sync_state', get_state(), room=None)

def animate_wheel():
    global angle, speed, spinning, slowdown_mode, slowdown_start, winner, anim_task
    global decel_angle0, decel_time0, decel_speed0
    last_time = time.time()
    while spinning:
        now = time.time()
        dt = now - last_time
        last_time = now
        if slowdown_mode and slowdown_start is not None:
            t = now - slowdown_start
            v0 = decel_speed0
            T = slowdown_duration
            v1 = min_speed
            a = (v1 - v0) / T
            if t < T:
                angle = (decel_angle0 + v0 * t + 0.5 * a * t * t) % (2 * math.pi)
                speed = v0 + a * t
            else:
                angle = (decel_angle0 + v0 * T + 0.5 * a * T * T) % (2 * math.pi)
                speed = v1
                spinning = False
                slowdown_mode = False
                idx = get_winner_index(angle, names)
                winner = names[idx] if idx is not None else ''
                cumulative_winners.append({'round': spin_count, 'winner': winner})
        else:
            angle = (angle + speed * dt) % (2 * math.pi)
        last_update_time = now
        socketio.emit('sync_state', get_state(), room=None)
        eventlet.sleep(1/60)
    anim_task = None

@socketio.on('reset_all')
def handle_reset_all():
    global names, winner, spinning, spin_count, slowdown_mode, angle, speed, slowdown_start, last_update_time, cumulative_winners
    global decel_angle0, decel_time0, decel_speed0, base_speed, shuffle_on, common_memo, shared_text
    names = list(DEFAULT_NAMES)
    winner = ''
    spinning = False
    spin_count = 0
    slowdown_mode = False
    angle = 0.0
    speed = 5.0
    base_speed = 5.0
    shuffle_on = False
    slowdown_start = None
    last_update_time = time.time()
    cumulative_winners = []
    decel_angle0 = 0.0
    decel_time0 = 0.0
    decel_speed0 = 5.0
    common_memo = "1,3"
    shared_text = "defaulttext,text"
    socketio.emit('sync_state', get_state(), room=None)

@socketio.on('reset_winners')
def handle_reset_winners():
    global cumulative_winners, winner
    cumulative_winners = []
    winner = ''
    socketio.emit('sync_state', get_state(), room=None)

@socketio.on('connect')
def handle_connect():
    emit('sync_state', get_state())
    emit('text_update', {'shared_text':shared_text})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
