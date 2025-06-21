import os
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..decorators import log_io


class TravelPlanShareInput(BaseModel):
    """여행 계획서 공유를 위한 입력 모델"""

    travel_plan: str = Field(description="공유할 여행 계획서 내용 (마크다운 형식)")
    share_method: Literal["email", "file", "cloud", "link"] = Field(
        description="공유 방식: email(이메일), file(파일 저장), cloud(클라우드 스토리지), link(공유 링크)"
    )
    recipients: Optional[List[str]] = Field(
        default=None, description="이메일 공유 시 수신자 목록"
    )
    email_subject: Optional[str] = Field(
        default=None, description="이메일 제목 (이메일 공유 시)"
    )
    file_path: Optional[str] = Field(
        default=None, description="파일 저장 경로 (파일 공유 시)"
    )
    title: Optional[str] = Field(
        default="나의 여행 계획서", description="여행 계획서 제목"
    )
    additional_message: Optional[str] = Field(default=None, description="추가 메시지")


def create_html_from_markdown(markdown_content: str, title: str = "여행 계획서") -> str:
    """마크다운 내용을 HTML로 변환"""
    try:
        import markdown

        # 마크다운을 HTML로 변환
        html_content = markdown.markdown(markdown_content, extensions=["tables", "toc"])

        # HTML 템플릿
        html_template = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .container {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                }}
                h2 {{
                    color: #34495e;
                    margin-top: 30px;
                }}
                h3 {{
                    color: #7f8c8d;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    text-align: center;
                    color: #7f8c8d;
                    font-size: 0.9em;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                {html_content}
                <div class="footer">
                    <p>생성일: {datetime.now().strftime('%Y년 %m월 %d일')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html_template

    except ImportError:
        # markdown 라이브러리가 없는 경우 간단한 HTML 변환
        html_content = markdown_content.replace("\n", "<br>")
        return f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
        </head>
        <body>
            <h1>{title}</h1>
            <div>{html_content}</div>
        </body>
        </html>
        """


def save_travel_plan_to_file(
    travel_plan: str, title: str, file_path: Optional[str] = None
) -> str:
    """여행 계획서를 파일로 저장"""
    try:
        # 파일 경로 설정
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"travel_plan_{timestamp}.html"

        # 디렉토리 생성
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        # HTML 내용 생성
        html_content = create_html_from_markdown(travel_plan, title)

        # 파일 저장
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return file_path

    except Exception as e:
        raise


def send_email_with_travel_plan(
    travel_plan: str,
    recipients: List[str],
    subject: str,
    title: str,
    additional_message: Optional[str] = None,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> bool:
    """여행 계획서를 이메일로 전송"""
    try:
        # 환경 변수에서 이메일 설정 가져오기
        sender_email = os.getenv("EMAIL_ADDRESS")
        sender_password = os.getenv("EMAIL_PASSWORD")

        if not sender_email or not sender_password:
            return False

        # HTML 내용 생성
        html_content = create_html_from_markdown(travel_plan, title)

        # 이메일 메시지 생성
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = ", ".join(recipients)

        # 추가 메시지가 있는 경우 포함
        if additional_message:
            html_content = (
                f"<div style='margin-bottom: 20px; padding: 15px; background-color: #e8f4f8; border-left: 4px solid #3498db;'>{additional_message}</div>"
                + html_content
            )

        # HTML 파트 추가
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # SMTP 서버 연결 및 전송
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        return True

    except Exception as e:
        return False


def create_shareable_link(travel_plan: str, title: str) -> str:
    """공유 가능한 링크를 생성 (간단한 파일 기반)"""
    try:
        # 고유한 ID 생성
        share_id = str(uuid.uuid4())

        # 공유 디렉토리 생성
        share_dir = Path("shared_plans")
        share_dir.mkdir(exist_ok=True)

        # HTML 파일 생성
        html_content = create_html_from_markdown(travel_plan, title)
        share_file = share_dir / f"{share_id}.html"

        with open(share_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 공유 링크 반환 (실제 환경에서는 웹 서버 URL 사용)
        share_link = f"http://localhost:8000/shared/{share_id}.html"

        return share_link

    except Exception as e:
        raise


@tool
@log_io
def share_travel_plan(
    travel_plan: str,
    share_method: Literal["email", "file", "cloud", "link"],
    title: str = "나의 여행 계획서",
    recipients: Optional[List[str]] = None,
    email_subject: Optional[str] = None,
    file_path: Optional[str] = None,
    additional_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    여행 계획서를 다양한 방식으로 외부에 공유합니다.

    Args:
        travel_plan: 공유할 여행 계획서 내용 (마크다운 형식)
        share_method: 공유 방식 (email, file, cloud, link)
        title: 여행 계획서 제목
        recipients: 이메일 수신자 목록 (이메일 공유 시 필수)
        email_subject: 이메일 제목
        file_path: 파일 저장 경로
        additional_message: 추가 메시지

    Returns:
        공유 결과를 포함한 딕셔너리
    """
    try:
        result = {
            "success": False,
            "share_method": share_method,
            "title": title,
            "message": "",
        }

        if share_method == "email":
            if not recipients:
                result["message"] = "이메일 공유를 위해서는 수신자 목록이 필요합니다."
                return result

            subject = email_subject or f"[여행 계획서] {title}"
            success = send_email_with_travel_plan(
                travel_plan, recipients, subject, title, additional_message
            )

            if success:
                result["success"] = True
                result["message"] = (
                    f"여행 계획서가 {len(recipients)}명에게 이메일로 전송되었습니다."
                )
                result["recipients"] = recipients
            else:
                result["message"] = (
                    "이메일 전송에 실패했습니다. 이메일 설정을 확인하세요."
                )

        elif share_method == "file":
            saved_path = save_travel_plan_to_file(travel_plan, title, file_path)
            result["success"] = True
            result["message"] = f"여행 계획서가 파일로 저장되었습니다: {saved_path}"
            result["file_path"] = saved_path

        elif share_method == "link":
            share_link = create_shareable_link(travel_plan, title)
            result["success"] = True
            result["message"] = "공유 링크가 생성되었습니다."
            result["share_link"] = share_link

        elif share_method == "cloud":
            # 클라우드 스토리지 기능은 향후 구현
            result["message"] = "클라우드 스토리지 공유 기능은 현재 구현 중입니다."

        else:
            result["message"] = f"지원하지 않는 공유 방식입니다: {share_method}"

        return result

    except Exception as e:
        return {
            "success": False,
            "share_method": share_method,
            "title": title,
            "message": f"공유 중 오류가 발생했습니다: {str(e)}",
        }


@tool
def share_content(
    content: str,
    share_method: Literal["email", "file", "link"] = "file",
    title: str = "공유 내용",
    recipients: Optional[List[str]] = None,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    일반적인 내용을 공유합니다. (base.py에서 참조하는 함수)

    Args:
        content: 공유할 내용
        share_method: 공유 방식
        title: 제목
        recipients: 이메일 수신자 (이메일 공유 시)
        file_path: 파일 경로 (파일 공유 시)

    Returns:
        공유 결과
    """
    return share_travel_plan(
        travel_plan=content,
        share_method=share_method,
        title=title,
        recipients=recipients,
        file_path=file_path,
    )
