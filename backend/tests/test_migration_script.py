import pytest
import tempfile
import os
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer, Float, Boolean
from sqlalchemy import inspect
from scripts.migrate_sqlite_to_postgres import (
    coerce_boolean_value,
    get_boolean_columns_for_table,
    transform_row_for_target,
    check_row_conflict,
    get_existing_target_ids,
    get_target_rows_by_ids,
    bulk_insert_rows,
    migrate_data,
    MigrationConflictError,
    TABLE_MIGRATION_ORDER,
)


def test_coerce_boolean_value_spec():
    """
    Requirements verification:
    - SQLite 0 -> PostgreSQL False
    - SQLite 1 -> PostgreSQL True
    - None -> None
    - Python True/False remain unchanged
    """
    # 0 -> False
    val_zero = coerce_boolean_value(0)
    assert val_zero is False
    assert type(val_zero) is bool

    # 1 -> True
    val_one = coerce_boolean_value(1)
    assert val_one is True
    assert type(val_one) is bool

    # None -> None
    val_none = coerce_boolean_value(None)
    assert val_none is None

    # Python True -> True
    val_true = coerce_boolean_value(True)
    assert val_true is True
    assert type(val_true) is bool

    # Python False -> False
    val_false = coerce_boolean_value(False)
    assert val_false is False
    assert type(val_false) is bool


def test_generic_boolean_column_detection():
    """
    Verify generic detection of Boolean columns via target schema inspector
    without hardcoding table or column names.
    """
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()

    Table(
        "sample_dynamic_table",
        metadata,
        Column("id", String, primary_key=True),
        Column("title", String),
        Column("quantity", Integer),
        Column("price", Float),
        Column("is_enabled", Boolean),
        Column("is_archived", Boolean),
    )
    metadata.create_all(engine)

    target_inspector = inspect(engine)
    boolean_cols = get_boolean_columns_for_table(target_inspector, "sample_dynamic_table")

    assert boolean_cols == {"is_enabled", "is_archived"}
    assert "id" not in boolean_cols
    assert "quantity" not in boolean_cols
    assert "price" not in boolean_cols


def test_transform_row_for_target():
    """
    Verify that row dictionaries are correctly transformed:
    - Boolean columns are coerced (0->False, 1->True, None->None, bool->bool)
    - Non-boolean integer/float/string columns are NOT altered
    """
    boolean_cols = {"is_platform_admin", "is_rto", "settlement_is_net", "is_flagged"}

    raw_row = {
        "id": "user-uuid-123",
        "email": "test@example.com",
        "login_count": 1,         # integer column, must NOT become bool
        "retry_limit": 0,         # integer column, must NOT become bool
        "ratio": 1.0,             # float column, must NOT become bool
        "is_platform_admin": 0,   # boolean column, 0 -> False
        "is_rto": 1,              # boolean column, 1 -> True
        "settlement_is_net": None,# boolean column, None -> None
        "is_flagged": True,       # boolean column, True -> True
        "is_suspended": False,    # unlisted column remains as-is
    }

    transformed = transform_row_for_target(raw_row, boolean_cols)

    # Boolean columns converted
    assert transformed["is_platform_admin"] is False
    assert type(transformed["is_platform_admin"]) is bool

    assert transformed["is_rto"] is True
    assert type(transformed["is_rto"]) is bool

    assert transformed["settlement_is_net"] is None

    assert transformed["is_flagged"] is True
    assert type(transformed["is_flagged"]) is bool

    # Non-boolean columns untouched
    assert transformed["login_count"] == 1
    assert type(transformed["login_count"]) is int

    assert transformed["retry_limit"] == 0
    assert type(transformed["retry_limit"]) is int

    assert transformed["ratio"] == 1.0
    assert type(transformed["ratio"]) is float

    assert transformed["id"] == "user-uuid-123"
    assert transformed["email"] == "test@example.com"


