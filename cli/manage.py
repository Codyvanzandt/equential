import typer
import asyncio
from app.database import init_db
from app.models import User
from app.config import get_settings

app = typer.Typer()

async def async_create_user(email: str, full_name: str):
    await init_db()
    user = await User.create_user(email=email, full_name=full_name)
    return user

async def async_delete_user(email: str):
    await init_db()
    user = await User.find_one({"email": email})
    if user:
        await user.delete()
        return True
    return False

@app.command()
def create_user(email: str, full_name: str):
    """Create a new user and generate their access link"""
    settings = get_settings()
    user = asyncio.run(async_create_user(email, full_name))
    typer.echo(f"User created successfully!")
    typer.echo(f"Access link: {settings.base_url}/user/{user.access_id}")

@app.command()
def delete_user(email: str):
    """Delete a user"""
    success = asyncio.run(async_delete_user(email))
    if success:
        typer.echo(f"User {email} has been deleted")
    else:
        typer.echo(f"User {email} not found")

if __name__ == "__main__":
    app() 