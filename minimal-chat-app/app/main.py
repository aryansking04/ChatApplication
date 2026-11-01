import os
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import engine, Base
from app.routes import users, conversations, messages
from app.auth import decode_access_token

# Initialize database tables
Base.metadata.create_all(bind=engine)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="Minimalist Chat App",
    description="Real-Time Messaging & Instagram Reels Sharing with Minimalist Design",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include API Routers
app.include_router(users.router)
app.include_router(conversations.router)
app.include_router(messages.router)


def is_authenticated(request: Request) -> bool:
    """Helper to check if user has a valid access token in cookies."""
    cookie = request.cookies.get("access_token")
    if not cookie:
        return False
    token = cookie.replace("Bearer ", "").strip()
    payload = decode_access_token(token)
    return payload is not None


# --- Web Page Routes ---

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to chat if logged in, otherwise to login page."""
    if is_authenticated(request):
        return RedirectResponse(url="/chat", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/chat", status_code=302)
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/chat", status_code=302)
    return templates.TemplateResponse(request=request, name="register.html")


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="chat.html")


@app.get("/health")
def health():
    return {"status": "ok", "app": "Minimalist Chat"}
