import os
import random
import string
import base64
import uuid
import hashlib
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Session settings
# ----------------
# By default Flask uses a signed cookie for session storage.  We
# do *not* mark the session as permanent, which means the cookie is
# discarded when the browser closes.  This prevents the situation
# where somebody opens the app, logs in, copies a URL and sends it to
# a friend who then magically has a valid login – the friend has no
# session cookie, so our @login_required guards will redirect them to
# /login.

app.config['SESSION_PERMANENT'] = False
# you can also customise the lifetime in case you want automatic
# expiration while the browser is still open:
# from datetime import timedelta
# app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# ---------------- SOCKET.IO INITIALIZATION ----------------
# SINGLE, CLEAN INITIALIZATION - avoids duplicate re-init issues
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    manage_session=False,
    max_http_buffer_size=10000000
)

# Master dictionary to keep track of everyone
# now maps user_id -> set of active socket session ids.  a single
# logical user may have multiple sockets (chat window + call popup,
# mobile + desktop, etc).  we only consider the user "offline" when
# the set becomes empty.
online_users = {}

# track currently in-progress calls by room so we can record them when
# they end.  key is the WebRTC room string used throughout the app.
ongoing_calls = {}

# ---------------- DATABASE HELPER ----------------
####################################################################
# FUNCTION: get_db
####################################################################
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        autocommit=True
    )

# ---------------- MAIL ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_USE_TLS'] = True
mail = Mail(app)

# ---------------- HELPERS ----------------
####################################################################
# FUNCTION: hash_pass
####################################################################
def hash_pass(password):
    return generate_password_hash(password)

####################################################################
# FUNCTION: send_otp
####################################################################
def send_otp(email):
    otp = ''.join(random.choices(string.digits, k=6))
    msg = Message("Your VeloApp OTP",
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[email])
    msg.body = f"Your OTP is {otp}"
    mail.send(msg)
    return otp

####################################################################
# FUNCTION: get_room_name
####################################################################
def get_room_name(user1, user2):
    return f"chat_{min(user1, user2)}_{max(user1, user2)}"

# ---------------- GOOGLE VERIFICATION ----------------
####################################################################
# FUNCTION: google_verify
####################################################################
@app.route('/google<verification_id>.html')
def google_verify(verification_id):
    filename = f"google{verification_id}.html"
    return send_from_directory('.', filename)

# ---------------- ROUTES ----------------
####################################################################
# FUNCTION: index
####################################################################
@app.route('/')
def index():
    return redirect('/login')


####################################################################
# FUNCTION: call_page
# Serves the call UI template at /call.html (expects query params)
####################################################################
@app.route('/call.html')
def call_page():
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('call.html')

####################################################################
# FUNCTION: call_alias
# Optional alias for convenience
####################################################################
@app.route('/call')
def call_alias():
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('call.html')



####################################################################
# FUNCTION: login
####################################################################
@app.route('/login', methods=['GET','POST'])
def login():
    # If already logged in, go straight to chat
    if session.get('user_id'):
        return redirect('/chat')

    # Clear any leftover session data so old sessions don't bleed in
    session.clear()

    if request.method == 'POST' and 'phone' in request.form:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        phone = request.form.get('phone')
        raw_password = request.form.get('password', '')

        cursor.execute("SELECT * FROM users WHERE phone_number=%s", (phone,))
        user = cursor.fetchone()

        if user:
            stored = user['password']
            # Detect legacy SHA-256 hash (plain 64-char hex) vs new Werkzeug hash
            legacy_hash = hashlib.sha256(raw_password.encode()).hexdigest()
            is_legacy = stored == legacy_hash
            is_new = (not is_legacy) and check_password_hash(stored, raw_password)

            if is_legacy or is_new:
                # Migrate legacy hash to secure Werkzeug hash on the fly
                if is_legacy:
                    new_hash = generate_password_hash(raw_password)
                    migrate_cursor = db.cursor()
                    migrate_cursor.execute(
                        "UPDATE users SET password=%s WHERE id=%s",
                        (new_hash, user['id'])
                    )
                    db.commit()
                    migrate_cursor.close()

                cursor.close()
                db.close()
                session['user_id'] = user['id']
                return redirect('/chat')

        cursor.close()
        db.close()
        return redirect('/login?error=Invalid+phone+number+or+password')

    return render_template('auth.html')

