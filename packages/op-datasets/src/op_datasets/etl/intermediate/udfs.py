"""DuckDB UDFs that are shared across intermediate models."""

from dataclasses import dataclass

from op_coreutils.duckdb_inmem import init_client


@dataclass
class Expression:
    """Helper class to hold the definition of an expression along with its alias."""

    alias: str
    sql_expr: str

    @property
    def expr(self):
        return self.sql_expr + " AS " + self.alias


def to_sql(exprs: list[Expression]):
    """Convert a list of expressions to a string that can be used as part of a SELECT."""
    return ",\n    ".join([_.expr for _ in exprs])


def create_duckdb_macros():
    """Create general purpose macros on the DuckDB in-memory client.

    These macros can be used as part of data model definitions.
    """
    client = init_client()

    client.sql("""
    CREATE OR REPLACE MACRO wei_to_eth(a)
    AS a::DECIMAL(28, 0) * 0.000000000000000001::DECIMAL(19, 19);

    CREATE OR REPLACE MACRO wei_to_gwei(a)
    AS a::DECIMAL(28, 0) * 0.000000001::DECIMAL(10, 10);

    CREATE OR REPLACE MACRO safe_div(a, b) AS
    IF(b = 0, NULL, a / b);
    """)

    # Return the client for convenience when writing unit tests.
    # Tests can use the client to run sql queries that exercise the defined macros.
    return client


# The functions below are defined for cosmetic purposes. When used they add syntax highlighting
# to SQL expressions which makes them easier to read.


def wei_to_eth(x):
    return f"wei_to_eth({x})"


def wei_to_gwei(x):
    return f"wei_to_gwei({x})"


def safe_div(x, y):
    return f"safe_div({x}, {y})"
