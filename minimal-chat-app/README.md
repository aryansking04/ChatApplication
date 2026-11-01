# Aura — Minimalist Real-Time Chat & Instagram Reels Sharing

A clean, modern, minimalist private messaging application built with **FastAPI**, **WebSockets**, **SQLite (SQLAlchemy)**, and vanilla **HTML/CSS/JavaScript**.

Inspired by the design philosophy of **Linear**, **Telegram**, and **WhatsApp**, Aura focuses strictly on private 1-on-1 conversations and rich media link sharing without the noise or clutter of social feeds.

---

## ✨ Features

### 1. User Authentication & Profile
- **Registration & Login**: Secure account creation with unique usernames and email validation.
- **Password Security**: Strong bcrypt password hashing with automatic 72-byte boundary compliance.
- **Persistent Sessions**: JWT authentication using both HTTP-only cookies and Bearer tokens for seamless browser page reloads.
- **Custom Minimalist Avatars**: DiceBear SVG avatar generator and style selector with initials fallback.

### 2. One-to-One Private Chatting
- **Type-Ahead User Search**: Instantly find other registered users by username and start conversations.
- **Real-Time Messaging**: Bi-directional instant messaging powered by WebSockets.
- **Persistence**: All messages, conversations, and participants permanently stored in SQLite.
- **Message Delivery & Read Receipts**: Visual status indicators (single check for sent, double check for read).
- **Typing Indicators**: Real-time typing status broadcast across active conversation rooms.
- **Online/Offline Presence**: Real-time presence detection and broadcast.
- **Convenient Controls**: `Enter` to send, `Shift + Enter` for multi-line messages, one-click message copy button with toast feedback.
- **Emoji Picker**: Built-in popup reaction picker.

### 3. Instagram Reels & Rich Link Sharing
- **Instagram Reel & Post Recognition**: Automatically detects Instagram URLs:
  - `https://www.instagram.com/reel/{shortcode}/...`
  - `https://www.instagram.com/p/{shortcode}/...`
  - `https://www.instagram.com/share/...`
- **Minimalist Media Cards**: Renders an attractive preview card with an Instagram icon badge, reel shortcode/caption, video overlay, and a clean **"Open Instagram"** action button.
- **YouTube Support**: Automatic video and short detection with high-resolution thumbnail preview (`hqdefault.jpg`), title, and direct link.
- **General Web Links**: Open Graph parsing (`og:title`, `og:description`, `og:image`, `og:site_name`) with domain attribution.
- **SSRF Protection**: Strict server-side validation rejecting private networks, loopback addresses (`127.0.0.1`, `localhost`, `10.x`, `192.168.x`, `169.254.x`), non-HTTP schemes, and unroutable IP addresses.

### 4. Minimalist UI/UX
- **Desktop Layout**:
  - **Left Sidebar**: App logo, user search bar, recent conversation list with real-time snippets, unread badges, and user profile pill with logout.
  - **Main Chat Area**: Spacious conversation header, partner presence status, message stream with clean bubble styling, autolinked text, and composer.
  - **Distraction-Free**: No permanent right sidebar, leaving ample whitespace.
- **Mobile Responsive**: Smooth transition between conversation list and active chat view with a Back button.
- **Color Palette**: Sophisticated neutral tones (slate, off-white, obsidian) with refined indigo/emerald accents.
- **Icons**: Powered by **Lucide Icons**.

---

## 🏗️ Architecture & Project Structure

```
minimal-chat-app/
│
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application, routes, middleware, and page rendering
│   ├── database.py                # SQLAlchemy engine, session maker, and Base model
│   ├── models.py                  # User, Conversation, ConversationParticipant, Message models
│   ├── schemas.py                 # Pydantic validation schemas (V2 with ConfigDict)
│   ├── auth.py                    # JWT token creation/decoding and bcrypt password hashing
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── users.py               # /api/register, /api/login, /api/logout, /api/users/search
│   │   ├── conversations.py       # /api/conversations (list, create, get by ID)
│   │   └── messages.py            # /api/messages, read receipts, and /ws/{conversation_id} WebSocket
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── manager.py             # Room connection manager, status broadcaster
│   └── services/
│       ├── __init__.py
│       └── link_preview.py        # URL extractor, SSRF guard, Instagram/YouTube/OG parser
│
├── templates/
│   ├── login.html                 # Minimalist sign-in screen
│   ├── register.html              # Account creation screen with avatar picker
│   └── chat.html                  # Main responsive chat interface
│
├── static/
│   ├── css/
│   │   └── style.css              # Custom minimalist CSS design system
│   ├── js/
│   │   ├── auth.js                # Form submission, token storage, avatar toggling
│   │   └── chat.js                # WebSocket engine, message stream, search, cards
│   └── images/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures and in-memory test database setup
│   ├── test_auth.py               # Auth, registration, duplicate checks, login tests
│   ├── test_conversations.py      # Conversation creation, uniqueness, access control tests
│   ├── test_messages.py           # Message sending, link detection, read receipts tests
│   ├── test_link_preview.py       # Instagram/YouTube regex, SSRF security validation
│   └── test_websocket.py          # Real-time WebSocket multi-user delivery and typing tests
│
├── requirements.txt               # Python package dependencies
├── README.md                      # Documentation
├── .env.example                   # Environment variable template
└── .gitignore                     # Git exclusions
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- pip

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default configuration works out of the box with SQLite.

### 4. Run the Application
Launch the server with Uvicorn:
```bash
uvicorn app.main:app --reload
```

Open your browser and navigate to:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧪 Running Automated Tests

Run the full automated test suite covering authentication, conversations, messaging, SSRF protection, Instagram Reel detection, and real-time WebSockets:

```bash
pytest tests -v
```

All 16 tests execute in under 5 seconds with in-memory isolation.

---

## 🛡️ Security Implementation
- **Password Hashing**: Direct bcrypt salt hashing.
- **SSRF Defense**: IP address resolution check rejecting RFC 1918 private ranges, loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`), and non-HTTP schemes.
- **XSS Defense**: Strict HTML escaping on frontend message rendering before DOM injection.
- **WebSocket Auth**: Authenticated via JWT token query parameter or signed HTTP-only cookie.
- **Authorization**: Strict participant validation on all conversation and message queries.
