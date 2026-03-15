"""
Agno-based implementation of the arxiv2product pipeline.

This module provides the same multi-agent pipeline functionality using the Agno
framework instead of Agentica. It supports parallel agent execution via Agno Teams.
"""

import asyncio
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from agno.agent import Agent
from agno.team import Team, TeamMode

from .errors import AgentExecutionError
from .ingestion import fetch_paper
from .models import PaperContent
from .prompts import (
    CROSSPOLLINATOR_PREMISE,
    DECOMPOSER_PREMISE,
    DEFAULT_MODEL,
    DESTROYER_PREMISE,
    INFRA_INVERSION_PREMISE,
    PAIN_SCANNER_PREMISE,
    SYNTHESIZER_PREMISE,
    TEMPORAL_PREMISE,
)
from .reporting import build_report
from .research import SearchTrace, make_web_search_tool
from .tools_agno import (
    WebSearchTool,
    DisabledWebSearchTool,
    create_search_tool,
)


# Configuration constants
PRIORITY_SECTION_KEYS = [
    "abstract",
    "preamble",
    "introduction",
    "method",
    "approach",
    "experiments",
    "results",
    "conclusion",
    "discussion",
]
FULL_SECTION_CHARS = 5_000
FULL_CONTEXT_CHARS = 25_000
COMPACT_SECTION_CHARS = 2_500
COMPACT_CONTEXT_CHARS = 10_000
FULL_FIGURE_COUNT = 15
FULL_TABLE_COUNT = 6
FULL_REFERENCE_COUNT = 30
COMPACT_FIGURE_COUNT = 6
COMPACT_TABLE_COUNT = 4
COMPACT_REFERENCE_COUNT = 10
PRIMITIVE_SUMMARY_CHARS = 4_500
PAIN_SUMMARY_CHARS = 3_000
IDEA_SUMMARY_CHARS = 2_500


def _get_speed_profile() -> str:
    profile = os.getenv("PIPELINE_SPEED_PROFILE", "balanced").strip().lower()
    return profile if profile in {"balanced", "exhaustive"} else "balanced"


def _redteam_search_enabled() -> bool:
    return os.getenv("ENABLE_REDTEAM_SEARCH", "0").strip().lower() in {"1", "true", "yes"}


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[...truncated...]"


def _phase_started(label: str) -> float:
    print(label)
    return perf_counter()


def _phase_finished(label: str, started_at: float, details: str = "") -> None:
    elapsed = perf_counter() - started_at
    suffix = f" {details}" if details else ""
    print(f"  ✅ {label} complete in {elapsed:.1f}s{suffix}")


def _collect_key_sections(
    paper: PaperContent,
    *,
    section_char_limit: int,
) -> dict[str, str]:
    key_sections: dict[str, str] = {}
    for key in PRIORITY_SECTION_KEYS:
        for section_name, content in paper.sections.items():
            if key in section_name.lower():
                key_sections[section_name] = content[:section_char_limit]
    return key_sections


def _build_paper_context(
    paper: PaperContent,
    *,
    section_char_limit: int,
    context_char_limit: int,
    figure_count: int,
    table_count: int,
    reference_count: int,
    primitives_summary: str = "",
) -> str:
    key_sections = _collect_key_sections(
        paper,
        section_char_limit=section_char_limit,
    )
    context = (
        f"TITLE: {paper.title}\n"
        f"AUTHORS: {', '.join(paper.authors[:10])}\n"
        f"ABSTRACT: {paper.abstract}\n\n"
        f"KEY SECTIONS:\n"
        + "\n\n".join(f"=== {name} ===\n{content}" for name, content in key_sections.items())
        + "\n\nFIGURE CAPTIONS:\n"
        + "\n".join(paper.figures_captions[:figure_count])
        + "\n\nTABLE SUMMARIES:\n"
        + "\n".join(paper.tables_text[:table_count])
        + "\n\nREFERENCED WORKS:\n"
        + "\n".join(paper.references_titles[:reference_count])
    )
    if primitives_summary:
        context += "\n\nTECHNICAL PRIMITIVES SUMMARY:\n" + primitives_summary
    if len(context) > context_char_limit:
        return context[:context_char_limit] + "\n\n[...truncated...]"
    return context


