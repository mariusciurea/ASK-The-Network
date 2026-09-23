"""Tools for all sub-agents"""

import json
from logging import getLogger

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from google.genai.types import Part
from google.adk.tools import ToolContext

from backend.data_models.models import SQLCommandResult, SQLCommandInput
from backend.database.db import engine

from backend.core.settings import settings

from typing import Any


logger = getLogger(__name__)
sql_command_logger = getLogger("audit.sql.commands")
sql_result_logger = getLogger("audit.sql.results")

SQL_OUTPUT_ARTIFACT = "sql_command_output.json"


async def save_rows_artifact(
    rows: list[dict[str, Any]],
    tool_context: ToolContext,
    artifact_filename: str = SQL_OUTPUT_ARTIFACT,
) -> str:
    """Store a full result set as an artifact so no row is silently lost.

    Args:
        rows: Rows returned by the database.
        tool_context: ToolContext object of the calling tool.
        artifact_filename: Name of the artifact to write.

    Returns:
        The artifact filename.
    """

    bytes_query_response = json.dumps(rows, indent=2, default=str).encode("utf-8")

    artifact_content = Part.from_bytes(
        data=bytes_query_response,
        mime_type="application/json",
    )
    await tool_context.save_artifact(artifact_filename, artifact_content)
    return artifact_filename


async def send_sql_command(sql_query: str, tool_context: ToolContext) -> SQLCommandResult:
    """Execute a read-only SQL query using the configured database connection.

      Args:
          sql_query: Raw SQL query to execute. Must be a single SELECT statement.
          tool_context: ToolContext object - context of the send_sql_command tool

      Returns:
          SQLCommandResult with either returned rows or error details. When the
          result is larger than the row budget, the rows are truncated for the
          model and the full result set is stored as an artifact.
    """

    if not sql_query:
        return SQLCommandResult.failure("sql_query parameter should not be empty")

    try:
        sql_query_model = SQLCommandInput(sql_query=sql_query)
    except ValidationError as error:
        # Surfaced to the agent on purpose: it can correct the query and retry.
        logger.warning("Rejected SQL query: %s", error)
        return SQLCommandResult.failure(
            f"The query was rejected before execution: {error.errors()[0]['msg']}",
            sql_query=sql_query,
        )

    try:
        with engine.connect() as connection:
            sql_command_logger.info(f"Sending SQL command: {sql_query_model.sql_query}")
            result = connection.execute(text(sql_query_model.sql_query))

            if not result.returns_rows:
                return SQLCommandResult.success(rows=[], sql_query=sql_query_model.sql_query)

            rows = [dict(row) for row in result.mappings().all()]

            if len(rows) > settings.MAX_ROWS:
                artifact = await save_rows_artifact(rows, tool_context)
                sql_result_logger.info(f"rows: {rows[0:settings.MAX_ROWS]}")
                return SQLCommandResult.success(
                    rows=rows[0:settings.MAX_ROWS],
                    row_count=len(rows),
                    truncated=True,
                    artifact=artifact,
                    sql_query=sql_query_model.sql_query,
                )

            sql_result_logger.info(f"rows: {rows}")
            return SQLCommandResult.success(rows=rows, sql_query=sql_query_model.sql_query)
    except SQLAlchemyError as e:
        logger.error(str(e))
        return SQLCommandResult.failure(str(e), sql_query=sql_query_model.sql_query)
