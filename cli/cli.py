from typing import Annotated, Optional
import typer

# Import all our safe functions and ui components
from api_client import (
    safe_list_habits,
    safe_create_habit,
    safe_delete_habit,
    safe_update_habit,
)
import ui

app = typer.Typer(help="HabitForge CLI - Manage your habits from the terminal.")


# --- NEW: Define a common User ID option ---
# We make this a require option for all commands.
# This is our temporary "login"
UserIDOption = Annotated[
    int,
    typer.Option(
        ...,  # The '...' makes it required
        "--user-id",
        "-u",
        help="The ID of the user to perform the action for.",
        envvar="HABIT_USER_ID",
    ),
]


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Main entrypoint. Shows welcome message or runs a command.
    """
    if ctx.invoked_subcommand is None:
        ui.show_welcome()


@app.command("list")
def list_all(
    user_id: UserIDOption,  # <-- NEW
    api_url: Optional[str] = typer.Option(
        None, "--api-url", help="Override API base URL"
    ),
):
    """
    List all habits in the database.
    """
    result = safe_list_habits(user_id=user_id, base_url=api_url)

    if result["ok"]:
        ui.render_habit_table(result["data"])
    else:
        ui.show_error(f"Failed to fetch habits: {result['error']}")


@app.command("add")
def add(
    user_id: UserIDOption,  # <-- NEW
    # Use 'name' to match our API
    name: str = typer.Argument(..., help="The name of the habit to create."),
    # Add a 'frequency' option
    frequency: str = typer.Option(
        "daily",
        "--freq",
        "-f",
        help="The frequency of the habit (e.g., 'daily', 'weekly').",
    ),
    api_url: Optional[str] = typer.Option(
        None, "--api-url", help="Override API base URL"
    ),
):
    """
    Add a new habit to the database.
    """

    # --- THIS IS THE KEY FIX ---
    # Call the correct function with the correct keyword arguments
    result = safe_create_habit(
        user_id=user_id, name=name, frequency=frequency, base_url=api_url
    )
    # ---------------------------

    if result["ok"]:
        ui.render_create_habit(result["data"])
    else:
        ui.show_error(f"Failed to create a new habit: {result['error']}")


@app.command("delete")
def delete(
    user_id: UserIDOption,  # <-- NEW
    id: int = typer.Argument(..., help="The ID of the habit to delete."),
    api_url: Optional[str] = typer.Option(
        None, "--api-url", help="Override API base URL"
    ),
):
    """
    Delete a habit from the database.
    """
    result = safe_delete_habit(id=id, user_id=user_id, base_url=api_url)

    if result["ok"]:
        ui.render_delete_habit(result["data"]["message"])
    else:
        ui.show_error(f"Failed to delete habit: {result['error']}")


@app.command("update")
def update(
    user_id: UserIDOption,  # <-- NEW
    id: int = typer.Argument(..., help="ID of the habit to update."),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="The new name of the habit."
    ),
    frequency: Optional[str] = typer.Option(
        None, "--freq", "-f", help="The new frequency of the habit."
    ),
    api_url: Optional[str] = typer.Option(
        None, "--api-url", help="Override API base URL"
    ),
):
    """
    Update a habit's details in the database.
    """
    # Check that the user actually provided something to update
    if name is None and frequency is None:
        ui.show_error("You must provide a --name or --freq to update.")
        raise typer.Exit(code=1)

    result = safe_update_habit(
        id=id, user_id=user_id, name=name, frequency=frequency, base_url=api_url
    )

    if result["ok"]:
        ui.render_update_habit(result["data"])
    else:
        ui.show_error(f"Failed to update habit: {result['error']}")


if __name__ == "__main__":
    app()
