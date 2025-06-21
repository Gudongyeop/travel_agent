from langgraph.prebuilt import create_react_agent

from ...prompts.template import apply_prompt_template
from ..llm_model import llm
from .tool import create_calendar_event, list_upcoming_events


def build_calendar_agent(checkpointer):
    return create_react_agent(
        model=llm,
        tools=[create_calendar_event, list_upcoming_events],
        prompt=lambda state: apply_prompt_template("calendar", state),
        checkpointer=checkpointer,
    )
