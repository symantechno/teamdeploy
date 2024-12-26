from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, LoginManager, login_required, current_user, logout_user, UserMixin
from flask_socketio import SocketIO,join_room, leave_room,send
from datetime import datetime
import random
from string import ascii_uppercase
import secrets


app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Manish_23'
app.config['MYSQL_DB'] = 'flask_login'
app.config['SECRET_KEY'] =secrets.token_hex(16)



mysql = MySQL(app)
socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    if user:
        return User(id=user[0], username=user[1], email=user[2])
    return None


@app.route('/')
def welcome():
    if current_user.is_authenticated: 
        return redirect(url_for('dashboard'))
    return render_template('welcome.html')

@app.route('/learn') 
def learn():
    return render_template('learn.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user[3], password):
            user_obj = User(id=user[0], username=user[1], email=user[2])
            login_user(user_obj)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, hashed_password))
            mysql.connection.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Email already exists', 'error')
        finally:
            cur.close()
    
    return render_template('register.html')


@app.route('/dashboard')
@login_required  
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE id = %s", (current_user.id,))
    username = cur.fetchone()[0]
    cur.close()
    
    return render_template('dashboard.html', username=username)


@app.route('/logout')
@login_required  
def logout():
    logout_user()  
    return redirect(url_for('login'))

@app.route("/meeting")
@login_required
def meeting():
    return render_template("meeting.html", username=current_user.username)

@app.route("/join", methods=["GET", "POST"])
@login_required
def join():
    if request.method == "POST":
        room_id = request.form.get("roomID")
        return redirect(f"/meeting?roomID={room_id}")

    return render_template("join.html", username=current_user.username)



@app.route('/create_room', methods=['GET', 'POST'])
@login_required
def create_room():
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO chat_rooms (name, created_by) VALUES (%s, %s)",
                   (room_name, current_user.id))
        mysql.connection.commit()
        room_id = cur.lastrowid
        cur.close()
        flash('Room created successfully!', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
    return render_template('create_room.html')

rooms = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in rooms:
            break
    return code

def save_message_to_db(room_code, username, message, message_type='message'):
    cur = mysql.connection.cursor()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""
        INSERT INTO messages (room_code, username, message, timestamp, message_type) 
        VALUES (%s, %s, %s, %s, %s)
    """, (room_code, username, message, current_time, message_type))
    mysql.connection.commit()
    cur.close()
    return current_time

def get_or_create_room(room_code):
    cur = mysql.connection.cursor()
    # Check if room exists in rooms table
    cur.execute("SELECT * FROM rooms WHERE room_code = %s", [room_code])
    room = cur.fetchone()
    
    if not room:
        # Create new room if it doesn't exist
        cur.execute("INSERT INTO rooms (room_code, created_at) VALUES (%s, NOW())", [room_code])
        mysql.connection.commit()
    
    cur.close()
    
    if room_code not in rooms:
        rooms[room_code] = {"members": 0, "messages": []}

def get_room_messages(room_code):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT username, message, timestamp, message_type 
        FROM messages 
        WHERE room_code = %s 
        ORDER BY timestamp
    """, [room_code])
    messages = []
    for msg in cur.fetchall():
        messages.append({
            "name": msg[0],
            "message": msg[1],
            "timestamp": msg[2].strftime('%H:%M:%S'),
            "type": msg[3]
        })
    cur.close()
    return messages

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, LoginManager, login_required, current_user, logout_user, UserMixin
from flask_socketio import SocketIO, emit, join_room, leave_room, send
from datetime import datetime
import random
from string import ascii_uppercase
import secrets

# [Previous imports and configurations remain the same]

@app.route("/chat", methods=["POST", "GET"])
@login_required
def home():
    if request.method == "POST":
        name = current_user.username  # Use logged-in username instead of form input
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if join != False and not code:
            return render_template("home1.html", error="Please enter a room code.", code=code)

        room = code
        if create != False:
            room = generate_unique_code(4)
            get_or_create_room(room)
        else:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM rooms WHERE room_code = %s", [code])
            if not cur.fetchone():
                cur.close()
                return render_template("home1.html", error="Room does not exist.", code=code)
            cur.close()
            get_or_create_room(room)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home1.html")

@app.route("/chatroom")
@login_required
def room():
    room = session.get("room")
    if room is None:
        return redirect(url_for("home"))
    
    get_or_create_room(room)
    messages = get_room_messages(room)
    return render_template("room.html", code=room, messages=messages)

@socketio.on("message")
def message(data):
    if not current_user.is_authenticated:
        return
        
    room = session.get("room")
    if room not in rooms:
        return

    name = current_user.username
    current_time = save_message_to_db(room, name, data["data"])
    
    content = {
        "name": name,
        "message": data["data"],
        "timestamp": datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S'),
        "type": "message"
    }
    
    send(content, to=room)

@socketio.on("connect")
def connect(auth):
    if not current_user.is_authenticated:
        return
        
    room = session.get("room")
    name = current_user.username
    if not room or not name:
        return
        
    join_room(room)
    current_time = save_message_to_db(room, name, "has entered the room", "join")
    
    message_content = {
        "name": name,
        "message": "has entered the room",
        "timestamp": datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S'),
        "type": "join"
    }
    send(message_content, to=room)
    rooms[room]["members"] += 1

@socketio.on("disconnect")
def disconnect():
    if not current_user.is_authenticated:
        return
        
    room = session.get("room")
    name = current_user.username
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1

    current_time = save_message_to_db(room, name, "has left the room", "leave")
    message_content = {
        "name": name,
        "message": "has left the room",
        "timestamp": datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S'),
        "type": "leave"
    }
    send(message_content, to=room)
    print(f"{name} has left the room {room}")


if __name__ == '__main__':
    socketio.run(app, debug=True)

