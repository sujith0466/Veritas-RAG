"""restore_uq_workspace_members_active_user

Revision ID: 20261111_ws_member_uq
Revises: wh_01_webhook_crypto
Create Date: 2026-11-11 13:00:00.000000+00:00

"""
from collections.abc import Sequence
from typing import Any, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20261111_ws_member_uq'
down_revision: Union[str, None] = 'wh_01_webhook_crypto'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = 'workspace_members'
INDEX_NAME = 'uq_workspace_members_active_user'


def _resolve_and_lock_table(conn: sa.engine.Connection) -> tuple[str, str, int]:
    """
    Deterministically resolves the visible schema, table name, and OID for the table,
    acquires a SHARE ROW EXCLUSIVE lock, and re-validates the relation OID post-lock
    to eliminate rename/replacement race conditions during lock wait.
    """
    preparer = conn.dialect.identifier_preparer

    # 1. Resolve table in visible search_path, rejecting system/temporary schemas
    initial_row = conn.execute(
        sa.text("""
            SELECT n.nspname, c.relname, c.oid, c.relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = :table_name
              AND pg_table_is_visible(c.oid)
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_temp%'
              AND n.nspname NOT LIKE 'pg_toast%';
        """),
        {"table_name": TABLE_NAME}
    ).fetchone()

    if initial_row is None:
        raise RuntimeError(
            f"Migration Abort: Table '{TABLE_NAME}' could not be resolved to a visible user table "
            f"in the current database search_path. Verify schema setup before running migrations."
        )

    schema_name, table_name, initial_oid = (
        str(initial_row[0]), str(initial_row[1]), int(initial_row[2])
    )
    raw_relkind = initial_row[3]
    relkind = raw_relkind.decode('ascii') if isinstance(raw_relkind, (bytes, bytearray)) else str(raw_relkind)

    if relkind != 'r':
        raise RuntimeError(
            f"Migration Abort: Visible relation '{schema_name}'.'{table_name}' is not an ordinary table "
            f"(relkind='{relkind}'). Refusing to operate on non-table relations."
        )

    # 2. Acquire schema-qualified table lock with timeout
    quoted_table = f"{preparer.quote_schema(schema_name)}.{preparer.quote(table_name)}"
    conn.execute(sa.text("SET LOCAL lock_timeout = '10s';"))
    conn.execute(sa.text(f"LOCK TABLE {quoted_table} IN SHARE ROW EXCLUSIVE MODE;"))

    # 3. Post-lock revalidation: verify OID and relkind have not changed while waiting for lock
    post_lock_row = conn.execute(
        sa.text("""
            SELECT c.oid, c.relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema_name
              AND c.relname = :table_name;
        """),
        {"schema_name": schema_name, "table_name": table_name}
    ).fetchone()

    if post_lock_row is None or int(post_lock_row[0]) != initial_oid:
        raise RuntimeError(
            f"Migration Abort: Relation '{schema_name}'.'{table_name}' identity changed "
            f"during lock acquisition wait window (initial OID={initial_oid}, "
            f"post-lock OID={post_lock_row[0] if post_lock_row else None}). "
            f"Transaction aborted to prevent targeting a swapped object."
        )

    post_raw_relkind = post_lock_row[1]
    post_relkind = (
        post_raw_relkind.decode('ascii')
        if isinstance(post_raw_relkind, (bytes, bytearray))
        else str(post_raw_relkind)
    )

    if post_relkind != 'r':
        raise RuntimeError(
            f"Migration Abort: Locked relation '{schema_name}'.'{table_name}' is no longer an ordinary table."
        )

    return schema_name, table_name, initial_oid


