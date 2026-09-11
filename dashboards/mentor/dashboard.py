import os
from datetime import date, timedelta

import streamlit as st

from authentication import hash_password
from database.users import create_user, list_users
from database.reports import save_report, list_reports
from ai.performance_agent import create_performance_report, get_last_middleware_trace
from database.admin import list_notices
from database.admin import create_notice, delete_notice, update_notice
from ai.newsletter_agent import format_notice
from database.resources import (
    add_resource,
    delete_resource,
    list_resources,
    update_resource,
)
from .notice import render_notice_management
from .meetings import render_mentor_meetings
from dashboards.shared_messages import render_mentor_messages
from database.messages import count_unread_messages


TEAMS_MEETING_LINK = os.getenv("TEAMS_MEETING_LINK", "")


def render_mentor_dashboard():
    """
    Main Mentor Dashboard.
    """

    st.title("Mentor Dashboard")

    st.write(
        "Welcome to the Intern Connect Mentor Dashboard."
    )

    # ---------------------------------------------------------
    # Get logged-in user
    # ---------------------------------------------------------

    user = st.session_state.get("user", {})

    mentor_name = user.get(
        "name",
        "Mentor"
    )

    st.markdown(
        f"### Welcome, {mentor_name}"
    )

    st.divider()

    # ---------------------------------------------------------
    # Dashboard statistics
    # ---------------------------------------------------------

    try:
        users = list_users()
    except Exception:
        users = []

    try:
        meetings = list_meetings(
            user.get("id"),
            role="mentor"
        )
    except Exception:
        meetings = []

    try:
        notices = list_notices()
    except Exception:
        notices = []

    students = [
        u for u in users
        if isinstance(u, dict)
        and u.get("role") == "student"
    ]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Students",
            len(students)
        )

    with col2:
        st.metric(
            "Meetings",
            len(meetings)
        )

    with col3:
        st.metric(
            "Notices",
            len(notices)
        )

    st.divider()

    # ---------------------------------------------------------
    # Mentor navigation
    # ---------------------------------------------------------

    st.subheader("Mentor Tools")

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "👥 Students",
            use_container_width=True
        ):
            st.session_state[
                "mentor_page"
            ] = "students"

    with col2:

        if st.button(
            "📅 Meetings",
            use_container_width=True
        ):
            st.session_state[
                "mentor_page"
            ] = "meetings"

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "📢 Notices",
            use_container_width=True
        ):
            st.session_state[
                "mentor_page"
            ] = "notices"

    with col2:

        if st.button(
            "📚 Resources",
            use_container_width=True
        ):
            st.session_state[
                "mentor_page"
            ] = "resources"

    if st.button(
        f"📝 Doubt Clarifications ({count_unread_messages(st.session_state.get('user_id'))})",
        use_container_width=True,
    ):
        st.session_state["mentor_page"] = "messages"

    # ---------------------------------------------------------
    # Current selected page
    # ---------------------------------------------------------

    selected_page = st.session_state.get(
        "mentor_page",
        "dashboard"
    )

    st.divider()

    if selected_page == "students":

        render_students_preview()

    elif selected_page == "meetings":

        render_meetings_preview()

    elif selected_page == "notices":

        render_notice_management()

    elif selected_page == "resources":

        render_resources_preview()

    elif selected_page == "messages":

        render_mentor_messages()

    else:

        render_dashboard_overview()


# =============================================================
# DASHBOARD OVERVIEW
# =============================================================

def render_dashboard_overview():

    st.subheader("Dashboard Overview")

    st.info(
        "Use the Mentor Tools above to manage students, "
        "meetings, notices and learning resources."
    )

    st.markdown(
        """
        ### Mentor Responsibilities

        - Monitor student progress
        - Conduct meetings
        - Review learning plans
        - Share notices
        - Provide learning resources
        - Support students during the internship
        """
    )


# =============================================================
# STUDENTS
# =============================================================

