import re
from typing import Any, Dict, List, Optional, Tuple

import msgpack

from ..db import get_db

_collection_travel_planner_history = "travel_planner_history"


def extract_response_content(text: str) -> str:
    """Response 태그 안의 내용만 추출합니다."""
    if not isinstance(text, str):
        return text

    # <response> 태그 안의 내용을 추출
    pattern = r"<response>\s*(.*?)\s*</response>"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    # <response> 태그가 없으면 원본 텍스트 반환
    return text


def unpack_ext_type_title(binary_value: bytes) -> Optional[List[str | dict]]:
    """Agent 응답 MongoDB 저장된 binarybase64 -> obj 로 변환

    Args:
        binary_value (bytes): MongoDB - Binary.createFromBase64

    Returns:
        [str, dict] : [HumanMessage, {tool_name: tool_call_id, args: {}...}]
    """
    if not binary_value:
        return None
    value_unpacked = msgpack.unpackb(binary_value)
    if not isinstance(value_unpacked, list) or len(value_unpacked) == 0:
        return None

    item = value_unpacked[-1]
    if isinstance(item, dict) and "content" in item:
        return item["content"]
    return None


def unpack_ext_type(binary_value: bytes) -> Optional[List[str | dict]]:
    """Agent 응답 MongoDB 저장된 binarybase64 -> obj 로 변환

    Args:
        binary_value (bytes): MongoDB - Binary.createFromBase64

    Returns:
        [str, dict] : [HumanMessage, {tool_name: tool_call_id, args: {}...}]
    """
    if not binary_value:
        return None
    value_unpacked = msgpack.unpackb(binary_value)
    if not isinstance(value_unpacked, list) or len(value_unpacked) == 0:
        return None

    item = value_unpacked[-1]

    if not isinstance(item, msgpack.ExtType):
        return None

    ext_unpacked = msgpack.unpackb(item.data)
    if not isinstance(ext_unpacked, list) or len(ext_unpacked) < 2:
        return None

    return ext_unpacked[1:3]


async def get_grouped_all_history_by_user_id(
    user_id: str, page: int, page_size: int
) -> Tuple[int, List[Dict[str, Any]]]:
    """user_id로 그룹화된 채팅 내역을 가져옵니다."""
    client = await get_db()

    pipeline = [
        {"$match": {"user_id": user_id, "channel": "messages"}},
        {"$sort": {"timestamp": 1}},
        {
            "$group": {
                "_id": "$thread_id",
                "first_message": {"$first": "$$ROOT"},
                "last_message": {"$last": "$$ROOT"},
            }
        },
        {"$sort": {"first_message.timestamp": -1}},
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
        {"$replaceRoot": {"newRoot": "$first_message"}},
    ]

    # 전체 그룹 수 계산을 위한 파이프라인
    count_pipeline = [
        {"$match": {"user_id": user_id, "channel": "messages"}},
        {"$group": {"_id": "$thread_id"}},
        {"$count": "total"},
    ]
    # 쿼리 실행
    result = (
        await client[_collection_travel_planner_history]
        .aggregate(pipeline)
        .to_list(length=None)
    )
    count_result = (
        await client[_collection_travel_planner_history]
        .aggregate(count_pipeline)
        .to_list(length=None)
    )

    total_threads = count_result[0]["total"] if count_result else 0

    # 결과 변환
    formatted_result = []
    for group in result:
        # 최신 메시지를 기준으로 데이터 구성
        unpack_value = unpack_ext_type_title(group["value"])
        if not unpack_value:
            continue

        item = {
            "id": group["thread_id"],
            "thread_id": group["thread_id"],
            "message": unpack_value,
            "timestamp": group["timestamp"],
            "user_id": user_id,
        }
        formatted_result.append(item)

    return total_threads, formatted_result


async def get_thread_ids_by_user_id(user_id: str) -> List[str]:
    """user_id로 채팅 아이디를 가져옵니다."""
    client = await get_db()
    chat_ids = await client[_collection_travel_planner_history].distinct(
        "thread_id", {"user_id": user_id}
    )
    return chat_ids


async def get_grouped_travel_planner_detail_history_by_chat_id(
    user_id: str, thread_id: str
) -> List[Dict[str, Any]]:
    """chat_id로 그룹화된 채팅 내역을 가져옵니다."""
    client = await get_db()
    chat_ids = await get_thread_ids_by_user_id(user_id=user_id)
    if thread_id not in chat_ids:
        return []
    chat_list = client[_collection_travel_planner_history].find(
        {"thread_id": thread_id, "user_id": user_id}
    )
    result = await chat_list.to_list(length=None)
    formatted_result = []
    seen_contents = set()  # 중복 제거를 위한 content 추적

    for item in result:
        unpack_value = unpack_ext_type(item["value"])
        if not unpack_value:
            new_unpack_value = unpack_ext_type_title(item["value"])
            if new_unpack_value:
                unpack_value = new_unpack_value
            else:
                continue
        # <response> 태그 안의 내용만 추출
        processed_message = unpack_value
        content_for_dedup = None  # 중복 체크용 content

        if isinstance(unpack_value, list) and len(unpack_value) > 1:
            # unpack_value[1]이 딕셔너리이고 'content' 키가 있는 경우
            if isinstance(unpack_value[1], dict) and "content" in unpack_value[1]:
                original_content = unpack_value[1]["content"]
                extracted_content = extract_response_content(original_content)

                # 새로운 딕셔너리 생성 (기존 값 복사 후 content만 수정)
                new_message_dict = unpack_value[1].copy()
                new_message_dict["content"] = extracted_content
                processed_message = [unpack_value[0], new_message_dict] + unpack_value[
                    2:
                ]
                content_for_dedup = extracted_content

        # content가 문자열인 경우 (unpack_ext_type_title의 경우)
        if isinstance(unpack_value, str):
            content_for_dedup = unpack_value

        # content 중복 체크
        if content_for_dedup and content_for_dedup in seen_contents:
            continue  # 중복된 content는 건너뛰기

        if content_for_dedup:
            seen_contents.add(content_for_dedup)

        item = {
            "id": item["thread_id"],
            "thread_id": item["thread_id"],
            "message": processed_message,
            "timestamp": item["timestamp"],
            "user_id": user_id,
        }
        formatted_result.append(item)
    formatted_result.sort(key=lambda x: x["timestamp"])
    return formatted_result
