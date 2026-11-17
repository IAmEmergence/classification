"""Model and predict() for the Destination Finder.

The model input is a float tensor of shape (1, 30). The 30 numbers are,
in this order (terminal/terminal_ui.py builds exactly this layout):

    budget (1), climate (5), months (12), urban/rural (1),
    terrain (4), quiet/exciting (1), activities (5), folk legends (1)

Multi-pick questions use one 0/1 slot per option, in option order.
"""

# standard library
import ast
import csv
from functools import lru_cache
from pathlib import Path

# third party
import torch
from torch import nn


BASE_DIR: Path = Path(__file__).resolve().parent
DATA_PATH: Path = BASE_DIR / "training_data.csv"
MODEL_PATH: Path = BASE_DIR / "destination_model.pt"

N_CLIMATES: int = 5
N_MONTHS: int = 12
N_TERRAINS: int = 4
N_ACTIVITIES: int = 5
FEATURE_SIZE: int = 1 + N_CLIMATES + N_MONTHS + 1 + N_TERRAINS + 1 + N_ACTIVITIES + 1 #  30

# log(1,100,000) is about 14, so the scaled budget stays close to 0..1.
LOG_BUDGET_SCALE: float = 14.0


def load_destinations(path: Path = DATA_PATH) -> list[dict]:
    """Read training_data.csv into a list of destination dictionaries."""
    with open(path, newline="", encoding="utf-8") as file:
        return [
            {
                "name": row["destination"],
                "country": row["country"],
                "cost": float(row["cost_inr"]),
                "climate": int(row["climate"]),
                "months": ast.literal_eval(row["best_months"]),
                "urban_rural": int(row["urban_rural"]),
                "terrain": ast.literal_eval(row["features"]),
                "quiet_exciting": int(row["quiet_exciting"]),
                "activities": ast.literal_eval(row["activities"]),
                "folk_legends": int(row["folk_legends"]),
            }
            for row in csv.DictReader(file)
        ]


class DestinationNet(nn.Module):
    """Scores every destination for one user."""

    def __init__(self, n_destinations: int, hidden: int = 256) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(FEATURE_SIZE, hidden),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden, n_destinations),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Budgets range from thousands to lakhs, so scale them on a log curve.
        budget = torch.log1p(x[:, :1].clamp(min=0.0)) / LOG_BUDGET_SCALE
        return self.layers(torch.cat([budget, x[:, 1:]], dim=1))


@lru_cache(maxsize=1)
def _load_model() -> tuple:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No trained model at {MODEL_PATH}. Run: python train_model.py")

    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
    destinations = checkpoint["destinations"]
    model = DestinationNet(len(destinations))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, destinations


@lru_cache(maxsize=100)
def predict(tensor: torch.Tensor, top_k: int = 5) -> list[str]:
    """Return the best destinations the user's budget can afford, best first.

    The list is empty when no destination fits the budget.
    """
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise TypeError("top_k must be a positive integer.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    
    x = tensor.detach().to(torch.float32)
    if x.dim() == 1:
        x = x.unsqueeze(0)
    if tuple(x.shape) != (1, FEATURE_SIZE):
        raise ValueError(f"Expected a tensor of shape (1, {FEATURE_SIZE}), got {tuple(x.shape)}.")

    model, destinations = _load_model()
    with torch.no_grad():
        scores = model(x)[0]

    costs = torch.tensor([destination["cost"] for destination in destinations])
    affordable = costs <= x[0, 0]
    count = min(top_k, int(affordable.sum()))
    if count == 0:
        return []

    best = scores.masked_fill(~affordable, float("-inf")).topk(count).indices.tolist()
    return [
        f"{destinations[i]['name']}, {destinations[i]['country']} (about INR {destinations[i]['cost']:,.0f})"
        for i in best
    ]
