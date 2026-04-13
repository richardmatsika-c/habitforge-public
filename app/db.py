# app/db.py

from typing import Annotated
from fastapi import Depends
from sqlmodel import SQLModel, Session, create_engine, select
import os
from dotenv import load_dotenv

# --- Imports are now cleaner ---
from .models import User, Habit, HabitCompletion, Feedback, ForgeNote

load_dotenv()

# --------------------------------
#  Engine Setup
# --------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "False").lower() == "true",
    connect_args=connect_args,
)

# --------------------------------
#  Session Dependency
# --------------------------------


def get_session():
    """FastAPI dependency to provide a DB session per request."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

# -------------------------------------
#  Database Initialization Logic
# -------------------------------------


def create_db_tables():
    """
    Create all database tables.
    """
    print("Creating database tables...")
    from .models import User, Habit, HabitCompletion, Feedback, ForgeNote

    SQLModel.metadata.create_all(engine)
    print("Database tables created successfully!")


# --- All seeding functions have been removed ---


# --- THIS IS THE NEW MIGRATION FUNCTION ---
def migrate_existing_users():
    """
    Finds any users with NULL forge_state and graduates them
    to 'Steel' so they don't get stuck in the 'Ash' journey.
    """
    print("Running migration for existing users...")
    with Session(engine) as session:
        try:
            # 1. Find all users who haven't been migrated yet
            query = select(User).where(
                User.forge_state == None
            )  # 'None' maps to 'IS NULL'
            users_to_migrate = session.exec(query).all()

            if not users_to_migrate:
                print("No users to migrate. Database is up to date.")
                return

            print(f"Found {len(users_to_migrate)} existing users to migrate...")

            # 2. "Graduate" them to the main dashboard
            for user in users_to_migrate:
                user.forge_state = "Steel"
                user.forge_progress = 0  # Just to be clean
                session.add(user)

            session.commit()
            print("User migration successful.")

        except Exception as e:
            print(f"Error during user migration: {e}")
            session.rollback()