####################################################################
# FUNCTION: register
####################################################################
@app.route('/register', methods=['POST'])
def register():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    username = request.form.get('username')
    phone = request.form.get('phone')
    email = request.form.get('email')
    password = hash_pass(request.form.get('password'))

    cursor.execute("SELECT * FROM users WHERE email=%s OR phone_number=%s",
                   (email, phone))
    if cursor.fetchone():
        cursor.close()
        db.close()
        return redirect('/login?tab=register&error=An+account+with+that+email+or+phone+already+exists')

    otp = send_otp(email)
    session['otp'] = otp
    session['otp_expiry'] = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    session['reg_data'] = {
        'username': username,
        'phone': phone,
        'email': email,
        'password': password
    }

    cursor.close()
    db.close()
    return redirect('/verify')

#-----------------PROFILE-----------------------
UPLOAD_FOLDER_PFP = os.path.join('static', 'uploads', 'profile_pics')
os.makedirs(UPLOAD_FOLDER_PFP, exist_ok=True)

####################################################################
# FUNCTION: update_profile
####################################################################
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('user_id'):
        return redirect('/login')

    if 'profile_pic' not in request.files:
        return redirect('/profile')

    file = request.files['profile_pic']
    if file.filename == '':
        return redirect('/profile')

    if file:
        ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        parts = file.filename.rsplit('.', 1)
        if len(parts) != 2 or parts[1].lower() not in ALLOWED_EXTENSIONS:
            return redirect('/profile')
        ext = parts[1].lower()
        filename = f"pfp_{session['user_id']}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER_PFP, filename)
        file.save(filepath)
        db_path = f"profile_pics/{filename}"
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET profile_pic = %s WHERE id = %s", (db_path, session['user_id']))
        db.commit()
        cursor.close()
        db.close()

    return redirect('/profile')

####################################################################
# FUNCTION: profile
####################################################################
@app.route('/profile')
def profile():
    if not session.get('user_id'):
        return redirect('/login')
        
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    db.close()
    
    return render_template('profile.html', 
                           username=user['username'], 
                           email=user['email'], 
                           phone=user['phone_number'], 
                           profile_pic=user['profile_pic'])

####################################################################
# FUNCTION: logout
####################################################################
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

