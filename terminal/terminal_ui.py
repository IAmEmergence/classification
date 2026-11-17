"""Terminal version of the Destination Finder.

Asks the same 8 questions as the website, turns the answers into a
PyTorch tensor, and passes it to predict().

Run from the classification/ folder:
    python terminal_ui.py
"""

# standard library
import math
from dataclasses import dataclass

# third party
import torch
from beartype import beartype
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

# my files
from api.parse_response import UserResponse
from model import predict


# ===== SETTINGS YOU MAY EDIT =====
MIN_BUDGET = 15000
PALETTE = ((255, 92, 108), (255, 196, 69), (18, 181, 165), (91, 63, 217))
# =================================


@beartype
@dataclass(frozen=True)
class Question:
    key: str
    title: str
    text: str
    kind: str  # "number", "single" or "multiple"
    options: tuple = ()  # (value, label) pairs, same values as the website


QUESTIONS = (
    Question(
        key="budget",
        title="Budget",
        text=f"What is your budget? (In INR, minimum {MIN_BUDGET:,}.)",
        kind="number",
    ),
    Question(
        key="climate",
        title="Climate",
        text="Which climates do you enjoy?",
        kind="multiple",
        options=((0, "Tropical"), (1, "Dry"), (2, "Temperate"), (3, "Continental"), (4, "Polar")),
    ),
    Question(
        key="months",
        title="Months",
        text="Which months can you travel?",
        kind="multiple",
        options=(
            (1, "January"), (2, "February"), (3, "March"), (4, "April"),
            (5, "May"), (6, "June"), (7, "July"), (8, "August"),
            (9, "September"), (10, "October"), (11, "November"), (12, "December"),
        ),
    ),
    Question(
        key="urban_or_rural",
        title="Setting",
        text="Do you prefer urban or rural areas?",
        kind="single",
        options=((0, "Urban"), (1, "Rural")),
    ),
    Question(
        key="terrain",
        title="Landscape",
        text="Which landscapes excite you most?",
        kind="multiple",
        options=((0, "Beaches"), (1, "Forests"), (2, "Mountains"), (3, "Plains")),
    ),
    Question(
        key="quiet_or_exciting",
        title="Mood",
        text="Do you prefer quiet or exciting places?",
        kind="single",
        options=((0, "Quiet"), (1, "Exciting")),
    ),
    Question(
        key="activities",
        title="Activities",
        text="Which activities excite you most?",
        kind="multiple",
        options=(
            (0, "Surfing"), (1, "Hiking"), (2, "Camping"),
            (3, "Just roaming around"), (4, "Swimming"),
        ),
    ),
    Question(
        key="folk_legends",
        title="Folk legends",
        text="Do folk legends attract you?",
        kind="single",
        options=((1, "Yes"), (0, "No")),
    ),
)


# ---------- Colours and widgets ----------


@beartype
def colour_at(position: float) -> str:
    """Return a hex colour along the palette. position runs from 0 to 1."""
    scaled = max(0.0, min(position, 1.0)) * (len(PALETTE) - 1)
    index = min(int(scaled), len(PALETTE) - 2)
    fraction = scaled - index
    start, end = PALETTE[index], PALETTE[index + 1]
    return "#" + "".join(f"{round(a + (b - a) * fraction):02x}" for a, b in zip(start, end))


@beartype
def gradient(text: str) -> Text:
    result = Text()
    last = max(len(text) - 1, 1)
    for position, character in enumerate(text):
        result.append(character, style=f"bold {colour_at(position / last)}")
    return result


@beartype
def progress_bar(done: int, total: int, width: int = 32) -> Text:
    filled = round(width * done / total)
    bar = Text()
    for position in range(width):
        if position < filled:
            bar.append("━", style=f"bold {colour_at(position / (width - 1))}")
        else:
            bar.append("━", style="grey27")
    return bar


@beartype
def show_banner(console: Console) -> None:
    body = Group(
        Align.center(gradient("DESTINATION FINDER")),
        Align.center(Text("Eight questions. One perfect place.", style="italic grey70")),
    )
    console.print(Panel(body, box=box.DOUBLE, border_style=colour_at(0.5), padding=(1, 4)))


@beartype
def option_items(
    options: tuple[tuple[int, str], ...]
) -> list[Text]:
    items = []
    for number, (_, label) in enumerate(options, start=1):
        colour = colour_at((number - 1) / max(len(options) - 1, 1))
        item = Text()
        item.append(f" {number:>2} ", style=f"bold black on {colour}")
        item.append(f"  {label}")
        items.append(item)
    return items


@beartype
def hint_for(question: Question) -> str:
    if question.kind == "number":
        return "Type an amount, like 15000."
    if question.kind == "single":
        return "Type one number."
    return "Type numbers separated by commas, like 1, 3. Type all to pick everything."


@beartype
def show_question(console: Console, index: int, question: Question) -> None:
    console.clear()
    show_banner(console)
    console.print(Align.center(progress_bar(index, len(QUESTIONS))))
    console.print(
        Align.center(Text(f"Question {index + 1} of {len(QUESTIONS)}", style="grey70")),
        end="\n\n",
    )

    parts = [Text(question.text, style="bold")]
    if question.options:
        parts += [Text(), Columns(option_items(question.options), padding=(0, 3))]
    parts += [Text(), Text(hint_for(question), style="italic grey58")]

    border = colour_at(index / (len(QUESTIONS) - 1))
    console.print(Panel(Group(*parts), title=question.title, border_style=border, padding=(1, 2)))


