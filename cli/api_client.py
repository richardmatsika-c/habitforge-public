import os
from typing import Any, Dict, List, Optional
import requests
from requests import RequestException, Session

API_URL = os.getenv("HABIT_API_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = 5.0


def session() -> Session:
    """
    This helper function creates a 'Session' object.
    """
    s = requests.Session()
    s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return s


def list_habits(
    user_id: int,  # <-- NEW
    base_url: Optional[str] = None,
    timeout: float = REQUEST_TIMEOUT,
) -> List[Dict[str, Any]]:
    """This is the main function for getting all todos."""
    url = (base_url or API_URL).rstrip("/") + "/habits/"
    params = {"user_id": user_id}  # <-- NEW

    s = session()
    # Pass 'params' to the request
    resp = s.get(url, params=params, timeout=timeout)
    resp.raise_for_status()

    return resp.json()


def create_habit(
    user_id: int,  # <-- NEW
    name: str,  # <-- Renamed from 'habit'
    frequency: str = "daily",  # <-- Renamed from 'done' and given a default
    base_url: Optional[str] = None,
    timeout: float = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    """
    This is the main function for creating a new habit.
    """
    url = (base_url or API_URL).rstrip("/") + "/habits/"
    params = {"user_id": user_id}  # <-- NEW

    # --- THIS IS THE KEY FIX ---
    # The payload must match your API's HabitCreate model
    payload = {"name": name, "frequency": frequency}
    # ---------------------------

    s = session()
    resp = s.post(url, params=params, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def delete_habit(
    user_id: int,  # <-- NEW
    id: int,
    base_url: Optional[str] = None,
    timeout: float = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    """
    This is the main function for deleting a habit.
    """
    url = (base_url or API_URL).rstrip("/") + f"/habits/{id}"
    params = {"user_id": user_id}  # <-- NEW

    s = session()
    resp = s.delete(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# api_client.py
def update_habit(
    user_id: int,
    id: int,
    name: Optional[str],  # <-- Change this to Optional
    frequency: Optional[str],
    base_url: Optional[str] = None,
    timeout: float = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    """
    This is the main function to update a habit.
    """
    url = (base_url or API_URL).rstrip("/") + f"/habits/{id}"
    params = {"user_id": user_id}  # <-- NEW

    # This logic now works for both name and frequency
    payload = {}
    if name is not None:
        payload["name"] = name
    if frequency is not None:
        payload["frequency"] = frequency

    # We should also check if the payload is empty, though the API
    # will just return a 200 OK with no changes.
    # The check in cli.py is the best place to handle this.

    s = session()
    resp = s.patch(url, params=params, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# --- Safe wrapper functions ----


def safe_list_habits(*args, **kwargs):  # <-- Renamed to plural
    """Wrapper function to catch errors that 'list_habits' might raise."""
    try:
        return {"ok": True, "data": list_habits(*args, **kwargs)}
    except (RequestException, ValueError) as e:
        return {"ok": False, "error": str(e)}


def safe_create_habit(*args, **kwargs):
    """Wrapper function to catch errors that 'create_habit' might raise."""
    try:
        return {"ok": True, "data": create_habit(*args, **kwargs)}
    except (RequestException, ValueError) as e:
        return {"ok": False, "error": str(e)}


def safe_delete_habit(*args, **kwargs):
    """Wrapper function to catch errors that 'delete_habit' might raise."""
    try:
        return {"ok": True, "data": delete_habit(*args, **kwargs)}
    except (RequestException, ValueError) as e:
        return {"ok": False, "error": str(e)}


def safe_update_habit(*args, **kwargs):
    """Wrapper function to catch errors that 'delete_habit' might raise."""
    try:
        return {"ok": True, "data": update_habit(*args, **kwargs)}
    except (RequestException, ValueError) as e:
        return {"ok": False, "error": str(e)}
