# Lynx — AI Fundraising Intelligence

> Upload your startup docs, match with investors, generate personalized outreach, and practice your pitch — all AI-powered and secured with Auth0.

---

## 🚀 Live Demo

| | URL |
|---|---|
| **App** | `https://your-frontend.netlify.app` |
| **API** | `https://your-backend.railway.app` |
| **API Docs** | `https://your-backend.railway.app/docs` |

---

## ✨ Features

### 🧠 Brain — Document Intelligence
Upload any startup document (pitch deck, research paper, financials, code) and the AI synthesizes a complete investor-ready startup profile.

### 🤖 VC Matching
Three Backboard AI agents analyze your startup against every VC in the database and rank them by fit — Startup Analyst → VC Profiler → Match Reasoner.

### ✉️ Outreach Generator
One-click personalized cold emails, pitch scripts, LinkedIn DMs, and executive summaries tailored to each matched VC.

### 🎙 Pitch Simulator
Face an AI venture capitalist modelled on your matched VCs. Speak your answers aloud. Get dual-agent feedback (Strengths Agent + Improvement Agent).

### 🔒 Auth0 Authentication
- Social sign-in (Google, GitHub, LinkedIn)
- Email / password via Auth0 Universal Login
- Passwordless magic-link login
- Multi-Factor Authentication (MFA) enrollment
- JWT-secured API endpoints

---

## 🏗 Architecture

```
frontend/               ← Static HTML/CSS/JS (Netlify)
├── index.html          ← Main pipeline app (Upload → Match → Generate → Practice)
├── style.css
├── app.js
└── auth/               ← Auth0 integration (isolated)
    ├── login.html      ← Sign-in page
    ├── callback.html   ← Auth0 redirect handler
    ├── profile.html    ← User profile + MFA management
    ├── auth.js         ← Native PKCE auth flow (no SDK)
    ├── auth.css        ← Isolated styles
    └── auth-guard.js   ← Optional page protection

backend/                ← FastAPI Python API (Railway / Render)
├── main.py
├── config.py
├── requirements.txt
├── auth/
│   └── auth0.py        ← JWT verification middleware
├── routers/
│   ├── auth_router.py  ← /api/auth/* endpoints
│   ├── brain_router.py ← /api/brain/*
│   ├── matching_router.py
│   ├── generation_router.py
│   ├── simulator_router.py
│   └── scraper_router.py
└── data/
    └── vc_database.json
```

---

## 🔑 Environment Variables

Create a `backend/.env` file:

```env
# Gemini
GEMINI_API_KEY=your-gemini-api-key

# ElevenLabs (text-to-speech for pitch simulator)
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=your-voice-id

# Auth0
AUTH0_DOMAIN=dev-xxxx.us.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_API_AUDIENCE=

# Backboard.io (VC matching agents)
BACKBOARD_API_KEY=your-backboard-api-key
```

---

## 📡 API Reference

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/auth/me` | JWT | Returns authenticated user profile |
| `GET` | `/api/auth/mfa/status` | JWT | MFA enrollment status |
| `POST` | `/api/auth/mfa/enroll` | JWT | Start MFA enrollment (Guardian) |
| `POST` | `/api/auth/passwordless/start` | None | Send magic-link email |

### Pipeline

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/brain/upload` | Upload startup documents |
| `POST` | `/api/brain/synthesize` | Synthesize startup profile from docs |
| `POST` | `/api/match` | Run 3-agent VC matching pipeline |
| `POST` | `/api/generate` | Generate outreach content |
| `POST` | `/api/simulator/start` | Start mock pitch interview |
| `POST` | `/api/simulator/respond` | Submit answer and get AI feedback |

---

## 🔒 Auth0 Setup

1. Create a free account at [auth0.com](https://auth0.com)
2. Create a **Single Page Application**
3. Add your production URLs to **Application URIs**:

```
Allowed Callback URLs:  https://your-frontend.netlify.app/auth/callback.html
Allowed Logout URLs:    https://your-frontend.netlify.app
Allowed Web Origins:    https://your-frontend.netlify.app
```

4. Enable social connections (Google, GitHub, LinkedIn) in **Authentication → Social**
5. Enable MFA in **Security → Multi-factor Auth**
6. Paste your Domain and Client ID into `frontend/auth/login.html`, `callback.html`, and `profile.html`:

```js
window.AUTH0_CONFIG = {
  domain:      "dev-xxxx.us.auth0.com",
  clientId:    "your-client-id",
  audience:    "",
  redirectUri: window.location.origin + "/auth/callback.html",
  apiBase:     "https://your-backend.railway.app",
};
```

---

## 🚢 Deployment

### Frontend → Netlify
```bash
# Option 1: drag & drop the frontend/ folder at netlify.com/drop
# Option 2: CLI
npm install -g netlify-cli
netlify deploy --dir=frontend --prod
```

### Backend → Railway
```bash
railway login
railway init
railway up
```
Set root directory to `backend/` and add all `.env` variables in the Railway dashboard.  
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## 🛠 Local Development

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn main:app --reload
# → http://localhost:8000

# Frontend
cd frontend
python3 -m http.server 4000
# → http://localhost:4000/auth/login.html
# → http://localhost:4000/index.html
```

---

## 🏆 Built for Hack Canada 2026

Powered by **Gemini AI** · **Auth0** · **ElevenLabs** · **Backboard.io**
