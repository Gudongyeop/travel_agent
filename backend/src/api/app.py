import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..config import TEAM_MEMBERS
from ..db import close_db_connect, connect_and_init_db
from ..graph import build_graph
from ..service.history_service import (
    get_grouped_all_history_by_user_id,
    get_grouped_travel_planner_detail_history_by_chat_id,
)
from ..service.workflow_service import run_agent_workflow

# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 생명주기 관리"""
    await connect_and_init_db()
    yield
    await close_db_connect()


# Create FastAPI app
app = FastAPI(
    title="Travel Planner API",
    description="LangGraph 기반 여행 계획 에이전트 API - FastAPI + LangGraph 직접 통합",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for shared plans
# Get the path to shared_plans directory relative to this file
current_dir = Path(__file__).parent  # backend/src/api/
backend_dir = current_dir.parent.parent  # backend/
shared_plans_dir = backend_dir / "shared_plans"
app.mount("/shared", StaticFiles(directory=str(shared_plans_dir)), name="shared")


# Pydantic 모델 정의
class ContentItem(BaseModel):
    """콘텐츠 아이템 모델"""

    type: str = Field(..., description="콘텐츠 타입 (text, image 등)")
    text: Optional[str] = Field(None, description="텍스트 콘텐츠")
    image_url: Optional[str] = Field(None, description="이미지 URL")


class ChatMessage(BaseModel):
    """채팅 메시지 모델"""

    role: str = Field(..., description="메시지 역할 (user 또는 assistant)")
    content: Union[str, List[ContentItem]] = Field(
        ..., description="메시지 내용 (문자열 또는 콘텐츠 아이템 리스트)"
    )


class ChatRequest(BaseModel):
    """채팅 요청 모델"""

    messages: List[ChatMessage] = Field(..., description="대화 기록")
    search_before_planning: Optional[bool] = Field(
        False, description="계획 수립 전 검색 여부"
    )


class ChatHistoryResponse(BaseModel):
    """채팅 히스토리 응답 모델"""

    total_cnt: int = Field(..., description="전체 개수")
    history: List[dict] = Field(..., description="히스토리 데이터")


# 기존 스트리밍 엔드포인트 유지 (호환성을 위해)
@app.post("/api/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest, req: Request, thread_id: str = None, user_id: str = None
):
    """
    스트리밍 채팅 엔드포인트 (기존 호환성 유지)

    Args:
        request: 채팅 요청
        req: FastAPI 요청 객체
        thread_id: 스레드 ID
        user_id: 사용자 ID

    Returns:
        스트리밍 응답
    """
    try:
        # Pydantic 모델을 딕셔너리로 변환하고 콘텐츠 형식 정규화
        messages = []
        for msg in request.messages:
            message_dict = {"role": msg.role}

            # 문자열 콘텐츠와 콘텐츠 아이템 리스트 모두 처리
            if isinstance(msg.content, str):
                message_dict["content"] = msg.content
            else:
                # 콘텐츠 리스트를 워크플로우에서 예상하는 형식으로 변환
                content_items = []
                for item in msg.content:
                    if item.type == "text" and item.text:
                        content_items.append({"type": "text", "text": item.text})
                    elif item.type == "image" and item.image_url:
                        content_items.append(
                            {"type": "image", "image_url": item.image_url}
                        )
                message_dict["content"] = content_items

            messages.append(message_dict)

        async def event_generator():
            """이벤트 생성기"""
            try:
                async with build_graph() as graph:
                    async for event in run_agent_workflow(
                        graph,
                        user_id,
                        thread_id,
                        messages,
                        request.search_before_planning,
                    ):
                        # 클라이언트 연결 상태 확인
                        if await req.is_disconnected():
                            logger.info("Client disconnected, stopping workflow")
                            break

                        yield {
                            "event": event["event"],
                            "data": json.dumps(event["data"], ensure_ascii=False),
                        }
            except asyncio.CancelledError:
                logger.info("Stream processing cancelled")
                raise

        return EventSourceResponse(
            event_generator(),
            media_type="text/event-stream",
            sep="\n",
        )
    except Exception as e:
        logger.error(f"Error in chat stream endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy", "service": "travel-planner-api"}


@app.get("/api/chat/history", response_model=List[dict])
async def get_chat_history(user_id: str, thread_id: str):
    """채팅 히스토리 조회"""
    try:
        history = await get_grouped_travel_planner_detail_history_by_chat_id(
            user_id, thread_id
        )
        return history
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/history/all", response_model=ChatHistoryResponse)
async def get_all_chat_history(user_id: str, page: int = 1, page_size: int = 10):
    """전체 채팅 히스토리 조회"""
    try:
        total_cnt, history = await get_grouped_all_history_by_user_id(
            user_id, page, page_size
        )
        return {"total_cnt": total_cnt, "history": history}
    except Exception as e:
        logger.error(f"Error getting all chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
