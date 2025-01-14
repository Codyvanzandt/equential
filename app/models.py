import uuid
from beanie import Document
from pydantic import EmailStr
from typing import Optional
from app.config import get_settings

class User(Document):
    email: EmailStr
    full_name: str
    access_id: str = str(uuid.uuid4())

    class Settings:
        name = get_settings().users_collection

    @classmethod
    async def create_user(cls, email: str, full_name: str) -> "User":
        user = cls(
            email=email,
            full_name=full_name,
            access_id=str(uuid.uuid4())
        )
        await user.insert()
        return user 