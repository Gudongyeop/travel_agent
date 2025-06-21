import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse

import markdownify
import readabilipy.simple_json
from bs4 import BeautifulSoup
from curl_cffi import AsyncSession
from langchain_core.tools import tool
from langchain_tavily.tavily_search import TavilySearch
from pydantic import BaseModel, Field

from ..decorators import create_logged_tool, log_io

LoggedTavilySearch = create_logged_tool(TavilySearch)
tavily_tool = LoggedTavilySearch(name="tavily_search", max_results=10)

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


class WebExtractInput(BaseModel):
    """
    웹페이지 내용 추출을 위한 입력 모델
    """

    urls: List[str] = Field(description="추출할 URL 목록")
    extract_depth: Optional[Literal["basic", "advanced"]] = Field(
        default="basic",
        description="""웹 콘텐츠 추출의 세밀함을 제어합니다.
        
        "basic": 주요 텍스트 콘텐츠의 빠른 추출을 위해 사용합니다.
        
        "advanced": 테이블 및 임베디드 요소를 포함한 포괄적인 콘텐츠를 검색합니다.
        LinkedIn 및 YouTube URL에 대해서는 항상 "advanced"를 사용하여 최적의 결과를 얻으세요.
        
        복잡한 웹사이트에 더 적합하지만 응답 시간이 증가할 수 있습니다.
        """,
    )
    include_images: Optional[bool] = Field(
        default=False,
        description="""소스 URL에서 이미지를 추출하고 포함할지 결정합니다.
   
        시각화가 더 나은 컨텍스트나 이해를 위해 필요한 경우 True로 설정합니다.
    
        기본값은 False입니다 (텍스트 콘텐츠만 추출).
        """,
    )
    max_length: Optional[int] = Field(
        default=5000,
        description="반환할 최대 문자 수",
    )


def extract_content_from_html(html: str, include_images: bool = False) -> str:
    """HTML 콘텐츠를 마크다운 형식으로 추출하고 변환합니다."""
    try:
        # readabilipy를 사용한 기본 추출
        ret = readabilipy.simple_json.simple_json_from_html_string(
            html, use_readability=True
        )

        if not ret["content"]:
            # BeautifulSoup을 사용한 대체 추출 방법 시도
            soup = clean_html_content(BeautifulSoup(html, "html.parser"))

            # 메인 콘텐츠 영역 후보 식별
            main_candidates = soup.find_all(
                ["article", "main", "div", "section"],
                class_=lambda c: c
                and any(
                    x in str(c).lower()
                    for x in ["content", "article", "main", "body", "entry"]
                ),
            )

            if main_candidates:
                # 가장 많은 텍스트를 포함한 요소 선택
                main_content = max(main_candidates, key=lambda x: len(x.get_text()))
                content = markdownify.markdownify(
                    str(main_content), heading_style=markdownify.ATX
                )
                return content

            # 단락 텍스트만 추출하는 대안
            paragraphs = soup.find_all("p")
            if paragraphs:
                content = "\n\n".join(
                    [
                        p.get_text().strip()
                        for p in paragraphs
                        if len(p.get_text().strip()) > 100
                    ]
                )
                return content

            return "<error>HTML에서 페이지를 간소화하지 못했습니다</error>"

        content = markdownify.markdownify(
            ret["content"],
            heading_style=markdownify.ATX,
        )

        # 이미지 포함 옵션 처리
        if include_images and ret.get("images"):
            images_section = "\n\n## 이미지\n\n"
            for img in ret.get("images", []):
                if isinstance(img, dict):
                    img_url = img.get("src", "")
                    img_alt = img.get("alt", "")
                    if img_url:
                        images_section += f"![{img_alt}]({img_url})\n\n"
            content += images_section

        return content
    except Exception as e:
        return f"<error>콘텐츠 추출 중 오류 발생: {str(e)}</error>"


def clean_html_content(soup: BeautifulSoup) -> BeautifulSoup:
    """불필요한 HTML 요소를 제거합니다."""
    # 일반적인 불필요 요소 선택자
    noise_selectors = [
        "nav",
        "header",
        "footer",
        "aside",
        '[class*="nav"]',
        '[class*="menu"]',
        '[class*="sidebar"]',
        '[class*="footer"]',
        '[class*="header"]',
        '[class*="banner"]',
        '[id*="nav"]',
        '[id*="menu"]',
        '[id*="sidebar"]',
        '[id*="footer"]',
        '[id*="header"]',
        '[id*="banner"]',
    ]

    for selector in noise_selectors:
        for element in soup.select(selector):
            element.decompose()

    return soup


