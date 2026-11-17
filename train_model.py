"""Train the destination model.

Run from the classification/ folder:
    python train_model.py

training_data.csv has one row per destination and no real user answers.
So each epoch invents fresh "users" who would be happy with a destination
(they like its climate, can travel in its good months, can afford it, and
so on) and teaches the model to name that destination.
"""

# standard library
import math

# third party
import numpy as np
import torch
from torch import nn

# my files
from model import (
    MODEL_PATH,
    N_ACTIVITIES,
    N_CLIMATES,
    N_MONTHS,
    N_TERRAINS,
    DestinationNet,
    load_destinations,
)


# ===== SETTINGS YOU MAY EDIT =====
EPOCHS: int = 60
USERS_PER_DESTINATION: int = 20  # fresh invented users per destination, per epoch
BATCH_SIZE: int = 512
LEARNING_RATE: float = 2e-3
SEED: int = 7
# =================================


def multi_hot(rows: list, size: int, start: int = 0) -> np.ndarray:
    """One 0/1 slot per option. start is the lowest option number (1 for months)."""
    matrix = np.zeros((len(rows), size), dtype=np.float32)
    for row_number, values in enumerate(rows):
        for value in values:
            if not 0 <= value - start < size:
                raise ValueError(f"Value {value} is out of range in training_data.csv.")
            matrix[row_number, value - start] = 1.0
    return matrix


def build_profiles(destinations: list[dict]) -> dict:
    return {
        "climate": multi_hot([[d["climate"]] for d in destinations], N_CLIMATES),
        "months": multi_hot([d["months"] for d in destinations], N_MONTHS, start=1),
        "urban_rural": np.array([d["urban_rural"] for d in destinations], dtype=np.float32),
        "terrain": multi_hot([d["terrain"] for d in destinations], N_TERRAINS),
        "quiet_exciting": np.array([d["quiet_exciting"] for d in destinations], dtype=np.float32),
        "activities": multi_hot([d["activities"] for d in destinations], N_ACTIVITIES),
        "folk_legends": np.array([d["folk_legends"] for d in destinations], dtype=np.float32),
        "cost": np.array([d["cost"] for d in destinations], dtype=np.float64),
    }


def sample_subset(rng: np.random.Generator, base: np.ndarray) -> np.ndarray:
    """A user's multi-pick answer: some of the destination's options (at least one) plus random extras."""
    keep = base * (rng.random(base.shape) < 0.7)

    empty = keep.sum(axis=1) == 0
    forced = np.argmax(base * rng.random(base.shape), axis=1)
    keep[empty, forced[empty]] = 1.0

    extra = rng.random(base.shape) < 0.15
    return np.maximum(keep, extra).astype(np.float32)


def flip(rng: np.random.Generator, values: np.ndarray, chance: float = 0.05) -> np.ndarray:
    """Occasionally flip a 0/1 answer, so users are not perfectly consistent."""
    return np.where(rng.random(values.shape) < chance, 1.0 - values, values)


def make_users(rng: np.random.Generator, profiles: dict, indices: np.ndarray) -> np.ndarray:
    """Invent one user per destination index. Output shape: (len(indices), 30)."""
    chosen = {key: value[indices] for key, value in profiles.items()}
    size = len(indices)

    folk_chance = np.where(chosen["folk_legends"] == 1, 0.6, 0.05)

    folk = (rng.random(size) < folk_chance).astype(np.float32)

    budget = chosen["cost"] * np.exp(rng.uniform(0.0, math.log(4.0), size))

    columns = [
        budget[:, None],
        sample_subset(rng, chosen["climate"]),
        sample_subset(rng, chosen["months"]),
        flip(rng, chosen["urban_rural"])[:, None],
        sample_subset(rng, chosen["terrain"]),
        flip(rng, chosen["quiet_exciting"])[:, None],
        sample_subset(rng, chosen["activities"]),
        folk[:, None],
    ]
    return np.concatenate(columns, axis=1).astype(np.float32)


def evaluate(model: DestinationNet, rng: np.random.Generator, profiles: dict, count: int) -> dict:
    """Measure top-k accuracy among destinations the user can afford."""
    indices = np.repeat(np.arange(count), 5).astype(np.int64)
    users_np = make_users(rng, profiles, indices)

    users = torch.from_numpy(users_np)
    labels = torch.from_numpy(indices)
    costs = torch.tensor(profiles["cost"], dtype=torch.float32)

    affordable = costs.unsqueeze(0) <= users[:, :1]

    if not affordable.gather(1, labels.unsqueeze(1)).all():
        raise RuntimeError(
            "An evaluation label is unaffordable for its generated user."
        )

    model.eval()
    with torch.no_grad():
        scores = model(users)
        scores = scores.masked_fill(~affordable, float("-inf"))
        ranked = scores.topk(min(10, count), dim=1).indices

    hits = ranked == labels[:, None]
    return {
        k: hits[:, :min(k, ranked.shape[1])].any(dim=1).float().mean().item()
        for k in (1, 5, 10)
    }


def train() -> None:
    destinations = load_destinations()
    count = len(destinations)
    profiles = build_profiles(destinations)

    rng = np.random.default_rng(SEED)
    torch.manual_seed(SEED)

    model = DestinationNet(count)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    loss_function = nn.CrossEntropyLoss()

    print(f"Training on {count} destinations for {EPOCHS} epochs.")

    for epoch in range(1, EPOCHS + 1):
        model.train()
        indices = rng.permutation(np.repeat(np.arange(count), USERS_PER_DESTINATION)).astype(np.int64)
        total_loss = 0.0

        costs = torch.tensor(profiles["cost"], dtype=torch.float32)

        for start in range(0, len(indices), BATCH_SIZE):
            batch = indices[start:start + BATCH_SIZE]
            users_np = make_users(rng, profiles, batch)

            users = torch.from_numpy(users_np)
            labels = torch.from_numpy(batch)

            affordable = costs.unsqueeze(0) <= users[:, :1]

            if not affordable.gather(1, labels.unsqueeze(1)).all():
                raise RuntimeError(
                    "A training label is unaffordable for its generated user."
                )

            optimizer.zero_grad()

            scores = model(users)
            scores = scores.masked_fill(~affordable, float("-inf"))

            loss = loss_function(scores, labels)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(batch)

        if epoch == 1 or epoch % 10 == 0:
            print(f"epoch {epoch:>3}/{EPOCHS}   loss {total_loss / len(indices):.3f}")

    scores = evaluate(model, np.random.default_rng(SEED + 1), profiles, count)
    print(
        f"Chance the right destination is in the top 1 / 5 / 10: "
        f"{scores[1]:.0%} / {scores[5]:.0%} / {scores[10]:.0%}"
    )

    checkpoint = {
        "state_dict": model.state_dict(),
        "destinations": [
            {"name": d["name"], "country": d["country"], "cost": d["cost"]} for d in destinations
        ],
    }
    torch.save(checkpoint, MODEL_PATH)
    print(f"Saved the model to {MODEL_PATH}")


if __name__ == "__main__":
    train()
