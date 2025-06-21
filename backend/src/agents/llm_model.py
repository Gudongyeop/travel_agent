import os

from langchain.chat_models import init_chat_model

llm = init_chat_model(
    model="gpt-4o",
    model_provider="openai",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
)