####################################################################
# FUNCTION: remove_profile_pic
####################################################################
@app.route('/remove_profile_pic')
def remove_profile_pic():
    if not session.get('user_id'):
        return redirect('/login')

    uid = session['user_id']
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT profile_pic FROM users WHERE id = %s", (uid,))
    user = cursor.fetchone()

    if user and user['profile_pic']:
        file_path = os.path.join(app.root_path, 'static', 'uploads', user['profile_pic'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file: {e}")

    cursor.execute("UPDATE users SET profile_pic = NULL WHERE id = %s", (uid,))
    db.commit()
    
    cursor.close()
    db.close()

    return redirect('/profile')

####################################################################
# FUNCTION: verify
####################################################################
@app.route('/verify', methods=['GET','POST'])
def verify():
    if request.method == 'POST':
        expiry_str = session.get('otp_expiry')
        if expiry_str and datetime.utcnow() > datetime.fromisoformat(expiry_str):
            session.pop('otp', None)
            session.pop('otp_expiry', None)
            session.pop('reg_data', None)
            return redirect('/login?tab=register&error=OTP+expired.+Please+register+again')

        if request.form['otp'] == session.get('otp'):
            db = get_db()
            cursor = db.cursor()

            data = session.pop('reg_data')
            session.pop('otp', None)
            session.pop('otp_expiry', None)
            cursor.execute("""
                INSERT INTO users (username, phone_number, email, password, verified)
                VALUES (%s,%s,%s,%s,1)
            """, (data['username'], data['phone'],
                  data['email'], data['password']))

            cursor.close()
            db.close()
            return redirect('/login')

        return redirect('/verify?error=Invalid+OTP.+Please+try+again')

    return render_template('verify.html')

####################################################################
# FUNCTION: chat
####################################################################
@app.route('/chat')
def chat():
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('chat.html', my_id=session.get('user_id'))

####################################################################
# FUNCTION: search_users
####################################################################
@app.route('/search_users')
def search_users():
    my_id = session.get('user_id')
    if not my_id:
        return jsonify({'error': 'Unauthorized'}), 401
    query = request.args.get('q', '')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, username, profile_pic
        FROM users
        WHERE username LIKE %s
        AND id != %s
        LIMIT 20
    """, (query + "%", my_id))

    users = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify(users)

####################################################################
# FUNCTION: recent_chats
####################################################################
@app.route('/recent_chats')
def recent_chats():
    my_id = session.get('user_id')
    if not my_id:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT u.id, u.username, u.profile_pic, m.message, m.timestamp
        FROM messages m
        JOIN users u 
          ON u.id = IF(m.sender_id=%s, m.receiver_id, m.sender_id)
        WHERE m.sender_id=%s OR m.receiver_id=%s
        ORDER BY m.timestamp DESC
    """, (my_id, my_id, my_id))

    rows = cursor.fetchall()
    seen = set()
    recent = []
    for row in rows:
        if row['id'] not in seen:
            seen.add(row['id'])
            recent.append(row)

    cursor.close()
    db.close()
    return jsonify(recent)

####################################################################
# FUNCTION: get_messages
####################################################################
@app.route('/messages/<int:other_id>')
def get_messages(other_id):
    my_id = session.get('user_id')
    if not my_id:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM messages 
        WHERE (sender_id=%s AND receiver_id=%s)
        OR (sender_id=%s AND receiver_id=%s)
        ORDER BY timestamp
    """, (my_id, other_id, other_id, my_id))

    messages = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(messages)

# -------- SOCKET HANDLERS --------

####################################################################
# FUNCTION: on_connect
####################################################################
@socketio.on('connect')
def on_connect():
    uid = session.get('user_id')
    if not uid:
        return

    join_room(str(uid))

    first_socket = False
    # add this socket id to the user's set
    if uid in online_users:
        online_users[uid].add(request.sid)
    else:
        online_users[uid] = {request.sid}
        first_socket = True

    # only broadcast "user became online" when the first connection appears
    if first_socket:
        emit('user_status', {'user_id': uid, 'online': True}, broadcast=True)
    # always send the fresh list to the connecting client so their UI updates
    emit('online_users_list', list(online_users.keys()), room=str(uid))

####################################################################
# FUNCTION: on_disconnect
####################################################################
@socketio.on('disconnect')
def on_disconnect():
    uid = session.get('user_id')
    if not uid or uid not in online_users:
        return

    sids = online_users[uid]
    sids.discard(request.sid)
    if not sids:
        # no remaining sockets for this user
        del online_users[uid]
        emit('user_status', {'user_id': uid, 'online': False}, broadcast=True)

####################################################################
# FUNCTION: handle_user_online
####################################################################
@socketio.on('user_online')
def handle_user_online(data):
    # this event is triggered manually by the client when they come back
    # from a locked screen or similar.  treat it almost exactly like
    # connect: add the socket id and broadcast if this is the first one.
    uid = session.get('user_id')
    if not uid:
        return

    first_socket = False
    if uid in online_users:
        online_users[uid].add(request.sid)
    else:
        online_users[uid] = {request.sid}
        first_socket = True

    if first_socket:
        emit('user_status', {'user_id': uid, 'online': True}, broadcast=True)
    emit('online_users_list', list(online_users.keys()), broadcast=True)

####################################################################
# FUNCTION: handle_join
####################################################################
@socketio.on('join')
def handle_join(data):
    room = data.get('room', '')
    uid = session.get('user_id')
    if not uid or not room:
        return
    # For chat rooms, ensure the requesting user is a participant
    if room.startswith('chat_'):
        parts = room.split('_')
        if len(parts) != 3:
            return
        try:
            if uid not in {int(parts[1]), int(parts[2])}:
                return
        except ValueError:
            return
    join_room(room)

####################################################################
# FUNCTION: handle_incoming_call
####################################################################
@socketio.on('incoming_call_notification')
def handle_incoming_call(data):
    """Relay a call notification to the intended recipient only.

    A few things to watch out for that were causing "everyone hears the
    call" reports:

    * if the `callee` value is missing or has the wrong type the ``room``
      argument becomes something unexpected; ``emit`` then falls back to a
      broadcast.  (``room=None`` == broadcast in some configurations).
    * users who open multiple tabs share the same session id and therefore
      join the same private room; all of those sockets will legitimately
      receive the event.  This can look like "all users" when you are
      testing with several tabs of the same account.

    To make the routing bullet‑proof we now look up the target socket id
    from ``online_users`` and emit directly to that socket, and log what
    we're doing for easier debugging.
    """
    callee = data.get('callee')
    if callee is None:
        app.logger.debug('incoming_call_notification missing callee: %r', data)
        return

    try:
        callee_id = int(callee)
    except (TypeError, ValueError):
        app.logger.warning('invalid callee id received: %r', callee)
        return

    # Store call metadata so we can log it when the call ends
    room = data.get('room')
    if room:
        try:
            caller_id = int(data.get('caller'))
        except (TypeError, ValueError):
            caller_id = None
        ongoing_calls[room] = {
            'caller': caller_id,
            'callee': callee_id,
            'type': data.get('type', 'audio'),
            'start': datetime.utcnow()
        }
        app.logger.info(f'[INCOMING_CALL] stored: room={room}, caller={caller_id}, callee={callee_id}, type={data.get("type")}')

    sid_set = online_users.get(callee_id)
    if sid_set:
        app.logger.debug('relaying call from %s to %s (sids=%s)',
                         data.get('caller'), callee_id, sid_set)
        # either send via room (simpler) or to each sid individually
        # using the room means Socket.IO takes care of multiple sockets.
        emit('incoming_call_notification', data, room=str(callee_id))
    else:
        app.logger.debug('callee %s is not online, dropping notification', callee_id)

####################################################################
# FUNCTION: handle_join_call_room
# Only allow the two participants to join; verify via ongoing_calls
####################################################################
@socketio.on('join_call_room')
def handle_join_call_room(data):
    room = data.get('room')
    user_id = session.get('user_id')
    
    if not room or not user_id:
        app.logger.warning('join_call_room: missing room or user_id')
        return
    
    # Verify this user is part of the call
    call_rec = ongoing_calls.get(room)
    if call_rec:
        is_caller = call_rec.get('caller') == user_id
        is_callee = call_rec.get('callee') == user_id
        if is_caller or is_callee:
            join_room(room)
            app.logger.info(f'join_call_room: {user_id} joined {room}')
            emit('peer_ready', {'userId': user_id}, room=room, include_self=False)
        else:
            app.logger.warning(f'join_call_room: user {user_id} not in call {room}')
    else:
        app.logger.warning(f'join_call_room: no call record for {room}')

####################################################################
# FUNCTION: handle_mark_as_read
####################################################################
@socketio.on('mark_as_read')
def handle_mark_as_read(data):
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    
    if not sender_id or not receiver_id:
        return

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE messages 
        SET is_seen = 1 
        WHERE sender_id = %s AND receiver_id = %s AND is_seen = 0
    """, (sender_id, receiver_id))
    db.commit()
    cursor.close()
    db.close()

    emit('messages_read', {'reader_id': receiver_id}, room=str(sender_id))

