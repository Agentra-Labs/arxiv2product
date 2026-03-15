import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from arxiv2product.errors import AgentExecutionError
from arxiv2product.models import PaperContent
from arxiv2product.pipeline import (
    build_compact_paper_context,
    build_full_paper_context,
    gather_agent_calls,
)


class PipelineAsyncTests(unittest.IsolatedAsyncioTestCase):
    def test_compact_context_is_smaller_than_full_context(self):
        paper = PaperContent(
            arxiv_id="2603.09229",
            title="Example",
            authors=["Alice", "Bob"],
            abstract="Abstract",
            full_text="Full text",
            sections={
                "introduction": "intro " * 5000,
                "method": "method " * 5000,
                "results": "results " * 5000,
            },
            figures_captions=["Figure 1"] * 20,
            tables_text=["Table 1"] * 10,
            references_titles=["Reference"] * 30,
        )
        full_context = build_full_paper_context(paper)
        compact_context = build_compact_paper_context(
            paper,
            primitives_summary="primitive summary " * 400,
        )
        self.assertLess(len(compact_context), len(full_context))
        self.assertIn("TECHNICAL PRIMITIVES SUMMARY", compact_context)

    async def test_gather_agent_calls_returns_outputs_when_all_succeed(self):
        async def ok(value: str) -> str:
            return value

        results = await gather_agent_calls(
            {
                "pain scanner": ok("pain"),
                "temporal arbitrage": ok("temporal"),
            }
        )
        self.assertEqual(results["pain scanner"], "pain")
        self.assertEqual(results["temporal arbitrage"], "temporal")

    async def test_gather_agent_calls_raises_single_controlled_error(self):
        async def ok() -> str:
            return "ok"

        async def timeout() -> str:
            raise asyncio.TimeoutError()

        with self.assertRaises(AgentExecutionError) as ctx:
            await gather_agent_calls(
                {
                    "pain scanner": ok(),
                    "temporal arbitrage": timeout(),
                }
            )

        self.assertIn("temporal arbitrage timed out inside Agentica", str(ctx.exception))

    async def test_run_pipeline_uses_agno_backend_by_default(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "arxiv2product.pipeline_agno.run_pipeline_agno",
                new_callable=AsyncMock,
                return_value="products_2603_09229.md",
            ) as run_agno,
        ):
            from arxiv2product.pipeline import run_pipeline

            output = await run_pipeline("2603.09229")

        self.assertEqual(output, "products_2603_09229.md")
        run_agno.assert_awaited_once_with("2603.09229", "anthropic/claude-sonnet-4")

    async def test_run_pipeline_uses_openai_compatible_when_configured(self):
        with (
            patch.dict(os.environ, {"EXECUTION_BACKEND": "openai_compatible"}, clear=True),
            patch("arxiv2product.pipeline.build_openai_compatible_backend", return_value="backend"),
            patch(
                "arxiv2product.pipeline._run_pipeline_with_openai_compatible",
                new_callable=AsyncMock,
                return_value="products_2603_09229.md",
            ) as run_direct,
        ):
            from arxiv2product.pipeline import run_pipeline

            output = await run_pipeline("2603.09229")

        self.assertEqual(output, "products_2603_09229.md")
        run_direct.assert_awaited_once_with("2603.09229", "anthropic/claude-sonnet-4", "backend")


if __name__ == "__main__":
    unittest.main()
