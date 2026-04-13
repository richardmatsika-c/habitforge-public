# app/utils.py

from datetime import date, timedelta, datetime, timezone
from typing import Sequence, List, Any, Iterable, cast, Dict
from sqlmodel import Session, select
from sqlalchemy import asc
from sqlalchemy.sql.elements import ColumnElement

from .models import HabitCompletion, Habit, User


def compute_streak(completions: Sequence[HabitCompletion], today_utc: date) -> int:
    """
    Computes the consecutive-day streak ending today (UTC).
    """
    dates = {c.completed_at.date() for c in completions}
    streak = 0
    d = today_utc
    while d in dates:
        streak += 1
        d = d - timedelta(days=1)
    return streak


def extract_scalar_ids(rows: Iterable[Any]) -> List[int]:
    """
    Normalizes various `session.exec(...).all()` return shapes
    into a `List[int]`.
    """
    ids: List[int] = []
    for r in rows:
        if r is None:
            continue
        if isinstance(r, (tuple, list)):
            if len(r) > 0 and r[0] is not None:
                ids.append(int(r[0]))
        else:
            ids.append(int(r))
    return ids


# --- THIS IS THE UPDATED FUNCTION ---
def get_dashboard_stats(session: Session, user: User) -> Dict[str, Any]:
    """
    Fetches and computes all statistics needed for the user's dashboard.
    """
    query = (
        select(Habit)
        .where(Habit.user_id == user.id)
        .order_by(asc(cast(ColumnElement, Habit.created_at)))
    )
    habits = session.exec(query).all()

    today_utc = datetime.now(timezone.utc).date()

    habit_ids = [h.id for h in habits if h.id]
    all_completions_map = {h_id: [] for h_id in habit_ids}

    if habit_ids:
        comp_query = select(HabitCompletion).where(
            cast(ColumnElement, HabitCompletion.habit_id).in_(habit_ids)
        )
        all_completions = session.exec(comp_query).all()
        for comp in all_completions:
            if comp.habit_id in all_completions_map:
                all_completions_map[comp.habit_id].append(comp)

    # --- NEW LOGIC: Create two lists ---
    pending_habits = []
    completed_habits = []
    completed_today_count = 0
    # ----------------------------------

    for habit in habits:
        if habit.id is None:
            continue

        habit_completions = all_completions_map.get(habit.id, [])
        is_done_today = any(
            c.completed_at.date() == today_utc for c in habit_completions
        )

        stat_block = {
            "habit": habit,
            "is_done_today": is_done_today,
            "streak": compute_streak(habit_completions, today_utc),
        }

        # --- NEW LOGIC: Sort into lists ---
        if is_done_today:
            completed_today_count += 1
            completed_habits.append(stat_block)
        else:
            pending_habits.append(stat_block)

    # Return the two new lists
    return {
        "pending_habits": pending_habits,
        "completed_habits": completed_habits,
        "completed_today_count": completed_today_count,
    }


# --- (This function was added in the previous refactor, make sure it's here) ---
def get_habit_stats(session: Session, habit_id: int, today_utc: date) -> Dict[str, Any]:
    """
    Computes the current streak and completion status for a single habit.
    """
    q_all = select(HabitCompletion).where(HabitCompletion.habit_id == habit_id)
    completions = session.exec(q_all).all()

    completed_today = any(c.completed_at.date() == today_utc for c in completions)
    streak = compute_streak(completions, today_utc)

    return {"completed_today": completed_today, "streak": streak}


# --- (This function was added in the previous refactor, make sure it's here) ---
def get_total_completions_today(session: Session, user_id: int, today_utc: date) -> int:
    """
    Computes the total number of habits a user has completed today.
    """
    start_dt = datetime.combine(today_utc, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(
        today_utc + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )

    q_user_habit_ids = select(Habit.id).where(Habit.user_id == user_id)
    user_habit_ids = extract_scalar_ids(session.exec(q_user_habit_ids).all())

    if not user_habit_ids:
        return 0

    q_ct = select(HabitCompletion).where(
        cast(ColumnElement, HabitCompletion.habit_id).in_(user_habit_ids),
        HabitCompletion.completed_at >= start_dt,
        HabitCompletion.completed_at < end_dt,
    )
    return len(session.exec(q_ct).all())
