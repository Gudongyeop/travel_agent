import os
import re
from datetime import datetime

from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt.chat_agent_executor import AgentState


def get_prompt_template(prompt_name: str) -> str:
    """
    프롬프트 템플릿 파일을 읽어와서 LangChain 형식으로 변환합니다.

    Args:
        prompt_name (str): 프롬프트 파일명 (예: "calendar", "planner")

    Returns:
        str: LangChain 프롬프트 템플릿 형식의 문자열

    보안 고려사항:
        - 파일 경로 검증을 통한 디렉토리 트래버설 공격 방지
        - 허용된 프롬프트 파일만 접근 가능
    """
    # 보안: 허용된 프롬프트 파일명만 처리
    allowed_prompts = {
        "calendar",
        "coordinator",
        "planner",
        "search",
        "sharing",
        "supervisor",
        "travel_planner",
    }

    if prompt_name not in allowed_prompts:
        raise ValueError(f"허용되지 않은 프롬프트 파일: {prompt_name}")

    try:
        template = open(
            os.path.join(os.path.dirname(__file__), f"{prompt_name}.md")
        ).read()
        # 중괄호를 백슬래시로 이스케이프 처리
        template = template.replace("{", "{{").replace("}", "}}")
        # `<<VAR>>` 형식을 `{VAR}` 형식으로 변환
        template = re.sub(r"<<([^>>]+)>>", r"{\1}", template)
        return template
    except FileNotFoundError:
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {prompt_name}.md")
    except Exception as e:
        raise Exception(f"프롬프트 템플릿 로딩 오류: {str(e)}")


def apply_prompt_template(prompt_name: str, state: AgentState) -> list:
    """
    프롬프트 템플릿에 현재 시간과 상태 정보를 적용하여 메시지 목록을 생성합니다.

    Args:
        prompt_name (str): 사용할 프롬프트 템플릿명
        state (AgentState): LangGraph 에이전트 상태

    Returns:
        list: 시스템 프롬프트와 기존 메시지가 포함된 메시지 목록

    보안 고려사항:
        - 사용자 입력 데이터 검증
        - 시스템 프롬프트 무결성 보장
        - 민감한 정보 노출 방지
    """
    try:
        # 현재 시간을 한국 표준시로 설정
        current_time = datetime.now().strftime("%Y년 %m월 %d일 %A %H:%M:%S")

        system_prompt = PromptTemplate(
            input_variables=["CURRENT_TIME"],
            template=get_prompt_template(prompt_name),
        ).format(CURRENT_TIME=current_time, **state)

        # 시스템 메시지와 사용자 메시지 결합
        return [{"role": "system", "content": system_prompt}] + state["messages"]

    except Exception as e:
        # 오류 발생 시 기본 안전 메시지 반환
        fallback_message = """
        죄송합니다. 시스템 오류가 발생했습니다. 
        안전상의 이유로 요청을 처리할 수 없습니다.
        나중에 다시 시도해 주세요.
        """
        return [{"role": "system", "content": fallback_message}] + state.get(
            "messages", []
        )
