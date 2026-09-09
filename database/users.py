from datetime import datetime

from .connection import get_connection


# ============================================================
# CREATE USER
# ============================================================

def create_user(
    name,
    email,
    role,
    password_hash,
    start_date=None,
    end_date=None
):
    """
    Create a new user.

    Returns:
        user_id if successful
        None if creation fails
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Older databases may still contain a required ``username`` column.
        # Include it when present so those databases remain usable.
        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(users)")
        }

        insert_columns = [
            "name",
            "email",
            "role",
            "password_hash",
            "is_active",
            "start_date",
            "end_date",
            "last_login",
            "created_at",
        ]
        values = [
            name.strip(),
            email.strip().lower(),
            role,
            password_hash,
            1,
            start_date,
            end_date,
            None,
            datetime.now().isoformat(),
        ]

        if "username" in columns:
            insert_columns.insert(1, "username")
            values.insert(1, email.strip().lower())

        if "password" in columns:
            password_index = insert_columns.index("password_hash") + 1
            insert_columns.insert(password_index, "password")
            values.insert(password_index, password_hash)

        placeholders = ", ".join("?" for _ in values)
        cursor.execute(
            f"INSERT INTO users ({', '.join(insert_columns)}) "
            f"VALUES ({placeholders})",
            values,
        )

        conn.commit()

        return cursor.lastrowid

    except Exception as e:
        print(f"Error creating user: {e}")
        return None

    finally:
        conn.close()


# ============================================================
# GET USER
# ============================================================

def get_user(email):
    """Return a user safely across both legacy and current SQLite schemas."""
    if not email:
        return None
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ? LIMIT 1", (email.strip().lower(),)).fetchone()
        if not row:
            return None
        user = dict(row)
        # Legacy deployments used password instead of password_hash and may omit metadata.
        user["password_hash"] = user.get("password_hash") or user.get("password") or ""
        user.setdefault("is_active", 1)
        user.setdefault("name", user.get("username") or user.get("email", ""))
        user.setdefault("start_date", None)
        user.setdefault("end_date", None)
        user.setdefault("last_login", None)
        user.setdefault("created_at", None)
        return user
    finally:
        conn.close()


# ============================================================
# GET USER BY ID
# ============================================================

def get_user_by_id(user_id):
    """
    Get a user by ID.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                role,
                password_hash,
                is_active,
                start_date,
                end_date,
                last_login,
                created_at
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (user_id,)
        )

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None

    finally:
        conn.close()


# ============================================================
# GET USER BY EMAIL
# ============================================================

def get_user_by_email(email):
    """
    Get a user by email.

    This is an alias for get_user().
    """

    return get_user(email)


# ============================================================
# UPDATE LAST LOGIN
# ============================================================

def update_last_login(user_id):
    """
    Update the user's last login time.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE users
            SET last_login = ?
            WHERE id = ?
            """,
            (
                datetime.now().isoformat(),
                user_id
            )
        )

        conn.commit()

        return True

    except Exception as e:
        print(f"Error updating last login: {e}")
        return False

    finally:
        conn.close()


# ============================================================
# AUTHENTICATE USER
# ============================================================

def authenticate_user(email, password_hash):
    """
    Basic database-level authentication helper.

    Note:
    The main application authentication is handled by
    authentication.py using password verification.
    """

    user = get_user(email)

    if not user:
        return None

    if not user["is_active"]:
        return None

    if user["password_hash"] != password_hash:
        return None

    return user


# ============================================================
# ACTIVATE USER
# ============================================================

def activate_user(user_id):
    """
    Activate a user account.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE users
            SET is_active = 1
            WHERE id = ?
            """,
            (user_id,)
        )

        conn.commit()

        return True

    except Exception as e:
        print(f"Error activating user: {e}")
        return False

    finally:
        conn.close()


# ============================================================
# DEACTIVATE USER
# ============================================================

def deactivate_user(user_id):
    """
    Deactivate a user account.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE users
            SET is_active = 0
            WHERE id = ?
            """,
            (user_id,)
        )

        conn.commit()

        return True

    except Exception as e:
        print(f"Error deactivating user: {e}")
        return False

    finally:
        conn.close()


# ============================================================
# UPDATE USER
# ============================================================

def update_user(
    user_id,
    name=None,
    email=None,
    role=None,
    start_date=None,
    end_date=None
):
    """
    Update user information.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        if name is not None:
            cursor.execute(
                """
                UPDATE users
                SET name = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    user_id
                )
            )

        if email is not None:
            cursor.execute(
                """
                UPDATE users
                SET email = ?
                WHERE id = ?
                """,
                (
                    email.strip().lower(),
                    user_id
                )
            )

        if role is not None:
            cursor.execute(
                """
                UPDATE users
                SET role = ?
                WHERE id = ?
                """,
                (
                    role,
                    user_id
                )
            )

        if start_date is not None:
            cursor.execute(
                """
                UPDATE users
                SET start_date = ?
                WHERE id = ?
                """,
                (
                    str(start_date),
                    user_id
                )
            )

        if end_date is not None:
            cursor.execute(
                """
                UPDATE users
                SET end_date = ?
                WHERE id = ?
                """,
                (
                    str(end_date),
                    user_id
                )
            )

        conn.commit()

        return True

    except Exception as e:
        print(f"Error updating user: {e}")
        return False

    finally:
        conn.close()


# ============================================================
# DELETE USER
# ============================================================

def delete_user(user_id):
    """
    Delete a user.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (user_id,)
        )

        conn.commit()

        return True

    except Exception as e:
        print(f"Error deleting user: {e}")
        return False

    finally:
        conn.close()


# ============================================================
# LIST USERS
# ============================================================

def list_users(role=None):
    """
    Get all users.

    If role is supplied, only that role is returned.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        if role:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    role,
                    is_active,
                    start_date,
                    end_date,
                    last_login,
                    created_at
                FROM users
                WHERE role = ?
                ORDER BY created_at DESC
                """,
                (role,)
            )

        else:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    role,
                    is_active,
                    start_date,
                    end_date,
                    last_login,
                    created_at
                FROM users
                ORDER BY created_at DESC
                """
            )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()
