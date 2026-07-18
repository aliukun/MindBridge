from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, inspect
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.sql.elements import ClauseElement
from sqlalchemy.sql.schema import Column, Table

from app.core.database import Base
from app.models import entities  # noqa: F401


class IncompatibleDatabaseSchemaError(RuntimeError):
    """已有数据库结构与当前 ORM 元数据不兼容。"""

    def __init__(self, differences: Sequence[str]) -> None:
        self.differences = tuple(sorted(differences))

        detail = " | ".join(self.differences)

        super().__init__(
            "Database schema is incompatible with the current "
            "ORM metadata; no schema changes were applied. "
            f"Differences: {detail}"
        )


def _normalize_sql(value: object | None) -> str | None:
    """归一化数据库反射得到的 SQL 片段，减少格式差异。"""

    if value is None:
        return None

    normalized = "".join(str(value).upper().split())

    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1]

    return normalized


def _compiled_type(
    column_type: Any,
    dialect: Dialect,
) -> str:
    """把 ORM 类型和数据库反射类型编译成可比较文本。"""

    return str(column_type.compile(dialect=dialect)).upper()


def _expected_default(
    column: Column[Any],
    dialect: Dialect,
) -> str | None:
    if column.server_default is None:
        return None

    default_value = getattr(
        column.server_default,
        "arg",
        None,
    )

    if isinstance(default_value, ClauseElement):
        default_value = default_value.compile(dialect=dialect)

    return _normalize_sql(default_value)


def _expected_columns(
    table: Table,
    dialect: Dialect,
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            column.name,
            _compiled_type(column.type, dialect),
            bool(column.nullable),
            bool(column.primary_key),
            _expected_default(column, dialect),
        )
        for column in table.columns
    )


def _actual_columns(
    inspector: Any,
    table_name: str,
    dialect: Dialect,
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            column["name"],
            _compiled_type(column["type"], dialect),
            bool(column["nullable"]),
            bool(column["primary_key"]),
            _normalize_sql(column.get("default")),
        )
        for column in inspector.get_columns(table_name)
    )


def _expected_indexes(
    table: Table,
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                index.name,
                tuple(column.name for column in index.columns),
                bool(index.unique),
            )
            for index in table.indexes
        )
    )


def _actual_indexes(
    inspector: Any,
    table_name: str,
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                index["name"],
                tuple(index["column_names"]),
                bool(index["unique"]),
            )
            for index in inspector.get_indexes(table_name)
        )
    )


def _expected_checks(
    table: Table,
) -> tuple[tuple[str | None, str | None], ...]:
    checks = [
        (
            (None if constraint.name is None else str(constraint.name)),
            _normalize_sql(constraint.sqltext),
        )
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    return tuple(
        sorted(
            checks,
            key=lambda check: (
                check[0] or "",
                check[1] or "",
            ),
        )
    )


def _actual_checks(
    inspector: Any,
    table_name: str,
) -> tuple[tuple[str | None, str | None], ...]:
    checks = [
        (
            (str(constraint["name"]) if constraint.get("name") is not None else None),
            _normalize_sql(constraint.get("sqltext")),
        )
        for constraint in inspector.get_check_constraints(table_name)
    ]

    return tuple(
        sorted(
            checks,
            key=lambda check: (
                check[0] or "",
                check[1] or "",
            ),
        )
    )


def _ondelete(value: object | None) -> str:
    if value is None:
        return "NO ACTION"

    return str(value).upper()


def _expected_foreign_keys(
    table: Table,
) -> tuple[tuple[object, ...], ...]:
    foreign_keys: list[tuple[object, ...]] = []

    for constraint in table.constraints:
        if not isinstance(
            constraint,
            ForeignKeyConstraint,
        ):
            continue

        elements = list(constraint.elements)

        foreign_keys.append(
            (
                tuple(element.parent.name for element in elements),
                elements[0].column.table.name,
                tuple(element.column.name for element in elements),
                _ondelete(constraint.ondelete),
            )
        )

    return tuple(sorted(foreign_keys))


def _actual_foreign_keys(
    inspector: Any,
    table_name: str,
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                tuple(constraint["constrained_columns"]),
                constraint["referred_table"],
                tuple(constraint["referred_columns"]),
                _ondelete(constraint.get("options", {}).get("ondelete")),
            )
            for constraint in inspector.get_foreign_keys(table_name)
        )
    )


def schema_differences(bind: Engine) -> tuple[str, ...]:
    """只读比较现有数据库与当前 ORM Schema。"""

    inspector = inspect(bind)
    dialect = bind.dialect
    expected_tables = set(Base.metadata.tables)
    actual_tables = set(inspector.get_table_names())
    differences: list[str] = []

    missing_tables = sorted(expected_tables - actual_tables)
    unexpected_tables = sorted(actual_tables - expected_tables)

    if missing_tables:
        differences.append("missing tables=" + ",".join(missing_tables))

    if unexpected_tables:
        differences.append("unexpected tables=" + ",".join(unexpected_tables))

    for table_name in sorted(expected_tables & actual_tables):
        table = Base.metadata.tables[table_name]

        if _actual_columns(
            inspector,
            table_name,
            dialect,
        ) != _expected_columns(table, dialect):
            differences.append(f"{table_name}: columns differ")

        if _actual_indexes(
            inspector,
            table_name,
        ) != _expected_indexes(table):
            differences.append(f"{table_name}: indexes differ")

        if _actual_checks(
            inspector,
            table_name,
        ) != _expected_checks(table):
            differences.append(f"{table_name}: check constraints differ")

        if _actual_foreign_keys(
            inspector,
            table_name,
        ) != _expected_foreign_keys(table):
            differences.append(f"{table_name}: foreign keys differ")

    return tuple(sorted(differences))


def ensure_schema(bind: Engine) -> bool:
    """空库建表；非空库只读核验，绝不自动修改。"""

    existing_tables = set(inspect(bind).get_table_names())

    if existing_tables:
        differences = schema_differences(bind)

        if differences:
            raise IncompatibleDatabaseSchemaError(differences)

        return False

    Base.metadata.create_all(bind=bind)

    differences = schema_differences(bind)

    if differences:
        raise RuntimeError(
            "New database schema failed validation: " + " | ".join(differences)
        )

    return True