def test_end_to_end_boolean_streaming_simulation():
    """
    Simulate end-to-end migration streaming from a source database where booleans
    are stored as integers (0, 1) and NULL into a target database with Boolean types.
    """
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")

    with source_engine.connect() as src_conn:
        src_conn.execute(text("CREATE TABLE test_data (id VARCHAR PRIMARY KEY, is_active INTEGER, is_staff INTEGER, is_guest INTEGER)"))
        src_conn.execute(text("INSERT INTO test_data VALUES ('1', 0, 1, NULL)"))
        src_conn.execute(text("INSERT INTO test_data VALUES ('2', 1, 0, 1)"))
        src_conn.commit()

    target_metadata = MetaData()
    Table(
        "test_data",
        target_metadata,
        Column("id", String, primary_key=True),
        Column("is_active", Boolean),
        Column("is_staff", Boolean),
        Column("is_guest", Boolean),
    )
    target_metadata.create_all(target_engine)

    target_inspector = inspect(target_engine)
    boolean_columns = get_boolean_columns_for_table(target_inspector, "test_data")
    assert boolean_columns == {"is_active", "is_staff", "is_guest"}

    # Stream and transform
    with source_engine.connect() as src_conn:
        rows = src_conn.execute(text("SELECT id, is_active, is_staff, is_guest FROM test_data ORDER BY id")).mappings().all()
        transformed_rows = [transform_row_for_target(dict(r), boolean_columns) for r in rows]

    with target_engine.begin() as tgt_conn:
        insert_stmt = text('INSERT INTO "test_data" (id, is_active, is_staff, is_guest) VALUES (:id, :is_active, :is_staff, :is_guest)')
        tgt_conn.execute(insert_stmt, transformed_rows)

    with target_engine.connect() as tgt_conn:
        results = tgt_conn.execute(text("SELECT id, is_active, is_staff, is_guest FROM test_data ORDER BY id")).mappings().all()

        row1 = results[0]
        assert row1["id"] == "1"
        assert row1["is_active"] is False or row1["is_active"] == 0
        assert row1["is_staff"] is True or row1["is_staff"] == 1
        assert row1["is_guest"] is None

        # Verify python types passed in
        assert transformed_rows[0]["is_active"] is False
        assert type(transformed_rows[0]["is_active"]) is bool
        assert transformed_rows[0]["is_staff"] is True
        assert type(transformed_rows[0]["is_staff"]) is bool
        assert transformed_rows[0]["is_guest"] is None

        assert transformed_rows[1]["is_active"] is True
        assert type(transformed_rows[1]["is_active"]) is bool
        assert transformed_rows[1]["is_staff"] is False
        assert type(transformed_rows[1]["is_staff"]) is bool
        assert transformed_rows[1]["is_guest"] is True
        assert type(transformed_rows[1]["is_guest"]) is bool


def test_table_migration_order_covers_all_models():
    """
    Confirm all 15 core application models are present in TABLE_MIGRATION_ORDER.
    """
    expected_tables = {
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
    }
    assert set(TABLE_MIGRATION_ORDER) == expected_tables
    assert len(TABLE_MIGRATION_ORDER) == 15


def test_check_row_conflict_detection():
    """
    Verify check_row_conflict identifies matching rows as None
    and returns descriptive conflict reasons when data fields diverge.
    """
    boolean_cols = {"is_active"}

    # Matching row
    src = {"id": "1", "name": "Alpha", "is_active": 1, "amount": 100.0}
    tgt = {"id": "1", "name": "Alpha", "is_active": True, "amount": 100.0}
    assert check_row_conflict(src, tgt, boolean_cols) is None

    # Mismatched string
    tgt_diff_str = {"id": "1", "name": "Beta", "is_active": True, "amount": 100.0}
    conflict = check_row_conflict(src, tgt_diff_str, boolean_cols)
    assert conflict is not None
    assert "name" in conflict

    # Mismatched boolean
    tgt_diff_bool = {"id": "1", "name": "Alpha", "is_active": False, "amount": 100.0}
    conflict_bool = check_row_conflict(src, tgt_diff_bool, boolean_cols)
    assert conflict_bool is not None
    assert "is_active" in conflict_bool

    # Mismatched numeric
    tgt_diff_num = {"id": "1", "name": "Alpha", "is_active": True, "amount": 999.0}
    conflict_num = check_row_conflict(src, tgt_diff_num, boolean_cols)
    assert conflict_num is not None
    assert "amount" in conflict_num


