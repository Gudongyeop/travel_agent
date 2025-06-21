# Travel Agent Backend

## 📖 프로젝트 개요

Travel Agent Backend는 LangGraph와 FastAPI를 기반으로 한 다중 에이전트 여행 계획 시스템입니다. 여러 전문화된 AI 에이전트들이 협력하여 사용자의 여행 계획을 종합적으로 수립하고 관리합니다.

![프로젝트 스크린샷](./images/스크린샷%202025-06-22%20오전%201.25.43.png)
*웹 인터페이스 메인 화면*

## 🏗️ 시스템 아키텍처

### 🔗 LangGraph 기반 Multi-Agent 워크플로우

이 프로젝트는 LangGraph의 StateGraph를 활용한 다중 에이전트 협업 시스템으로 구성되어 있습니다:

![워크플로우 다이어그램](./images/스크린샷%202025-06-22%20오전%201.26.09.png)
*에이전트 협업 워크플로우*

### 🤖 전문화된 AI 에이전트들

- **🧠 Supervisor Agent**: 전체 워크플로우를 관리하고 다음 실행할 에이전트를 결정
- **📅 Calendar Agent**: Google Calendar API를 통한 일정 관리 및 스케줄링
- **🔍 Search Agent**: Tavily API를 활용한 실시간 여행 정보 검색
- **📤 Sharing Agent**: 여행 계획을 HTML 포맷으로 생성 및 공유
- **✈️ Travel Planner Agent**: 종합적인 여행 계획 수립

![에이전트 구조](./images/스크린샷%202025-06-22%20오전%201.26.49.png)
*에이전트별 역할 분담*

## 📁 백엔드 폴더 구조

```
backend/
├── src/                          # 메인 소스 코드
│   ├── agents/                   # AI 에이전트 모듈
│   │   ├── calendar/            # 캘린더 에이전트
│   │   │   ├── base.py         # 기본 에이전트 클래스
│   │   │   ├── tool.py         # Google Calendar API 툴
│   │   │   └── README.md       # 캘린더 에이전트 상세 문서
│   │   ├── search/             # 검색 에이전트
│   │   │   ├── base.py         # 검색 에이전트 기본 클래스
│   │   │   └── tool.py         # Tavily 검색 API 툴
│   │   ├── sharing/            # 공유 에이전트
│   │   │   ├── base.py         # 공유 에이전트 기본 클래스
│   │   │   └── tool.py         # HTML 생성 및 공유 툴
│   │   ├── travel_planner/     # 여행 계획 에이전트
│   │   │   ├── base.py         # 여행 계획 에이전트 기본 클래스
│   │   │   └── tool.py         # 여행 계획 관련 툴
│   │   ├── decorators.py       # 에이전트 데코레이터
│   │   └── llm_model.py        # LLM 모델 설정
│   ├── api/                     # FastAPI 웹 API
│   │   └── app.py              # 메인 API 애플리케이션
│   ├── graph/                   # LangGraph 워크플로우
│   │   ├── builder.py          # 그래프 빌더 (워크플로우 구성)
│   │   └── types.py            # 타입 정의 및 상태 관리
│   ├── prompts/                 # AI 프롬프트 템플릿
│   │   ├── calendar.md         # 캘린더 에이전트 프롬프트
│   │   ├── coordinator.md      # 코디네이터 프롬프트
│   │   ├── planner.md          # 플래너 프롬프트
│   │   ├── search.md           # 검색 에이전트 프롬프트
│   │   ├── sharing.md          # 공유 에이전트 프롬프트
│   │   ├── supervisor.md       # 수퍼바이저 프롬프트
│   │   ├── travel_planner.md   # 여행 계획 에이전트 프롬프트
│   │   └── template.py         # 프롬프트 템플릿 엔진
│   ├── db/                      # 데이터베이스 설정
│   │   ├── base.py             # 기본 DB 설정
│   │   └── mongodb_checkpoint.py # MongoDB 체크포인트 관리
│   ├── service/                 # 비즈니스 로직 서비스
│   │   ├── history_service.py  # 채팅 히스토리 관리
│   │   └── workflow_service.py # 워크플로우 실행 서비스
│   └── config.py               # 환경 설정
├── shared_plans/               # 생성된 여행 계획 공유 파일
├── server.py                   # 서버 진입점
├── pyproject.toml             # 프로젝트 의존성 관리
├── Dockerfile                 # Docker 컨테이너 설정
└── uv.lock                   # 의존성 잠금 파일
```

