# 💬 Chit Chat

A modern, real-time chat & calling web application built with Flask, Socket.IO, and WebRTC. Features text/voice/image/video messaging, live presence, OTP email verification, profile management, and peer-to-peer audio/video calling over UDP (WebRTC/SRTP).

---

## 📸 Overview

Chit Chat is a full-stack messaging platform with a premium glassmorphic UI. It supports:

- End-to-end **text, voice, image, and video messaging**
- **Real-time audio and video calling** via WebRTC (UDP/SRTP)
- **Incoming call notifications** with accept/decline overlay
- **OTP-verified registration** via email
- **Online presence** indicators
- **Message read receipts** (double-tick, blue on seen)
- **Profile management** with custom avatar upload
- Emoji picker, voice recording, file attachment

---

## 🗂️ Project Structure

```
CHIT-CHAT/
├── app.py                       # Flask app — routes + Socket.IO handlers
├── requirements.txt             # Python dependencies
├── .env                         # Secrets (not in repo)
├── static/
│   ├── style.css                # Legacy stylesheet (minimal)
│   ├── main.js                  # Legacy JS stub
│   ├── Images/
│   │   └── chit_chat.png        # App logo / favicon
│   └── uploads/
│       ├── images/              # Uploaded image messages
│       ├── voice/               # Uploaded voice messages
│       ├── videos/              # Uploaded video messages
│       └── profile_pics/        # User avatar uploads
└── templates/
    ├── auth.html                # Login + Register page
    ├── verify.html              # OTP verification page
    ├── chat.html                # Main chat UI + calling buttons
    ├── call.html                # Full WebRTC call page (audio + video)
    └── profile.html             # User profile + avatar management
```

---

## ⚙️ Tech Stack

| Layer     | Technology                                   |
| --------- | -------------------------------------------- |
| Backend   | Python 3, Flask, Flask-SocketIO              |
| Database  | MySQL (via `mysql-connector-python`)         |
| Real-time | Socket.IO (WebSocket + long-poll fallback)   |
| Calling   | WebRTC (RTCPeerConnection, SRTP/DTLS/UDP)    |
| Signaling | Socket.IO events (offer/answer/ICE)          |
| Mail      | Flask-Mail → Gmail SMTP (OTP)                |
| Security  | SHA-256 password hashing, session-based auth |
| Frontend  | Vanilla JS, HTML5, CSS3 (glassmorphic)       |
| Fonts     | Plus Jakarta Sans (Google Fonts)             |
| Server    | Gunicorn + Gevent (production)               |

---

## 🛠️ Setup

### 1. Clone & Install

```bash
git clone <repo-url>
cd CHIT-CHAT
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your_flask_secret_key
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=chitchat
MAIL_USERNAME=your_gmail@gmail.com
MAIL_PASSWORD=your_gmail_app_password
```

> For Gmail, use an **App Password** (not your main password).  
> Enable 2FA → Google Account → Security → App Passwords.

### 3. Database Setup

Run the following SQL in your MySQL server:

```sql
CREATE DATABASE IF NOT EXISTS chitchat;
USE chitchat;

CREATE TABLE users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,
    password    VARCHAR(256) NOT NULL,
    verified    TINYINT(1) DEFAULT 0,
    profile_pic VARCHAR(300) DEFAULT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    sender_id   INT NOT NULL,
    receiver_id INT NOT NULL,
    message     LONGTEXT NOT NULL,
    type        ENUM('text','voice','image','video') DEFAULT 'text',
    is_seen     TINYINT(1) DEFAULT 0,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id)   REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
);
```

### 4. Run

**Development:**

```bash
python app.py
```

**Production (Gunicorn + Gevent):**

```bash
gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
         --workers 1 --bind 0.0.0.0:5000 app:app
```

App will be available at `http://localhost:5000`.

---

## 🌐 Routes

| Method   | Path                  | Description                           |
| -------- | --------------------- | ------------------------------------- |
| GET      | `/`                   | Redirect → `/login`                   |
| GET/POST | `/login`              | Login with phone + password           |
| POST     | `/register`           | Register new user, trigger OTP email  |
| GET/POST | `/verify`             | OTP verification for registration     |
| GET      | `/chat`               | Main chat UI (auth required)          |
| GET      | `/call.html`          | WebRTC call page (auth required)      |
| GET      | `/call`               | Alias for `/call.html`                |
| GET      | `/profile`            | User profile page                     |
| POST     | `/update_profile`     | Upload new avatar                     |
| GET      | `/remove_profile_pic` | Remove avatar                         |
| GET      | `/logout`             | Clear session, redirect to login      |
| GET      | `/search_users?q=`    | Search users by username prefix       |
| GET      | `/recent_chats`       | List recent conversations             |
| GET      | `/messages/<id>`      | Load message history with user `<id>` |

---

## 📡 Socket.IO Events

### Client → Server

| Event                        | Payload                               | Description                         |
| ---------------------------- | ------------------------------------- | ----------------------------------- |
| `join`                       | `{ room }`                            | Join a chat room                    |
| `send_message`               | `{ sender, receiver, message, type }` | Send text/voice/image/video message |
| `mark_as_read`               | `{ sender_id, receiver_id }`          | Mark messages as read               |
| `user_online`                | `{ user_id }`                         | Announce presence                   |
| `incoming_call_notification` | `{ caller, callee, room, type }`      | Notify callee of incoming call      |
| `join_call_room`             | `{ room }`                            | Join WebRTC call room               |
| `call_offer`                 | `{ room, sdp }`                       | Send SDP offer (caller → callee)    |
| `call_answer`                | `{ room, sdp }`                       | Send SDP answer (callee → caller)   |
| `ice_candidate`              | `{ room, candidate }`                 | Exchange ICE candidates (UDP)       |
| `call_ended`                 | `{ room }`                            | Signal call termination             |

