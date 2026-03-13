import asyncio
import unittest

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


if __name__ == "__main__":
    unittest.main()