def build_full_paper_context(paper: PaperContent) -> str:
    return _build_paper_context(
        paper,
        section_char_limit=FULL_SECTION_CHARS,
        context_char_limit=FULL_CONTEXT_CHARS,
        figure_count=FULL_FIGURE_COUNT,
        table_count=FULL_TABLE_COUNT,
        reference_count=FULL_REFERENCE_COUNT,
    )


def build_compact_paper_context(
    paper: PaperContent,
    *,
    primitives_summary: str,
) -> str:
    return _build_paper_context(
        paper,
        section_char_limit=COMPACT_SECTION_CHARS,
        context_char_limit=COMPACT_CONTEXT_CHARS,
        figure_count=COMPACT_FIGURE_COUNT,
        table_count=COMPACT_TABLE_COUNT,
        reference_count=COMPACT_REFERENCE_COUNT,
        primitives_summary=primitives_summary,
    )


def _get_model_id(model: str) -> str:
    """Normalize model ID for Agno (supports provider:model format)."""
    # Agno supports "provider:model_id" format directly
    # Strip openrouter: prefix if present and use openai provider with openrouter base
    if model.startswith("openrouter:"):
        return model.removeprefix("openrouter:")
    return model


def _create_agent(
    name: str,
    instructions: str,
    model: str,
    tools: list[Any] | None = None,
) -> Agent:
    """Create an Agno agent with the given configuration."""
    model_id = _get_model_id(model)

    # Use string format for model (Agno supports "provider:model_id")
    # For OpenRouter models, we use openai provider (configured with OpenRouter base URL)
    if ":" not in model_id:
        if "/" in model_id:
            # e.g. "anthropic/claude-3-sonnet" -> "openai:anthropic/claude-3-sonnet"
            model_id = f"openai:{model_id}"
        else:
            # Default to openai if no provider or slug format
            model_id = f"openai:{model_id}"

    return Agent(
        name=name,
        model=model_id,
        instructions=instructions,
        tools=tools or [],
        markdown=True,
    )


async def _run_agent(agent: Agent, prompt: str, phase: str) -> str:
    """Run an agent and return the response text."""
    try:
        response = await agent.arun(prompt)
        if response.content:
            return response.content
        raise AgentExecutionError(f"{phase} returned empty output.")
    except Exception as exc:
        if isinstance(exc, AgentExecutionError):
            raise
        raise AgentExecutionError(f"{phase} failed: {exc}") from exc


