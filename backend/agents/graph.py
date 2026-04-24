"""LangGraph wiring for the SourceMD trust pipeline."""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from backend.agents.nodes.claim_extractor import extract_claims
from backend.agents.nodes.retriever import retrieve_passages
from backend.agents.nodes.scorer import score_claims
from backend.agents.state import PipelineState


@lru_cache(maxsize=1)
def build_graph():
    """Build and compile the 3-node linear trust pipeline.

    START -> extract_claims -> retrieve_passages -> score_claims -> END
    The compiled graph is cached so repeated calls reuse the same instance.
    """
    graph = StateGraph(PipelineState)
    graph.add_node("extract_claims", extract_claims)
    graph.add_node("retrieve_passages", retrieve_passages)
    graph.add_node("score_claims", score_claims)

    graph.add_edge(START, "extract_claims")
    graph.add_edge("extract_claims", "retrieve_passages")
    graph.add_edge("retrieve_passages", "score_claims")
    graph.add_edge("score_claims", END)

    return graph.compile()


def run_pipeline(question: str, ai_answer: str) -> dict:
    """Run the pipeline end to end and return the final state as a dict.

    Returns a dict with keys: claims, retrieved, scored_claims, trust_score,
    corrected_answer.
    """
    app = build_graph()
    initial: PipelineState = {"question": question, "ai_answer": ai_answer}
    result = app.invoke(initial)
    return dict(result)
