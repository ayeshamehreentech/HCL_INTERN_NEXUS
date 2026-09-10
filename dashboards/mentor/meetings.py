import streamlit as st
import streamlit.components.v1 as components
from ai.config import get_setting
from database.meetings import list_meetings, save_meeting, save_recurring_meetings, update_meeting
from database.users import list_users


def render_mentor_meetings():
    st.subheader("📅 Meetings")
    students = [user for user in list_users() if user.get("role") == "student"]
    with st.expander("＋ Schedule or change a meeting", expanded=False):
        options = {"{} · {}".format(student.get("name", "Student"), student.get("email", "")): student for student in students}
        label = st.selectbox("Student", list(options), key="meeting_student") if options else None
        student = options.get(label) if label else None
        title = st.text_input("Meeting title", key="meeting_title")
        meeting_date = st.date_input("First meeting date", key="meeting_date")
        hour, minute, meridiem = st.columns(3)
        with hour: value_hour = st.selectbox("Hour", list(range(1,13)), index=8, key="meeting_hour")
        with minute: value_minute = st.selectbox("Minute", [0,15,30,45], key="meeting_minute")
        with meridiem: value_meridiem = st.selectbox("AM / PM", ["AM","PM"], index=1, key="meeting_meridiem")
        time = "{:02d}:{:02d} {}".format(value_hour, value_minute, value_meridiem)
        link = st.text_input("Meeting link", value=get_setting("TEAMS_MEETING_LINK"), key="meeting_link")
        repeat = st.checkbox("Repeat every Tuesday and Thursday (next 12 meetings)", value=True, key="meeting_repeat_tue_thu")
        if st.button("Schedule meeting", use_container_width=True):
            if not student or not title.strip() or not link.strip():
                st.error("Select a student and enter a title and meeting link.")
            elif repeat:
                save_recurring_meetings(student["id"], st.session_state.get("user_id"), title, meeting_date, time, link)
                st.success("12 Tuesday/Thursday meetings scheduled."); st.rerun()
            else:
                save_meeting(student["id"], st.session_state.get("user_id"), title, meeting_date, time, link)
                st.success("Meeting scheduled."); st.rerun()
    meetings = list_meetings(st.session_state.get("user_id"), role="mentor")
    if not meetings: st.info("No meetings scheduled.")
    for meeting in meetings:
        with st.container(border=True):
            st.markdown("### " + meeting.get("title", "Meeting"))
            st.write("Date: {} · Time: {}".format(meeting.get("meeting_date", "N/A"), meeting.get("meeting_time", "N/A")))
            link = meeting.get("meeting_link", "")
            if link:
                if st.button("🖥️ Show meeting here", key="mentor_show_{}".format(meeting["id"])):
                    st.session_state["active_mentor_meeting_link"] = link; st.rerun()
            with st.expander("Edit meeting"):
                changed_title = st.text_input("Title", meeting.get("title", ""), key="edit_title_{}".format(meeting["id"]))
                changed_date = st.text_input("Date", meeting.get("meeting_date", ""), key="edit_date_{}".format(meeting["id"]))
                changed_time = st.text_input("Time", meeting.get("meeting_time", ""), key="edit_time_{}".format(meeting["id"]))
                changed_link = st.text_input("Meeting link", link, key="edit_link_{}".format(meeting["id"]))
                if st.button("Save meeting changes", key="save_meeting_{}".format(meeting["id"])):
                    update_meeting(meeting["id"], changed_title, changed_date, changed_time, changed_link); st.rerun()
    if st.session_state.get("active_mentor_meeting_link"):
        components.iframe(st.session_state["active_mentor_meeting_link"], height=520, scrolling=True)