def _inspect_schema_collision(conn: sa.engine.Connection, schema_name: str) -> dict[str, Any] | None:
    """
    Directly query PostgreSQL pg_catalog to detect whether an object named INDEX_NAME
    already exists anywhere within schema_name, returning its owning table and structural properties.
    Requires PostgreSQL 11+ for pg_index.indnkeyatts (Veritas RAG specifies PostgreSQL 15+).
    """
    query = sa.text("""
        SELECT
            c.oid AS object_oid,
            c.relkind AS object_kind,
            c.relname AS object_name,
            n.nspname AS schema_name,
            tbl.relname AS owning_table_name,
            tbl.oid AS owning_table_oid,
            i.indisunique AS is_unique,
            i.indisvalid AS is_valid,
            i.indisready AS is_ready,
            i.indnkeyatts AS num_key_columns,
            i.indnatts AS total_columns,
            pg_get_expr(i.indpred, i.indrelid) AS predicate_expr,
            am.amname AS access_method,
            ARRAY(
                SELECT 
                    CASE 
                        WHEN i.indkey[ord - 1] = 0 THEN pg_get_indexdef(i.indexrelid, ord, true)
                        ELSE a.attname
                    END
                FROM generate_series(1, i.indnkeyatts) AS ord
                LEFT JOIN pg_attribute a 
                  ON a.attrelid = i.indrelid 
                 AND a.attnum = i.indkey[ord - 1]
                ORDER BY ord
            ) AS key_columns
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_index i ON i.indexrelid = c.oid
        LEFT JOIN pg_class tbl ON tbl.oid = i.indrelid
        LEFT JOIN pg_am am ON am.oid = c.relam
        WHERE n.nspname = :schema_name
          AND c.relname = :index_name;
    """)
    row = conn.execute(query, {
        "schema_name": schema_name,
        "index_name": INDEX_NAME
    }).fetchone()

    if row is None:
        return None

    return {
        "object_oid": int(row[0]),
        "object_kind": str(row[1]),
        "object_name": str(row[2]),
        "schema_name": str(row[3]),
        "owning_table_name": str(row[4]) if row[4] else None,
        "owning_table_oid": int(row[5]) if row[5] else None,
        "is_unique": bool(row[6]) if row[6] is not None else None,
        "is_valid": bool(row[7]) if row[7] is not None else None,
        "is_ready": bool(row[8]) if row[8] is not None else None,
        "num_key_columns": int(row[9]) if row[9] is not None else None,
        "total_columns": int(row[10]) if row[10] is not None else None,
        "predicate_expr": str(row[11]) if row[11] is not None else None,
        "access_method": str(row[12]) if row[12] else None,
        "key_columns": list(row[13]) if row[13] is not None else [],
    }


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Deterministic Resolution & Anti-Race Table Lock
    schema_name, table_name, table_oid = _resolve_and_lock_table(conn)

    # 2. Schema-Wide Index Collision Inspection
    existing_object = _inspect_schema_collision(conn, schema_name)

    if existing_object is not None:
        if existing_object["object_kind"] != 'i':
            raise RuntimeError(
                f"Schema Collision Failure: An object named '{INDEX_NAME}' already exists in schema "
                f"'{schema_name}', but is of type relkind='{existing_object['object_kind']}' (not an index).\n"
                f"Automated migration execution is halted. Manual DBA reconciliation is required."
            )

        if existing_object["owning_table_oid"] != table_oid:
            raise RuntimeError(
                f"Schema Collision Failure: An index named '{INDEX_NAME}' already exists in schema "
                f"'{schema_name}', but belongs to table '{existing_object['owning_table_name']}' "
                f"(OID={existing_object['owning_table_oid']}), not target table '{table_name}' (OID={table_oid}).\n"
                f"Automated migration execution is halted. Manual DBA reconciliation is required."
            )

        raise RuntimeError(
            f"Migration Precondition Failure: An index named '{INDEX_NAME}' already exists on target table "
            f"'{schema_name}'.'{table_name}'.\n"
            f"Catalog State: {existing_object}\n"
            f"Automated migration execution is halted. Manual Database Administrator (DBA) "
            f"inspection and explicit Project Owner authorization are required to reconcile database state."
        )

    # 3. Dialect-Safe Pre-Flight Duplicate Checking
    tbl = sa.table(
        table_name,
        sa.column("workspace_id"),
        sa.column("user_id"),
        sa.column("is_deleted"),
        schema=schema_name,
    )
    dup_stmt = (
        sa.select(
            tbl.c.workspace_id,
            tbl.c.user_id,
            sa.func.count().label("active_count"),
        )
        .where(tbl.c.is_deleted.is_(False))
        .group_by(tbl.c.workspace_id, tbl.c.user_id)
        .having(sa.func.count() > 1)
    )
    duplicate_rows = conn.execute(dup_stmt).fetchall()

    if duplicate_rows:
        formatted_duplicates = [
            f"(workspace_id={row[0]}, user_id={row[1]}, active_count={row[2]})"
            for row in duplicate_rows
        ]
        raise RuntimeError(
            f"Pre-flight migration check aborted: Found {len(duplicate_rows)} duplicate active membership group(s) "
            f"in '{schema_name}'.'{table_name}'. Creating unique index '{INDEX_NAME}' would fail.\n"
            f"Manual administrative de-duplication is required before migration execution.\n"
            f"Duplicate groups: {'; '.join(formatted_duplicates[:5])}"
        )

    # 4. Schema-Qualified Canonical Index Creation
    op.create_index(
        INDEX_NAME,
        table_name,
        ['workspace_id', 'user_id'],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text('is_deleted = false')
    )


def downgrade() -> None:
    conn = op.get_bind()

    # 1. Deterministic Resolution & Anti-Race Table Lock
    schema_name, table_name, table_oid = _resolve_and_lock_table(conn)

    # 2. Inspect Existing Index Before Dropping
    existing_object = _inspect_schema_collision(conn, schema_name)

    if existing_object is None:
        raise RuntimeError(
            f"Downgrade Precondition Failure: Expected canonical index '{INDEX_NAME}' "
            f"does not exist on '{schema_name}'.'{table_name}'.\n"
            f"Refusing to execute downgrade against a missing object. Manual DBA inspection required."
        )

    if existing_object["owning_table_oid"] != table_oid:
        raise RuntimeError(
            f"Downgrade Abort: Index '{INDEX_NAME}' in schema '{schema_name}' belongs to table "
            f"'{existing_object['owning_table_name']}', not target table '{table_name}'.\n"
            f"Refusing to drop an unrelated object. Manual DBA inspection required."
        )

    # 3. Verify All 7 Material Canonical Properties
    pred_normalized = (existing_object["predicate_expr"] or "").strip().lower()
    matches_canonical = (
        existing_object["access_method"] == 'btree'
        and existing_object["is_unique"] is True
        and existing_object["is_valid"] is True
        and existing_object["is_ready"] is True
        and existing_object["num_key_columns"] == 2
        and existing_object["total_columns"] == 2
        and existing_object["key_columns"] == ['workspace_id', 'user_id']
        and pred_normalized in ('(is_deleted = false)', '(not is_deleted)')
    )

    if not matches_canonical:
        raise RuntimeError(
            f"Downgrade Abort: Index '{INDEX_NAME}' on '{schema_name}'.'{table_name}' does not match "
            f"the expected canonical schema definition.\n"
            f"Catalog State: {existing_object}\n"
            f"Refusing to drop an unverified or malformed index. Manual DBA inspection required."
        )

    # 4. Schema-Qualified Drop of Verified Canonical Index
    op.drop_index(INDEX_NAME, table_name=table_name, schema=schema_name)
