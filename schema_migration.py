import psycopg2
from psycopg2 import sql

PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "admin"
PG_PASSWORD = "wjsqnrai"

OLD_DB = "webui"     # 구 DB
NEW_DB = "customui"  # 신 DB


def get_table_columns(conn, schema="public"):
    """
    해당 DB 커넥션에서 (schema, table_name) -> [ (column_name, data_type, is_nullable, column_default) ... ] 맵을 반환
    """
    q = """
    SELECT
        table_name,
        column_name,
        data_type,
        is_nullable,
        column_default,
        ordinal_position
    FROM information_schema.columns
    WHERE table_schema = %s
    ORDER BY table_name, ordinal_position;
    """
    cur = conn.cursor()
    cur.execute(q, (schema,))
    rows = cur.fetchall()
    cur.close()

    table_map = {}
    for table_name, col_name, data_type, is_nullable, col_default, pos in rows:
        table_map.setdefault(table_name, []).append(
            (col_name, data_type, is_nullable, col_default)
        )
    return table_map


def connect(dbname):
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=dbname,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def find_compatible_tables():
    """
    webui vs customui 스키마를 비교해서,
    컬럼 이름/타입/nullable/default/순서까지 완전히 동일한 테이블 목록을 반환
    """
    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

    try:
        old_cols = get_table_columns(old_conn, schema="public")
        new_cols = get_table_columns(new_conn, schema="public")

        old_tables = set(old_cols.keys())
        new_tables = set(new_cols.keys())

        common_tables = sorted(old_tables & new_tables)

        compatible = []
        incompatible = {}

        for tbl in common_tables:
            old_def = old_cols[tbl]
            new_def = new_cols[tbl]

            if old_def == new_def:
                compatible.append(tbl)
            else:
                incompatible[tbl] = {
                    "old": old_def,
                    "new": new_def,
                }

        return compatible, incompatible
    finally:
        old_conn.close()
        new_conn.close()


def main():
    compatible, incompatible = find_compatible_tables()

    print("=== 스키마 완전 동일 테이블 목록 ===")
    for t in compatible:
        print(" -", t)

    print("\n=== 스키마가 다른 공통 테이블 (참고용) ===")
    for t, defs in incompatible.items():
        print(f"\n[테이블] {t}")
        print("  OLD(webui):")
        for col in defs["old"]:
            print("    ", col)
        print("  NEW(customui):")
        for col in defs["new"]:
            print("    ", col)


if __name__ == "__main__":
    main()

