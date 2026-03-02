"""Notification service for admin alerts."""
import uuid
from typing import Optional, List, Dict, Any

from app.db.session import get_db_connection


def create_notification(
    notification_type: str,
    title: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    recipient_role: str = "admin",
    priority: str = "normal",
) -> Optional[str]:
    """Create a notification for admin. Returns notification id or None on failure.
    Priority: 'low', 'normal', or 'high'.
    """
    notification_id = str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        import json
        meta_json = json.dumps(metadata or {}) if metadata else "{}"
        cur.execute(
            """
            INSERT INTO notifications (id, type, title, message, metadata, recipient_role, priority)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (notification_id, notification_type, title, message, meta_json, recipient_role, priority),
        )
        conn.commit()
        return notification_id
    except Exception as e:
        conn.rollback()
        print(f"Error creating notification: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def list_admin_notifications(
    limit: int = 50,
    unread_only: bool = False,
) -> List[Dict[str, Any]]:
    """List notifications for admin. Most recent first."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT id, type, title, message, metadata, created_at, read_at, priority
            FROM notifications
            WHERE recipient_role = 'admin'
        """
        params = []
        if unread_only:
            query += " AND read_at IS NULL"
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        notifications = []
        for row in rows:
            notifications.append({
                "id": str(row[0]),
                "type": row[1],
                "title": row[2],
                "message": row[3],
                "metadata": row[4] or {},
                "created_at": row[5].isoformat() if row[5] else None,
                "read_at": row[6].isoformat() if row[6] else None,
                "priority": row[7] or "normal",
            })
        return notifications
    except Exception as e:
        print(f"Error listing notifications: {e}")
        return []
    finally:
        cur.close()
        conn.close()
