#!/usr/bin/env python3
import psycopg2
from psycopg2 import sql
import json

# ────────────────────────────────────────────
# DB 설정 (구 webui → 새 customui)
# ────────────────────────────────────────────
PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "admin"
PG_PASSWORD = "wjsqnrai"

OLD_DB = "webui"     # 구 PostgreSQL DB
NEW_DB = "customui"  # 새 PostgreSQL DB


def connect(dbname: str):
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=dbname,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def adapt_row_values(row):
    """
    row 내부에 dict / list 가 있으면 json.dumps 로 문자열 변환.
    (PostgreSQL json/jsonb 컬럼에 그대로 넣어도 자동 캐스팅됨)
    """
    return tuple(
        json.dumps(v) if isinstance(v, (dict, list)) else v
        for v in row
    )


# ────────────────────────────────────────────
# 0. 동일 스키마 + 이전에 실패했던 테이블만
# ────────────────────────────────────────────
IDENTICAL_TABLES = [
    "config",
    "feedback",
    "folder",
    "note",
    "tool",
]


def copy_identical_table(table_name: str, truncate_before: bool = True):
    """
    webui.public.table_name -> customui.public.table_name
    컬럼/타입이 완전히 동일한 테이블용.
    (이 스크립트에서는 config / feedback / folder / note / tool 만 대상)
    """
    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

    old_cur = new_cur = None
    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        # 컬럼 순서 맞추기
        col_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
        """
        old_cur.execute(col_query, (table_name,))
        cols = [row[0] for row in old_cur.fetchall()]
        if not cols:
            print(f"[{table_name}] 컬럼 정보를 찾지 못했습니다. 스킵.")
            return

        col_list = sql.SQL(", ").join(sql.Identifier(c) for c in cols)

        if truncate_before:
            new_cur.execute(
                sql.SQL("TRUNCATE TABLE {}.{};").format(
                    sql.Identifier("public"),
                    sql.Identifier(table_name),
                )
            )
            print(f"[{table_name}] TRUNCATE 완료")

        # webui 에서 데이터 스트리밍
        old_cur.execute(
            sql.SQL("SELECT {} FROM {}.{};").format(
                col_list,
                sql.Identifier("public"),
                sql.Identifier(table_name),
            )
        )

        batch_size = 1000
        total = 0

        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(cols))
        insert_q = sql.SQL("""
            INSERT INTO {schema}.{tbl} ({columns})
            VALUES ({values});
        """).format(
            schema=sql.Identifier("public"),
            tbl=sql.Identifier(table_name),
            columns=col_list,
            values=placeholders,
        )

        while True:
            rows = old_cur.fetchmany(batch_size)
            if not rows:
                break

            adapted_rows = [adapt_row_values(r) for r in rows]
            new_cur.executemany(insert_q, adapted_rows)

            total += len(rows)
            print(f"[{table_name}] {total} rows copied...")

        new_conn.commit()
        print(f"[{table_name}] 복사 완료, 총 {total} rows")
    except Exception as e:
        new_conn.rollback()
        print(f"[{table_name}] 복사 중 에러:", e)
    finally:
        if old_cur:
            old_cur.close()
        if new_cur:
            new_cur.close()
        old_conn.close()
        new_conn.close()


def migrate_identical_tables():
    print("=== (에러났던) 동일 스키마 테이블 이관 시작 ===")
    for t in IDENTICAL_TABLES:
        copy_identical_table(t, truncate_before=True)
    print("=== 동일 스키마 테이블 이관 완료 ===")


# ────────────────────────────────────────────
# 1. group 테이블 이관 (공통 컬럼 + UPSERT)
# ────────────────────────────────────────────

def migrate_group(truncate_before: bool = False):
    """
    webui.public.group -> customui.public.group
    공통 컬럼:
    id, user_id, name, description, data, meta, permissions, created_at, updated_at

    새 customui 에 이미 데이터가 있을 수 있으므로
    - truncate_before 기본 False
    - ON CONFLICT(id) UPSERT 방식으로 덮어쓰기
    """
    table_name = "group"  # reserved word

    common_cols = [
        "id",
        "user_id",
        "name",
        "description",
        "data",
        "meta",
        "permissions",
        "created_at",
        "updated_at",
    ]

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)
    old_cur = new_cur = None

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        select_sql = f"""
        SELECT {", ".join(common_cols)}
        FROM public."{table_name}";
        """
        old_cur.execute(select_sql)

        if truncate_before:
            new_cur.execute(f'TRUNCATE TABLE public."{table_name}";')
            print(f'["{table_name}"] TRUNCATE 완료')

        batch_size = 1000
        total = 0

        placeholders = ", ".join(["%s"] * len(common_cols))
        insert_sql = f"""
        INSERT INTO public."{table_name}" ({", ".join(common_cols)})
        VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            data = EXCLUDED.data,
            meta = EXCLUDED.meta,
            permissions = EXCLUDED.permissions,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at;
        """

        rows = old_cur.fetchmany(batch_size)
        while rows:
            adapted_rows = [adapt_row_values(r) for r in rows]
            new_cur.executemany(insert_sql, adapted_rows)

            total += len(rows)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        if old_cur:
            old_cur.close()
        if new_cur:
            new_cur.close()
        old_conn.close()
        new_conn.close()


# ────────────────────────────────────────────
# 2. chat 테이블 이관 (template_id 버리고 공통 컬럼만)
# ────────────────────────────────────────────

def migrate_chat(truncate_before: bool = False):
    """
    webui.public.chat -> customui.public.chat

    공통 컬럼:
    id, user_id, title, share_id, archived,
    created_at, updated_at, chat, pinned, meta, folder_id

    OLD에만 있던 template_id 는 버림.
    customui 에 이미 데이터 있을 수 있으므로 ON CONFLICT(id) UPSERT.
    """
    table_name = "chat"

    cols = [
        "id",
        "user_id",
        "title",
        "share_id",
        "archived",
        "created_at",
        "updated_at",
        "chat",
        "pinned",
        "meta",
        "folder_id",
    ]

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)
    old_cur = new_cur = None

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        select_sql = f"""
        SELECT {", ".join(cols)}
        FROM public."{table_name}";
        """
        old_cur.execute(select_sql)

        if truncate_before:
            new_cur.execute(f'TRUNCATE TABLE public."{table_name}";')
            print(f'["{table_name}"] TRUNCATE 완료')

        batch_size = 1000
        total = 0

        placeholders = ", ".join(["%s"] * len(cols))
        insert_sql = f"""
        INSERT INTO public."{table_name}" ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            title = EXCLUDED.title,
            share_id = EXCLUDED.share_id,
            archived = EXCLUDED.archived,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at,
            chat = EXCLUDED.chat,
            pinned = EXCLUDED.pinned,
            meta = EXCLUDED.meta,
            folder_id = EXCLUDED.folder_id;
        """

        rows = old_cur.fetchmany(batch_size)
        while rows:
            adapted_rows = [adapt_row_values(r) for r in rows]
            new_cur.executemany(insert_sql, adapted_rows)

            total += len(rows)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        if old_cur:
            old_cur.close()
        if new_cur:
            new_cur.close()
        old_conn.close()
        new_conn.close()


# ────────────────────────────────────────────
# 3. file 테이블 이관 (TRUNCATE 없이 UPSERT)
# ────────────────────────────────────────────

def migrate_file_upsert():
    """
    webui.public.file -> customui.public.file

    주의:
    - 이전 스크립트에서 TRUNCATE 시도 중 FK(knowledge_file -> file) 때문에 실패했음.
    - 그래서 여기서는 TRUNCATE 절대 하지 않고,
      webui 기준 row 들을 customui.file 에 INSERT ... ON CONFLICT(id) DO UPDATE 방식으로만 넣는다.
    - 기존 customui.file 에 있는 데이터는 유지되지만,
      같은 id 가 있으면 webui 값으로 덮어쓴다.
    """
    table_name = "file"

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)
    old_cur = new_cur = None

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        # 컬럼 목록 가져오기
        col_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
        """
        old_cur.execute(col_query, (table_name,))
        cols = [row[0] for row in old_cur.fetchall()]
        if not cols:
            print(f'["{table_name}"] 컬럼 정보를 찾지 못했습니다. 스킵.')
            return

        # webui 에서 전체 row 스트리밍
        select_sql = f'SELECT {", ".join(cols)} FROM public."{table_name}";'
        old_cur.execute(select_sql)

        # INSERT ... ON CONFLICT(id) DO UPDATE 쿼리 구성
        col_idents = [sql.Identifier(c) for c in cols]
        col_list_sql = sql.SQL(", ").join(col_idents)

        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(cols))

        # id 를 제외한 컬럼들에 대해 "col = EXCLUDED.col"
        update_assignments = sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
            for c in cols
            if c != "id"
        )

        insert_q = sql.SQL("""
            INSERT INTO {schema}.{tbl} ({columns})
            VALUES ({values})
            ON CONFLICT (id) DO UPDATE SET
                {updates};
        """).format(
            schema=sql.Identifier("public"),
            tbl=sql.Identifier(table_name),
            columns=col_list_sql,
            values=placeholders,
            updates=update_assignments,
        )

        batch_size = 1000
        total = 0

        while True:
            rows = old_cur.fetchmany(batch_size)
            if not rows:
                break

            adapted_rows = [adapt_row_values(r) for r in rows]
            new_cur.executemany(insert_q, adapted_rows)

            total += len(rows)
            print(f'["{table_name}"] {total} rows upserted...')

        new_conn.commit()
        print(f'["{table_name}"] 이관(UPSERT) 완료, 총 {total} rows 처리')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관(UPSERT) 중 에러:', e)
    finally:
        if old_cur:
            old_cur.close()
        if new_cur:
            new_cur.close()
        old_conn.close()
        new_conn.close()


# ────────────────────────────────────────────
# 엔트리 포인트
# ────────────────────────────────────────────

if __name__ == "__main__":
    # 0. 예전에 dict 문제로 실패했던 동일 스키마 테이블들부터 재이관
    migrate_identical_tables()  # config / feedback / folder / note / tool

    # 1. 스키마 달라서 실패했던 그룹/채팅 재이관
    migrate_group(truncate_before=False)
    migrate_chat(truncate_before=False)

    # 2. FK 때문에 실패했던 file 은 TRUNCATE 없이 UPSERT로만 이관
    migrate_file_upsert()

    print("=== webui -> customui (에러났던 테이블 재이관 전체 완료) ===")

