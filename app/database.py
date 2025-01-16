from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from .models import User, Experiment
from .config import get_settings
import logging

async def init_db():
    try:
        settings = get_settings()
        client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=5000
        )
        # Test the connection
        await client.server_info()
        await init_beanie(
            database=client[settings.database_name],
            document_models=[User, Experiment]
        )
        logging.info("Successfully connected to MongoDB Atlas")
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB Atlas: {str(e)}")
        raise 