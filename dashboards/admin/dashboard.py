import streamlit as st

from database.users import list_users
from database.admin import list_notices


# =============================================================
# MAIN ADMIN DASHBOARD
# =============================================================

def render_admin_dashboard():
    """
    Main Admin Dashboard.
    """

    st.title("Admin Dashboard")

    user = st.session_state.get(
        "user",
        {}
    )

    admin_name = user.get(
        "name",
        "Administrator"
    )

    st.markdown(
        f"### Welcome, {admin_name}"
    )

    st.divider()

    # ---------------------------------------------------------
    # Load users
    # ---------------------------------------------------------

    try:
        users = list_users()

    except Exception as e:

        users = []

        st.warning(
            f"Could not load users: {e}"
        )

    # ---------------------------------------------------------
    # Load notices
    # ---------------------------------------------------------

    try:
        notices = list_notices()

    except Exception:

        notices = []

    # ---------------------------------------------------------
    # Calculate statistics
    # ---------------------------------------------------------

    total_users = len(users)

    students = [
        user
        for user in users
        if isinstance(user, dict)
        and user.get("role") == "student"
    ]

    mentors = [
        user
        for user in users
        if isinstance(user, dict)
        and user.get("role") == "mentor"
    ]

    admins = [
        user
        for user in users
        if isinstance(user, dict)
        and user.get("role") == "admin"
    ]

    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------

    st.subheader("System Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Total Users",
            total_users
        )

    with col2:

        st.metric(
            "Students",
            len(students)
        )

    with col3:

        st.metric(
            "Mentors",
            len(mentors)
        )

    with col4:

        st.metric(
            "Admins",
            len(admins)
        )

    st.divider()

    # ---------------------------------------------------------
    # Admin Navigation
    # ---------------------------------------------------------

    st.subheader("Admin Tools")

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "👥 Manage Users",
            use_container_width=True
        ):

            st.session_state[
                "admin_page"
            ] = "users"

    with col2:

        if st.button(
            "🔐 Permissions",
            use_container_width=True
        ):

            st.session_state[
                "admin_page"
            ] = "permissions"

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "📚 Formula Vault",
            use_container_width=True
        ):

            st.session_state[
                "admin_page"
            ] = "formulas"

    with col2:

        if st.button(
            "📖 Resources",
            use_container_width=True
        ):

            st.session_state[
                "admin_page"
            ] = "resources"

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "📢 Notices",
            use_container_width=True
        ):

            st.session_state[
                "admin_page"
            ] = "notices"

    with col2:

        if st.button(
            "⚙️ System",
            use_container_width=True
        ):

            st.session_state[
                "admin_page"
            ] = "system"

    # ---------------------------------------------------------
    # Selected page
    # ---------------------------------------------------------

    selected_page = st.session_state.get(
        "admin_page",
        "dashboard"
    )

    st.divider()

    if selected_page == "users":

        render_users()

    elif selected_page == "permissions":

        render_permissions()

    elif selected_page == "formulas":

        render_formulas()

    elif selected_page == "resources":

        render_resources()

    elif selected_page == "notices":

        render_notices()

    elif selected_page == "system":

        render_system()

    else:

        render_overview()


# =============================================================
# OVERVIEW
# =============================================================

def render_overview():

    st.subheader("System Overview")

    st.info(
        "The Admin Dashboard provides centralized control "
        "over users, permissions, formulas, resources, "
        "notices and system settings."
    )

    st.markdown(
        """
        ### Administrator Responsibilities

        - Manage student accounts
        - Manage mentor accounts
        - Control user roles
        - Manage permissions
        - Manage formulas
        - Manage learning resources
        - Publish notices
        - Monitor the application
        """
    )


# =============================================================
# USERS
# =============================================================

