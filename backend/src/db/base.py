import logging

from motor.motor_asyncio import AsyncIOMotorClient

from ..config import MONGO_DB_NAME, MONGO_URI

client: AsyncIOMotorClient = None


async def get_db() -> AsyncIOMotorClient:
    if client is None:
        await connect_and_init_db()
    db_name = MONGO_DB_NAME
    return client[db_name]


async def connect_and_init_db():
    global client
    try:
        client = AsyncIOMotorClient(
            MONGO_URI,
            maxPoolSize=300,
            minPoolSize=15,
            uuidRepresentation="standard",
            serverSelectionTimeoutMS=5000,  # 서버 선택 타임아웃
            connectTimeoutMS=10000,  # 연결 타임아웃
            socketTimeoutMS=45000,  # 소켓 타임아웃
            waitQueueTimeoutMS=30000,  # 대기열 타임아웃
            retryReads=True,  # 읽기 재시도
        )

        logging.info("Connected to mongo.")
    except Exception as e:
        logging.exception(f"Could not connect to mongo: {e}")
        raise


async def close_db_connect():
    global client
    if client is None:
        logging.warning("Connection is None, nothing to close.")
        return
    client.close()
    client = None
    logging.info("Mongo connection closed.")
