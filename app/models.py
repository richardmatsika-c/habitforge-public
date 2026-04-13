# app/models.py

from datetime import datetime, timezone, date
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel
from pydantic import EmailStr

# --------------------------------
#  User Models
# --------------------------------


class UserBase(SQLModel):
    """Base properties for a User."""

    username: str = Field(min_length=3, max_length=50, regex="^[a-zA-Z0-9_-]+$")
    email: Optional[EmailStr] = Field(default=None, index=True)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: Optional[EmailStr] = Field(default=None, unique=True, index=True)
    hashed_password: str = Field(min_length=8)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    habits: List["Habit"] = Relationship(back_populates="user")
    # We track their "phase" (Ash, Ember, Steel)
    forge_state: str = Field(default="Ash", index=True)
    # We track their "day" in the current phase
    forge_progress: int = Field(default=0, index=True)


class UserCreate(SQLModel):
    """Input model for creating a User."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    email: Optional[EmailStr] = None


class UserUpdate(SQLModel):
    """Input for updating a User."""

    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)
    is_active: Optional[bool] = None


class UserPublic(SQLModel):
    """Public user data (without sensitive information)."""

    id: int
    username: str
    email: Optional[str] = None
    is_active: bool
    is_superuser: bool
    created_at: datetime


# --------------------------------
#  Habits Models
# --------------------------------


class HabitBase(SQLModel):
    """Shared properties for a Habit."""

    name: str = Field(index=True)
    frequency: str = Field(index=True, default="daily")


class Habit(HabitBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")

    # Optional: A 'denormalized' field for quick checks.
    # The 'HabitCompletion' table is the real source of truth.
    last_completed: Optional[datetime] = Field(default=None, index=True)

    # --- NEW RELATIONSHIPS ---
    user: Optional["User"] = Relationship(back_populates="habits")
    completions: List["HabitCompletion"] = Relationship(back_populates="habit")


# --- THIS IS THE NEW MODEL ---
class HabitCompletion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habit.id", index=True)
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    # Relationship back to the habit
    habit: Optional[Habit] = Relationship(back_populates="completions")


class HabitCreate(HabitBase):
    """Input model for creating a Habit."""

    pass  # inherits name and frequency


class HabitUpdate(SQLModel):
    """Input model for updating a Habit (all fields optional)."""

    name: Optional[str] = None
    frequency: Optional[str] = None


class HabitRead(HabitBase):
    """Output model for reading a Habit (API response)"""

    id: int
    created_at: datetime
    user_id: int


# --------------------------------
#  Token Models
# --------------------------------


class Token(SQLModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(SQLModel):
    """Token payload data (internal)."""

    username: Optional[str] = None
    user_id: Optional[int] = None


# --------------------------------
#  Feedback Models
# --------------------------------
class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str
    page: Optional[str] = Field(default=None)

    # Relationship back to the user (optional, but good)
    user: Optional["User"] = Relationship()


# --------------------------------
#  Forge Note Models
# --------------------------------
class ForgeNote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # We encrypt this field in the database
    # For now, we'll store it as plain text.
    # We can add real encryption later.
    content: str

    user: User = Relationship()
