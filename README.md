# Destination Finder

Destination Finder is a small machine-learning project that recommends travel destinations from a user's preferences. It includes a PyTorch model, a training script, a FastAPI endpoint, a browser-based questionnaire, and an interactive terminal questionnaire.

## Features

- Collects eight preferences: budget, climate, travel months, urban/rural setting, terrain, quiet/exciting preference, activities, and interest in folk legends.
- Encodes answers into a 30-feature `float32` PyTorch tensor.
- Scores destinations with a trained neural network.
- Filters out destinations whose listed cost is above the user's budget.
- Offers both a web interface and a terminal interface.
- Protects the API endpoint with an API key supplied through an environment variable.

## Project layout

```text
classification/
├── api/
│   ├── __init__.py
│   ├── api.py                 # FastAPI application and recommendation endpoint
│   └── parse_response.py      # Pydantic input schema and tensor conversion
├── schema/
│   ├── choices.txt            # Urban/rural numeric encoding note
│   └── questions.md           # Questionnaire outline
├── terminal/
│   └── terminal_ui.py         # Interactive terminal questionnaire
├── website/
│   ├── index.html             # Browser interface
│   ├── script.js              # Questionnaire behaviour and API request
│   └── style.css              # Website styling
├── destination_model.pt       # Trained model checkpoint and destination metadata
├── model.py                   # Model architecture, data loading, prediction
├── train_model.py             # Synthetic-user generation and model training
├── training_data.csv          # Destination profiles used for training
└── requirements.txt           # Python package dependencies
```

The distributed ZIP may omit `website/resources/` and `website/resources_backup/`. The HTML references images under `/website/resources/`; restore the `resources` directory if you want those option images to appear.

## Requirements

- Python 3.10 or newer is recommended because the code uses modern type-union syntax.
- Install the packages listed in `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

- The API server command below uses Uvicorn.

The project uses PyTorch, NumPy, Pydantic, FastAPI, Rich, and beartype. `beartype` is used by the terminal interface.

## Run the terminal application

From the project root:

```bash
python terminal/terminal_ui.py
```

Answer the eight questions. For multiple-choice questions, enter the displayed option numbers separated by commas, or enter `all` where the prompt allows it. The terminal summarizes the answers and asks the model for recommendations. It then offers to run another recommendation.

## Run the web application and API

The API reads its secret from the `API_KEY` environment variable when `api/api.py` is imported. Set it before starting the server.

Linux / macOS / Termux:

```bash
export API_KEY='replace-this-with-a-long-random-secret'
uvicorn api.api:app --host 127.0.0.1 --port 8000
```

Open the website at:

```text
http://127.0.0.1:8000/website/
```

The browser sends a `POST` request to `/recommend-destination` and supplies the entered password in the `x-api-key` request header. The password is compared with `API_KEY` by the API. The endpoint returns a JSON object with the key `recommended-destination`.

For access from another device on your local network, the server may be bound to `0.0.0.0` instead of `127.0.0.1`. Only do this on a network you trust, and use HTTPS plus an appropriate secret-management setup before exposing the service beyond local development.

### API request shape

The endpoint is:

```text
POST /recommend-destination
Content-Type: application/json
x-api-key: <your API_KEY>
```

Example JSON body:

```json
{
  "budget": 25000,
  "climate": [0, 2],
  "months": [1, 3, 5],
  "urban_or_rural": "urban",
  "terrain": [0, 2],
  "quiet_or_exciting": "exciting",
  "activities": [1, 2],
  "folk_legends": true
}
```

The numeric selections are indices defined by the questionnaire:

- Climate: `0` Tropical, `1` Dry, `2` Temperate, `3` Continental, `4` Polar.
- Months: integers `1` through `12`, where `1` is January.
- Terrain: `0` Beaches, `1` Forests, `2` Mountains, `3` Plains.
- Activities: `0` Surfing, `1` Hiking, `2` Camping, `3` Just roaming around, `4` Swimming.
- Urban/rural: `"urban"` or `"rural"`.
- Quiet/exciting: `"quiet"` or `"exciting"`.
- Folk legends: `true` or `false`.

The budget is in INR and must be at least 7,000. The multi-select fields must each contain at least one valid option.

## Input tensor format

`UserResponse.to_tensor()` converts validated answers into a tensor of shape `(1, 30)` and dtype `torch.float32`. The feature order must remain identical during training and inference:

| Feature group | Width | Encoding |
|---|---:|---|
| Budget | 1 | Raw budget in INR; `DestinationNet.forward()` applies logarithmic scaling |
| Climate | 5 | Multi-hot vector in climate option order |
| Months | 12 | Multi-hot vector for months 1–12 |
| Urban/rural | 1 | Urban = 0, rural = 1 |
| Terrain | 4 | Multi-hot vector in terrain option order |
| Quiet/exciting | 1 | Quiet = 0, exciting = 1 |
| Activities | 5 | Multi-hot vector in activity option order |
| Folk legends | 1 | False = 0, true = 1 |
| **Total** | **30** | |

The terminal converts its numeric single-choice answers into the string values expected by `UserResponse`, then delegates tensor construction to `UserResponse.to_tensor()`. Keep this conversion in one place to avoid differences between the terminal and API.

## Model and prediction

`model.py` contains:

- `load_destinations()`, which reads destination records from `training_data.csv`.
- `DestinationNet`, a feed-forward neural network that scores each destination.
- `_load_model()`, which loads `destination_model.pt` and caches the loaded model.
- `predict()`, which accepts a tensor, checks its shape, scores destinations, filters out destinations above the user's budget, and returns up to five recommendation strings by default.

If no destination is affordable, `predict()` returns an empty list.

The checkpoint stores the trained model weights and the destination name, country, and cost metadata used to interpret the model's output.

## Train the model

From the project root:

```bash
python train_model.py
```

The training script reads destination profiles from `training_data.csv`. The file contains destination records, not real user-response examples. To train the classifier, the script generates synthetic user preference vectors from those destination profiles, trains the network, prints loss periodically, reports top-1 / top-5 / top-10 evaluation hit rates on generated examples, and saves the checkpoint to `destination_model.pt`.

The evaluation figures are measured on generated synthetic examples. They should not be interpreted as verified recommendation accuracy for real users.

Training settings such as epoch count, synthetic users per destination, batch size, learning rate, and random seed are defined near the top of `train_model.py`.

## Configuration and data

- `training_data.csv` is the source of destination profiles and estimated costs.
- `destination_model.pt` is the trained checkpoint used for inference.
- `API_KEY` is required to start the API application.
- `MIN_BUDGET` and the terminal colour palette are configured in `terminal/terminal_ui.py`.
- The model's feature counts and budget scaling constant are defined in `model.py`.

After changing the destination dataset or model architecture, retrain the model so `destination_model.pt` matches the current code and data.

## Current limitations and operational notes

- Training uses generated synthetic users because the CSV contains destination profiles rather than labelled real-user preference examples.
- Recommendation quality therefore depends on the assumptions in `train_model.py` and the quality and coverage of `training_data.csv`.
- The listed destination costs are used as an affordability filter; they are not live travel prices.
- The API key check is a simple shared-secret comparison. It is suitable as a basic access gate for local use, not a complete production authentication system.
- The website and API are designed to be served from the same origin because the browser uses the relative endpoint `/recommend-destination`.
- The website image assets are not included if the `resources` directories were excluded from the archive.

## License and credits

See the [LICENSE](LICENSE.md) file for licensing terms.
