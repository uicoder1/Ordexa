"""
Ordexa SQLite to PostgreSQL Migration Utility
=============================================
Safely streams records from the local SQLite database to a target PostgreSQL database
preserving primary keys, foreign key relationships, timestamps, and precision.

Features:
- Resumable: skips already-migrated primary keys safely.
- Conflict detection: raises MigrationConflictError if an existing ID has differing data.
- Chunk-level transactions: avoids holding long-lived transactions/connections.
- High-efficiency bulk insertion: uses psycopg2 execute_values for PostgreSQL.
- Boolean coercion: generically handles SQLite integer booleans to PostgreSQL booleans.
"""

import sys
import argparse
import re
from typing import List, Dict, Any, Set, Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.types import Boolean


class MigrationConflictError(Exception):
    """Raised when an existing target record conflicts with source record data."""
    pass


# Dependency-ordered tables to satisfy foreign key constraints
TABLE_MIGRATION_ORDER: List[str] = [
    "users",
    "organizations",
    "organization_members",
    "organization_subscriptions",
    "calculation_configs",
    "products",
    "uploaded_files",
    "orders",
    "returns",
    "settlements",
    "order_item_ledger",
    "cashback_ledger",
    "sku_metrics",
    "audit_logs",
    "password_reset_tokens",
]

CHUNK_SIZE = 1000


def coerce_boolean_value(val: Any) -> Any:
    """
    Coerce a SQLite boolean representation into a Python bool for PostgreSQL.
    - 0 must become False
    - 1 must become True
    - None must remain None
    - existing Python bool values must remain unchanged
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if val == 0:
        return False
    if val == 1:
        return True
    return bool(val)


def get_boolean_columns_for_table(target_inspector, tbl: str) -> Set[str]:
    """
    Generically detect boolean columns from the target table schema.
    Inspects SQLAlchemy column types to identify Boolean types across dialects.
    """
    try:
        columns = target_inspector.get_columns(tbl)
    except Exception:
        return set()

    boolean_cols = set()
    for col in columns:
        col_type = col.get("type")
        if isinstance(col_type, Boolean) or (hasattr(col_type, "as_generic") and isinstance(col_type.as_generic(), Boolean)):
            boolean_cols.add(col["name"])
    return boolean_cols


def transform_row_for_target(row_dict: Dict[str, Any], boolean_columns: Set[str]) -> Dict[str, Any]:
    """
    Transform row values to ensure compatibility with target column types.
    Applies boolean coercion generically for all identified boolean columns.
    """
    if not boolean_columns:
        return row_dict

    transformed = dict(row_dict)
    for col in boolean_columns:
        if col in transformed:
            transformed[col] = coerce_boolean_value(transformed[col])
    return transformed


def check_row_conflict(source_row: Dict[str, Any], target_row: Dict[str, Any], boolean_cols: Set[str]) -> Optional[str]:
    """
    Compare a source record against an already-existing target record.
    Returns a description string if there is a conflict, or None if matching.
    """
    for col, src_val in source_row.items():
        if col not in target_row:
            continue
        tgt_val = target_row[col]

        if col in boolean_cols:
            src_b = coerce_boolean_value(src_val)
            tgt_b = coerce_boolean_value(tgt_val)
            if src_b != tgt_b:
                return f"Column '{col}' differs: source={src_b!r}, target={tgt_b!r}"
            continue

        if isinstance(src_val, (float, int)) and isinstance(tgt_val, (float, int)):
            if abs(float(src_val) - float(tgt_val)) > 1e-6:
                return f"Column '{col}' differs: source={src_val!r}, target={tgt_val!r}"
            continue

        src_str = None if src_val is None else str(src_val).strip()
        tgt_str = None if tgt_val is None else str(tgt_val).strip()
        if src_str and tgt_str and src_str != tgt_str:
            s_clean = re.sub(r"\.0+$", "", src_str)
            t_clean = re.sub(r"\.0+$", "", tgt_str)
            if s_clean != t_clean:
                return f"Column '{col}' differs: source={src_val!r}, target={tgt_val!r}"
        elif (src_val is None) != (tgt_val is None):
            return f"Column '{col}' differs: source={src_val!r}, target={tgt_val!r}"

    return None


def get_existing_target_ids(target_engine, tbl: str) -> Set[str]:
    """
    Retrieve all primary key IDs already stored in target table.
    """
    inspector = inspect(target_engine)
    try:
        cols = [c["name"] for c in inspector.get_columns(tbl)]
    except Exception:
        return set()

    if "id" not in cols:
        return set()

    with target_engine.connect() as conn:
        res = conn.execute(text(f'SELECT "id" FROM "{tbl}"')).scalars().all()
        return set(res)


def get_target_rows_by_ids(target_engine, tbl: str, ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch existing target records for a list of IDs to enable conflict checking.
    """
    if not ids:
        return {}
    res = {}
    with target_engine.connect() as conn:
        for i in range(0, len(ids), 1000):
            sub_ids = ids[i : i + 1000]
            param_names = [f":id_{idx}" for idx in range(len(sub_ids))]
            stmt = text(f'SELECT * FROM "{tbl}" WHERE "id" IN ({", ".join(param_names)})')
            params = {f"id_{idx}": id_val for idx, id_val in enumerate(sub_ids)}
            rows = conn.execute(stmt, params).mappings().all()
            for r in rows:
                res[r["id"]] = dict(r)
    return res


