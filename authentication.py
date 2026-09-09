import os
import re
import hashlib
import hmac
import secrets
from datetime import date

import streamlit as st
from dotenv import load_dotenv

from database.users import (
    get_user,
    create_user,
    update_last_login,
)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    ""
).strip().lower()

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    ""
)

MENTOR_EMAIL = os.getenv(
    "MENTOR_EMAIL",
    ""
).strip().lower()


# ============================================================
# PASSWORD VALIDATION
# ============================================================

def password_is_strong(password):
    """
    Password must contain:
    - At least 8 characters
    - Uppercase letter
    - Lowercase letter
    - Number
    - Special character
    """

    return (
        len(password) >= 8
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"\d", password)
        and re.search(r"[^A-Za-z0-9]", password)
    )


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password):
    """
    Hash password using PBKDF2-HMAC-SHA256.
    """

    salt = secrets.token_bytes(16)

    iterations = 310000

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )

    return (
        f"pbkdf2_sha256$"
        f"{iterations}$"
        f"{salt.hex()}$"
        f"{digest.hex()}"
    )


# ============================================================
# PASSWORD VERIFICATION
# ============================================================

def verify_password(password, stored_password):
    """Verify PBKDF2 hashes and safely support legacy plaintext/SHA-256 records."""
    if not stored_password:
        return False
    try:
        if stored_password.startswith("pbkdf2_sha256$"):
            algorithm, iterations, salt_hex, digest_hex = stored_password.split("$")
            digest = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            )
            return hmac.compare_digest(digest.hex(), digest_hex)
        if re.fullmatch(r"[a-fA-F0-9]{64}", stored_password):
            return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored_password.lower())
        # Old local SQLite installations stored passwords directly. A successful
        # legacy login is accepted so existing accounts are not locked out.
        return hmac.compare_digest(password, stored_password)
    except (TypeError, ValueError):
        return False


# ============================================================
# SET LOGIN SESSION
# ============================================================

def set_logged_in(user):
    """
    Store authenticated user information
    in Streamlit session state.
    """

    st.session_state.authenticated = True

    st.session_state.user_id = user["id"]

    st.session_state.user_name = user["name"]

    st.session_state.user_email = user["email"]

    st.session_state.user_role = user["role"]


# ============================================================
# LOGIN USER
# ============================================================

def login_user(
    email,
    password,
):
    """
    Authenticate student or mentor.
    """

    email = email.strip().lower()

    if not email or not password:
        return False

    user = get_user(email)

    if not user:
        return False

    # Check whether account is active.
    if not user["is_active"]:
        return False

    # Verify password.
    if not verify_password(
        password,
        user["password_hash"],
    ):
        return False

    # Update login timestamp.
    update_last_login(
        user["id"]
    )

    # Create login session.
    set_logged_in(user)

    return True


# ============================================================
# SIGNUP USER
# ============================================================

def signup_user(
    name,
    email,
    role,
    password,
    confirm_password,
    start_date=None,
    end_date=None,
):
    """
    Create a Student, Mentor, or Administrator demo account.
    """

    name = name.strip()
    email = email.strip().lower()

    # --------------------------------------------------------
    # ROLE VALIDATION
    # --------------------------------------------------------

    if role not in {
        "student",
        "mentor",
        "admin",
    }:
        return (
            False,
            "Choose Student, Mentor, or Administrator.",
        )

    # --------------------------------------------------------
    # NAME VALIDATION
    # --------------------------------------------------------

    if not name:
        return (
            False,
            "Enter your name.",
        )

    # --------------------------------------------------------
    # EMAIL VALIDATION
    # --------------------------------------------------------

    if not re.match(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        email,
    ):
        return (
            False,
            "Enter a valid email address.",
        )

    # --------------------------------------------------------
    # PASSWORD VALIDATION
    # --------------------------------------------------------

    if not password_is_strong(password):
        return (
            False,
            "Password must contain 8+ characters, "
            "uppercase, lowercase, number and "
            "special character.",
        )

    # --------------------------------------------------------
    # CONFIRM PASSWORD
    # --------------------------------------------------------

    if password != confirm_password:
        return (
            False,
            "Passwords do not match.",
        )

    # --------------------------------------------------------
    # DUPLICATE ACCOUNT
    # --------------------------------------------------------

    if get_user(email):
        return (
            False,
            "An account with this email already exists.",
        )

    # --------------------------------------------------------
    # MENTOR AUTHORIZATION
    # --------------------------------------------------------

    if (
        role == "mentor"
        and MENTOR_EMAIL
        and email != MENTOR_EMAIL
    ):
        return (
            False,
            "This mentor email is not authorized.",
        )

    # --------------------------------------------------------
    # DATE VALIDATION
    # --------------------------------------------------------

    if role == "student":
        if not start_date or not end_date:
            return (
                False,
                "Students must provide internship start and end dates.",
            )

        if end_date < start_date:
            return (
                False,
                "Internship end date cannot be "
                "before start date.",
            )
    else:
        # Mentors and administrators do not have internship periods.
        start_date = None
        end_date = None

    # --------------------------------------------------------
    # HASH PASSWORD
    # --------------------------------------------------------

    password_hash = hash_password(
        password
    )

    # --------------------------------------------------------
    # CREATE DATABASE USER
    # --------------------------------------------------------

    user_id = create_user(
        name=name,
        email=email,
        role=role,
        password_hash=password_hash,
        start_date=(
            str(start_date)
            if start_date
            else None
        ),
        end_date=(
            str(end_date)
            if end_date
            else None
        ),
    )

    if user_id:
        return (
            True,
            "Account created successfully. "
            "Please login.",
        )

    return (
        False,
        "Could not create account.",
    )


# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

def authenticate_admin(
    email,
    password,
):
    """
    Authenticate administrator.

    Admin credentials can come from:
    1. .env
    2. Existing admin database account
    """

    email = email.strip().lower()

    # --------------------------------------------------------
    # ENVIRONMENT ADMIN
    # --------------------------------------------------------

    if (
        ADMIN_EMAIL
        and ADMIN_PASSWORD
        and email == ADMIN_EMAIL
        and hmac.compare_digest(
            password,
            ADMIN_PASSWORD,
        )
    ):

        user = get_user(
            ADMIN_EMAIL
        )

        # ----------------------------------------------------
        # CREATE ADMIN ACCOUNT IF NEEDED
        # ----------------------------------------------------

        if not user:

            user_id = create_user(
                name="Administrator",
                email=ADMIN_EMAIL,
                role="admin",
                password_hash=hash_password(
                    ADMIN_PASSWORD
                ),
                start_date=None,
                end_date=None,
            )

            if user_id:
                user = get_user(
                    ADMIN_EMAIL
                )

        # ----------------------------------------------------
        # LOGIN ADMIN
        # ----------------------------------------------------

        if (
            user
            and user["is_active"]
        ):

            update_last_login(
                user["id"]
            )

            set_logged_in(user)

            return True

    # --------------------------------------------------------
    # EXISTING DATABASE ADMIN
    # --------------------------------------------------------

    user = get_user(email)

    if (
        user
        and user["role"] == "admin"
        and user["is_active"]
        and verify_password(
            password,
            user["password_hash"],
        )
    ):

        update_last_login(
            user["id"]
        )

        set_logged_in(user)

        return True

    return False


# ============================================================
# LOGOUT
# ============================================================

def logout():
    """
    Clear authentication-related session state.
    """

    keys = [
        "authenticated",
        "user_id",
        "user_name",
        "user_email",
        "user_role",
    ]

    for key in keys:
        st.session_state.pop(
            key,
            None,
        )


# ============================================================
# LOGIN PAGE
# ============================================================

def login_page():
    """
    Display login form.
    """

    st.subheader("Login")

    with st.form(
        "login_form"
    ):

        email = st.text_input(
            "Email",
            placeholder="Enter your email",
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
        )

        submitted = st.form_submit_button(
            "Login",
            use_container_width=True,
        )

    if submitted:

        email = email.strip().lower()

        # ----------------------------------------------------
        # BASIC VALIDATION
        # ----------------------------------------------------

        if not email or not password:
            st.error(
                "Please enter your email and password."
            )
            return

        # ----------------------------------------------------
        # STUDENT / MENTOR LOGIN
        # ----------------------------------------------------

        student_or_mentor = login_user(
            email,
            password,
        )

        # ----------------------------------------------------
        # ADMIN LOGIN
        # ----------------------------------------------------

        admin = False

        if not student_or_mentor:
            admin = authenticate_admin(
                email,
                password,
            )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if student_or_mentor or admin:
            st.rerun()

        # ----------------------------------------------------
        # FAILURE
        # ----------------------------------------------------

        st.error(
            "Invalid email/password "
            "or inactive account."
        )


# ============================================================
# SIGNUP PAGE
# ============================================================

def signup_page():
    """
    Display account creation form.
    """

    st.subheader("Create Account")

    # This control is outside the form so the page can immediately display
    # dates only for a student account.
    role_label = st.selectbox(
        "I am joining as",
        ["Student (User)", "Mentor", "Administrator"],
        key="signup_role",
    )

    role = {
        "Student (User)": "student",
        "Mentor": "mentor",
        "Administrator": "admin",
    }[role_label]

    if role == "student":
        st.info("Internship dates are required for Student progress tracking.")
    else:
        st.caption(f"{role_label} accounts do not need internship dates.")

    with st.form(
        "signup_form"
    ):

        # ----------------------------------------------------
        # BASIC INFORMATION
        # ----------------------------------------------------

        name = st.text_input(
            "Full Name",
            placeholder="Enter your full name",
        )

        email = st.text_input(
            "Email",
            placeholder="Enter your email",
        )

        # ----------------------------------------------------
        # INTERNSHIP DATES
        # ----------------------------------------------------

        start_date = None
        end_date = None

        if role == "student":

            col1, col2 = st.columns(2)

            with col1:

                start_date = st.date_input(
                    "Internship Start",
                    value=date.today(),
                )

            with col2:

                end_date = st.date_input(
                    "Internship End",
                    value=date.today(),
                )

        # ----------------------------------------------------
        # PASSWORD
        # ----------------------------------------------------

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Create a strong password",
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Confirm your password",
        )

        # ----------------------------------------------------
        # SUBMIT
        # ----------------------------------------------------

        submitted = st.form_submit_button(
            "Create Account",
            use_container_width=True,
        )

    if submitted:

        success, message = signup_user(
            name=name,
            email=email,
            role=role,
            password=password,
            confirm_password=confirm_password,
            start_date=start_date,
            end_date=end_date,
        )

        if success:

            st.success(message)

        else:

            st.error(message)
