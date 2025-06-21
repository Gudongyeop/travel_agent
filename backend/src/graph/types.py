from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Set

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

TEAM_MEMBERS = ["calendar", "search", "sharing", "travel_planner"]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal["calendar", "search", "sharing", "travel_planner", "FINISH"]


class WorkflowMetadata(TypedDict):
    """워크플로우 메타데이터"""

    workflow_id: str
    user_id: str
    thread_id: str
    created_at: datetime
    step_count: int


class ExecutionStatus(TypedDict):
    """실행 상태 정보"""

    current_step: str
    completed_steps: Set[str]
    failed_steps: Set[str]
    is_completed: bool
    error_message: Optional[str]


class TravelPlannerState(TypedDict):
    """상태 관리를 위한 중앙화된 TypedDict 정의"""

    # 대화 기록 - LangGraph의 메시지 관리 사용
    messages: Annotated[List[BaseMessage], add_messages]

    # 워크플로우 설정
    TEAM_MEMBERS: List[str]
    search_before_planning: bool

    # 실행 상태 - 개선된 상태 관리
    next: str
    full_plan: Optional[str]
    execution_status: ExecutionStatus

    # 메타데이터 - 구조화된 메타데이터
    metadata: WorkflowMetadata

    # 결과 캐시 - 중복 방지를 위한 결과 캐싱
    agent_results: Dict[str, Any]
    processed_message_ids: Set[str]


# 기존 State 호환성을 위해 유지
State = TravelPlannerState