![파일 구조](./images/스크린샷%202025-06-22%20오전%201.34.14.png)
*상세 파일 구조 및 의존성*

## 🛠️ 주요 기술 스택

### 🔧 Core Framework
- **FastAPI**: 고성능 웹 API 프레임워크
- **LangGraph**: Multi-agent 워크플로우 오케스트레이션
- **LangChain**: LLM 통합 및 체인 관리
- **OpenAI GPT**: 자연어 처리 모델

### 🗄️ 데이터베이스 & 저장소
- **MongoDB**: 체크포인트 및 히스토리 저장
- **LangGraph Checkpoint**: 워크플로우 상태 관리

### 🔌 외부 API 통합
- **Google Calendar API**: 일정 관리
- **Tavily Search API**: 실시간 여행 정보 검색
- **OpenAI API**: AI 텍스트 생성

### 📦 개발 도구
- **UV**: 파이썬 패키지 관리
- **Docker**: 컨테이너화
- **Pydantic**: 데이터 검증

## 🚀 시작하기

### 📋 사전 요구사항

- Python 3.12+
- MongoDB
- OpenAI API 키
- Google Calendar API 자격증명
- Tavily API 키

### ⚙️ 환경 설정

1. **환경 변수 설정**
```bash
cp .env.sample .env
```

필요한 환경 변수:
```
OPENAI_API_KEY=your_openai_key
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=travel_planner
GOOGLE_CALENDAR_CREDENTIALS=path/to/credentials.json
TAVILY_API_KEY=your_tavily_key
```

2. **의존성 설치**
```bash
cd backend
uv sync
```

### 🏃‍♂️ 실행

**개발 모드:**
```bash
python server.py
```

**Docker로 실행:**
```bash
docker-compose up --build
```

![실행 화면](./images/스크린샷%202025-06-22%20오전%201.34.38.png)
*실행 중인 시스템 모니터링*

## 📋 API 엔드포인트

### 💬 채팅 API
- `POST /api/chat/stream` - 실시간 스트리밍 채팅
- `GET /api/chat/history` - 채팅 히스토리 조회
- `GET /api/chat/history/all` - 전체 히스토리 조회

### 🏥 헬스체크
- `GET /health` - 서비스 상태 확인

### 📁 정적 파일 서빙
- `/shared/` - 생성된 여행 계획 HTML 파일 서빙

## 🔄 워크플로우 동작 과정

1. **사용자 요청 접수**: FastAPI를 통해 사용자의 여행 계획 요청 접수
2. **초기 계획 생성**: Planner 노드에서 기본 여행 계획 생성
3. **Supervisor 판단**: 어떤 에이전트가 다음에 실행될지 결정
4. **전문 에이전트 실행**:
   - 🔍 검색이 필요한 경우 → Search Agent
   - 📅 일정 확인이 필요한 경우 → Calendar Agent
   - 📤 공유가 필요한 경우 → Sharing Agent
   - ✈️ 세부 계획이 필요한 경우 → Travel Planner Agent
5. **결과 통합**: 각 에이전트의 결과를 종합하여 최종 응답 생성
6. **MongoDB 저장**: 전체 대화 히스토리와 상태를 MongoDB에 저장

## 🔧 주요 특징

### 🎯 스트리밍 응답
- Server-Sent Events(SSE)를 통한 실시간 응답 스트리밍
- 사용자에게 실시간 진행 상황 제공

### 🧠 상태 관리
- LangGraph의 체크포인트 시스템으로 복잡한 워크플로우 상태 관리
- MongoDB를 통한 영구 저장 및 복구

### 🔒 안전성
- 에이전트 간 안전한 메시지 전달
- 오류 처리 및 복구 메커니즘

### 🎨 확장성
- 새로운 에이전트 쉽게 추가 가능
- 모듈화된 구조로 유지보수 용이

## 📝 개발 가이드

### 🆕 새 에이전트 추가
1. `src/agents/` 에 새 폴더 생성
2. `base.py`, `tool.py` 구현
3. `src/prompts/` 에 프롬프트 템플릿 추가
4. `graph/builder.py` 에 노드 등록

### 🔧 프롬프트 수정
`src/prompts/` 폴더의 마크다운 파일들을 수정하여 각 에이전트의 동작 조정

## 🙏 참고 자료

이 프로젝트는 [langmanus](https://github.com/Darwin-lfl/langmanus) 오픈소스 프로젝트를 참고하여 개발되었습니다. LangGraph 기반의 다중 에이전트 시스템 구현에 대한 영감과 아키텍처 패턴을 제공받았습니다.


