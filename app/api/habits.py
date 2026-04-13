# app/api/habits.py

from typing import List, Annotated, cast
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel, select
from sqlalchemy import asc
from sqlalchemy.sql.elements import ColumnElement
from datetime import datetime, timezone, timedelta, date

from ..db import SessionDep
from ..models import Habit, HabitCreate, HabitRead, User, HabitCompletion, ForgeNote
from ..web_auth import get_current_user_from_cookie  # Use cookie auth
from ..utils import get_habit_stats, get_total_completions_today, compute_streak

router = APIRouter(prefix="/api/habits", tags=["Habits (JSON API)"])
CurrentUser = Annotated[User, Depends(get_current_user_from_cookie)]

# --- Define our journey content ---
# This list stores the "story"
JOURNEY_RITUALS = [
    "Day 0: Write Your 'Honest Note'",  # This one is created at registration
    "Day 1: The Ember",
    "Day 2: The Flame",
    "Day 3: The Smoke",
    "Day 4: The Heat",
    "Day 5: The Hammer",
    "Day 6: The Steel",
]


class NoteCreate(SQLModel):
    text: str


# --- Standard "Headless" API Endpoints ---
# (These are for your CLI or a future mobile app)


@router.post("/", response_model=HabitRead)
async def create_habit_api(
    habit_data: HabitCreate, session: SessionDep, current_user: CurrentUser
):
    """Create a new habit via the JSON API."""
    habit = Habit.model_validate(habit_data, update={"user_id": current_user.id})
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


@router.get("/", response_model=List[HabitRead])
async def read_all_habits_api(session: SessionDep, current_user: CurrentUser):
    """Get a list of all habits for the currently logged-in user."""
    query = select(Habit).where(Habit.user_id == current_user.id)
    habits = session.exec(query).all()
    return habits


# --- Interactive (AJAX) API Endpoints ---


@router.post("/{habit_id}/toggle", response_class=JSONResponse)
async def ajax_toggle_completion(
    habit_id: int, session: SessionDep, current_user: CurrentUser
):
    """
    Toggles a habit's completion and checks for "level ups"
    in the user's journey.
    """
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    if current_user.id is None:  # Type-checking guard
        raise HTTPException(status_code=500, detail="User ID not found")

    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    start_dt = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(
        today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )

    q = select(HabitCompletion).where(
        HabitCompletion.habit_id == habit_id,
        HabitCompletion.completed_at >= start_dt,
        HabitCompletion.completed_at < end_dt,
    )
    today_completion = session.exec(q).first()

    action = ""
    if today_completion:
        # User is "un-doing" a task
        session.delete(today_completion)
        action = "undone"
        # We don't "level down" the user, as that's complex
        # and can be demotivating.

    else:
        # User is completing a task
        new_completion = HabitCompletion(habit_id=habit_id, completed_at=now_utc)
        session.add(new_completion)
        habit.last_completed = now_utc
        session.add(habit)
        action = "done"

        # --- "Level Up" Logic ---
        if current_user.forge_state == "Ash":
            # Check if the habit they just completed is the *correct* one
            if habit.name == JOURNEY_RITUALS[current_user.forge_progress]:

                current_user.forge_progress += 1

                if current_user.forge_progress >= len(JOURNEY_RITUALS):
                    # They've graduated!
                    current_user.forge_state = "Steel"
                    print(f"User {current_user.username} has graduated to 'Steel'")
                else:
                    # Create the *next* day's ritual
                    next_ritual_name = JOURNEY_RITUALS[current_user.forge_progress]
                    next_ritual = Habit(
                        name=next_ritual_name, frequency="once", user_id=current_user.id
                    )
                    session.add(next_ritual)
                    print(
                        f"User {current_user.username} advanced to Day {current_user.forge_progress}. Creating ritual: {next_ritual_name}"
                    )

                session.add(current_user)  # Save progress
        # --- End of "Level Up" Logic ---

    session.commit()  # Commit all changes

    # --- Recompute stats and send them back to the UI ---
    habit_stats = get_habit_stats(session, habit_id, today)
    total_count = get_total_completions_today(session, current_user.id, today)

    return JSONResponse(
        {
            "habit_id": habit_id,
            "action": action,
            "completed_today": habit_stats["completed_today"],
            "streak": habit_stats["streak"],
            "completed_today_count": total_count,
        }
    )


@router.post("/{habit_id}/delete", response_class=JSONResponse)
async def ajax_delete_habit(
    habit_id: int, session: SessionDep, current_user: CurrentUser
):
    """
    Deletes a habit and all its completions.
    """
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != current_user.id:
        return JSONResponse({"error": "not_found"}, status_code=404)

    # Delete completions first
    q = select(HabitCompletion).where(HabitCompletion.habit_id == habit_id)
    for c in session.exec(q).all():
        session.delete(c)

    session.delete(habit)
    session.commit()

    return JSONResponse(
        {
            "habit_id": habit_id,
            "deleted": True,
        }
    )


# --- NEW "SAVE NOTE" ENDPOINT ---
@router.post("/{habit_id}/note", response_class=JSONResponse)
async def ajax_save_note(
    habit_id: int,
    note_data: NoteCreate,  # <-- Use our new Pydantic model
    session: SessionDep,
    current_user: CurrentUser,
):
    """
    Saves a "ForgeNote" (like an Honest Note or reflection)
    and associates it with the user.
    """
    # 1. Check ownership of the *habit* (optional but good)
    habit = session.get(Habit, habit_id)
    if not habit or habit.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Habit not found")

    if current_user.id is None:  # Type-checking guard
        raise HTTPException(status_code=500, detail="User ID not found")

    if not note_data.text.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")

    # 2. Create and save the new note
    new_note = ForgeNote(
        content=note_data.text,
        user_id=current_user.id,
        # We could also link it to the habit_id
        # habit_id=habit_id
    )
    session.add(new_note)

    # 3. Handle "Level Up" logic
    # If this is the Day 0 ritual, completing this note
    # graduates the user to Day 1.
    if current_user.forge_state == "Ash" and current_user.forge_progress == 0:

        # Check if the habit is the Day 0 ritual
        if habit.name == JOURNEY_RITUALS[0]:  # "Day 0: Write Your 'Honest Note'"
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
    session.refresh(new_note)

    return JSONResponse(
        {"success": True, "note_id": new_note.id}, status_code=status.HTTP_201_CREATED
    )
