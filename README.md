# arxiv2product

`arxiv2product` is a multi-agent pipeline designed to generate product ideas from arXiv papers. It ingests research papers, analyzes their technical primitives, maps them to market pain points, and synthesizes robust product concepts using a suite of specialized AI agents.

## Features

The pipeline runs through several intensive phases to extract maximum value from research:

1. **Extraction**: A Decomposer agent extracts all atomic technical primitives from the paper.
2. **Parallel Ideation**:
   - **Pain Scanner**: Searches the web for real, current market pain mapping to the primitives.
   - **Infrastructure Inverter**: Identifies second-order problems created by the technique's adoption.
   - **Temporal Arbitrage**: Identifies near-term windows of opportunity and industry trends.
3. **Cross-Pollination**: Forces non-obvious combinations between technical primitives and market pains.
4. **Red Teaming**: A Destroyer agent attempts to tear down every product idea to find weaknesses.
5. **Synthesis**: Synthesizes surviving ideas into a final, ranked list of the best product concepts.

The web search layer now routes between Serper and Exa automatically: Serper is preferred for fresh/current facts, while Exa Fast is preferred for low-latency discovery. The final Markdown report also includes supporting sources captured during search-heavy phases.

## Installation

This project uses `uv` for dependency management. Ensure you have modern Python (>=3.13) and `uv` installed.

```bash
# Clone the repository and navigate to it
cd arxiv2product

# Sync dependencies and create a virtual environment
uv sync
```

## Configuration

Before running the pipeline, set the necessary environment variables for the agent backend and web search capabilities:

```bash
export AGENTICA_API_KEY="your_agentica_api_key_here"
export SERPER_API_KEY="your_serper_api_key_here"  # Preferred for freshness-sensitive lookups
export EXA_API_KEY="your_exa_api_key_here"        # Preferred for low-latency discovery
export SEARCH_PROVIDER_MODE="auto"                # Optional: auto, serper, or exa
export SEARCH_MAX_CALLS_PER_AGENT="2"             # Optional: cap search tool calls per agent
export SEARCH_ENABLE_FALLBACK="0"                 # Optional: keep disabled for speed
export PIPELINE_SPEED_PROFILE="balanced"          # Optional: balanced or exhaustive
export AGENT_PHASE_TIMEOUT_SECONDS="180"          # Optional: hard timeout per agent call
export ENABLE_REDTEAM_SEARCH="0"                  # Optional: keep red-team offline for speed
export ENABLE_AGENT_LOGS="0"                      # Optional: disable Agentica listener/log shutdown path
```

## Usage

You can run the pipeline by providing an arXiv ID or an AlphaXiv URL. Optionally, you can specify a specific model to use (defaulting to the specified fallback or configured default).

**Using `uv` with Python modules:**
```bash
uv run python main.py 2603.09229
uv run python -m arxiv2product 2603.09229
```

**Using the installed CLI command:**
```bash
uv run arxiv2product 2603.09229
```

**With a model override and URLs:**
```bash
uv run python main.py https://alphaxiv.org/abs/2603.09229 anthropic/claude-sonnet-4
uv run arxiv2product 2603.09229 openrouter:google/gemini-2.5-pro
```

## Project Structure

- `main.py`: Compatibility wrapper script for the CLI.
- `arxiv2product/`: Core package containing the pipeline logic.
  - `cli.py`: CLI arguments parser and entry point.
  - `pipeline.py`: Orchestrates the agents, phase timing, compact contexts, and runtime speed profile.
  - `ingestion.py`: Handles downloading and parsing arXiv PDFs.
  - `prompts.py`: Defines the system prompts for the various agents.
  - `reporting.py`: Formats the final output into a Markdown report.
  - `models.py`: Data models and structured payloads.
  - `research.py`: Search routing, provider adapters, and source capture for report citations.

## Output

The pipeline will save the final analysis locally as a Markdown file named after the arXiv ID, e.g., `products_2603_09229.md`. Search-heavy sections include supporting sources when external search results were used. In the default balanced profile, phase 1 gets the full paper context, downstream phases use a compact digest, search budgets are capped, and red-team search is disabled unless explicitly enabled.
