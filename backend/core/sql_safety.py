"""Read-only SQL safety checks shared by every agent that executes SQL.

An LLM writes the queries, so the database must never depend on the model
behaving. These checks parse the statement with sqlglot and reject anything
that is not a single, bounded, read-only SELECT before it reaches the engine.

A first-word blacklist is not enough: `SELECT 1; DROP TABLE ticket_data` and
`SELECT ... INTO OUTFILE '/tmp/x'` both start with SELECT.
"""

from logging import getLogger

import sqlglot
from sqlglot import expressions as exp


logger = getLogger(__name__)

DEFAULT_DIALECT = "mysql"

# Statement roots that only read data.
READ_ONLY_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Subquery)

# Node types that write, change or leak data, wherever they appear.
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
    exp.Set,
    exp.Use,
    exp.Command,  # anything sqlglot could not model, e.g. CALL / SHOW / vendor syntax
    exp.Into,  # SELECT ... INTO OUTFILE / INTO DUMPFILE
)

# MySQL functions used to stall, probe or read the host filesystem.
FORBIDDEN_FUNCTIONS = frozenset(
    {
        "sleep",
        "benchmark",
        "load_file",
        "get_lock",
        "release_lock",
        "master_pos_wait",
        "sys_exec",
        "sys_eval",
    }
)


class UnsafeSQLError(ValueError):
    """Raised when a statement is not a safe, read-only query."""


def parse_read_only(sql_query: str, dialect: str = DEFAULT_DIALECT) -> exp.Expression:
    """Parse a query and guarantee it only reads data.

    Args:
        sql_query: The raw SQL statement.
        dialect: SQL dialect used for parsing.

    Returns:
        The parsed sqlglot expression, reusable by callers that inspect the query.

    Raises:
        UnsafeSQLError: If the statement cannot be parsed, contains more than one
            statement, or performs anything other than a read.
    """

    if not sql_query or not sql_query.strip():
        raise UnsafeSQLError("The query is empty.")

    try:
        statements = [statement for statement in sqlglot.parse(sql_query, dialect=dialect) if statement]
    except sqlglot.ParseError as error:
        raise UnsafeSQLError(f"The query could not be parsed: {error}") from error

    if not statements:
        raise UnsafeSQLError("The query contains no statement.")

    if len(statements) > 1:
        raise UnsafeSQLError(
            "Only one statement per call is allowed; stacked statements are rejected."
        )

    statement = statements[0]
    expression = statement.this if isinstance(statement, exp.With) else statement

    if not isinstance(expression, READ_ONLY_ROOTS):
        raise UnsafeSQLError(
            f"Only SELECT statements are allowed, got {type(expression).__name__.upper()}."
        )

    for node in statement.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeSQLError(
                f"The query contains a forbidden construct: {type(node).__name__.upper()}."
            )
        if isinstance(node, exp.Anonymous) and str(node.this).lower() in FORBIDDEN_FUNCTIONS:
            raise UnsafeSQLError(f"The function {node.this}() is not allowed.")

    return statement


def enforce_limit(
    statement: exp.Expression,
    max_limit: int,
    dialect: str = DEFAULT_DIALECT,
) -> str:
    """Add or cap the LIMIT clause so a query can never return an unbounded result.

    Args:
        statement: A parsed statement, as returned by :func:`parse_read_only`.
        max_limit: Highest number of rows a query may return.
        dialect: SQL dialect used when rendering the statement back to text.

    Returns:
        The SQL text with a LIMIT of at most `max_limit`.
    """

    limit = statement.args.get("limit")
    current = limit.expression if limit is not None else None

    if current is None or not current.is_int or int(current.name) > max_limit:
        statement = statement.limit(max_limit, copy=True)

    return statement.sql(dialect=dialect)
