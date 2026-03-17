import asyncio
import os
from pathlib import Path
from typing import Optional

import click
import pyfiglet
from dotenv import load_dotenv
from click import Group, command, option, argument, echo

from .errors import AgentExecutionError, AgenticaConnectionError
from .prompts import DEFAULT_MODEL

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PACKAGE_ROOT.parent

load_dotenv(PACKAGE_ROOT / ".env")
load_dotenv(WORKSPACE_ROOT / ".env")


def print_banner() -> None:
    banner = pyfiglet.figlet_format("arxiv2product", font="double_blocky")
    echo(banner)


async def _run_cli(
    arxiv_id_or_url: str,
    model: str,
    save: bool,
    output: Optional[str],
    display: bool,
    quiet: bool,
    search_papers: bool,
) -> None:
    """Generate product ideas from arXiv papers with a multi-agent pipeline."""
    if not quiet:
        print_banner()
        echo(f"📄 Processing: {arxiv_id_or_url}")
        echo(f"⚙️ Model: {model}")

    from .pipeline import run_pipeline

    try:
        report_path = await run_pipeline(
            arxiv_id_or_url,
            model=model,
            save=save,
            output_path=output,
            display=display,
            quiet=quiet,
            search_papers=search_papers,
        )

        if not quiet:
            if save or output:
                echo(f"✅ Report saved to: {report_path}")
            else:
                echo(f"✅ Processing complete: {arxiv_id_or_url}")
    except AgenticaConnectionError as exc:
        echo(f"❌ Agentica connection error: {exc}", err=True)
        raise SystemExit(1) from exc
    except AgentExecutionError as exc:
        echo(f"❌ Agent execution error: {exc}", err=True)
        raise SystemExit(1) from exc


@command()
@argument("arxiv_id_or_url")
@option("--model", default=DEFAULT_MODEL, help="LLM model to use")
@option("--save", is_flag=True, help="Save report to file")
@option("--output", type=click.Path(), help="Output file path")
@option("--display", is_flag=True, help="Display report in terminal")
@option("--quiet", is_flag=True, help="Suppress progress output")
@option(
    "--search-papers",
    is_flag=True,
    help="Enable PASA-style paper search for topic queries",
)
def cli(
    arxiv_id_or_url: str,
    model: str = DEFAULT_MODEL,
    save: bool = False,
    output: Optional[str] = None,
    display: bool = False,
    quiet: bool = False,
    search_papers: bool = False,
):
    """Generate product ideas from arXiv papers with a multi-agent pipeline."""
    asyncio.run(
        _run_cli(arxiv_id_or_url, model, save, output, display, quiet, search_papers)
    )
