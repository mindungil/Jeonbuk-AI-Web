import psycopg2
from psycopg2 import sql
import json

PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "admin"
PG_PASSWORD = "wjsqnrai"

OLD_DB = "webui"     # 구 PostgreSQL DB
NEW_DB = "customui"  # 새 PostgreSQL DB


def connect(dbname):
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=dbname,
        user=PG_USER,
        password=PG_PASSWORD,
    )


# ─────────────────────────────────────────────
# 0. 스키마 동일 테이블 (단, alembic_version은 제외 추천)
# ─────────────────────────────────────────────
# 네가 올려준 "=== 스키마 완전 동일 테이블" 목록에서
# alembic_version만 위험해서 뺐다. (원하면 다시 넣어도 됨)
IDENTICAL_TABLES = [
    "auth",
    "chatidtag",
    "config",
    "document",
    "feedback",
    "file",
    "folder",
    "function",
    "memory",
    "message_reaction",
    "migratehistory",
    "note",
    "oauth_session",
    "prompt",
    "tag",
    "tool",
]


def copy_identical_table(table_name, truncate_before=True):
    """
    webui.public.table_name -> customui.public.table_name
    컬럼/타입이 완전히 동일한 테이블용.
    """
    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

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

        # webui에서 데이터 스트리밍
        old_cur.execute(
            sql.SQL("SELECT {} FROM {}.{};").format(
                col_list,
                sql.Identifier("public"),
                sql.Identifier(table_name),
            )
        )

        batch_size = 1000
        total = 0
        while True:
            rows = old_cur.fetchmany(batch_size)
            if not rows:
                break

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

            new_cur.executemany(insert_q, rows)
            total += len(rows)
            print(f"[{table_name}] {total} rows copied...")

        new_conn.commit()
        print(f"[{table_name}] 복사 완료, 총 {total} rows")
    except Exception as e:
        new_conn.rollback()
        print(f"[{table_name}] 복사 중 에러:", e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


def migrate_identical_tables():
    print("=== 스키마 완전 동일 테이블 이관 시작 ===")
    for t in IDENTICAL_TABLES:
        copy_identical_table(t, truncate_before=True)
    print("=== 스키마 완전 동일 테이블 이관 완료 ===")


# ─────────────────────────────────────────────
# 1. group 테이블 이관 (공통 컬럼 + UPSERT)
# ─────────────────────────────────────────────

def migrate_group(truncate_before=False):
    """
    webui.public.group -> customui.public.group
    공통 컬럼:
    id, user_id, name, description, data, meta, permissions, created_at, updated_at
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
        rows = old_cur.fetchmany(batch_size)
        while rows:
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
            new_cur.executemany(insert_sql, rows)
            total += len(rows)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


# ─────────────────────────────────────────────
# 2. user 테이블 이관 (text → json + UPSERT)
# ─────────────────────────────────────────────

def safe_json(value):
    """
    settings, info 컬럼용:
    - None/빈 문자열: {}
    - 유효한 JSON 문자열: 해당 JSON
    - 그 외: {"raw": 원문}
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    s = str(value).strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {"raw": s}


def migrate_user():
    """
    webui.public.user -> customui.public.user

    옮기는 컬럼:
    id, name, email, role, profile_image_url,
    created_at, updated_at, last_active_at,
    settings(text→json), info(text→json),
    username, bio, gender, date_of_birth
    """
    table_name = "user"

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        select_sql = """
        SELECT
            id,
            name,
            email,
            role,
            profile_image_url,
            created_at,
            updated_at,
            last_active_at,
            settings,
            info,
            username,
            bio,
            gender,
            date_of_birth
        FROM public."user";
        """
        old_cur.execute(select_sql)

        batch_size = 500
        total = 0

        rows = old_cur.fetchmany(batch_size)
        while rows:
            transformed = []
            for row in rows:
                (
                    id_,
                    name,
                    email,
                    role,
                    profile_image_url,
                    created_at,
                    updated_at,
                    last_active_at,
                    settings,
                    info,
                    username,
                    bio,
                    gender,
                    date_of_birth,
                ) = row

                settings_json = safe_json(settings)
                info_json = safe_json(info)

                transformed.append(
                    (
                        id_,
                        name,
                        email,
                        role,
                        profile_image_url,
                        created_at,
                        updated_at,
                        last_active_at,
                        json.dumps(settings_json),
                        json.dumps(info_json),
                        username,
                        bio,
                        gender,
                        date_of_birth,
                    )
                )

            insert_sql = """
            INSERT INTO public."user" (
                id,
                name,
                email,
                role,
                profile_image_url,
                created_at,
                updated_at,
                last_active_at,
                settings,
                info,
                username,
                bio,
                gender,
                date_of_birth
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                role = EXCLUDED.role,
                profile_image_url = EXCLUDED.profile_image_url,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at,
                last_active_at = EXCLUDED.last_active_at,
                settings = EXCLUDED.settings,
                info = EXCLUDED.info,
                username = EXCLUDED.username,
                bio = EXCLUDED.bio,
                gender = EXCLUDED.gender,
                date_of_birth = EXCLUDED.date_of_birth;
            """
            new_cur.executemany(insert_sql, transformed)
            total += len(transformed)
            print(f'["user"] {total} rows migrated...')

            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["user"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print('["user"] 이관 중 에러:', e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


# ─────────────────────────────────────────────
# 3. chat 테이블 이관 (template_id 버리고 공통 컬럼만)
# ─────────────────────────────────────────────

def migrate_chat(truncate_before=False):
    """
    webui.public.chat -> customui.public.chat

    공통 컬럼:
    id, user_id, title, share_id, archived,
    created_at, updated_at, chat, pinned, meta, folder_id
    (OLD에만 있던 template_id는 버림)
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
        rows = old_cur.fetchmany(batch_size)
        while rows:
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
            new_cur.executemany(insert_sql, rows)
            total += len(rows)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


# ─────────────────────────────────────────────
# 4. channel 테이블 이관 (공통 컬럼만)
# ─────────────────────────────────────────────

def migrate_channel():
    """
    webui.public.channel -> customui.public.channel

    공통 컬럼:
    id, user_id, name, description, data, meta,
    access_control, created_at, updated_at, type

    새 스키마에 추가된 is_private, archived_at 등은 기본값/NULL 유지
    """
    table_name = "channel"

    cols = [
        "id",
        "user_id",
        "name",
        "description",
        "data",
        "meta",
        "access_control",
        "created_at",
        "updated_at",
        "type",
    ]

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        select_sql = f"""
        SELECT {", ".join(cols)}
        FROM public.{table_name};
        """
        old_cur.execute(select_sql)

        batch_size = 1000
        total = 0
        rows = old_cur.fetchmany(batch_size)
        while rows:
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = f"""
            INSERT INTO public.{table_name} ({", ".join(cols)})
            VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                data = EXCLUDED.data,
                meta = EXCLUDED.meta,
                access_control = EXCLUDED.access_control,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at,
                type = EXCLUDED.type;
            """
            new_cur.executemany(insert_sql, rows)
            total += len(rows)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


# ─────────────────────────────────────────────
# 5. channel_member 이관 (공통 + 기본값 세팅)
# ─────────────────────────────────────────────

def migrate_channel_member():
    """
    webui.public.channel_member -> customui.public.channel_member

    OLD 컬럼: id, channel_id, user_id, created_at
    NEW에는 status, is_active, is_channel_muted, ... joined_at(필수) 등 추가.

    전략:
    - 공통 컬럼: id, channel_id, user_id, created_at
    - joined_at = created_at로 넣기
    - is_active = true
    - is_channel_muted = false
    - is_channel_pinned = false
    - 나머지 컬럼은 NULL 유지
    """
    table_name = "channel_member"

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        select_sql = """
        SELECT id, channel_id, user_id, created_at
        FROM public.channel_member;
        """
        old_cur.execute(select_sql)

        batch_size = 1000
        total = 0
        rows = old_cur.fetchmany(batch_size)
        while rows:
            transformed = []
            for r in rows:
                id_, channel_id, user_id, created_at = r
                joined_at = created_at or 0
                is_active = True
                is_channel_muted = False
                is_channel_pinned = False
                transformed.append(
                    (
                        id_,
                        channel_id,
                        user_id,
                        created_at,
                        joined_at,
                        is_active,
                        is_channel_muted,
                        is_channel_pinned,
                    )
                )

            insert_sql = """
            INSERT INTO public.channel_member (
                id,
                channel_id,
                user_id,
                created_at,
                joined_at,
                is_active,
                is_channel_muted,
                is_channel_pinned
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                user_id = EXCLUDED.user_id,
                created_at = EXCLUDED.created_at,
                joined_at = EXCLUDED.joined_at,
                is_active = EXCLUDED.is_active,
                is_channel_muted = EXCLUDED.is_channel_muted,
                is_channel_pinned = EXCLUDED.is_channel_pinned;
            """
            new_cur.executemany(insert_sql, transformed)
            total += len(transformed)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


# ─────────────────────────────────────────────
# 6. knowledge 이관 (data, source 버리고 공통 컬럼만)
# ─────────────────────────────────────────────

def migrate_knowledge():
    """
    webui.public.knowledge -> customui.public.knowledge

    OLD: id, user_id, name, description, data, meta, created_at, updated_at, access_control, source
    NEW: id, user_id, name, description, meta, created_at, updated_at, access_control

    => 공통: id, user_id, name, description, meta, created_at, updated_at, access_control
    data, source는 버림 (원하면 meta에 넣는 것도 가능하지만 일단 단순하게)
    """
    table_name = "knowledge"

    cols = [
        "id",
        "user_id",
        "name",
        "description",
        "meta",
        "created_at",
        "updated_at",
        "access_control",
    ]

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        # OLD에서 meta, access_control은 그대로 가져옴 (data/source 무시)
        select_sql = """
        SELECT
            id,
            user_id,
            name,
            description,
            meta,
            created_at,
            updated_at,
            access_control
        FROM public.knowledge;
        """
        old_cur.execute(select_sql)

        batch_size = 1000
        total = 0
        rows = old_cur.fetchmany(batch_size)
        while rows:
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = f"""
            INSERT INTO public.{table_name} ({", ".join(cols)})
            VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                meta = EXCLUDED.meta,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at,
                access_control = EXCLUDED.access_control;
            """
            new_cur.executemany(insert_sql, rows)
            total += len(rows)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


# ─────────────────────────────────────────────
# 7. message 이관 (새 pinned 필드는 기본값 사용)
# ─────────────────────────────────────────────

def migrate_message():
    """
    webui.public.message -> customui.public.message

    공통 컬럼:
    id, user_id, channel_id, content, data, meta,
    created_at, updated_at, parent_id, reply_to_id

    NEW에 추가된 is_pinned, pinned_at, pinned_by는 기본값/NULL 유지
    """
    table_name = "message"

    cols = [
        "id",
        "user_id",
        "channel_id",
        "content",
        "data",
        "meta",
        "created_at",
        "updated_at",
        "parent_id",
        "reply_to_id",
    ]

    old_conn = connect(OLD_DB)
    new_conn = connect(NEW_DB)

    try:
        old_cur = old_conn.cursor()
        new_cur = new_conn.cursor()

        select_sql = f"""
        SELECT {", ".join(cols)}
        FROM public.{table_name};
        """
        old_cur.execute(select_sql)

        batch_size = 1000
        total = 0
        rows = old_cur.fetchmany(batch_size)
        while rows:
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = f"""
            INSERT INTO public.{table_name} ({", ".join(cols)})
            VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                channel_id = EXCLUDED.channel_id,
                content = EXCLUDED.content,
                data = EXCLUDED.data,
                meta = EXCLUDED.meta,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at,
                parent_id = EXCLUDED.parent_id,
                reply_to_id = EXCLUDED.reply_to_id;
            """
            new_cur.executemany(insert_sql, rows)
            total += len(rows)
            print(f'["{table_name}"] {total} rows migrated...')
            rows = old_cur.fetchmany(batch_size)

        new_conn.commit()
        print(f'["{table_name}"] 이관 완료, 총 {total} rows')
    except Exception as e:
        new_conn.rollback()
        print(f'["{table_name}"] 이관 중 에러:', e)
    finally:
        old_cur.close()
        new_cur.close()
        old_conn.close()
        new_conn.close()


# ─────────────────────────────────────────────
# 엔트리 포인트
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # 0. 완전 동일 테이블들 먼저 이관 (model은 애초에 여기에 없음)
    migrate_identical_tables()

    # 1. 스키마 다른 애들 이관 (model만 제외)
    migrate_group(truncate_before=False)
    migrate_user()
    migrate_chat(truncate_before=False)
    migrate_channel()
    migrate_channel_member()
    migrate_knowledge()
    migrate_message()

    print("=== webui -> customui (model 제외) 마이그레이션 전체 완료 ===")

