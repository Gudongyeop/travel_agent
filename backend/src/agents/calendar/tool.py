import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..decorators import log_io

# Google Calendar API 스코프
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarEventInput(BaseModel):
    """Google Calendar 이벤트 생성을 위한 입력 모델"""

    summary: str = Field(description="이벤트 제목")
    description: Optional[str] = Field(default=None, description="이벤트 설명")
    start_datetime: str = Field(
        description="시작 시간 (ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)"
    )
    end_datetime: str = Field(
        description="종료 시간 (ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)"
    )
    timezone: str = Field(default="Asia/Seoul", description="시간대")
    location: Optional[str] = Field(default=None, description="장소")
    attendees: Optional[list[str]] = Field(
        default=None, description="참석자 이메일 목록"
    )


def get_calendar_service():
    """Google Calendar API 서비스 인스턴스를 가져옵니다."""
    creds = None

    # token.json 파일이 있다면 기존 credentials 로드
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # 유효한 credentials가 없다면 인증 진행
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json 파일이 필요합니다 (Google Cloud Console에서 다운로드)
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("credentials.json 파일을 찾을 수 없습니다.")

            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # credentials를 저장하여 다음에 다시 사용
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


@tool
@log_io
def create_calendar_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str = None,
    timezone: str = "Asia/Seoul",
    location: str = None,
    attendees: list[str] = None,
) -> Dict[str, Any]:
    """
    Google Calendar에 새로운 일정을 등록합니다.

    Args:
        summary: 이벤트 제목
        start_datetime: 시작 시간 (ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
        end_datetime: 종료 시간 (ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
        description: 이벤트 설명 (선택사항)
        timezone: 시간대 (기본값: Asia/Seoul)
        location: 장소 (선택사항)
        attendees: 참석자 이메일 목록 (선택사항)

    Returns:
        생성된 이벤트 정보를 포함한 딕셔너리
    """
    try:
        service = get_calendar_service()

        # 이벤트 데이터 구성
        event = {
            "summary": summary,
            "start": {
                "dateTime": start_datetime,
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_datetime,
                "timeZone": timezone,
            },
        }

        # 선택적 필드들 추가
        if description:
            event["description"] = description

        if location:
            event["location"] = location

        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]

        # 이벤트 생성
        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        return {
            "success": True,
            "event_id": created_event.get("id"),
            "event_link": created_event.get("htmlLink"),
            "summary": summary,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "message": f'일정 "{summary}"이(가) 성공적으로 등록되었습니다.',
        }

    except HttpError as error:
        return {
            "success": False,
            "error": f"HTTP 오류: {error}",
            "message": "일정 등록 중 오류가 발생했습니다.",
        }
    except FileNotFoundError as error:
        return {
            "success": False,
            "error": str(error),
            "message": "Google Calendar API 인증 파일이 필요합니다. credentials.json 파일을 확인하세요.",
        }
    except Exception as error:
        return {
            "success": False,
            "error": str(error),
            "message": "일정 등록 중 예상치 못한 오류가 발생했습니다.",
        }


@tool
def list_upcoming_events(max_results: int = 10) -> Dict[str, Any]:
    """
    다가오는 Google Calendar 이벤트 목록을 가져옵니다.

    Args:
        max_results: 가져올 최대 이벤트 수 (기본값: 10)

    Returns:
        이벤트 목록을 포함한 딕셔너리
    """
    try:
        service = get_calendar_service()

        # 현재 시간 이후의 이벤트만 가져옴
        now = datetime.utcnow().isoformat() + "Z"

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            return {
                "success": True,
                "events": [],
                "message": "다가오는 일정이 없습니다.",
            }

        event_list = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            event_info = {
                "id": event.get("id"),
                "summary": event.get("summary", "제목 없음"),
                "start": start,
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "link": event.get("htmlLink", ""),
            }
            event_list.append(event_info)

        return {
            "success": True,
            "events": event_list,
            "count": len(event_list),
            "message": f"{len(event_list)}개의 다가오는 일정을 찾았습니다.",
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
            "message": "이벤트 목록 조회 중 오류가 발생했습니다.",
        }