def render_users():

    st.subheader("👥 Manage Users")

    try:

        users = list_users()

    except Exception as e:

        st.error(
            f"Unable to load users: {e}"
        )

        return

    if not users:

        st.info(
            "No users found."
        )

        return

    # ---------------------------------------------------------
    # Filters
    # ---------------------------------------------------------

    role_filter = st.selectbox(
        "Filter by Role",
        [
            "All",
            "student",
            "mentor",
            "admin"
        ]
    )

    filtered_users = users

    if role_filter != "All":

        filtered_users = [
            user
            for user in users
            if user.get("role") == role_filter
        ]

    st.write(
        f"Showing {len(filtered_users)} user(s)"
    )

    # ---------------------------------------------------------
    # User cards
    # ---------------------------------------------------------

    for user in filtered_users:

        with st.container(border=True):

            name = user.get(
                "name",
                user.get(
                    "username",
                    "Unknown User"
                )
            )

            email = user.get(
                "email",
                "N/A"
            )

            role = user.get(
                "role",
                "N/A"
            )

            st.markdown(
                f"### {name}"
            )

            st.write(
                f"Email: {email}"
            )

            st.write(
                f"Role: {role}"
            )

            user_id = user.get(
                "id",
                "N/A"
            )

            st.write(
                f"User ID: {user_id}"
            )


# =============================================================
# PERMISSIONS
# =============================================================

def render_permissions():

    st.subheader("🔐 Permissions")

    st.info(
        "Role-based access control."
    )

    st.markdown(
        """
        ### Student

        - Access learning planner
        - Access meetings
        - Access resources
        - Access Formula Vault
        - Use Helping Bot

        ### Mentor

        - View students
        - Manage meetings
        - Share resources
        - Publish notices
        - Monitor student progress

        ### Admin

        - Manage users
        - Manage roles
        - Manage permissions
        - Manage system data
        - Manage formulas
        - Manage resources
        - Manage notices
        """
    )


# =============================================================
# FORMULAS
# =============================================================

def render_formulas():

    st.subheader("📚 Formula Management")

    st.info(
        "Formula management can be connected to the "
        "Formula Vault database."
    )

    st.markdown(
        """
        Admin can manage:

        - Add formulas
        - Edit formulas
        - Delete formulas
        - Search formulas
        - Update formula content
        """
    )


# =============================================================
# RESOURCES
# =============================================================

def render_resources():

    st.subheader("📖 Learning Resources")

    st.info(
        "Admin resource management."
    )

    st.markdown(
        """
        Admin can manage:

        - Learning documents
        - Tutorials
        - Course materials
        - Internship resources
        - Reference links
        """
    )


# =============================================================
# NOTICES
# =============================================================

def render_notices():

    st.subheader("📢 Notices")

    try:

        notices = list_notices()

    except Exception as e:

        st.error(
            f"Unable to load notices: {e}"
        )

        return

    if not notices:

        st.info(
            "No notices available."
        )

        return

    for notice in notices:

        with st.container(border=True):

            if isinstance(
                notice,
                dict
            ):

                title = notice.get(
                    "title",
                    "Notice"
                )

                message = notice.get(
                    "message",
                    notice.get(
                        "content",
                        ""
                    )
                )

                st.markdown(
                    f"### {title}"
                )

                st.write(message)

            else:

                st.write(notice)


# =============================================================
# SYSTEM
# =============================================================

def render_system():

    st.subheader("⚙️ System Management")

    st.markdown(
        """
        ### System Information
        """
    )

    st.write(
        "Application: Intern Connect"
    )

    st.write(
        "Platform: Streamlit"
    )

    st.write(
        "Database: SQLite"
    )

    st.write(
        "AI Backend: Groq"
    )

    st.write(
        "Architecture: Modular"
    )

    st.divider()

    st.markdown(
        """
        ### System Administration

        - Database management
        - User management
        - Permission management
        - AI configuration
        - Resource management
        - Application monitoring
        """
    )


# =============================================================
# OPTIONAL ALIAS
# =============================================================

def render_dashboard():

    render_admin_dashboard()