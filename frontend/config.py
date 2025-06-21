"""
Frontend configuration
"""

import os
from typing import Any, Dict

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Streamlit 설정
STREAMLIT_CONFIG: Dict[str, Any] = {
    "page_title": "여행 계획 플래너",
    "page_icon": "✈️",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# API 엔드포인트
API_ENDPOINTS = {"chat_stream": "/api/chat/stream"}

# UI 설정
UI_CONFIG = {"max_message_length": 2000, "request_timeout": 30, "typing_delay": 0.05}

# 예시 메시지들
EXAMPLE_MESSAGES = [
    "3박 4일 제주도 여행 계획을 세워줘",
    "서울에서 부산까지 2박 3일 기차여행",
    "가족과 함께하는 경주 1박 2일 역사여행",
    "친구들과 강릉 1박 2일 해변 여행",
    "혼자 떠나는 전주 당일치기 한옥마을 여행",
    "커플과 함께하는 여수 로맨틱 여행",
    "아이들과 함께하는 에버랜드 당일치기",
    "부모님과 함께하는 온천 여행",
]
