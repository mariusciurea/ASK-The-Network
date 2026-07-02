"""Pydantic models"""

from pydantic import BaseModel, Field
from typing import Literal, List, Any


class SQLCommandResult(BaseModel):
    """Normalized queries returned from SQL tools"""

    status: Literal["success", "failure"]
    rows: List[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


    @classmethod
    def success(cls, rows: list[dict[str, Any]]) -> "SQLCommandResult":
        return cls(status="success", rows=rows)

    @classmethod
    def failure(cls, error: str):
        return cls(status="failure", error=error)


class UserCreate(BaseModel):
    """Payload for registering a user."""

    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Payload for logging in a user."""

    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    """Public user fields."""

    id: int
    username: str
    email: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT response returned after authentication."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
