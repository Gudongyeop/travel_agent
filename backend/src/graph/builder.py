import json
import logging
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import AsyncGenerator, Literal

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from ..agents import (
    build_calendar_agent,
    build_search_agent,
    build_sharing_agent,
    build_travel_planner_agent,
)
from ..agents.llm_model import llm
from ..agents.search import tavily_tool
from ..config import MONGO_DB_NAME, MONGO_URI
from ..db import CustomAsyncMongoDBSaver
from ..prompts.template import apply_prompt_template
from .types import Router, State

logger = logging.getLogger(__name__)

RESPONSE_FORMAT = "Response from {}:\n\n<response>\n{}\n</response>\n\n*Please execute the next step.*"


@asynccontextmanager
async def build_graph() -> AsyncGenerator[CompiledStateGraph, None]:
    async with CustomAsyncMongoDBSaver.from_conn_string(
        MONGO_URI,
        db_name=MONGO_DB_NAME,
        checkpoint_collection_name="travel_planner_checkpoint",
        writes_collection_name="travel_planner_history",
    ) as checkpointer:

        calendar_agent = build_calendar_agent(checkpointer)
        search_agent = build_search_agent(checkpointer)
        sharing_agent = build_sharing_agent(checkpointer)
        travel_planner_agent = build_travel_planner_agent(checkpointer)

        async def calendar_node(state: State) -> Command[Literal["supervisor"]]:
            """Node for the calendar agent that performs calendar management tasks."""
            logger.info("Calendar agent starting task")
            result = await calendar_agent.ainvoke(state)
            logger.info("Calendar agent completed task")
            logger.debug(f"Calendar agent response: {result['messages'][-1].content}")
            return Command(
                update={
                    "messages": [
                        AIMessage(
                            content=RESPONSE_FORMAT.format(
                                "calendar", result["messages"][-1].content
                            ),
                            name="calendar",
                        )
                    ]
                },
                goto="supervisor",
            )

        async def search_node(state: State) -> Command[Literal["supervisor"]]:
            """Node for the search agent that performs web search tasks."""
            logger.info("Search agent starting task")
            result = await search_agent.ainvoke(state)
            logger.info("Search agent completed task")
            logger.debug(f"Search agent response: {result['messages'][-1].content}")
            return Command(
                update={
                    "messages": [
                        AIMessage(
                            content=RESPONSE_FORMAT.format(
                                "search", result["messages"][-1].content
                            ),
                            name="search",
                        )
                    ]
                },
                goto="supervisor",
            )

        async def sharing_node(state: State) -> Command[Literal["supervisor"]]:
            """Node for the sharing agent that performs content sharing tasks."""
            logger.info("Sharing agent starting task")
            result = await sharing_agent.ainvoke(state)
            logger.info("Sharing agent completed task")
            logger.debug(f"Sharing agent response: {result['messages'][-1].content}")
            return Command(
                update={
                    "messages": [
                        AIMessage(
                            content=RESPONSE_FORMAT.format(
                                "sharing", result["messages"][-1].content
                            ),
                            name="sharing",
                        )
                    ]
                },
                goto="supervisor",
            )

        async def travel_planner_node(state: State) -> Command[Literal["supervisor"]]:
            """Node for the travel planner agent that performs travel planning tasks."""
            logger.info("Travel planner agent starting task")
            result = await travel_planner_agent.ainvoke(state)
            logger.info("Travel planner agent completed task")
            logger.debug(
                f"Travel planner agent response: {result['messages'][-1].content}"
            )
            return Command(
                update={
                    "messages": [
                        AIMessage(
                            content=RESPONSE_FORMAT.format(
                                "travel_planner", result["messages"][-1].content
                            ),
                            name="travel_planner",
                        )
                    ]
                },
                goto="supervisor",
            )

        async def supervisor_node(state: State) -> Command[
            Literal[
                "calendar",
                "search",
                "sharing",
                "travel_planner",
                "__end__",
            ]
        ]:
            """Supervisor node that decides which agent should act next."""
            logger.info("Supervisor evaluating next action")
            messages = apply_prompt_template("supervisor", state)
            response = await llm.with_structured_output(Router).ainvoke(messages)
            goto = response["next"]
            logger.debug(f"Current state messages: {state['messages']}")
            logger.debug(f"Supervisor response: {response}")

            if goto == "FINISH":
                goto = "__end__"
                logger.info("Workflow completed")
            else:
                logger.info(f"Supervisor delegating to: {goto}")

            return Command(goto=goto, update={"next": goto})

        async def planner_node(
            state: State,
        ) -> Command[Literal["supervisor", "__end__"]]:
            """Planner node that generate the full plan."""
            logger.info("Planner generating full plan")
            messages = apply_prompt_template("planner", state)

            # Add search results if requested
            if state.get("search_before_planning"):
                searched_content = await tavily_tool.ainvoke(
                    {"query": state["messages"][-1].content}
                )
                messages = deepcopy(messages)
                messages[
                    -1
                ].content += f"\n\n# Relative Search Results\n\n{json.dumps([{'title': elem['title'], 'content': elem['content']} for elem in searched_content["results"]], ensure_ascii=False)}"

            # Stream response from LLM
            stream = llm.astream(messages)
            full_response = ""
            async for chunk in stream:
                full_response += chunk.content
            logger.debug(f"Current state messages: {state['messages']}")
            logger.debug(f"Planner response: {full_response}")

            # Clean up JSON formatting
            if full_response.startswith("```json"):
                full_response = full_response.removeprefix("```json")

            if full_response.endswith("```"):
                full_response = full_response.removesuffix("```")

            goto = "supervisor"
            try:
                json.loads(full_response)
            except json.JSONDecodeError:
                logger.warning("Planner response is not a valid JSON")
                # Continue to supervisor instead of ending
                # goto = "__end__"

            return Command(
                update={
                    "messages": [AIMessage(content=full_response, name="planner")],
                    "full_plan": full_response,
                },
                goto=goto,
            )

        async def coordinator_node(
            state: State,
        ) -> Command[Literal["planner", "__end__"]]:
            """Coordinator node that communicate with customers."""
            logger.info("Coordinator talking.")
            messages = apply_prompt_template("coordinator", state)
            response = await llm.ainvoke(messages)
            logger.debug(f"Current state messages: {state['messages']}")
            logger.debug(f"Coordinator response: {response}")

            goto = "__end__"
            if (
                "handoff_to_planner" in response.content
                or "hand_off_to_planner" in response.content
            ):
                goto = "planner"
                logger.info("Coordinator handing off to planner")

            # 항상 coordinator의 응답을 상태에 저장하여 checkpoint에 기록되도록 함
            return Command(
                update={
                    "messages": [
                        AIMessage(
                            content=response.content,
                            name="coordinator",
                        )
                    ]
                },
                goto=goto,
            )

        """Build and return the agent workflow graph."""
        builder = StateGraph(State)
        builder.add_edge(START, "coordinator")
        builder.add_node("coordinator", coordinator_node)
        builder.add_node("planner", planner_node)
        builder.add_node("supervisor", supervisor_node)
        builder.add_node("calendar", calendar_node)
        builder.add_node("search", search_node)
        builder.add_node("sharing", sharing_node)
        builder.add_node("travel_planner", travel_planner_node)
        graph = builder.compile(checkpointer=checkpointer)
        yield graph
