"""Notification-only grants: run as migration owner, never as the API role."""

import re
from psycopg import sql


def grant_notification_worker(cursor, role):
    if not re.fullmatch(r"haven_[a-z_]{1,30}", role):
        raise ValueError("Invalid notification role")
    cursor.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolname=current_user FROM pg_roles WHERE rolname=%s",
        [role],
    )
    flags = cursor.fetchone()
    if flags is None or any(flags):
        raise ValueError("Notification role must be an independent unprivileged login")
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=%s) AND relnamespace='public'::regnamespace)",
        [role],
    )
    if cursor.fetchone()[0]:
        raise ValueError("Notification role must not own application objects")
    target = sql.Identifier(role)
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname=%s))",
        [role],
    )
    if cursor.fetchone()[0]:
        raise ValueError("Notification role must not inherit other roles")
    # No future-table defaults. Re-provisioning also removes accidental direct grants.
    cursor.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(target))
    cursor.execute(sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}").format(target))
    # Table-level REVOKE does not revoke independent column ACLs.
    cursor.execute("""SELECT c.relname, array_agg(a.attname ORDER BY a.attnum)
        FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
        WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','v','p')
          AND a.attnum>0 AND NOT a.attisdropped GROUP BY c.relname""")
    for table, columns in cursor.fetchall():
        cursor.execute(
            sql.SQL("REVOKE ALL ({}) ON public.{} FROM {}").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)), sql.Identifier(table), target
            )
        )
    cursor.execute(
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {}").format(target)
    )
    cursor.execute(
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {}").format(target)
    )
    cursor.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(target))
    cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(target))
    cursor.execute(
        sql.SQL(
            "GRANT SELECT (id, envelope_id, sent_at, attempts), UPDATE (sent_at, attempts) ON core_notificationoutbox TO {}"
        ).format(target)
    )
    cursor.execute(sql.SQL("GRANT SELECT ON haven_notification_targets TO {}").format(target))
