"""Pydantic models"""

from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Literal, List, Any

from backend.core.sql_safety import parse_read_only


class SQLCommandInput(BaseModel):
    """Validator for SQL queries.

    A keyword blacklist is not enough: `SELECT 1; DROP TABLE ticket_data` also
    starts with SELECT. The statement is parsed instead, and anything that is
    not a single read-only query is refused.
    """

    sql_query: str

    @field_validator("sql_query")
    @classmethod
    def validate_query(cls, value: str):
        parse_read_only(value)
        return value


class SQLCommandResult(BaseModel):
    """Normalized queries returned from SQL tools"""

    status: Literal["success", "failure"]
    rows: List[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    artifact: str | None = None
    sql_query: str | None = None
    error: str | None = None


    @classmethod
    def success(
        cls,
        rows: list[dict[str, Any]],
        row_count: int | None = None,
        truncated: bool = False,
        artifact: str | None = None,
        sql_query: str | None = None,
    ) -> "SQLCommandResult":
        return cls(
            status="success",
            rows=rows,
            row_count=len(rows) if row_count is None else row_count,
            truncated=truncated,
            artifact=artifact,
            sql_query=sql_query,
        )

    @classmethod
    def failure(cls, error: str, sql_query: str | None = None) -> "SQLCommandResult":
        return cls(status="failure", error=error, sql_query=sql_query)


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
