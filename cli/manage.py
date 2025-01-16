import typer
import asyncio
from app.database import init_db
from app.models import User
from app.config import get_settings

app = typer.Typer()

@app.command()
def create_admin(email: str, full_name: str):
    """Create an admin user - this is the only CLI command we need to keep"""
    async def _create():
        await init_db()
        user = await User.create_user(
            email=email,
            full_name=full_name,
            is_admin=True
        )
        settings = get_settings()
        return user, settings

    user, settings = asyncio.run(_create())
    typer.echo(f"Admin user created successfully!")
    typer.echo(f"Email: {user.email}")
    typer.echo(f"Admin dashboard: {settings.base_url}/admin/{user.access_id}")

if __name__ == "__main__":
    app() 