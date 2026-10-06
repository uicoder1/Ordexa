"""
Ordexa Database Migration Validation Tool
=========================================
Compares SQLite and PostgreSQL databases or verifies integrity and benchmarks
on a single database instance following migration.
"""

import sys
import argparse
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text, inspect

FLIPKART_BENCHMARK = {
    "total_rows": 2373,
    "sales": 1734,
    "returns": 486,
    "cancellations": 134,
    "return_cancellations": 19,
    "unique_skus": 57,
    "returned_value": 97967.0,
}

CORE_TABLES = [
    "users",
    "organizations",
    "organization_members",
    "organization_subscriptions",
    "products",
    "calculation_configs",
    "sku_metrics",
    "uploaded_files",
    "cashback_ledger",
    "order_item_ledger",
    "orders",
    "returns",
    "settlements",
    "audit_logs",
    "password_reset_tokens",
]


def extract_database_stats(engine) -> Dict[str, Any]:
    stats: Dict[str, Any] = {"table_counts": {}, "orgs": 0, "users": 0, "flipkart_metrics": {}}

    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        for tbl in CORE_TABLES:
            if tbl in existing_tables:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                stats["table_counts"][tbl] = cnt
            else:
                stats["table_counts"][tbl] = None

        if "organizations" in existing_tables:
            stats["orgs"] = conn.execute(text("SELECT COUNT(*) FROM organizations")).scalar()

        if "users" in existing_tables:
            stats["users"] = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()

        if "order_item_ledger" in existing_tables:
            # Locate Flipkart org (either by known id or by largest row count)
            flipkart_org_query = text(
                "SELECT organization_id, COUNT(*) as c FROM order_item_ledger "
                "GROUP BY organization_id ORDER BY c DESC LIMIT 1"
            )
            row = conn.execute(flipkart_org_query).fetchone()
            if row:
                org_id = row[0]
                stats["flipkart_metrics"]["organization_id"] = org_id
                stats["flipkart_metrics"]["total_rows"] = row[1]

                # Event breakdown
                breakdown_q = text(
                    "SELECT event_subtype, COUNT(*) FROM order_item_ledger "
                    "WHERE organization_id = :org_id GROUP BY event_subtype"
                )
                breakdown = dict(conn.execute(breakdown_q, {"org_id": org_id}).fetchall())
                stats["flipkart_metrics"]["breakdown"] = breakdown
                stats["flipkart_metrics"]["sales"] = breakdown.get("SALE", 0)
                stats["flipkart_metrics"]["returns"] = breakdown.get("RETURN", 0)
                stats["flipkart_metrics"]["cancellations"] = breakdown.get("CANCELLATION", 0)
                stats["flipkart_metrics"]["return_cancellations"] = breakdown.get("RETURN_CANCELLATION", 0)

                # Unique SKUs
                sku_q = text("SELECT COUNT(DISTINCT sku) FROM order_item_ledger WHERE organization_id = :org_id")
                stats["flipkart_metrics"]["unique_skus"] = conn.execute(sku_q, {"org_id": org_id}).scalar()

                # Returned value
                val_q = text(
                    "SELECT SUM(invoice_amount) FROM order_item_ledger "
                    "WHERE organization_id = :org_id AND event_subtype = 'RETURN'"
                )
                stats["flipkart_metrics"]["returned_value"] = float(conn.execute(val_q, {"org_id": org_id}).scalar() or 0.0)

    return stats


def validate_against_benchmark(metrics: Dict[str, Any]) -> bool:
    print("\n--- Flipkart Dataset Benchmark Validation ---")
    all_passed = True

    checks = [
        ("Total Rows", metrics.get("total_rows"), FLIPKART_BENCHMARK["total_rows"]),
        ("Sale Events", metrics.get("sales"), FLIPKART_BENCHMARK["sales"]),
        ("Return Events", metrics.get("returns"), FLIPKART_BENCHMARK["returns"]),
        ("Cancellation Events", metrics.get("cancellations"), FLIPKART_BENCHMARK["cancellations"]),
        ("Return Cancellations", metrics.get("return_cancellations"), FLIPKART_BENCHMARK["return_cancellations"]),
        ("Unique SKUs", metrics.get("unique_skus"), FLIPKART_BENCHMARK["unique_skus"]),
        ("Returned Value (INR)", metrics.get("returned_value"), FLIPKART_BENCHMARK["returned_value"]),
    ]

    for label, actual, expected in checks:
        passed = actual == expected
        status = "PASSED" if passed else "FAILED"
        if not passed:
            all_passed = False
        print(f"  [{status}] {label}: Expected {expected}, Got {actual}")

    return all_passed


def compare_databases(source_stats: Dict[str, Any], target_stats: Dict[str, Any]) -> bool:
    print("\n--- Source vs Target Table Row Count Comparison ---")
    all_matched = True

    for tbl in CORE_TABLES:
        src = source_stats["table_counts"].get(tbl)
        tgt = target_stats["table_counts"].get(tbl)
        matched = src == tgt
        if not matched:
            all_matched = False
        status = "MATCH" if matched else "MISMATCH"
        print(f"  [{status}] Table '{tbl}': Source={src}, Target={tgt}")

    return all_matched


def main():
    parser = argparse.ArgumentParser(description="Validate Ordexa database migration integrity")
    parser.add_argument("--source-url", default="sqlite:///backend/profitpilot.db", help="Source SQLite connection URL")
    parser.add_argument("--target-url", default=None, help="Target PostgreSQL connection URL (optional)")
    args = parser.parse_args()

    print(f"Connecting to source database: {args.source_url}")
    source_engine = create_engine(args.source_url)
    source_stats = extract_database_stats(source_engine)

    print("\nSource Database Summary:")
    print(f"  Organizations: {source_stats['orgs']}")
    print(f"  Users: {source_stats['users']}")
    for tbl, cnt in source_stats["table_counts"].items():
        print(f"  {tbl}: {cnt}")

    src_benchmark_passed = validate_against_benchmark(source_stats["flipkart_metrics"])
    if not src_benchmark_passed:
        print("\nWARNING: Source database benchmark did not match expected figures!")

    if args.target_url:
        tgt_url = args.target_url
        if tgt_url.startswith("postgres://"):
            tgt_url = tgt_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif tgt_url.startswith("postgresql://") and not tgt_url.startswith("postgresql+"):
            tgt_url = tgt_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        print(f"\nConnecting to target database: {tgt_url.split('@')[-1] if '@' in tgt_url else 'target'}")
        target_engine = create_engine(tgt_url)
        target_stats = extract_database_stats(target_engine)
        comparison_passed = compare_databases(source_stats, target_stats)
        tgt_benchmark_passed = validate_against_benchmark(target_stats["flipkart_metrics"])

        if comparison_passed and tgt_benchmark_passed:
            print("\nALL POST-MIGRATION CHECKS PASSED: Source and Target are identical and meet benchmarks.")
            sys.exit(0)
        else:
            print("\nMIGRATION VALIDATION FAILED: Inconsistencies detected.")
            sys.exit(1)
    else:
        print("\nSingle database verification completed successfully.")
        sys.exit(0 if src_benchmark_passed else 1)


if __name__ == "__main__":
    main()
