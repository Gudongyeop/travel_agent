import re
import time
from typing import Any, Dict, List, Optional

import streamlit as st


def format_message_content(content: Any) -> str:
    """메시지 내용을 적절히 포맷팅"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        formatted = ""
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    formatted += item.get("text", "")
                elif item.get("type") == "image":
                    formatted += f"[이미지: {item.get('image_url', '')}]"
            else:
                formatted += str(item)
        return formatted
    return str(content)


def validate_message_length(message: str, max_length: int = 2000) -> bool:
    """메시지 길이 검증"""
    return len(message.strip()) <= max_length


def clean_message(message: str) -> str:
    """메시지 정리 (불필요한 공백 제거 등)"""
    # 여러 줄바꿈을 2개로 제한
    message = re.sub(r"\n{3,}", "\n\n", message)
    # 앞뒤 공백 제거
    message = message.strip()
    return message


def format_travel_plan(content: str) -> str:
    """여행 계획을 더 읽기 쉽게 포맷팅"""
    # 일차별 계획을 구분하여 표시
    formatted = content

    # 날짜 패턴 감지하여 강조
    date_patterns = [
        r"(\d+일차)",
        r"(Day \d+)",
        r"(\d+일째)",
        r"(\d+월 \d+일)",
        r"(\d{4}-\d{2}-\d{2})",
    ]

    for pattern in date_patterns:
        formatted = re.sub(pattern, r"**\1**", formatted)

    # 시간 패턴 강조
    time_pattern = r"(\d{1,2}:\d{2})"
    formatted = re.sub(time_pattern, r"**\1**", formatted)

    return formatted


def show_typing_effect(text: str, delay: float = 0.05) -> None:
    """타이핑 효과를 보여주는 함수"""
    placeholder = st.empty()
    displayed_text = ""

    for char in text:
        displayed_text += char
        placeholder.markdown(displayed_text)
        time.sleep(delay)


def create_download_link(content: str, filename: str) -> str:
    """다운로드 링크 생성"""
    import base64

    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:text/plain;base64,{b64}" download="{filename}">📥 {filename} 다운로드</a>'
    return href


def extract_itinerary_data(content: str) -> Optional[Dict[str, List[str]]]:
    """여행 일정에서 구조화된 데이터 추출"""
    try:
        itinerary = {}

        # 일차별 계획 추출
        day_pattern = r"(\d+일차|Day \d+|(\d+)일째)"
        sections = re.split(day_pattern, content)

        current_day = None
        for section in sections:
            if re.match(day_pattern, section):
                current_day = section
                itinerary[current_day] = []
            elif current_day and section.strip():
                # 활동 목록 추출
                activities = []
                lines = section.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # 시간 정보와 활동 분리
                        time_match = re.match(r"(\d{1,2}:\d{2})\s*(.+)", line)
                        if time_match:
                            activities.append(
                                f"{time_match.group(1)} - {time_match.group(2)}"
                            )
                        elif line.startswith("-") or line.startswith("•"):
                            activities.append(line[1:].strip())
                        elif line:
                            activities.append(line)

                itinerary[current_day] = activities

        return itinerary if itinerary else None
    except Exception:
        return None


def display_itinerary_timeline(itinerary: Dict[str, List[str]]) -> None:
    """여행 일정을 타임라인 형태로 표시"""
    st.markdown("### 📅 여행 일정 타임라인")

    for day, activities in itinerary.items():
        st.markdown(f"#### {day}")

        for i, activity in enumerate(activities):
            if activity.strip():
                # 시간 정보가 있는지 확인
                time_match = re.match(r"(\d{1,2}:\d{2})\s*-\s*(.+)", activity)
                if time_match:
                    time_str, activity_str = time_match.groups()
                    st.markdown(f"🕐 **{time_str}** - {activity_str}")
                else:
                    st.markdown(f"📍 {activity}")

        if day != list(itinerary.keys())[-1]:  # 마지막 날이 아니면 구분선 추가
            st.markdown("---")


def get_message_stats(messages: List[Dict[str, Any]]) -> Dict[str, int]:
    """대화 통계 정보 반환"""
    stats = {
        "total_messages": len(messages),
        "user_messages": len([m for m in messages if m.get("role") == "user"]),
        "assistant_messages": len(
            [m for m in messages if m.get("role") == "assistant"]
        ),
        "total_characters": sum(
            len(format_message_content(m.get("content", ""))) for m in messages
        ),
    }
    return stats


def export_chat_history(messages: List[Dict[str, Any]]) -> str:
    """채팅 기록을 텍스트 형태로 내보내기"""
    exported = "# 여행 계획 플래너 대화 기록\n\n"
    exported += f"생성일: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    for i, message in enumerate(messages, 1):
        role = "👤 사용자" if message.get("role") == "user" else "🤖 AI 어시스턴트"
        content = format_message_content(message.get("content", ""))

        exported += f"## {i}. {role}\n\n{content}\n\n"
        exported += "---\n\n"

    return exported
