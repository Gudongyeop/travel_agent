from langgraph.prebuilt import create_react_agent

from ...prompts.template import apply_prompt_template
from ..llm_model import llm


def build_travel_planner_agent(checkpointer):
    return create_react_agent(
        model=llm,
        tools=[],
        prompt=lambda state: apply_prompt_template("travel_planner", state),
        checkpointer=checkpointer,
    )