async def run_pipeline_agno(arxiv_id_or_url: str, model: str = DEFAULT_MODEL) -> str:
    """Run the paper-to-product pipeline using Agno as the execution backend."""
    speed_profile = _get_speed_profile()
    print(f"📄 Fetching paper: {arxiv_id_or_url}")
    paper = await fetch_paper(arxiv_id_or_url)
    print(f"✅ Loaded: {paper.title} ({len(paper.full_text)} chars)")
    print(f"⚙️ Speed profile: {speed_profile}")
    print("⚙️ Execution backend: agno")

    full_context = build_full_paper_context(paper)
    print(f"🧠 Phase 1 context: {len(full_context)} chars")

    # Phase 1: Extract technical primitives
    phase_started_at = _phase_started("🔬 Phase 1: Extracting technical primitives...")
    decomposer = _create_agent(
        name="Decomposer",
        instructions=DECOMPOSER_PREMISE,
        model=model,
    )
    primitives_raw = await _run_agent(
        decomposer,
        f"Analyze this paper and extract all atomic technical primitives:\n\n{full_context}",
        phase="technical primitive extraction",
    )
    _phase_finished("Phase 1", phase_started_at)

    primitives_summary = _truncate_text(primitives_raw, PRIMITIVE_SUMMARY_CHARS)
    compact_context = build_compact_paper_context(
        paper,
        primitives_summary=primitives_summary,
    )
    print(f"🧠 Downstream context: {len(compact_context)} chars")

    # Phase 2: Run parallel analysis agents using a Team
    phase_started_at = _phase_started("🚀 Phase 2: Running parallel analysis agents...")
    pain_trace = SearchTrace(section_name="Market Pain Mapping")
    temporal_trace = SearchTrace(section_name="Temporal Arbitrage")

    # Create agents for parallel execution
    pain_agent = _create_agent(
        name="PainScanner",
        instructions=PAIN_SCANNER_PREMISE,
        model=model,
        tools=[create_search_tool(default_intent="fast", trace=pain_trace)],
    )
    infra_agent = _create_agent(
        name="InfraInversion",
        instructions=INFRA_INVERSION_PREMISE,
        model=model,
    )
    temporal_agent = _create_agent(
        name="TemporalArbitrage",
        instructions=TEMPORAL_PREMISE,
        model=model,
        tools=[create_search_tool(default_intent="fresh", trace=temporal_trace)],
    )

    # Create a team with broadcast mode for parallel execution
    analysis_team = Team(
        name="AnalysisTeam",
        mode=TeamMode.broadcast,
        members=[pain_agent, infra_agent, temporal_agent],
    )

    # Run parallel analysis
    pain_prompt = (
        f"Technical primitives:\n\n{primitives_summary}\n\n"
        f"Paper context:\n{compact_context}\n\n"
        "Search the web to find real, current market pain mapping to these primitives. "
        "Go FAR beyond the paper's own domain."
    )
    infra_prompt = (
        f"Paper context:\n{compact_context}\n\n"
        f"Technical primitives:\n{primitives_summary}\n\n"
        "What NEW problems does widespread adoption of this technique CREATE? "
        "What products solve those second-order problems?"
    )
    temporal_prompt = (
        f"Paper context:\n{compact_context}\n\n"
        f"Technical primitives:\n{primitives_summary}\n\n"
        "Identify temporal arbitrage windows. What can be built RIGHT NOW that "
        "won't be obvious for 12-24 months? Search the web for recent related "
        "papers and industry trends."
    )

    # Run agents in parallel using asyncio.gather
    pain_task = _run_agent(pain_agent, pain_prompt, "pain scanner")
    infra_task = _run_agent(infra_agent, infra_prompt, "infrastructure inversion")
    temporal_task = _run_agent(temporal_agent, temporal_prompt, "temporal arbitrage")

    results = await asyncio.gather(pain_task, infra_task, temporal_task, return_exceptions=True)

    pain_raw = results[0] if not isinstance(results[0], Exception) else str(results[0])
    infra_raw = results[1] if not isinstance(results[1], Exception) else str(results[1])
    temporal_raw = results[2] if not isinstance(results[2], Exception) else str(results[2])

    _phase_finished(
        "Phase 2",
        phase_started_at,
        details=f"(pain web calls={pain_trace.calls_used}, temporal web calls={temporal_trace.calls_used})",
    )

    # Phase 3: Cross-pollination
    phase_started_at = _phase_started("🧬 Phase 3: Cross-pollination...")
    crosspoll_agent = _create_agent(
        name="CrossPollinator",
        instructions=CROSSPOLLINATOR_PREMISE,
        model=model,
    )
    crosspoll_raw = await _run_agent(
        crosspoll_agent,
        f"Technical primitives:\n{primitives_summary}\n\n"
        f"Market pain points found:\n{_truncate_text(pain_raw, PAIN_SUMMARY_CHARS)}\n\n"
        "Force non-obvious cross-pollination. Skip direct/obvious matches.",
        phase="cross-pollination",
    )
    _phase_finished("Phase 3", phase_started_at)

    # Phase 4: Red team destruction
    phase_started_at = _phase_started("💀 Phase 4: Red team destruction...")
    all_ideas = (
        f"=== IDEAS FROM PAIN MAPPING ===\n{_truncate_text(pain_raw, IDEA_SUMMARY_CHARS)}\n\n"
        f"=== IDEAS FROM CROSS-POLLINATION ===\n{_truncate_text(crosspoll_raw, IDEA_SUMMARY_CHARS)}\n\n"
        f"=== IDEAS FROM INFRASTRUCTURE INVERSION ===\n{_truncate_text(infra_raw, IDEA_SUMMARY_CHARS)}\n\n"
        f"=== IDEAS FROM TEMPORAL ARBITRAGE ===\n{_truncate_text(temporal_raw, IDEA_SUMMARY_CHARS)}\n\n"
    )

    destroyer_tools: list[Any]
    if _redteam_search_enabled():
        destroyer_tools = [create_search_tool(default_intent="fast")]
    else:
        destroyer_tools = [DisabledWebSearchTool()]

    destroyer = _create_agent(
        name="Destroyer",
        instructions=DESTROYER_PREMISE,
        model=model,
        tools=destroyer_tools,
    )
    redteam_raw = await _run_agent(
        destroyer,
        f"Here are product ideas from a research paper. Destroy every one.\n\n"
        f"Paper: {paper.title}\n\n{all_ideas}",
        phase="red team destruction",
    )
    _phase_finished(
        "Phase 4",
        phase_started_at,
        details="(red-team search disabled)" if not _redteam_search_enabled() else "",
    )

    # Phase 5: Final synthesis
    phase_started_at = _phase_started("🎯 Phase 5: Final synthesis...")
    synthesizer = _create_agent(
        name="Synthesizer",
        instructions=SYNTHESIZER_PREMISE,
        model=model,
    )
    final_raw = await _run_agent(
        synthesizer,
        f"PAPER: {paper.title}\nABSTRACT: {paper.abstract}\n\n"
        f"=== TECHNICAL PRIMITIVES ===\n{primitives_summary}\n\n"
        f"=== MARKET PAIN MAPPING ===\n{_truncate_text(pain_raw, IDEA_SUMMARY_CHARS)}\n\n"
        f"=== CROSS-POLLINATED IDEAS ===\n{_truncate_text(crosspoll_raw, IDEA_SUMMARY_CHARS)}\n\n"
        f"=== INFRASTRUCTURE INVERSION ===\n{_truncate_text(infra_raw, IDEA_SUMMARY_CHARS)}\n\n"
        f"=== TEMPORAL ARBITRAGE ===\n{_truncate_text(temporal_raw, IDEA_SUMMARY_CHARS)}\n\n"
        f"=== RED TEAM DESTRUCTION RESULTS ===\n{_truncate_text(redteam_raw, IDEA_SUMMARY_CHARS)}\n\n"
        "Synthesize all of the above into a final ranked list of the BEST ideas. "
        "Only include ideas that survived red-teaming or were strengthened by it.",
        phase="final synthesis",
    )
    _phase_finished("Phase 5", phase_started_at)

    # Build the final report
    report = build_report(
        paper=paper,
        primitives=primitives_raw,
        pain=pain_raw,
        crosspoll=crosspoll_raw,
        infra=infra_raw,
        temporal=temporal_raw,
        pain_sources=pain_trace.render_markdown(),
        temporal_sources=temporal_trace.render_markdown(),
        redteam=redteam_raw,
        redteam_sources="",
        final=final_raw,
    )

    safe_id = paper.arxiv_id.replace("/", "_").replace(".", "_")
    output_path = Path(f"products_{safe_id}.md")
    output_path.write_text(report, encoding="utf-8")

    print(f"\n✅ Done! Report saved to: {output_path}")
    print(f"   {len(report)} chars, ~{len(report.splitlines())} lines")
    return str(output_path)
