from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models.user import User


db = SessionLocal()

try:
    user = db.scalar(
        select(User)
        .where(User.email == "demo@example.com")
    )

    if user:
        print(f"Test user already exists: {user.id}")
    else:
        user = User(
            username="demo_user",
            email="demo@example.com",
            hashed_password="demo-only",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"Created test user: {user.id}")

finally:
    db.close()