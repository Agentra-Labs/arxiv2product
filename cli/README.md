# arxiv2product CLI

This is the Python app for the repository. It contains:

- the report-generation pipeline
- the HTTP API service
- the feedback scoring logic
- the Python tests

## Setup

```bash
cd cli
uv sync
```

## Run the pipeline

```bash
uv run arxiv2product 2603.09229
uv run python main.py 2603.09229
```

## Run the API service

```bash
uv run arxiv2product-api
```

The API exposes:

- `GET /health`
- `GET /dashboard/{userId}`
- `POST /reports`
- `GET /reports/{jobId}`
- `POST /feedback/score`

## Tests

```bash
python -m unittest discover -s tests
```

## Environment

Copy `.env.example` to `.env` in this directory if you want local env-file loading.
