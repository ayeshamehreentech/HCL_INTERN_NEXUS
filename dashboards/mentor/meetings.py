import os

import streamlit as st
import streamlit.components.v1 as components
from database.meetings import list_meetings, save_meeting, update_meeting
from database.users import list_users


TEAMS_MEETING_LINK = os.getenv("TEAMS_MEETING_LINK", "")


def render_mentor_meetings():
    """Render mentor scheduling, editing, joining, and in-page meeting video."""
    st.subheader("📅 Meetings")

    students = [user for user in list_users() if user.get("role") == "student"]
    with st.expander("＋ Schedule or change a meeting", expanded=False):
        student_options = {
            f"{student['name']} · {student.get('email', 'no email')}": student
            for student in students
        }
        selected_label = st.selectbox(
            "Student",
            list(student_options),
            key="meeting_student",
        ) if student_options else None
        selected_student = student_options.get(selected_label) if selected_label else None
        if selected_student:
            st.caption(f"Student email: {selected_student.get('email', 'Not available')}")

        meeting_title = st.text_input("Meeting title", key="meeting_title")
        meeting_date = st.date_input("Meeting date", key="meeting_date")
        hour_col, minute_col, meridiem_col = st.columns([2, 2, 2])
        with hour_col:
            meeting_hour = st.selectbox("Hour", list(range(1, 13)), index=8, key="meeting_hour")
        with minute_col:
            meeting_minute = st.selectbox("Minute", [0, 15, 30, 45], key="meeting_minute")
        with meridiem_col:
            meeting_meridiem = st.selectbox("AM / PM", ["AM", "PM"], index=1, key="meeting_meridiem")
        meeting_time = f"{meeting_hour:02d}:{meeting_minute:02d} {meeting_meridiem}"
        st.caption(f"Scheduled time: {meeting_time}")
        meeting_link = st.text_input("Meeting link", value=TEAMS_MEETING_LINK, key="meeting_link")

        if st.button("Schedule meeting", use_container_width=True):
            if selected_student and meeting_title.strip() and meeting_link.strip():
                save_meeting(
                    selected_student["id"],
                    st.session_state.get("user_id"),
                    meeting_title,
                    str(meeting_date),
                    meeting_time,
                    meeting_link,
                )
                st.success("Meeting scheduled.")
                st.rerun()
            else:
                st.error("Select a student and enter a title and meeting link.")

    mentor_id = st.session_state.get("user_id")
    meetings = list_meetings(mentor_id, role="mentor")
    if not meetings:
        st.info("No meetings scheduled.")
    else:
        for meeting in meetings:
            with st.container(border=True):
                st.markdown(f"### {meeting.get('title', 'Meeting')}")
                st.write(f"Date: {meeting.get('meeting_date', 'N/A')}")
                st.write(f"Time: {meeting.get('meeting_time', 'N/A')}")
                link = meeting.get("meeting_link", "")

                if link and st.button(
                    "🔗 Join Meeting",
                    key=f"mentor_join_{meeting['id']}",
                    use_container_width=True,
                ):
                    st.session_state["active_mentor_meeting_link"] = link
                    st.rerun()

                with st.expander("Edit meeting"):
                    edited_title = st.text_input(
                        "Title", value=meeting.get("title", ""),
                        key=f"edit_meeting_title_{meeting['id']}",
                    )
                    edited_date = st.text_input(
                        "Date", value=meeting.get("meeting_date", ""),
                        key=f"edit_meeting_date_{meeting['id']}",
                    )
                    edited_time = st.text_input(
                        "Time", value=meeting.get("meeting_time", ""),
                        key=f"edit_meeting_time_{meeting['id']}",
                    )
                    edited_link = st.text_input(
                        "Meeting link", value=link,
                        key=f"edit_meeting_link_{meeting['id']}",
                    )
                    if st.button(
                        "Save meeting changes",
                        key=f"save_meeting_{meeting['id']}",
                        use_container_width=True,
                    ):
                        update_meeting(
                            meeting["id"],
                            edited_title,
                            edited_date,
                            edited_time,
                            edited_link,
                        )
                        st.success("Meeting updated.")
                        st.rerun()

    active_link = st.session_state.get("active_mentor_meeting_link")
    if active_link:
        components.iframe(active_link, height=520, scrolling=True)
