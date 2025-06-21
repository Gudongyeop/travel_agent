from langgraph.prebuilt import create_react_agent

from ...prompts.template import apply_prompt_template
from ..llm_model import llm
from .tool import extract_web_content, tavily_tool


def build_search_agent(checkpointer):
    return create_react_agent(
        model=llm,
        tools=[tavily_tool, extract_web_content],
        prompt=lambda state: apply_prompt_template("search", state),
        checkpointer=checkpointer,
    )