async def fetch_url_task(
    url: str,
    session: AsyncSession,
    user_agent: str,
    extract_depth: str,
    include_images: bool = False,
) -> Tuple[str, str, str]:
    """URL 가져오기 작업

    Args:
        url: 가져올 URL
        session: 요청에 사용할 AsyncSession
        user_agent: 사용할 User-Agent
        extract_depth: 추출 깊이 ("basic" 또는 "advanced")
        include_images: 이미지 포함 여부

    Returns:
        URL, 콘텐츠, 에러 메시지 튜플
    """
    try:
        # URL 유효성 검사
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return (url, "", f"유효하지 않은 URL 형식: {url}")

        response = await session.request(
            "GET",
            url,
            headers={"User-Agent": user_agent},
            timeout=20,
            impersonate="chrome131",
        )

        if response.status_code >= 400:
            error_message = f"HTTP {response.status_code} 오류"
            if response.status_code == 404:
                error_message = "페이지를 찾을 수 없습니다(404)"
            elif response.status_code == 403:
                error_message = "접근이 거부되었습니다(403)"
            elif response.status_code == 429:
                error_message = "너무 많은 요청을 보냈습니다(429)"
            elif response.status_code >= 500:
                error_message = f"서버 오류({response.status_code})"

            return (url, "", error_message)

        page_raw = response.text
        if not page_raw.strip():
            return (url, "", "빈 응답 받음")

        content_type = response.headers.get("content-type", "").lower()
        is_page_html = (
            "<html" in page_raw[:100] or "text/html" in content_type or not content_type
        )

        # 페이지 제목 추출
        page_title = ""
        if is_page_html:
            title_match = re.search(
                r"<title[^>]*>(.*?)</title>", page_raw, re.IGNORECASE | re.DOTALL
            )
            if title_match:
                page_title = title_match.group(1).strip()

        # HTML 콘텐츠 처리
        if is_page_html:
            if extract_depth == "advanced":
                # advanced 모드에서는 더 정교한 추출 수행
                content = extract_content_from_html(page_raw, include_images)
            else:
                # basic 모드에서는 기본 텍스트 추출
                soup = BeautifulSoup(page_raw, "html.parser")
                # 스크립트와 스타일 태그 제거
                for script in soup(["script", "style"]):
                    script.decompose()
                content = soup.get_text()
                # 여러 공백을 단일 공백으로 변환
                content = re.sub(r"\s+", " ", content).strip()

            # 내용이 너무 짧으면 오류 처리
            if len(content) < 50:
                return (
                    url,
                    "",
                    f"콘텐츠 추출 실패. 페이지 제목: {page_title or '제목 없음'}",
                )

            # 제목 추가
            if page_title:
                content = f"# {page_title}\n\n{content}"

            return (url, content, "")

        # HTML이 아닌 콘텐츠 처리 (JSON, XML, 텍스트 등)
        if "application/json" in content_type:
            try:
                parsed_json = json.loads(page_raw)
                formatted_json = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                return (url, f"```json\n{formatted_json}\n```", "")
            except json.JSONDecodeError:
                return (url, page_raw, "")
        else:
            return (url, page_raw, "")

    except asyncio.TimeoutError:
        return (url, "", "요청 시간 초과")
    except Exception as e:
        return (url, "", f"가져오기 실패: {str(e)}")


async def fetch_multiple_urls(
    urls: List[str],
    extract_depth: str = "basic",
    include_images: bool = False,
    max_urls: int = 10,
) -> List[Dict[str, Any]]:
    """여러 URL을 동시에 가져와 콘텐츠를 추출합니다.

    Args:
        urls: 가져올 URL 목록
        extract_depth: 추출 깊이 ("basic" 또는 "advanced")
        include_images: 이미지 포함 여부
        max_urls: 한 번에 처리할 최대 URL 수

    Returns:
        추출된 콘텐츠를 포함한 딕셔너리 목록
    """
    if not urls:
        return []

    # 최대 URL 수 제한
    urls = urls[:max_urls]

    # 중복 URL 제거
    unique_urls = []
    for url in urls:
        if url not in unique_urls:
            unique_urls.append(url)

    async with AsyncSession() as session:
        tasks = [
            fetch_url_task(
                url, session, DEFAULT_USER_AGENT, extract_depth, include_images
            )
            for url in unique_urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    extracted_results = []
    for i, (url, result) in enumerate(zip(unique_urls, results)):
        if isinstance(result, Exception):
            extracted_results.append(
                {
                    "url": url,
                    "content": "",
                    "success": False,
                    "error": str(result),
                    "index": i,
                }
            )
        else:
            url_result, content, error = result
            extracted_results.append(
                {
                    "url": url_result,
                    "content": content,
                    "success": not bool(error),
                    "error": error if error else None,
                    "index": i,
                }
            )

    return extracted_results


@tool
@log_io
def extract_web_content(
    urls: List[str],
    extract_depth: str = "basic",
    include_images: bool = False,
    max_length: int = 5000,
) -> Dict[str, Any]:
    """
    여러 웹페이지에서 내용을 추출합니다.

    Args:
        urls: 추출할 URL 목록
        extract_depth: 추출 깊이 ("basic" 또는 "advanced")
        include_images: 이미지 포함 여부 (기본값: False)
        max_length: 반환할 최대 문자 수 (기본값: 5000)

    Returns:
        추출된 웹페이지 내용을 포함한 딕셔너리
    """
    try:
        if not urls:
            return {"success": False, "error": "URL 목록이 비어있습니다", "results": []}

        # 비동기 함수 실행
        results = asyncio.run(
            fetch_multiple_urls(
                urls=urls,
                extract_depth=extract_depth,
                include_images=include_images,
                max_urls=len(urls),
            )
        )

        # 결과 처리 및 길이 제한
        processed_results = []
        for result in results:
            content = result["content"]
            if content and len(content) > max_length:
                content = content[:max_length] + "...\n\n[내용이 잘렸습니다]"

            processed_results.append(
                {
                    "url": result["url"],
                    "content": content,
                    "success": result["success"],
                    "error": result.get("error"),
                    "content_length": (
                        len(result["content"]) if result["content"] else 0
                    ),
                }
            )

        # 성공/실패 통계
        successful_extractions = sum(1 for r in processed_results if r["success"])
        failed_extractions = len(processed_results) - successful_extractions

        return {
            "success": successful_extractions > 0,
            "results": processed_results,
            "total_urls": len(urls),
            "successful_extractions": successful_extractions,
            "failed_extractions": failed_extractions,
            "message": f"{successful_extractions}개 URL에서 성공적으로 내용을 추출했습니다. ({failed_extractions}개 실패)",
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
            "results": [],
            "message": "웹 콘텐츠 추출 중 예상치 못한 오류가 발생했습니다.",
        }
