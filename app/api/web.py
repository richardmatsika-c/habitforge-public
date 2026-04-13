# app/api/web.py

from typing import Annotated, Optional, cast
from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select, desc
from datetime import timedelta, datetime, timezone, date
from jose import JWTError, jwt
import os

from sqlalchemy import asc
from sqlalchemy.sql.elements import ColumnElement

from ..db import SessionDep

# --- 1. Import all the models we need ---
from ..models import (
    User,
    Habit,
    HabitCompletion,
    HabitCreate,
    UserCreate,
    Feedback,
    ForgeNote,
)
from ..api.auth import (
    authenticate_user,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY_STR,
    get_user_by_username,
)

# Import the journey list
from ..api.habits import JOURNEY_RITUALS
from ..security import get_password_hash

# --- 2. Import auth and encryption functions ---
from ..web_auth import get_current_user_from_cookie, get_token_from_cookie
from ..utils import compute_streak, get_dashboard_stats, get_habit_stats
from ..encryption import encrypt_data, decrypt_data  # <-- Import encryption

# --- Router Setup ---
router_slash = APIRouter(prefix="/web")
router = APIRouter(tags=["Web (HTML)"], include_in_schema=False)
templates = Jinja2Templates(directory="templates")

# --- Cookie Security Config ---
APP_ENVIRONMENT = os.getenv("APP_ENV", "development")
IS_SECURE_COOKIE = APP_ENVIRONMENT == "production"


# --- Dependencies ---
async def get_current_user_optional(
    request: Request, session: SessionDep
) -> Optional[User]:
    """
    A dependency that gets the user *if they exist*, but does not
    fail or redirect if they are not logged in.
    """
    try:
        token = get_token_from_cookie(request=request)
        if not token:
            return None
        return await get_current_user_from_cookie(token=token, session=session)
    except HTTPException:
        return None


CurrentUser = Annotated[User, Depends(get_current_user_from_cookie)]


# -------------------
# Auth: Login
# -------------------
@router.get("/login", response_class=HTMLResponse)
async def get_login_page(
    request: Request, error: Optional[str] = None, info: Optional[str] = None
):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error, "info": info, "forge_state": "ash"},
    )


@router.post("/login")
async def handle_web_login(
    session: SessionDep,
    request: Request,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
):
    user = authenticate_user(session, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "bad_credentials", "forge_state": "ash"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_str = create_access_token(
        data={"sub": user.username, "user_id": user.id}, expires_delta=expires_delta
    )
    response = RedirectResponse(
        url="/web/dashboard", status_code=status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token_str}",
        httponly=True,
        max_age=int(expires_delta.total_seconds()),
        samesite="lax",
        path="/",
        secure=IS_SECURE_COOKIE,
    )
    return response


# -------------------
# Auth: Register
# -------------------
@router.get("/register", response_class=HTMLResponse)
async def get_register_page(request: Request):
    return templates.TemplateResponse(
        "register.html", {"request": request, "forge_state": "ash"}
    )


@router.post("/register")
async def handle_register(
    request: Request,
    session: SessionDep,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
):
    try:
        user_data = UserCreate(username=username, password=password)
    except ValueError as e:
        error_message = "Username must be 3+ chars and password must be 8+ chars."
        if "username" in str(e):
            error_message = "Username must be at least 3 characters."
        elif "password" in str(e):
            error_message = "Password must be at least 8 characters."
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": error_message, "forge_state": "ash"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    q = select(User).where(User.username == user_data.username)
    existing = session.exec(q).first()
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "That username is already taken",
                "forge_state": "ash",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    hashed = get_password_hash(user_data.password)
    new_user = User.model_validate(
        user_data,
        update={
            "hashed_password": hashed,
            "is_active": True,
            "forge_state": "Ash",
            "forge_progress": 0,
        },
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    day_0_ritual = Habit(
        name=JOURNEY_RITUALS[0],  # "Day 0: Write Your 'Honest Note'"
        frequency="once",
        user_id=new_user.id,
    )
    session.add(day_0_ritual)
    session.commit()

    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_str = create_access_token(
        data={"sub": new_user.username, "user_id": new_user.id},
        expires_delta=expires_delta,
    )
    response = RedirectResponse(
        url="/web/dashboard", status_code=status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token_str}",
        httponly=True,
        max_age=int(expires_delta.total_seconds()),
        samesite="lax",
        path="/",
        secure=IS_SECURE_COOKIE,
    )
    return response


# -------------------
# Auth: Logout
# -------------------
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/web/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token", path="/", samesite="lax")
    return response


