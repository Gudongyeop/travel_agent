FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치를 위한 파일들 복사
COPY frontend/pyproject.toml ./
COPY frontend/uv.lock ./

# uv 설치 및 의존성 설치
RUN pip install uv
RUN uv sync --frozen

# 소스 코드 복사
COPY frontend ./frontend

# 포트 노출
EXPOSE 8501

# 작업 디렉토리를 frontend로 변경
WORKDIR /app/frontend

# Streamlit 서버 실행
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"] 