def bulk_insert_rows(conn, tbl: str, columns: List[str], data_dicts: List[Dict[str, Any]]) -> None:
    """
    Insert rows into target table using high-efficiency batching.
    Uses psycopg2 execute_values on PostgreSQL for single-roundtrip batch insert,
    with standard parameterized executemany fallback on other engines.
    """
    if not data_dicts:
        return

    col_list_str = ", ".join(f'"{c}"' for c in columns)

    if conn.dialect.name == "postgresql":
        try:
            from psycopg2.extras import execute_values
            raw_conn = conn.connection.dbapi_connection
            cur = raw_conn.cursor()
            sql = f'INSERT INTO "{tbl}" ({col_list_str}) VALUES %s'
            records = [tuple(d.get(c) for c in columns) for d in data_dicts]
            execute_values(cur, sql, records, page_size=len(records))
            cur.close()
            return
        except Exception:
            # Fall back to standard execution if execute_values unavailable
            pass

    bind_list_str = ", ".join(f":{c}" for c in columns)
    insert_stmt = text(f'INSERT INTO "{tbl}" ({col_list_str}) VALUES ({bind_list_str})')
    conn.execute(insert_stmt, data_dicts)


def migrate_data(source_url: str, target_url: str, execute: bool = False):
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif target_url.startswith("postgresql://") and not target_url.startswith("postgresql+"):
        target_url = target_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    print(f"Connecting to Source (SQLite): {source_url}")
    source_engine = create_engine(source_url)

    masked_url = target_url.split("@")[-1] if "@" in target_url else target_url
    print(f"Connecting to Target (PostgreSQL): {masked_url}")
    target_engine = create_engine(target_url)

    source_inspector = inspect(source_engine)
    source_tables = set(source_inspector.get_table_names())

    target_inspector = inspect(target_engine)
    target_tables = set(target_inspector.get_table_names())

    print(f"\nMode: {'LIVE EXECUTION' if execute else 'DRY RUN (no changes will be written)'}")

    try:
        for tbl in TABLE_MIGRATION_ORDER:
            if tbl not in source_tables:
                print(f"  [SKIP] Table '{tbl}' does not exist in source database.")
                continue
            if tbl not in target_tables:
                print(f"  [ERROR] Table '{tbl}' does not exist in target database! Run alembic upgrade head first.")
                sys.exit(1)

            boolean_columns = get_boolean_columns_for_table(target_inspector, tbl)

            with source_engine.connect() as src_conn:
                total_source_rows = src_conn.execute(text(f'SELECT COUNT(*) FROM "{tbl}"')).scalar()

            existing_ids = get_existing_target_ids(target_engine, tbl)
            print(f"\nProcessing table '{tbl}' (Source: {total_source_rows} rows, Target existing: {len(existing_ids)} rows)...")
            if boolean_columns:
                print(f"  Detected boolean columns in target '{tbl}': {sorted(list(boolean_columns))}")

            if total_source_rows == 0:
                print(f"  0 rows in '{tbl}'. Continuing.")
                continue

            columns = [col["name"] for col in source_inspector.get_columns(tbl)]
            col_list_str = ", ".join(f'"{c}"' for c in columns)

            offset = 0
            total_migrated_table = 0
            total_skipped_table = 0

            while offset < total_source_rows:
                chunk_query = text(f'SELECT {col_list_str} FROM "{tbl}" LIMIT {CHUNK_SIZE} OFFSET {offset}')
                with source_engine.connect() as src_conn:
                    rows = src_conn.execute(chunk_query).mappings().all()

                if not rows:
                    break

                offset += len(rows)

                transformed_rows = [
                    transform_row_for_target(dict(r), boolean_columns)
                    for r in rows
                ]

                # Find rows that already exist in target for conflict verification
                chunk_existing_ids = [r["id"] for r in transformed_rows if "id" in r and r["id"] in existing_ids]
                if chunk_existing_ids:
                    target_rows_map = get_target_rows_by_ids(target_engine, tbl, chunk_existing_ids)
                    for r in transformed_rows:
                        r_id = r.get("id")
                        if r_id in target_rows_map:
                            tgt_row = target_rows_map[r_id]
                            conflict_reason = check_row_conflict(r, tgt_row, boolean_columns)
                            if conflict_reason:
                                raise MigrationConflictError(
                                    f"Data conflict detected for table '{tbl}', ID '{r_id}': {conflict_reason}"
                                )

                # Filter out already existing rows
                rows_to_insert = [r for r in transformed_rows if "id" not in r or r["id"] not in existing_ids]
                skipped_in_chunk = len(transformed_rows) - len(rows_to_insert)
                total_skipped_table += skipped_in_chunk

                if not execute:
                    total_migrated_table += len(rows_to_insert)
                    print(f"  [DRY RUN] Chunk offset {offset-len(rows)}: {len(rows_to_insert)} new rows would be inserted, {skipped_in_chunk} existing rows skipped.")
                    continue

                # Execute mode: chunk-level short transaction scope
                if rows_to_insert:
                    with target_engine.begin() as tgt_conn:
                        bulk_insert_rows(tgt_conn, tbl, columns, rows_to_insert)
                    for r in rows_to_insert:
                        if "id" in r:
                            existing_ids.add(r["id"])
                    total_migrated_table += len(rows_to_insert)
                    print(f"  Migrated {total_migrated_table}/{total_source_rows} rows into '{tbl}' (Chunk: {len(rows_to_insert)} inserted, {skipped_in_chunk} skipped)...")
                else:
                    print(f"  Chunk offset {offset-len(rows)}: All {skipped_in_chunk} rows already exist and matched target. Skipped safely.")

            if execute:
                print(f"  [COMPLETED] Table '{tbl}': {total_migrated_table} rows newly inserted, {total_skipped_table} rows skipped as already existing.")
            else:
                print(f"  [DRY RUN SUMMARY] Table '{tbl}': {total_migrated_table} rows would be inserted, {total_skipped_table} rows would be skipped.")

        print("\nData migration script finished.")
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Migrate Ordexa data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-url", default="sqlite:///backend/profitpilot.db", help="Source SQLite connection string")
    parser.add_argument("--postgres-url", required=True, help="Target PostgreSQL connection string")
    parser.add_argument("--execute", action="store_true", help="Execute the migration (defaults to dry-run)")
    args = parser.parse_args()

    migrate_data(args.sqlite_url, args.postgres_url, execute=args.execute)


if __name__ == "__main__":
    main()