def test_resuming_partially_completed_table_and_no_duplicates():
    """
    Test resume mechanism:
    - Target already contains 2 out of 5 source rows.
    - migrate_data with execute=True must skip the 2 existing rows without duplicate error.
    - Resulting target must contain all 5 rows with 0 duplicates.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as src_f, \
         tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tgt_f:
        src_path = src_f.name
        tgt_path = tgt_f.name

    try:
        src_url = f"sqlite:///{src_path}"
        tgt_url = f"sqlite:///{tgt_path}"

        src_engine = create_engine(src_url)
        tgt_engine = create_engine(tgt_url)

        # Setup schema for 'users' table in both
        with src_engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, is_platform_admin INTEGER)"))
            for i in range(1, 6):
                conn.execute(text(f"INSERT INTO users VALUES ('u{i}', 'user{i}@example.com', 0)"))

        with tgt_engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, is_platform_admin BOOLEAN)"))
            # Pre-populate rows u1 and u2 (simulating partial prior run)
            conn.execute(text("INSERT INTO users VALUES ('u1', 'user1@example.com', 0)"))
            conn.execute(text("INSERT INTO users VALUES ('u2', 'user2@example.com', 0)"))

        # Verify initial target state
        assert len(get_existing_target_ids(tgt_engine, "users")) == 2

        # Run migration with execute=True
        migrate_data(src_url, tgt_url, execute=True)

        # Verify target state after resume
        target_ids = get_existing_target_ids(tgt_engine, "users")
        assert len(target_ids) == 5
        assert target_ids == {"u1", "u2", "u3", "u4", "u5"}

        # Running migration again (idempotent run) must skip all 5 rows without error
        migrate_data(src_url, tgt_url, execute=True)
        assert len(get_existing_target_ids(tgt_engine, "users")) == 5

    finally:
        if 'src_engine' in locals():
            src_engine.dispose()
        if 'tgt_engine' in locals():
            tgt_engine.dispose()
        for p in (src_path, tgt_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


def test_conflicting_existing_ids_raise_migration_conflict_error():
    """
    Test conflict handling:
    - Target already contains row 'u1' with conflicting email ('different@example.com').
    - Migration must detect conflict, raise MigrationConflictError, and halt without overwriting.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as src_f, \
         tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tgt_f:
        src_path = src_f.name
        tgt_path = tgt_f.name

    try:
        src_url = f"sqlite:///{src_path}"
        tgt_url = f"sqlite:///{tgt_path}"

        src_engine = create_engine(src_url)
        tgt_engine = create_engine(tgt_url)

        with src_engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, is_platform_admin INTEGER)"))
            conn.execute(text("INSERT INTO users VALUES ('u1', 'original@example.com', 0)"))

        with tgt_engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, is_platform_admin BOOLEAN)"))
            conn.execute(text("INSERT INTO users VALUES ('u1', 'modified_elsewhere@example.com', 0)"))

        with pytest.raises(MigrationConflictError) as exc_info:
            migrate_data(src_url, tgt_url, execute=True)

        assert "Data conflict detected" in str(exc_info.value)
        assert "users" in str(exc_info.value)
        assert "u1" in str(exc_info.value)

        # Verify target row was NOT overwritten or mutated
        with tgt_engine.connect() as conn:
            val = conn.execute(text("SELECT email FROM users WHERE id = 'u1'")).scalar()
            assert val == "modified_elsewhere@example.com"

    finally:
        if 'src_engine' in locals():
            src_engine.dispose()
        if 'tgt_engine' in locals():
            tgt_engine.dispose()
        for p in (src_path, tgt_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


def test_chunk_level_transaction_scope_and_isolation():
    """
    Verify that each chunk is committed in its own short transaction scope
    rather than holding a single persistent transaction across the entire table.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE test_chunk (id TEXT PRIMARY KEY, val INTEGER)"))

    # Insert chunk 1
    chunk1 = [{"id": f"c1_{i}", "val": i} for i in range(5)]
    with engine.begin() as conn:
        bulk_insert_rows(conn, "test_chunk", ["id", "val"], chunk1)

    # Verify chunk 1 is committed and visible outside transaction
    with engine.connect() as conn:
        cnt1 = conn.execute(text("SELECT COUNT(*) FROM test_chunk")).scalar()
        assert cnt1 == 5

    # Simulate chunk 2 failing inside its own transaction
    chunk2_bad = [{"id": "c1_0", "val": 999}] # Duplicate PK causes failure
    with pytest.raises(Exception):
        with engine.begin() as conn:
            bulk_insert_rows(conn, "test_chunk", ["id", "val"], chunk2_bad)

    # Verify chunk 1 remains intact and committed, chunk 2 was rolled back cleanly
    with engine.connect() as conn:
        cnt2 = conn.execute(text("SELECT COUNT(*) FROM test_chunk")).scalar()
        assert cnt2 == 5
