# app/scheduler_jobs.py

import asyncio
import time  # <-- 1. Import the 'time' module
from sqlmodel import Session, select, SQLModel
from datetime import datetime, timezone, timedelta, date
from sqlalchemy.sql.elements import ColumnElement
from typing import cast

from .db import engine
from .models import User, Habit, HabitCompletion
from .email import send_reminder_email

# --- 2. Define our retry settings ---
MAX_RETRIES = 2  # Total attempts (1st try + 1 retry)
RETRY_DELAY_SECONDS = 10  # Wait 10 seconds between retries


async def send_daily_reminders():
    """
    A scheduled job that queries the database and
    sends reminder emails, with a retry mechanism.
    """

    # --- 3. Add the retry loop ---
    for attempt in range(MAX_RETRIES):
        try:
            print(f"\n--- [JOB_RUN] ---")
            print(
                f"Starting 'send_daily_reminders' (Attempt {attempt + 1}/{MAX_RETRIES}) at {datetime.now()}"
            )

            with Session(engine) as session:
                users_query = select(User).where(User.is_active == True)
                users = session.exec(users_query).all()

                print(f"[JOB_RUN] Found {len(users)} active user(s) to check.")

                for user in users:
                    if not user.email:
                        print(
                            f"[JOB_RUN] User '{user.username}' has no email, skipping."
                        )
                        continue

                    habits_query = select(Habit).where(Habit.user_id == user.id)
                    habits = session.exec(habits_query).all()

                    if habits:
                        print(
                            f"[JOB_RUN] User '{user.username}' has {len(habits)} habits. Sending emails..."
                        )
                        email_tasks = []
                        for habit in habits:
                            email_tasks.append(
                                send_reminder_email(
                                    recipient=user.email,
                                    username=user.username,
                                    habit_name=habit.name,
                                )
                            )
                        await asyncio.gather(*email_tasks)

            print(f"[JOB_RUN] 'send_daily_reminders' finished successfully.")
            break  # <-- Success! Exit the retry loop.

        except Exception as e:
            print(
                f"[JOB_ERROR] 'send_daily_reminders' (Attempt {attempt + 1}) failed: {e}"
            )
            if attempt < MAX_RETRIES - 1:
                print(f"[JOB_RETRY] Retrying in {RETRY_DELAY_SECONDS} seconds...")
                await asyncio.sleep(RETRY_DELAY_SECONDS)  # Use asyncio.sleep for async
            else:
                print(
                    f"[JOB_FAIL] 'send_daily_reminders' failed after all {MAX_RETRIES} attempts."
                )

        finally:
            print(f"--- [JOB_END] ---")


async def log_missed_habits_summary():
    """
    Finds all habits that were NOT completed today and logs a
    summary, with a retry mechanism.
    """

    # --- 3. Add the retry loop ---
    for attempt in range(MAX_RETRIES):
        try:
            print(f"\n--- [JOB_RUN] ---")
            print(
                f"Starting 'log_missed_habits_summary' (Attempt {attempt + 1}/{MAX_RETRIES}) at {datetime.now()}"
            )

            with Session(engine) as session:
                today_utc = datetime.now(timezone.utc).date()
                start_dt = datetime.combine(
                    today_utc, datetime.min.time(), tzinfo=timezone.utc
                )
                end_dt = datetime.combine(
                    today_utc + timedelta(days=1),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )

                completed_habits_query = select(HabitCompletion.habit_id).where(
                    HabitCompletion.completed_at >= start_dt,
                    HabitCompletion.completed_at < end_dt,
                )
                completed_habit_ids = set(session.exec(completed_habits_query).all())

                print(
                    f"[JOB_RUN] Found {len(completed_habit_ids)} completed habits for {today_utc}."
                )

                missed_habits_query = (
                    select(Habit, User.username)
                    .join(User)
                    .where(
                        User.is_active == True,
                        cast(ColumnElement, Habit.id).notin_(completed_habit_ids),
                    )
                )
                missed_habits = session.exec(missed_habits_query).all()

                if not missed_habits:
                    print(f"[JOB_RUN] No missed habits today. Great job everyone!")
                else:
                    print(
                        f"[JOB_RUN] Found {len(missed_habits)} missed habits for {today_utc}:"
                    )
                    for habit, username in missed_habits:
                        print(f"  - [MISSED] User '{username}' missed: '{habit.name}'")

                print(f"[JOB_RUN] 'log_missed_habits_summary' finished successfully.")
                break  # <-- Success! Exit the retry loop.

        except Exception as e:
            print(
                f"[JOB_ERROR] 'log_missed_habits_summary' (Attempt {attempt + 1}) failed: {e}"
            )
            if attempt < MAX_RETRIES - 1:
                print(f"[JOB_RETRY] Retrying in {RETRY_DELAY_SECONDS} seconds...")
                # We use 'asyncio.sleep' because this is an async function
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                print(
                    f"[JOB_FAIL] 'log_missed_habits_summary' failed after all {MAX_RETRIES} attempts."
                )

        finally:
            print(f"--- [JOB_END] ---")
