from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from .db import Base

class UserToken(Base):
    __tablename__ = "user_tokens"
    id = Column(Integer, primary_key=True, index=True)
    # Spotify user id (stable)
    spotify_user_id = Column(String, unique=True, index=True, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_scope = Column(String, nullable=False)
    token_expires_at = Column(Integer, nullable=False)  # epoch seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