####################################################################
# FUNCTION: handle_message
####################################################################
@socketio.on('send_message')
def handle_message(data):
    sender = session.get('user_id')
    if not sender:
        return
    receiver = int(data['receiver'])
    data['sender'] = sender  # enforce server-side sender identity
    msg_type = data.get('type', 'text')
    content = data['message']

    if msg_type in ['voice', 'image', 'video']:
        try:
            type_config = {
                'voice': {'folder': 'voice', 'ext': 'webm'},
                'image': {'folder': 'images', 'ext': 'png'},
                'video': {'folder': 'videos', 'ext': 'mp4'}
            }
            
            config = type_config.get(msg_type)
            subfolder = config['folder']
            extension = config['ext']

            upload_dir = os.path.join(app.root_path, 'static', 'uploads', subfolder)
            os.makedirs(upload_dir, exist_ok=True)

            header, encoded = content.split(",", 1)
            file_binary = base64.b64decode(encoded)
            
            filename = f"{msg_type}_{uuid.uuid4().hex}.{extension}"
            filepath = os.path.join(upload_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(file_binary)
            
            content = f"/static/uploads/{subfolder}/{filename}"
            data['message'] = content 
            
        except Exception as e:
            print(f"Error processing {msg_type}: {e}")
            return

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO messages (sender_id, receiver_id, message, type)
        VALUES (%s, %s, %s, %s)
    """, (sender, receiver, content, msg_type))
    db.commit()
    cursor.close()
    db.close()

    room = get_room_name(sender, receiver)
    emit('receive_message', data, room=room)
    emit('update_recents', room=str(sender))
    emit('update_recents', room=str(receiver))

# ================= WEBRTC CALLING SIGNALING =================
####################################################################
# FUNCTION: handle_call_offer
# Receives 'call_offer' from a peer and relays it to the room (other participants)
####################################################################
@socketio.on('call_offer')
def handle_call_offer(data):
    room = data.get('room')
    if room:
        emit('call_offer', data, room=room, include_self=False)

####################################################################
# FUNCTION: handle_call_answer
# Receives 'call_answer' from callee and relays it to the room (caller)
####################################################################
@socketio.on('call_answer')
def handle_call_answer(data):
    room = data.get('room')
    if room:
        emit('call_answer', data, room=room, include_self=False)

####################################################################
# FUNCTION: handle_ice_candidate
# Receives ICE candidates and forwards to the other peer(s) in the room
####################################################################
@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    room = data.get('room')
    if room:
        emit('ice_candidate', data, room=room, include_self=False)

####################################################################
# FUNCTION: handle_call_ended
# Notifies participants in the room that the call ended and cleans up
####################################################################
@socketio.on('call_ended')
def handle_call_ended(data):
    room = data.get('room')
    app.logger.info(f'[CALL_ENDED] room={room}, ongoing_calls_keys={list(ongoing_calls.keys())}')
    
    if room:
        # log call in database if we previously recorded a start time
        rec = ongoing_calls.pop(room, None)
        app.logger.info(f'[CALL_ENDED] rec={rec}')
        
        if rec and rec.get('caller') and rec.get('callee'):
            end = datetime.utcnow()
            duration = int((end - rec['start']).total_seconds())
            
            # Determine call message based on connection status
            was_connected = data.get('was_connected', False)
            if was_connected:
                # Call was accepted and completed - include duration
                # Format duration as "1m 30s" or "45s"
                if duration >= 60:
                    mins = duration // 60
                    secs = duration % 60
                    duration_str = f"{mins}m {secs}s" if secs > 0 else f"{mins}m"
                else:
                    duration_str = f"{duration}s"
                msg_text = f"{rec['type'].capitalize()} Call - {duration_str}"
            else:
                # Call was not accepted
                msg_text = "Call not accepted"
            
            app.logger.info(f'[CALL_ENDED] inserting: caller={rec["caller"]}, callee={rec["callee"]}, duration={duration}, was_connected={was_connected}, msg={msg_text}')
            
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute("""
                    INSERT INTO messages (sender_id, receiver_id, message, type)
                    VALUES (%s, %s, %s, %s)
                """, (rec['caller'], rec['callee'], msg_text, 'call'))
                cursor.close()
                db.close()
                app.logger.info(f'[CALL_ENDED] database insert successful for call: {msg_text}')
            except Exception as e:
                app.logger.error(f'[CALL_ENDED] database error: {e}', exc_info=True)
                return
            
            # notify the participants in their chat rooms so they see the call record
            chat_room = get_room_name(rec['caller'], rec['callee'])
            msg_data = {
                'sender': rec['caller'],
                'receiver': rec['callee'],
                'message': msg_text,
                'type': 'call',
                'sender_id': rec['caller'],
                'receiver_id': rec['callee']
            }
            app.logger.info(f'[CALL_ENDED] emitting to chat_room={chat_room}')
            emit('receive_message', msg_data, room=chat_room)
            emit('update_recents', room=str(rec['caller']))
            emit('update_recents', room=str(rec['callee']))
        else:
            app.logger.warning(f'[CALL_ENDED] no valid call record found')

        emit('call_ended', data, room=room)
        try:
            leave_room(room)
        except Exception:
            pass

# -------- RUN --------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode,
                 allow_unsafe_werkzeug=debug_mode)