### Server → Client

| Event                        | Payload                                    | Description                            |
| ---------------------------- | ------------------------------------------ | -------------------------------------- |
| `receive_message`            | `{ sender, receiver, message, type, ... }` | New message delivered to room          |
| `user_status`                | `{ user_id, online }`                      | Presence change broadcast              |
| `online_users_list`          | `[user_id, ...]`                           | Full list of online users on connect   |
| `messages_read`              | `{ reader_id }`                            | Notify sender their messages were read |
| `update_recents`             | _(none)_                                   | Trigger recent-chat list refresh       |
| `peer_ready`                 | `{ userId }`                               | Callee has joined the call room        |
| `incoming_call_notification` | `{ caller, callee, room, type }`           | Relayed to callee's private room       |
| `call_offer`                 | `{ room, sdp }`                            | Relayed SDP offer                      |
| `call_answer`                | `{ room, sdp }`                            | Relayed SDP answer                     |
| `ice_candidate`              | `{ room, candidate }`                      | Relayed ICE candidate                  |
| `call_ended`                 | `{ room }`                                 | Call terminated notification           |

---

## 📞 Calling Architecture

### Transport (UDP)

WebRTC media (audio/video) is always sent over **UDP** using:

- **ICE** — discovers peer endpoints (host/srflx candidates)
- **DTLS** — key exchange over UDP
- **SRTP** — encrypted media over UDP (Secure Real-time Transport Protocol)

Signaling (offer/answer/ICE relay) travels over Socket.IO (TCP/WebSocket), but all actual call media is **pure UDP**.

### Call Flow

```
  CALLER                         SERVER (Socket.IO)                  CALLEE
    |                                    |                              |
    |── initiateCall(type) ────────────►|── incoming_call_notif ──────►|
    |                                    |                              |
    |── open call.html?isCaller=true ─  |    callee clicks "Accept"    |
    |── join_call_room ────────────────►|                              |
    |                                    |◄─── join_call_room ─────────|
    |◄─────────────── peer_ready ───────|                              |
    |                                    |                              |
    |── createOffer ─────────────────►  |                              |
    |── call_offer ──────────────────►  |── call_offer ──────────────►|
    |                                    |            createAnswer ─── |
    |◄─────────────── call_answer ──────|◄─ call_answer ──────────────|
    |                                    |                              |
    |── ice_candidate ───────────────►  |── ice_candidate ───────────►|
    |◄─────────────── ice_candidate ────|◄─ ice_candidate ────────────|
    |                                    |                              |
    |◄═══════════ SRTP/UDP Media (P2P) ══════════════════════════════► |
    |                   (direct browser-to-browser)                     |
```

### STUN Servers Used

Five Google public STUN servers are configured — completely free, no setup needed:

- `stun:stun.l.google.com:19302`
- `stun:stun1.l.google.com:19302`
- `stun:stun2.l.google.com:19302`
- `stun:stun3.l.google.com:19302`
- `stun:stun4.l.google.com:19302`

> **Note:** For calls behind strict NAT/firewalls you may need a TURN server (coturn). Add it to `RTC_CONFIG.iceServers` in `call.html`.

---

## 🎨 Design System

| Token           | Value                    | Usage                      |
| --------------- | ------------------------ | -------------------------- |
| `--charcoal`    | `#1A1C23`                | Text, sent message bubbles |
| `--sand`        | `#E1D9BC`                | Accents, received bubbles  |
| `--ivory`       | `#F0F0DB`                | Page background            |
| `--cream`       | `#FAF9F6`                | Gradient background        |
| `--muted`       | `#8E9BAE`                | Secondary text, icons      |
| `--white`       | `#FFFFFF`                | Card backgrounds           |
| `--glass`       | `rgba(255,255,255,0.85)` | Glassmorphic panels        |
| `--card-radius` | `40px`                   | Card border radius         |
| `--item-radius` | `24px`                   | List item border radius    |

Font: **Plus Jakarta Sans** (400/600/700/800 weights)

---

## 🔒 Security Notes

- Passwords are hashed with **SHA-256** before storage (upgrade to bcrypt/argon2 for production)
- Sessions use Flask's signed cookie (set a strong `SECRET_KEY`)
- OTP emails expire when a new registration session starts
- Media files are saved server-side; file extensions are validated
- Socket.IO `cors_allowed_origins="*"` — restrict this in production

---

## 📦 Dependencies

```
flask
flask-socketio
flask-mail
mysql-connector-python
python-dotenv
gevent
gevent-websocket
gunicorn
```

---

## 🚀 Deployment

1. Set all `.env` variables in your hosting provider's environment config
2. Run with Gunicorn + Gevent worker (required for Socket.IO)
3. Use a reverse proxy (Nginx) to handle SSL termination
4. Ensure WebSocket upgrade headers pass through Nginx:
   ```nginx
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   ```
5. For WebRTC calls on production: HTTPS is **mandatory** (getUserMedia requires secure context)

---

## 🧩 Future Enhancements

- [ ] TURN server for NAT-restricted networks (coturn)
- [ ] Group calling (SFU architecture with mediasoup or livekit)
- [ ] Call history / missed call log in database
- [ ] Push notifications for missed calls/messages (FCM)
- [ ] Message encryption (E2E)
- [ ] Background blur / virtual backgrounds (WebRTC insertable streams)
- [ ] Screen sharing
- [ ] Message reactions & threading
- [ ] Dark mode toggle

---

## 👤 Author

Built with ❤️ — Chit Chat v1.0
