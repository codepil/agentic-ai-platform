"""
SDLC LangGraph workflow.

Builds and compiles the full state machine that orchestrates the software
development lifecycle from intake through production deployment.

Graph topology
--------------
intake
  └─► requirements
        └─► requirements_approval  ← INTERRUPT
              ├─ approved ──────────► architecture
              ├─ rejected ──────────► requirements  (rework loop)
              └─ escalate ──────────► error_handler
architecture
  └─► dev
        └─► qa
              ├─ passed ────────────► devops
              ├─ retry ─────────────► qa_failed_handler ──► dev
              └─ escalate ──────────► error_handler
devops
  └─► staging_approval  ← INTERRUPT
        ├─ approved ──────────────► deploy_prod  ──► END
        ├─ rejected ──────────────► dev  (fix & redeploy loop)
        └─ escalate ──────────────► error_handler
error_handler ──────────────────────► END
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, END

from ..state.sdlc_state import SDLCState
from .nodes import (
    intake_node,
    requirements_node,
    requirements_approval_node,
    architecture_node,
    dev_node,
    qa_node,
    qa_failed_handler_node,
    devops_node,
    staging_approval_node,
    deploy_prod_node,
    error_handler_node,
)
from .edges.routing import (
    route_after_requirements_approval,
    route_after_qa,
    route_after_staging_approval,
)


def build_sdlc_graph(checkpointer: BaseCheckpointSaver):
    """
    Construct and compile the SDLC LangGraph workflow.

    Parameters
    ----------
    checkpointer:
        A LangGraph checkpoint saver (e.g. ``MemorySaver`` or
        ``MongoCheckpointer``) used for persistence and human-in-the-loop
        interrupts.

    Returns
    -------
    CompiledGraph
        Ready-to-invoke compiled LangGraph state machine.
    """
    builder = StateGraph(SDLCState)

    # ------------------------------------------------------------------
    # Register nodes
    # ------------------------------------------------------------------
    builder.add_node("intake", intake_node)
    builder.add_node("requirements", requirements_node)
    builder.add_node("requirements_approval", requirements_approval_node)
    builder.add_node("architecture", architecture_node)
    builder.add_node("dev", dev_node)
    builder.add_node("qa", qa_node)
    builder.add_node("qa_failed_handler", qa_failed_handler_node)
    builder.add_node("devops", devops_node)
    builder.add_node("staging_approval", staging_approval_node)
    builder.add_node("deploy_prod", deploy_prod_node)
    builder.add_node("error_handler", error_handler_node)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    builder.set_entry_point("intake")

    # ------------------------------------------------------------------
    # Linear edges
    # ------------------------------------------------------------------
    builder.add_edge("intake", "requirements")
    builder.add_edge("requirements", "requirements_approval")
    builder.add_edge("architecture", "dev")
    builder.add_edge("dev", "qa")
    builder.add_edge("qa_failed_handler", "dev")
    builder.add_edge("devops", "staging_approval")
    builder.add_edge("deploy_prod", END)
    builder.add_edge("error_handler", END)

    # ------------------------------------------------------------------
    # Conditional edges
    # ------------------------------------------------------------------
    builder.add_conditional_edges(
        "requirements_approval",
        route_after_requirements_approval,
        {
            "approved": "architecture",
            "rejected": "requirements",
            "escalate": "error_handler",
        },
    )

    builder.add_conditional_edges(
        "qa",
        route_after_qa,
        {
            "passed": "devops",
            "retry": "qa_failed_handler",
            "escalate": "error_handler",
        },
    )

    builder.add_conditional_edges(
        "staging_approval",
        route_after_staging_approval,
        {
            "approved": "deploy_prod",
            "rejected": "dev",
            "escalate": "error_handler",
        },
    )

    # ------------------------------------------------------------------
    # Compile
    # ------------------------------------------------------------------
    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["requirements_approval", "staging_approval"],
    )
    return graph
