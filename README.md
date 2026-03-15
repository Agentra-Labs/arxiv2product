# arxiv2product

Transforms arXiv research papers into SaaS product opportunity reports using a multi-agent AI pipeline.

## Setup

```bash
cd cli
uv sync
cp .env.example .env   # fill in your keys
```

## Usage

```bash
cd cli
uv run arxiv2product 2603.09229
uv run arxiv2product https://arxiv.org/abs/2603.09229
uv run arxiv2product-api   # start the local API service
```

## Repository Layout

- `cli/` — Python package, pipeline, API service, and tests
- `logs/` — generated logs (ignored)
- `data/` — generated local data (ignored)

## Notes

- Generated reports and runtime SQLite data stay out of version control.
- Set `EXECUTION_BACKEND=agentica` (default) or `openai_compatible` in `.env`.