# ---------- Reading answers ----------


@beartype
def parse_budget(raw: str) -> float:
    cleaned = raw.replace(",", "").strip()
    try:
        amount = float(cleaned)
    except ValueError:
        raise ValueError("Type a number, like 15000.") from None
    if not math.isfinite(amount):
        raise ValueError("Type a number, like 15000.")
    if amount < MIN_BUDGET:
        raise ValueError(f"The minimum budget is {MIN_BUDGET:,}.")
    return amount


@beartype
def parse_choices(raw: str, question: Question) -> list[int]:
    """Turn typed menu numbers into the option values used by the model."""
    options = question.options
    text = raw.strip().lower()

    if question.kind == "multiple" and text == "all":
        return [value for value, _ in options]

    try:
        numbers = [int(part) for part in text.replace(",", " ").split()]
    except ValueError:
        raise ValueError("Type numbers only, like 1, 3.") from None

    if not numbers:
        raise ValueError("Pick at least one option.")
    if question.kind == "single" and len(numbers) != 1:
        raise ValueError("Pick exactly one option.")
    if any(number < 1 or number > len(options) for number in numbers):
        raise ValueError(f"Choose numbers from 1 to {len(options)}.")

    return [options[number - 1][0] for number in sorted(set(numbers))]


@beartype
def ask(console: Console, question: Question) -> float | int | list[int]:
    """Ask one question until the answer is valid. Returns the answer value."""
    while True:
        raw = Prompt.ask("[bold bright_magenta]›[/]", console=console)
        try:
            if question.kind == "number":
                return parse_budget(raw)
            values = parse_choices(raw, question)
            return values if question.kind == "multiple" else values[0]
        except ValueError as error:
            console.print(f"[bold red]✗ {error}[/] Try again.")


@beartype
def label_for(question: Question, answer: float | int | list[int]) -> str:
    if question.kind == "number":
        return f"INR {answer:,.0f}"
    labels = dict(question.options)
    values = answer if question.kind == "multiple" else [answer]
    return ", ".join(labels[value] for value in values)


@beartype
def collect_answers(console: Console) -> tuple[dict[str, float | int | list[int]], list[tuple[str, str]]]:
    answers = {}
    summary = []

    for index, question in enumerate(QUESTIONS):
        show_question(console, index, question)
        answers[question.key] = ask(console, question)
        summary.append((question.title, label_for(question, answers[question.key])))

    return answers, summary


# ---------- Tensor and prediction ----------


@beartype
def multi_hot(chosen: list[int], question: Question) -> list[float]:
    """One 0/1 slot for every option of the question, in option order."""
    return [1.0 if value in chosen else 0.0 for value, _ in question.options]


@beartype
def build_tensor(
    answers: dict[str, float | int | bool | list[int]],
) -> torch.Tensor:
    """Convert terminal answers into the model input tensor."""

    response = UserResponse.model_validate({
        "budget": answers["budget"],
        "climate": answers["climate"],
        "months": answers["months"],
        "urban_or_rural": (
            "urban" if answers["urban_or_rural"] == 0 else "rural"
        ),
        "terrain": answers["terrain"],
        "quiet_or_exciting": (
            "quiet" if answers["quiet_or_exciting"] == 0 else "exciting"
        ),
        "activities": answers["activities"],
        "folk_legends": bool(answers["folk_legends"]),
    })

    return response.to_tensor()


@beartype
def show_summary(console: Console, summary: list[tuple[str, str]]) -> None:
    table = Table(box=box.SIMPLE_HEAD, show_header=False, border_style="grey35", expand=True)
    table.add_column(style="bold", no_wrap=True)
    table.add_column()
    for title, shown in summary:
        table.add_row(title, shown)

    console.clear()
    show_banner(console)
    console.print(Panel(table, title="Your answers", border_style=colour_at(0.25), padding=(1, 2)))


@beartype
def show_result(console: Console, result: object, tensor: torch.Tensor) -> None:
    if isinstance(result, torch.Tensor):
        result = result.tolist()

    body = Group(
        Align.center(Text(str(result), style=f"bold {colour_at(0.55)}", justify="center")),
        Text(),
        Align.center(Text(f"Model input: tensor of shape {tuple(tensor.shape)}", style="grey50")),
    )
    console.print(
        Panel(body, title="Your destination", box=box.HEAVY, border_style=colour_at(0.55), padding=(1, 2))
    )


@beartype
def run_once(console: Console) -> None:
    answers, summary = collect_answers(console)
    tensor = build_tensor(answers)
    show_summary(console, summary)

    try:
        with console.status("[bold]Finding your destination...", spinner="earth"):
            result = predict(tensor)
    except Exception as error:
        console.print(
            Panel(str(error) or type(error).__name__, title="Prediction failed", border_style="red")
        )
        return

    show_result(console, result, tensor)


@beartype
def main() -> None:
    console = Console()


    try:
        while True:
            run_once(console)
            if not Confirm.ask("\n[bold]Find another destination?[/]", default=False, console=console):
                break
    except (KeyboardInterrupt, EOFError):
        pass

    console.print("\n[bold]Safe travels![/] ✈")


if __name__ == "__main__":
    main()
