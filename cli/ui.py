from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import print  # Use rich's print for better JSON/dict output

console = Console()


# --- Helper Functions ---
def show_welcome():
    console.print("[bold green]Welcome to the HabitForge CLI[/bold green]")


def show_error(message: str):
    console.print(f"[bold red]{message}[/bold red]")


def show_info(message: str):
    console.print(f"[cyan]{message}[/cyan]")


# --- Render Display ---


def render_habit_table(
    habits: List[Dict[str, Any]], title: Optional[str] = "Habit List"
):
    """
    This is the main "view" function. It takes a list of habit dictionaries
    and render them in a beautiful Rich table.
    """
    if not habits:
        console.print("[yellow]No habits found. Try adding one![/yellow]")
        return

    table = Table(title=title)

    # --- THIS IS THE KEY FIX ---
    # Define columns that match our API model
    table.add_column("ID", justify="right")
    table.add_column("Habit Name", overflow="fold")
    table.add_column("Frequency", justify="center")
    # ---------------------------

    for item in habits:
        # Get data from the API's keys
        habit_id = str(item.get("id"))
        name = item.get("name", "<no name>")
        frequency = item.get("frequency", "<no frequency>")

        table.add_row(habit_id, name, frequency)

    console.print(table)


def render_create_habit(habit: Dict[str, Any]):
    """A simple confirmation view after creating a new habit."""
    console.print("\n[bold green]✅ Habit Created[/bold green]")
    # Use rich's print to auto-format the dictionary
    print(habit)


def render_delete_habit(habit_name: str):
    """A simple confirmation view after deleting a habit."""
    console.print(f"\n[bold red]❌ Habit Deleted: {habit_name}[/bold red]")


def render_update_habit(habit: Dict[str, Any]):
    """A simple confirmation view after updating a habit."""
    console.print("\n[bold blue]Habit updated[/bold blue]")
    print(habit)
