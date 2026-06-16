import click
from rich.console import Console
from rich.table import Table
import json
import os
import datetime

console = Console()
DATA_FILE = "log.json"

# Default goals if none are configured in the JSON file yet
DEFAULT_CALORIES = 2900
DEFAULT_PROTEIN = 190


# ==========================================
# DATA & FORMATTING HELPERS
# ==========================================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_today_string():
    """Returns today's date formatted as a string YYYY-MM-DD."""
    return str(datetime.date.today())


def get_day_data(data, date_str):
    """Normalizes old list formats and missing entries into a clean dict structure."""
    day = data.get(date_str, {})
    if isinstance(day, list):
        return {"weight": None, "meals": day}
    if not day:
        return {"weight": None, "meals": []}
    return day


def get_current_goals(data):
    """Fetches user goals from JSON, falling back to defaults if not set."""
    goals = data.get("goals", {})
    # Handle edge case if "goals" exists but is empty or missing specific keys
    cal_goal = goals.get("calories", DEFAULT_CALORIES)
    pro_goal = goals.get("protein", DEFAULT_PROTEIN)
    return cal_goal, pro_goal


def render_meals_table(title, meals):
    """Generates a styled Rich table for a list of meals and returns calculated sums."""
    table = Table(title=title, title_justify="left")
    table.add_column("Meal")
    table.add_column("Calories", justify="right")
    table.add_column("Protein", justify="right")

    total_cal = 0
    total_protein = 0

    for meal in meals:
        table.add_row(meal["name"], str(meal["calories"]), f"{meal['protein']}g")
        total_cal += meal["calories"]
        total_protein += meal["protein"]

    table.add_row("[bold]Total[/bold]", f"[bold]{total_cal}[/bold]", f"[bold]{total_protein}g[/bold]")
    return table, total_cal, total_protein


# ==========================================
# CLI COMMANDS
# ==========================================

@click.group()
def cli():
    pass


@cli.command()
@click.argument("calories", type=int)
@click.argument("protein", type=int)
def goal(calories, protein):
    """Set or change your daily nutritional goals."""
    data = load_data()

    # Store goals at the top-level of the JSON
    data["goals"] = {
        "calories": calories,
        "protein": protein
    }

    save_data(data)
    console.print(
        f"[green]Goals updated successfully![/green] Daily Target: [cyan]{calories} cal[/cyan] | [magenta]{protein}g protein[/magenta]")


@cli.command()
@click.argument("name")
@click.argument("calories", type=int)
@click.argument("protein", type=int)
def log(name, calories, protein):
    """Log a meal for today."""
    data = load_data()
    today_str = get_today_string()

    day_data = get_day_data(data, today_str)
    day_data["meals"].append({"name": name, "calories": calories, "protein": protein})

    data[today_str] = day_data
    save_data(data)
    console.print(f"[green]Logged:[/green] {name} — {calories} cal, {protein}g protein")


@cli.command()
def today():
    """Show everything logged for today."""
    data = load_data()
    today_str = get_today_string()

    day_data = get_day_data(data, today_str)
    meals = day_data["meals"]
    current_weight = day_data["weight"]

    if not meals and not current_weight:
        console.print("[yellow]No logs for today yet.[/yellow]")
        return

    table, total_cal, total_protein = render_meals_table(f"Today — {today_str}", meals)
    console.print(table)

    if current_weight:
        console.print(f"Weight: [yellow]{current_weight} lbs[/yellow]")

    # Fetch dynamically saved goals
    cal_goal, pro_goal = get_current_goals(data)
    console.print(
        f"Remaining: [cyan]{cal_goal - total_cal} cal[/cyan] / {cal_goal} cal | [magenta]{pro_goal - total_protein}g protein[/magenta] / {pro_goal}g")


@cli.command()
@click.argument("name")
def delete(name):
    """Delete a meal from today's log by name."""
    data = load_data()
    today_str = get_today_string()

    day_data = get_day_data(data, today_str)
    meals = day_data["meals"]

    meal_to_remove = next((m for m in meals if m["name"].lower() == name.lower()), None)

    if meal_to_remove:
        meals.remove(meal_to_remove)
        data[today_str] = day_data
        save_data(data)
        console.print(f"[red]Deleted:[/red] {meal_to_remove['name']}")
    else:
        console.print(f"[red]Error:[/red] Could not find any meal named '{name}' today.")


@cli.command()
def history():
    """View full chronological meal history."""
    data = load_data()

    if not data:
        console.print("[yellow]No history found. Start logging some meals![/yellow]")
        return

    # Skip top-level system metadata like "goals" when building history
    for log_date in sorted(data.keys()):
        if log_date == "goals":
            continue

        day_data = get_day_data(data, log_date)
        meals = day_data["meals"]

        if not meals:
            continue

        table, _, _ = render_meals_table(f"Log for {log_date}", meals)
        console.print(table)
        console.print()


@cli.command()
@click.argument("val", type=float)
def weight(val):
    """Log your weight for today."""
    data = load_data()
    today_str = get_today_string()

    day_data = get_day_data(data, today_str)
    day_data["weight"] = val

    data[today_str] = day_data
    save_data(data)
    console.print(f"[green]Logged weight for today:[/green] {val} lbs")


@cli.command()
def progress():
    """Track your historic weight change over time."""
    data = load_data()

    # Filter out metadata like "goals" and find only days that actually have a logged weight
    weight_history = []
    for log_date in sorted(data.keys()):
        if log_date == "goals":
            continue
        day_data = get_day_data(data, log_date)
        if day_data.get("weight") is not None:
            weight_history.append((log_date, day_data["weight"]))

    if not weight_history:
        console.print("[yellow]No weight history found yet. Use 'weight <val>' to log today's weight![/yellow]")
        return

    # Build a clean table to show the trend
    table = Table(title="Weight Tracking History", title_justify="left")
    table.add_column("Date", style="cyan")
    table.add_column("Weight (lbs)", justify="right", style="yellow")

    for log_date, wt in weight_history:
        table.add_row(log_date, f"{wt} lbs")

    console.print(table)


if __name__ == "__main__":
    cli()