# -------------------
# Dashboard (Smart Router)
# -------------------
@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_or_journey(
    request: Request, session: SessionDep, current_user: CurrentUser
):
    state = current_user.forge_state.lower()

    # --- 1. Get data for Sidebar (Recent Notes) ---
    notes_query = (
        select(ForgeNote)
        .where(ForgeNote.user_id == current_user.id)
        .order_by(desc(ForgeNote.created_at))
        .limit(4)
    )
    recent_notes_encrypted = session.exec(notes_query).all()

    # --- DECRYPT THE NOTES ---
    recent_notes = []
    for note in recent_notes_encrypted:
        note.content = decrypt_data(note.content)  # Decrypt for display
        recent_notes.append(note)

    # --- 2. Check user state ---
    if state == "ash":
        # --- "Ash" State: Show the journey ---
        today_utc = datetime.now(timezone.utc).date()

        # Find the user's *current* ritual for today
        current_ritual_obj = None
        if current_user.forge_progress < len(JOURNEY_RITUALS):
            ritual_name = JOURNEY_RITUALS[current_user.forge_progress]
            ritual_query = select(Habit).where(
                Habit.user_id == current_user.id, Habit.name == ritual_name
            )
            current_ritual = session.exec(ritual_query).first()

            if current_ritual and current_ritual.id is not None:
                stats = get_habit_stats(session, current_ritual.id, today_utc)
                current_ritual_obj = {
                    "id": current_ritual.id,
                    "name": current_ritual.name,
                    "frequency": current_ritual.frequency,
                    "completed_today": stats["completed_today"],
                    "streak": stats["streak"],
                }

        return templates.TemplateResponse(
            "dashboard.html",  # <-- Use the main dashboard template
            {
                "request": request,
                "current_user": current_user,
                "forge_state": state,
                "forge_progress": current_user.forge_progress,
                "progress_percent": (current_user.forge_progress / len(JOURNEY_RITUALS))
                * 100,
                "current_ritual": current_ritual_obj,
                "log_entries": recent_notes,
                "pending_habits": [],  # Not needed for Ash
                "completed_habits": [],  # Not needed for Ash
                "completed_today_count": 0,  # Not needed for Ash
            },
        )

    else:
        # --- "Steel" State: Show the full dashboard ---
        dashboard_data = get_dashboard_stats(session=session, user=current_user)
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "current_user": current_user,
                "forge_state": state,
                "forge_progress": 7,  # Max progress
                "progress_percent": 100,
                "current_ritual": None,  # No journey ritual
                "pending_habits": dashboard_data["pending_habits"],
                "completed_habits": dashboard_data["completed_habits"],
                "completed_today_count": dashboard_data["completed_today_count"],
                "log_entries": recent_notes,
            },
        )


# -------------------
# Habits: Create
# -------------------
@router.get("/habits/new", response_class=HTMLResponse)
async def new_habit_form(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(
        "new_habit.html",
        {
            "request": request,
            "current_user": current_user,
            "forge_state": current_user.forge_state.lower(),
        },
    )


@router.post("/habits/new")
async def create_habit_form(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    name: Annotated[str, Form(...)],
    frequency: Annotated[Optional[str], Form()] = "daily",
):
    if not name.strip():
        return templates.TemplateResponse(
            "new_habit.html",
            {
                "request": request,
                "error": "Please enter a ritual name.",
                "current_user": current_user,
                "forge_state": current_user.forge_state.lower(),
            },
        )

    habit_data = HabitCreate(name=name.strip(), frequency=frequency or "daily")
    new_habit = Habit.model_validate(habit_data, update={"user_id": current_user.id})
    session.add(new_habit)
    session.commit()
    session.refresh(new_habit)
    return RedirectResponse(url="/web/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# -------------------
# Forge Notes (THIS IS THE NEW SECTION YOU WERE LOOKING FOR)
# -------------------
@router.get("/notes/new", response_class=HTMLResponse)
async def get_new_note_form(request: Request, current_user: CurrentUser):
    """
    Shows the form for writing a new "Honest Note".
    """
    return templates.TemplateResponse(
        "new_note.html",
        {
            "request": request,
            "current_user": current_user,
            "forge_state": current_user.forge_state.lower(),
        },
    )


@router.post("/notes/new")
async def handle_new_note_form(
    session: SessionDep,
    request: Request,  # <-- Added request for error template
    current_user: CurrentUser,
    content: Annotated[str, Form(...)],
):
    """
    Saves the "Honest Note" to the database.
    This is called by the Day 0 form.
    """
    if not content.strip():
        return templates.TemplateResponse(
            "new_note.html",
            {
                "request": request,
                "current_user": current_user,
                "forge_state": current_user.forge_state.lower(),
                "error": "Your note cannot be empty.",
            },
            status_code=400,
        )

    # --- ENCRYPT THE DATA ---
    encrypted_content = encrypt_data(content)

    # 2. Save the *encrypted* note
    assert current_user.id is not None, "User must be logged in with an ID"
    new_note = ForgeNote(
        content=encrypted_content,  # <-- Save the encrypted version
        user_id=current_user.id,
    )
    session.add(new_note)

    # --- "Level Up" Logic ---
    if current_user.forge_state == "Ash" and current_user.forge_progress == 0:
        current_user.forge_progress = 1

        # Create the next day's ritual
        next_ritual_name = JOURNEY_RITUALS[1]  # "Day 1: The Ember"
        next_ritual = Habit(
            name=next_ritual_name, frequency="once", user_id=current_user.id
        )
        session.add(next_ritual)
        session.add(current_user)
        print(
            f"User {current_user.username} advanced to Day 1. Creating ritual: {next_ritual_name}"
        )

    session.commit()

    return RedirectResponse(url="/web/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# -------------------
# Feedback
# -------------------
@router.get("/feedback", response_class=HTMLResponse)
async def get_feedback_form(
    request: Request,
    info: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    return templates.TemplateResponse(
        "feedback.html",
        {
            "request": request,
            "info": info,
            "current_user": current_user,
            "forge_state": current_user.forge_state.lower() if current_user else "ash",
        },
    )


@router.post("/feedback")
async def handle_feedback_form(
    session: SessionDep,
    request: Request,
    message: Annotated[str, Form(...)],
    page: Annotated[Optional[str], Form()] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    feedback = Feedback(
        message=message, page=page, user_id=current_user.id if current_user else None
    )
    session.add(feedback)
    session.commit()
    return RedirectResponse(
        url="/web/feedback?info=success", status_code=status.HTTP_303_SEE_OTHER
    )


# --- (Password Reset Routes are disabled) ---

# --- ADD THIS LINE AT THE VERY BOTTOM ---
router_slash.include_router(router)