def render_students_preview():

    st.subheader("👥 Students")

    try:

        users = list_users()

        students = [
            user
            for user in users
            if user.get("role") == "student"
        ]

    except Exception as e:

        st.error(
            f"Unable to load students: {e}"
        )

        return

    if not students:

        st.info(
            "No students found."
        )

    with st.expander("＋ Add intern", expanded=False):
        intern_name = st.text_input("Intern name", key="mentor_new_intern_name")
        intern_email = st.text_input("Intern email", key="mentor_new_intern_email")
        intern_password = st.text_input("Temporary password", type="password", key="mentor_new_intern_password")
        if st.button("Create intern account", use_container_width=True):
            if not intern_name.strip() or not intern_email.strip() or not intern_password:
                st.error("Name, email, and temporary password are required.")
            else:
                created_id = create_user(
                    intern_name,
                    intern_email,
                    "student",
                    hash_password(intern_password),
                )
                if created_id:
                    st.success("Intern account created.")
                    st.rerun()
                else:
                    st.error("Could not create the intern. The email may already exist.")

    for student in students:

        with st.container(border=True):

            st.markdown(
                f"### {student.get('name', 'Student')}"
            )

            st.write(
                f"Email: {student.get('email', 'N/A')}"
            )

            st.write(
                f"Role: {student.get('role', 'student')}"
            )

            with st.expander("📊 Performance and report"):
                conn = __import__("database.connection", fromlist=["get_connection"]).get_connection()
                activity = conn.execute(
                    "SELECT COALESCE(SUM(seconds), 0) AS seconds, COUNT(*) AS sessions "
                    "FROM activity WHERE user_id = ?", (student["id"],)
                ).fetchone()
                plans = conn.execute(
                    "SELECT COUNT(*) AS count FROM learning_plans WHERE user_id = ?",
                    (student["id"],),
                ).fetchone()
                activity_by_day = conn.execute(
                    "SELECT substr(started_at, 1, 10) AS day, "
                    "COALESCE(SUM(seconds), 0) AS seconds FROM activity "
                    "WHERE user_id = ? GROUP BY day ORDER BY day DESC LIMIT 7",
                    (student["id"],),
                ).fetchall()
                conn.close()
                metric_col, plan_col = st.columns(2)
                metric_col.metric("Learning sessions", activity["sessions"] if activity and "sessions" in activity.keys() else 0)
                plan_col.metric("Plans created", plans.get("count", 0) if plans else 0)
                st.progress(min(1.0, (activity["seconds"] if activity and "seconds" in activity.keys() else 0) / 36000), text="Activity progress")
                if activity_by_day:
                    st.caption("Activity over the last seven active days")
                    st.bar_chart(
                        {row.get("day", str(row.get("started_at", ""))[:10]): row.get("seconds", 0) for row in reversed(activity_by_day)},
                        y_label="Seconds",
                    )

                report_period = st.selectbox(
                    "AI report period",
                    ["Weekly", "Monthly"],
                    key=f"performance_period_{student['id']}",
                )
                if st.button(
                    "Generate Groq performance report",
                    key=f"generate_performance_{student['id']}",
                    use_container_width=True,
                ):
                    end_date = date.today()
                    days = 7 if report_period == "Weekly" else 30
                    start_date = end_date - timedelta(days=days)
                    with st.spinner("Analyzing activity, plans, and meeting notes..."):
                        _, analysis = create_performance_report(
                            student,
                            st.session_state.get("user_id"),
                            report_period,
                            start_date.isoformat(),
                            end_date.isoformat() + "T23:59:59",
                        )
                    st.session_state[f"latest_report_{student['id']}"] = analysis
                    st.success(f"{report_period} report saved to history.")
                    with st.expander("View LangChain middleware trace"):
                        st.json(get_last_middleware_trace())

                for report in list_reports(student["id"]):
                    st.markdown(f"**{report['title']}**")
                    st.write(report["content"])
                    if report.get("attachment_data"):
                        st.download_button(
                            "Download PDF report",
                            report["attachment_data"],
                            file_name=report["attachment_name"] or "student_report.pdf",
                            mime="application/pdf",
                            key=f"download_report_{report['id']}",
                        )

                report_title = st.text_input("Report title", key=f"report_title_{student['id']}")
                report_content = st.text_area("Typed report", key=f"report_content_{student['id']}")
                report_pdf = st.file_uploader(
                    "Attach handwritten PDF",
                    type=["pdf"],
                    key=f"report_pdf_{student['id']}",
                )
                if st.button("Save student report", key=f"save_report_{student['id']}", use_container_width=True):
                    if not report_title.strip() or not report_content.strip():
                        st.error("Enter a report title and typed report.")
                    else:
                        save_report(
                            student["id"],
                            st.session_state.get("user_id"),
                            report_title,
                            report_content,
                            report_pdf.name if report_pdf else None,
                            report_pdf.getvalue() if report_pdf else None,
                        )
                        st.success("Student report saved.")
                        st.rerun()
                for report in list_reports(student["id"]):
                    st.markdown(f"**{report['title']}**")
                    st.write(report["content"])


# =============================================================
# MEETINGS
# =============================================================

