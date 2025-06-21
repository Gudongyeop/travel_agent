import json
import re
import uuid
from datetime import datetime

import config
import requests
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="여행 계획 플래너 Agent", page_icon="🤖", layout="wide")

# CSS for blinking effect and improved styling
st.markdown(
    """
    <style>
    .blink { animation: blink 1s step-start infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    
    .chat-history-item {
        padding: 8px;
        margin: 4px 0;
        border-radius: 4px;
        cursor: pointer;
        border: 1px solid #ddd;
        background-color: #f9f9f9;
    }
    .chat-history-item:hover {
        background-color: #e9e9e9;
    }
    .chat-history-item.selected {
        background-color: #007acc;
        color: white;
    }
    .chat-history-message {
        font-size: 12px;
        color: #666;
        margin-top: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .chat-history-time {
        font-size: 10px;
        color: #999;
        margin-top: 2px;
    }
    
    /* 메시지 스타일링 개선 */
    .stChatMessage > div {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
    }
    
    /* 여행지 목록 스타일 */
    .travel-destination {
        background-color: #f0f8ff;
        padding: 0.5rem;
        margin: 0.25rem 0;
        border-left: 4px solid #1f77b4;
        border-radius: 0.25rem;
    }
    
    /* 단계별 진행 상황 스타일 */
    .step-progress {
        background-color: #f9f9f9;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
    }
    
    .step-title {
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 0.25rem;
    }
    
    .step-description {
        color: #7f8c8d;
        font-size: 0.9rem;
    }
    
    /* Agent 작업 단계 스타일 */
    .agent-step {
        background-color: #f8f9fa;
        border-left: 3px solid #6c757d;
        padding: 0.5rem;
        margin: 0.25rem 0;
        border-radius: 0.25rem;
        font-size: 0.9rem;
    }
    
    .agent-step.completed {
        border-left-color: #28a745;
        background-color: #f8fff9;
    }
    
    .agent-step.in-progress {
        border-left-color: #007bff;
        background-color: #f0f8ff;
    }
    
    .agent-step-header {
        font-weight: 600;
        margin-bottom: 0.25rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .agent-icon {
        font-size: 1.1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 시스템 메시지 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
# 여행 계획(JSON) 저장용 상태
if "plan" not in st.session_state:
    st.session_state.plan = None
# 각 step placeholder
if "step_placeholders" not in st.session_state:
    st.session_state.step_placeholders = {}
# 대화 기록 상태
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "total_history_count" not in st.session_state:
    st.session_state.total_history_count = 0
if "selected_thread_id" not in st.session_state:
    st.session_state.selected_thread_id = None


# Backend API URL 설정
backend_url = config.BACKEND_URL


# 메인 헤더와 새 대화 시작 버튼
col1, col2 = st.columns([6, 1])
with col1:
    st.title("🧳 여행 계획 플래너 Agent")
with col2:
    if st.button("🆕 새 대화", use_container_width=True, type="secondary"):
        st.session_state.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        st.session_state.plan = None
        st.session_state.step_placeholders = {}
        st.session_state.selected_thread_id = None
        st.rerun()

# 사용자 ID 입력
if "user_id" not in st.session_state:
    st.session_state.user_id = ""

user_id = st.sidebar.text_input(
    "사용자 ID를 입력하세요:",
    value=st.session_state.user_id,
    placeholder="예: user123",
    help="채팅 세션을 구분하기 위한 사용자 ID입니다.",
)

# Agent 표시 이름 및 아이콘 매핑
AGENT_CONFIG = {
    "search": {
        "name": "정보 검색",
        "icon": "🔍",
        "description": "관련 정보를 검색하고 있습니다",
    },
    "travel_planner": {
        "name": "여행 계획 수립",
        "icon": "🗺️",
        "description": "여행 계획을 세우고 있습니다",
    },
    "sharing": {
        "name": "응답 정리",
        "icon": "📤",
        "description": "최종 응답을 정리하고 있습니다",
    },
    "coordinator": {
        "name": "응답 조정",
        "icon": "🤝",
        "description": "응답을 조정하고 있습니다",
    },
    "planner": {
        "name": "계획 수립",
        "icon": "🤔",
        "description": "전체 계획을 수립하고 있습니다",
    },
}

if user_id:
    st.session_state.user_id = user_id
    st.sidebar.success(f"사용자 ID: {user_id}")

    # 대화 기록 로드 함수
    def load_chat_history(page=1, reset=False):
        if reset:
            st.session_state.chat_history = []
            st.session_state.current_page = 1
            page = 1

        try:
            response = requests.get(
                f"{backend_url}/api/chat/history/all",
                params={"user_id": user_id, "page": page, "page_size": 10},
            )
            if response.status_code == 200:
                data = response.json()
                if reset:
                    st.session_state.chat_history = data["history"]
                else:
                    st.session_state.chat_history.extend(data["history"])
                st.session_state.total_history_count = data["total_cnt"]
                st.session_state.current_page = page
                return True
        except Exception as e:
            st.sidebar.error(f"대화 기록을 불러오는데 실패했습니다: {e}")
        return False

    # 특정 대화 내용 로드 함수
    def load_conversation(thread_id):
        try:
            response = requests.get(
                f"{backend_url}/api/chat/history",
                params={"user_id": user_id, "thread_id": thread_id},
            )
            if response.status_code == 200:
                conversation_data = response.json()
                # 메시지를 시간순으로 정렬
                conversation_data.sort(key=lambda x: x["timestamp"])

                # 기존 메시지 초기화하고 시스템 메시지만 남김
                st.session_state.messages = [
                    {"role": "system", "content": "You are a helpful assistant."}
                ]
                st.session_state.plan = None

                # 메시지들을 그룹별로 처리 (사용자 메시지 -> 관련 응답들)
                message_groups = []
                current_group = None

                # 대화 내용을 파싱하여 그룹으로 묶기
                for msg_data in conversation_data:
                    message_content = msg_data["message"]

                    # 문자열 메시지인 경우 (사용자 입력) - 새로운 그룹 시작
                    if isinstance(message_content, str):
                        # 이전 그룹이 있으면 저장
                        if current_group:
                            message_groups.append(current_group)

                        # 새 그룹 시작
                        current_group = {
                            "user_message": message_content,
                            "agent_responses": {},  # 에이전트별 응답 저장
                            "plan": None,
                            "thought": None,
                        }

                    # 리스트 형태의 메시지인 경우 (AI 응답)
                    elif (
                        isinstance(message_content, list)
                        and len(message_content) == 2
                        and current_group
                    ):
                        msg_type, msg_obj = message_content
                        content = msg_obj.get("content", "")
                        agent_name = msg_obj.get("name")

                        # handoff 메시지는 건너뛰기
                        if (
                            "hand_off" in content.lower()
                            or "handoff" in content.lower()
                        ):
                            continue

                        # planner의 JSON 응답 처리
                        if agent_name == "planner" and content.strip().startswith("{"):
                            try:
                                plan_data = json.loads(content)
                                current_group["plan"] = plan_data
                                if "thought" in plan_data:
                                    current_group["thought"] = plan_data["thought"]
                            except json.JSONDecodeError:
                                pass
                            continue

                        # tool_calls가 있는 메시지는 건너뛰기
                        if msg_obj.get("tool_calls"):
                            continue

                        # 유효한 내용이 있는 메시지만 수집
                        if content and content.strip() and agent_name:
                            current_group["agent_responses"][
                                agent_name
                            ] = content.strip()

                # 마지막 그룹 추가
                if current_group:
                    message_groups.append(current_group)

                # 각 그룹을 세션 메시지로 변환
                for group in message_groups:
                    # 사용자 메시지 추가
                    st.session_state.messages.append(
                        {"role": "user", "content": group["user_message"]}
                    )

                    # 해당 그룹의 최적 assistant 응답 선택
                    priority_order = [
                        "sharing",
                        "travel_planner",
                        "search",
                        "coordinator",
                    ]
                    best_response = None

                    for agent_name in priority_order:
                        if agent_name in group["agent_responses"]:
                            best_response = group["agent_responses"][agent_name]
                            break

                    # 최적 응답이 있으면 추가
                    if best_response:
                        assistant_msg = {
                            "role": "assistant",
                            "content": best_response,
                            "agent_responses": group[
                                "agent_responses"
                            ],  # 모든 에이전트 응답 저장
                        }

                        # thought 정보 저장
                        if group["thought"]:
                            assistant_msg["thought"] = group["thought"]

                        # 마지막 그룹의 plan 정보 저장
                        if group == message_groups[-1] and group["plan"]:
                            st.session_state.plan = group["plan"]

                        st.session_state.messages.append(assistant_msg)

                st.session_state.selected_thread_id = thread_id
                st.rerun()

        except Exception as e:
            st.sidebar.error(f"대화를 불러오는데 실패했습니다: {e}")

    # 대화 기록 섹션
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.subheader("📋 대화 기록")
    with col2:
        if st.button("🔄", key="refresh_history", help="대화 기록 새로고침"):
            load_chat_history(reset=True)
            st.rerun()

    # 첫 로드 또는 사용자 ID가 변경된 경우 대화 기록 로드
    if (
        not st.session_state.chat_history
        or st.session_state.get("last_user_id") != user_id
    ):
        st.session_state.last_user_id = user_id
        load_chat_history(reset=True)

    # 대화 기록 표시
    if st.session_state.chat_history:
        # thread_id별로 그룹화하여 중복 제거
        unique_threads = {}
        for chat in st.session_state.chat_history:
            thread_id = chat["thread_id"]
            if thread_id not in unique_threads:
                unique_threads[thread_id] = {
                    "first_message": None,
                    "latest_timestamp": chat["timestamp"],
                }

            # 첫 번째 사용자 메시지 찾기
            if (
                isinstance(chat["message"], str)
                and unique_threads[thread_id]["first_message"] is None
            ):
                unique_threads[thread_id]["first_message"] = chat["message"]

            # 최신 타임스탬프 업데이트
            if chat["timestamp"] > unique_threads[thread_id]["latest_timestamp"]:
                unique_threads[thread_id]["latest_timestamp"] = chat["timestamp"]

        # 최신 순으로 정렬
        sorted_threads = sorted(
            unique_threads.items(), key=lambda x: x[1]["latest_timestamp"], reverse=True
        )

        for thread_id, thread_info in sorted_threads:
            # 메시지 미리보기
            if thread_info["first_message"]:
                preview = thread_info["first_message"][:40]
                if len(thread_info["first_message"]) > 40:
                    preview += "..."
            else:
                preview = "대화 기록"

            # 타임스탬프 포맷팅
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(
                    thread_info["latest_timestamp"].replace("Z", "+00:00")
                )
                time_str = dt.strftime("%m/%d %H:%M")
            except:
                time_str = thread_info["latest_timestamp"][:16]

            # 선택된 대화인지 확인
            is_selected = st.session_state.selected_thread_id == thread_id

            # 대화 기록 아이템
            button_label = f"{preview}\n\n {time_str}"
            if st.sidebar.button(
                button_label,
                key=f"chat_{thread_id}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                load_conversation(thread_id)

        # 더 보기 버튼
        if len(st.session_state.chat_history) < st.session_state.total_history_count:
            if st.sidebar.button("📋 더 보기", use_container_width=True):
                load_chat_history(st.session_state.current_page + 1)
                st.rerun()

    else:
        st.sidebar.info("대화 기록이 없습니다.")

else:
    st.sidebar.warning("사용자 ID를 입력해주세요.")


# 메시지 내용을 포맷팅하는 함수
def format_message_content(content):
    """메시지 내용을 더 읽기 쉽게 포맷팅"""
    if not content:
        return content

    # 중복된 섹션 제거 (같은 내용이 반복되는 경우)
    lines = content.split("\n")

    # 연속된 중복 라인 제거
    filtered_lines = []
    prev_line = ""
    duplicate_count = 0

    for line in lines:
        line = line.strip()
        if line == prev_line and line:
            duplicate_count += 1
            if duplicate_count <= 1:  # 첫 번째 중복까지만 허용
                filtered_lines.append(line)
        else:
            duplicate_count = 0
            filtered_lines.append(line)
            prev_line = line

    # 마크다운 및 특수 포맷팅 처리
    formatted_lines = []
    in_travel_section = False

    for line in filtered_lines:
        if not line:
            formatted_lines.append("")
            continue

        # 마크다운 볼드 텍스트 변환 (**텍스트** -> <strong>텍스트</strong>)
        line = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)

        # 마크다운 이탤릭 텍스트 변환 (*텍스트* -> <em>텍스트</em>)
        line = re.sub(r"\*(.*?)\*", r"<em>\1</em>", line)

        # 섹션 헤더 감지 (### 로 시작하는 경우)
        if line.startswith("###"):
            in_travel_section = True
            # ### 제거하고 헤더 스타일 적용
            header_text = line.replace("###", "").strip()
            formatted_lines.append(
                f'<h3 style="color: #2c3e50; margin-top: 1.5rem; margin-bottom: 0.5rem;">{header_text}</h3>'
            )
            continue

        # 번호 목록 형태인지 확인 (1. 제주도: 같은 패턴)
        number_list_pattern = r"^(\d+\.)\s*(.+?):\s*(.+)$"
        match = re.match(number_list_pattern, line)

        if match:
            number = match.group(1)  # "1."
            title = match.group(2)  # "제주도"
            description = match.group(3)  # "설명..."

            formatted_lines.append(f'<div class="travel-destination">')
            formatted_lines.append(f"<strong>{number} {title}</strong>")
            formatted_lines.append(
                f'<p style="margin: 0.25rem 0 0 0; color: #666;">{description}</p>'
            )
            formatted_lines.append("</div>")
        else:
            # 일반 텍스트 - 들여쓰기가 있는 경우 처리
            if line.startswith("   - ") or line.startswith("  - "):
                # 리스트 아이템
                list_content = line.lstrip("- ").strip()
                formatted_lines.append(
                    f'<div style="margin-left: 1rem; margin: 0.25rem 0;">• {list_content}</div>'
                )
            elif line.startswith("- "):
                # 최상위 리스트 아이템
                list_content = line[2:].strip()
                formatted_lines.append(
                    f'<div style="margin: 0.5rem 0;">• {list_content}</div>'
                )
            else:
                formatted_lines.append(line)

    return "\n".join(formatted_lines)


def display_agent_steps(agent_responses, thought=None):
    """에이전트 작업 단계들을 Perplexity 스타일로 표시"""
    if thought:
        with st.expander("🤔 **Thought Process**", expanded=False):
            st.markdown(thought)

    if agent_responses:
        with st.expander("🔄 **작업 단계**", expanded=False):
            # 에이전트 실행 순서대로 정렬
            agent_order = ["search", "travel_planner", "sharing", "coordinator"]

            for agent_name in agent_order:
                if agent_name in agent_responses:
                    config = AGENT_CONFIG.get(
                        agent_name,
                        {"name": agent_name, "icon": "⚙️", "description": "작업 중"},
                    )

                    st.markdown(
                        f"""
                        <div class="agent-step completed">
                            <div class="agent-step-header">
                                <span class="agent-icon">{config['icon']}</span>
                                <span><strong>{config['name']}</strong></span>
                                <span style="color: #28a745; font-size: 0.8rem;">✓ 완료</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


def is_duplicate_content(content1, content2, threshold=0.8):
    """두 메시지 내용이 중복인지 확인 (유사도 기반)"""
    if not content1 or not content2:
        return False

    # 공백과 특수문자 제거 후 비교
    clean1 = "".join(content1.split()).lower()
    clean2 = "".join(content2.split()).lower()

    # 완전히 같은 경우
    if clean1 == clean2:
        return True

    # 한쪽이 다른 쪽을 포함하는 경우 (포함률이 threshold 이상)
    if len(clean1) > 0 and len(clean2) > 0:
        shorter = clean1 if len(clean1) < len(clean2) else clean2
        longer = clean2 if len(clean1) < len(clean2) else clean1

        if len(shorter) / len(longer) > threshold and shorter in longer:
            return True

    return False


def select_best_response(agent_responses):
    """에이전트 응답 중에서 우선순위에 따라 최적 응답 선택"""
    priority_order = ["sharing", "travel_planner", "search", "coordinator"]

    for agent_name in priority_order:
        if agent_name in agent_responses and agent_responses[agent_name].strip():
            return agent_responses[agent_name]

    return None


# 이전 대화 및 계획(Thought) 표시
displayed_contents = set()  # 이미 표시된 내용 추적

for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "assistant" and msg["content"]:
        # 중복 체크
        content_hash = hash(msg["content"].strip())
        if content_hash in displayed_contents:
            continue

        # 이전 메시지와 유사도 체크
        skip_message = False
        for prev_content_hash in displayed_contents:
            # 간단한 중복 체크를 위해 해시만 비교 (성능상 이유)
            pass  # 이미 해시로 체크했으므로 추가 체크 불필요

        if not skip_message:
            displayed_contents.add(content_hash)

            with st.chat_message("assistant"):
                # 에이전트 작업 단계 표시 (Perplexity 스타일)
                agent_responses = msg.get("agent_responses", {})
                thought = msg.get("thought")

                if agent_responses or thought:
                    display_agent_steps(agent_responses, thought)

                # 응답 내용을 포맷팅하여 깔끔하게 표시
                content = msg["content"]

                # 마크다운 형식이 많이 포함된 경우 순수 마크다운으로 처리
                if "**" in content or "###" in content:
                    # 순수 마크다운으로 표시
                    if len(content) > 500:
                        with st.expander("📝 **응답 내용**", expanded=True):
                            st.markdown(content)
                    else:
                        st.markdown(content)
                else:
                    # HTML 포맷팅 적용
                    formatted_content = format_message_content(content)
                    if len(content) > 500:
                        with st.expander("📝 **응답 내용**", expanded=True):
                            st.markdown(formatted_content, unsafe_allow_html=True)
                    else:
                        st.markdown(formatted_content, unsafe_allow_html=True)

# 계획이 로드되면 Thought 부분만 항상 표시 (새로운 대화에서만)
if st.session_state.plan and not any(
    msg.get("role") == "assistant" and "thought" in msg
    for msg in st.session_state.messages
):
    with st.expander("🤔 **Current Plan**", expanded=True):
        st.markdown(f"**Thought**: {st.session_state.plan['thought']}")

        # 계획 단계들도 표시
        if "steps" in st.session_state.plan:
            st.markdown("**📋 실행 단계:**")
            for i, step in enumerate(st.session_state.plan["steps"], 1):
                st.markdown(
                    f"""
                <div class="step-progress">
                    <div class="step-title">{i}. {step.get('title', 'Step')}</div>
                    <div class="step-description">{step.get('description', '')}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

# 사용자 입력 처리
user_input = st.chat_input("메시지를 입력하세요...")
if user_input:
    if not user_id:
        st.error("먼저 사용자 ID를 입력해주세요.")
        st.stop()

    # 사용자 메시지 기록
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 어시스턴트 응답 스트리밍
    # 기존 대화가 선택되어 있으면 해당 thread_id 사용, 아니면 새로 생성
    thread_id = st.session_state.selected_thread_id or str(uuid.uuid4())

    response = requests.post(
        f"{backend_url}/api/chat/stream?thread_id={thread_id}&user_id={user_id}",
        json={
            "messages": [{"role": "user", "content": user_input}],
            "search_before_planning": True,
        },
        stream=True,
    )

    with st.chat_message("assistant"):
        # 작업 단계 표시용 컨테이너들 - 한 번만 생성
        thought_placeholder = st.empty()
        steps_placeholder = st.empty()
        content_placeholder = st.empty()

        # 스트리밍 상태 변수들
        current_event = None
        current_agent = None
        current_agent_content = ""
        agent_responses = {}  # 에이전트별 응답 저장
        agent_status = {}  # 에이전트별 상태 저장
        saved_thought = ""
        in_planner = False

        # 작업 단계 표시 함수
        def update_agent_steps():
            # Thought Process 업데이트
            if saved_thought:
                with thought_placeholder.container():
                    with st.expander("🤔 **Thought Process**", expanded=False):
                        st.markdown(saved_thought)
            else:
                thought_placeholder.empty()

            # 작업 단계 업데이트
            if agent_status:
                # 진행 중인 작업이 있는지 확인
                has_in_progress = any(
                    status == "in_progress" for status in agent_status.values()
                )

                with steps_placeholder.container():
                    with st.expander("🔄 **작업 단계**", expanded=has_in_progress):
                        agent_order = [
                            "search",
                            "travel_planner",
                            "sharing",
                            "coordinator",
                        ]

                        for agent_name in agent_order:
                            if agent_name in agent_status:
                                config = AGENT_CONFIG.get(
                                    agent_name,
                                    {
                                        "name": agent_name,
                                        "icon": "⚙️",
                                        "description": "작업 중",
                                    },
                                )
                                status = agent_status[agent_name]

                                if status == "completed":
                                    status_text = '<span style="color: #28a745; font-size: 0.8rem;">✓ 완료</span>'
                                    css_class = "completed"
                                elif status == "in_progress":
                                    status_text = '<span style="color: #007bff; font-size: 0.8rem;">⏳ 진행 중...</span>'
                                    css_class = "in-progress"
                                else:
                                    status_text = '<span style="color: #6c757d; font-size: 0.8rem;">⏸️ 대기 중</span>'
                                    css_class = ""

                                st.markdown(
                                    f"""
                                    <div class="agent-step {css_class}">
                                        <div class="agent-step-header">
                                            <span class="agent-icon">{config['icon']}</span>
                                            <span><strong>{config['name']}</strong></span>
                                            {status_text}
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
            else:
                steps_placeholder.empty()

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.strip():
                continue

            line = line.strip()

            # 이벤트 타입 처리
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue

            # 데이터 처리
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()

                # 에이전트 시작
                if current_event == "start_of_agent":
                    try:
                        data = json.loads(data_str)
                        current_agent = data.get("agent_name")
                        current_agent_content = ""

                        if current_agent:
                            agent_status[current_agent] = "in_progress"
                            update_agent_steps()

                        if current_agent == "planner":
                            in_planner = True

                    except json.JSONDecodeError:
                        pass
                    continue

                # 에이전트 종료
                elif current_event == "end_of_agent":
                    try:
                        data = json.loads(data_str)
                        agent_name = data.get("agent_name")

                        if agent_name == "planner":
                            in_planner = False
                        elif agent_name and current_agent_content.strip():
                            # handoff 메시지가 아닌 경우만 저장
                            if not (
                                "hand_off" in current_agent_content.lower()
                                or "handoff" in current_agent_content.lower()
                            ):
                                agent_responses[agent_name] = (
                                    current_agent_content.strip()
                                )
                                agent_status[agent_name] = "completed"
                                update_agent_steps()

                                # 최적 응답 선택 및 실시간 표시
                                best_response = select_best_response(agent_responses)
                                if best_response:
                                    display_content = ""

                                    # 마크다운 형식 감지 및 적절한 렌더링
                                    if "**" in best_response or "###" in best_response:
                                        display_content = best_response
                                        content_placeholder.markdown(display_content)
                                    else:
                                        formatted_response = format_message_content(
                                            best_response
                                        )
                                        content_placeholder.markdown(
                                            formatted_response, unsafe_allow_html=True
                                        )

                            current_agent_content = ""
                    except json.JSONDecodeError:
                        pass
                    continue

                # 메시지 처리
                elif current_event == "message":
                    try:
                        msg_obj = json.loads(data_str)
                        delta = msg_obj.get("delta", {})
                        content = delta.get("content") or delta.get("reasoning_content")

                        if not content:
                            continue

                        # planner 단계에서는 JSON 파싱 시도
                        if in_planner:
                            current_agent_content += content

                            # JSON 파싱 시도
                            if current_agent_content.strip().startswith("{"):
                                try:
                                    plan_data = json.loads(current_agent_content)
                                    if "thought" in plan_data:
                                        st.session_state.plan = plan_data
                                        saved_thought = plan_data["thought"]
                                        update_agent_steps()
                                        continue
                                except json.JSONDecodeError:
                                    pass
                            continue

                        # 현재 에이전트의 내용에 추가
                        if current_agent:
                            current_agent_content += content

                    except json.JSONDecodeError:
                        continue

    # 최종 응답을 세션에 저장
    final_content = select_best_response(agent_responses)
    if final_content and final_content.strip():
        # 스트리밍 완료 후 작업 단계를 접힌 상태로 다시 표시
        if agent_responses or saved_thought:
            # Thought Process 최종 표시
            if saved_thought:
                with thought_placeholder.container():
                    with st.expander("🤔 **Thought Process**", expanded=False):
                        st.markdown(saved_thought)

            # 작업 단계 최종 표시
            if agent_responses:
                with steps_placeholder.container():
                    with st.expander("🔄 **작업 단계**", expanded=False):
                        agent_order = [
                            "search",
                            "travel_planner",
                            "sharing",
                            "coordinator",
                        ]

                        for agent_name in agent_order:
                            if agent_name in agent_responses:
                                config = AGENT_CONFIG.get(
                                    agent_name,
                                    {
                                        "name": agent_name,
                                        "icon": "⚙️",
                                        "description": "작업 중",
                                    },
                                )

                                st.markdown(
                                    f"""
                                    <div class="agent-step completed">
                                        <div class="agent-step-header">
                                            <span class="agent-icon">{config['icon']}</span>
                                            <span><strong>{config['name']}</strong></span>
                                            <span style="color: #28a745; font-size: 0.8rem;">✓ 완료</span>
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

        assistant_message = {
            "role": "assistant",
            "content": final_content.strip(),
            "agent_responses": agent_responses,  # 모든 에이전트 응답 저장
        }

        # thought 정보가 있으면 함께 저장
        if saved_thought:
            assistant_message["thought"] = saved_thought

        # 중복 체크 - 이전 메시지와 같은 내용이 아닌 경우만 저장
        is_duplicate = False
        if st.session_state.messages:
            last_msg = st.session_state.messages[-1]
            if (
                last_msg.get("role") == "assistant"
                and last_msg.get("content", "").strip() == final_content.strip()
            ):
                is_duplicate = True

        if not is_duplicate:
            st.session_state.messages.append(assistant_message)

    # 새 대화인 경우 thread_id 업데이트
    if not st.session_state.selected_thread_id:
        st.session_state.selected_thread_id = thread_id

    # 대화 기록 새로고침
    if user_id:
        load_chat_history(reset=True)
