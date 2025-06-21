from langgraph.prebuilt import create_react_agent

from ...prompts.template import apply_prompt_template
from ..llm_model import llm
from .tool import share_content, share_travel_plan


def build_sharing_agent(checkpointer):
    return create_react_agent(
        model=llm,
        tools=[share_content, share_travel_plan],
        prompt=lambda state: apply_prompt_template("sharing", state),
        checkpointer=checkpointer,
    )
