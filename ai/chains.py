"""Reusable LangChain pipelines with lightweight middleware tracing."""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from langchain_core.runnables import RunnableLambda


@dataclass
class MiddlewareTrace:
    """Execution trace shared by every chain step."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def wrap(self, step_name: str, handler: Callable[[dict], dict]):
        def invoke(payload: dict) -> dict:
            started = perf_counter()
            self.events.append({"step": step_name, "status": "started"})
            try:
                result = handler(payload)
                elapsed = round(perf_counter() - started, 3)
                self.events.append({
                    "step": step_name,
                    "status": "completed",
                    "seconds": elapsed,
                })
                return result
            except Exception as error:
                elapsed = round(perf_counter() - started, 3)
                self.events.append({
                    "step": step_name,
                    "status": "failed",
                    "seconds": elapsed,
                    "error": str(error),
                })
                raise

        return RunnableLambda(invoke)


def build_performance_chain(collect, analyze, render_pdf, persist):
    """Build the collect -> analyze -> PDF -> save report pipeline."""
    trace = MiddlewareTrace()
    chain = (
        trace.wrap("collect student signals", collect)
        | trace.wrap("analyze with Groq", analyze)
        | trace.wrap("render PDF report", render_pdf)
        | trace.wrap("save report history", persist)
    )
    return chain, trace


def run_middleware_step(trace, step_name, handler):
    """Run one UI workflow step through the shared middleware tracer."""
    step = trace.wrap(
        step_name,
        lambda payload: {"value": handler(payload)},
    )
    return step.invoke({})["value"]