def render_meetings_preview():
    render_mentor_meetings()


# =============================================================
# NOTICES
# =============================================================

def render_notices_preview():

    st.subheader("📢 Notices")

    with st.expander("＋ Publish notice", expanded=False):
        notice_title = st.text_input(
            "Notice title",
            key="mentor_notice_title",
        )
        notice_message = st.text_area(
            "Notice message",
            key="mentor_notice_message",
        )
        if st.button("Format and publish to students", use_container_width=True):
            if not notice_title.strip() or not notice_message.strip():
                st.error("Enter both a title and message.")
            else:
                formatted_title, formatted_message = format_notice(
                    notice_title,
                    notice_message,
                )
                create_notice(formatted_title, formatted_message)
                st.success("Notice published to students.")
                st.rerun()

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

            if isinstance(notice, dict):

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

                edit_key = f"edit_notice_{notice['id']}"
                if st.session_state.get(edit_key):
                    edited_title = st.text_input(
                        "Title", value=title, key=f"notice_title_{notice['id']}"
                    )
                    edited_message = st.text_area(
                        "Message", value=message, key=f"notice_message_{notice['id']}"
                    )
                    if st.button("Save edit", key=f"save_notice_{notice['id']}"):
                        formatted_title, formatted_message = format_notice(
                            edited_title, edited_message
                        )
                        update_notice(notice["id"], formatted_title, formatted_message)
                        st.session_state.pop(edit_key, None)
                        st.rerun()
                else:
                    st.markdown(f"### {title}")
                    st.write(message)
                    edit_col, delete_col = st.columns(2)
                    with edit_col:
                        if st.button("✏️ Edit", key=f"edit_notice_button_{notice['id']}"):
                            st.session_state[edit_key] = True
                            st.rerun()
                    with delete_col:
                        if st.button("🗑️ Delete", key=f"delete_notice_button_{notice['id']}"):
                            delete_notice(notice["id"])
                            st.rerun()

            else:

                st.write(notice)


# =============================================================
# RESOURCES
# =============================================================

def render_resources_preview():

    st.subheader("📚 Learning Resources")

    if st.button("＋ Add Resource", use_container_width=True):
        st.session_state["show_resource_form"] = True
        st.session_state.pop("editing_resource_id", None)

    resources = list_resources()

    if st.session_state.get("show_resource_form"):
        editing_id = st.session_state.get("editing_resource_id")
        editing = next(
            (item for item in resources if item["id"] == editing_id),
            None,
        )
        st.markdown("### Edit Resource" if editing else "### Add Resource")
        topic = st.text_input("Topic", value=editing["topic"] if editing else "")
        title = st.text_input("Title", value=editing["title"] if editing else "")
        url = st.text_input("YouTube or blog URL", value=editing["url"] if editing else "")
        resource_type = st.selectbox(
            "Resource type",
            ["YouTube", "Blog"],
            index=0 if not editing or editing["resource_type"] == "YouTube" else 1,
        )
        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button("Save Resource", use_container_width=True):
                if not topic.strip() or not title.strip() or not url.strip():
                    st.error("Topic, title, and URL are required.")
                elif editing:
                    update_resource(editing_id, topic, title, url, resource_type)
                    st.session_state.pop("show_resource_form", None)
                    st.session_state.pop("editing_resource_id", None)
                    st.rerun()
                else:
                    user = st.session_state.get("user", {})
                    add_resource(topic, title, url, resource_type, user.get("id"))
                    st.session_state.pop("show_resource_form", None)
                    st.rerun()
        with cancel_col:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pop("show_resource_form", None)
                st.session_state.pop("editing_resource_id", None)
                st.rerun()

    if not resources:
        st.info("No mentor resources have been added yet.")
        return

    for resource in resources:
        with st.container(border=True):
            st.markdown(f"### {resource['topic']}")
            st.write(f"**{resource['title']}** · {resource['resource_type']}")
            st.link_button("Open resource", resource["url"])
            edit_col, delete_col = st.columns(2)
            with edit_col:
                if st.button("✏️ Edit", key=f"edit_resource_{resource['id']}", use_container_width=True):
                    st.session_state["show_resource_form"] = True
                    st.session_state["editing_resource_id"] = resource["id"]
                    st.rerun()
            with delete_col:
                if st.button("🗑️ Delete", key=f"delete_resource_{resource['id']}", use_container_width=True):
                    delete_resource(resource["id"])
                    st.rerun()


# =============================================================
# OPTIONAL ALIAS
# =============================================================

def render_dashboard():

    render_mentor_dashboard()
