import streamlit as st

from ai.newsletter_agent import format_notice
from database.admin import (
    create_notice,
    delete_notice,
    list_notices,
    update_notice,
)


def render_notice_management():
    """Let mentors publish, edit, and delete student notices."""
    st.subheader("📢 Notices")

    with st.expander("＋ Write a notice", expanded=False):
        title = st.text_input("Notice title", key="notice_module_title")
        message = st.text_area("What should students know?", key="notice_module_message")
        if st.button("Format and send notice", key="notice_module_send", use_container_width=True):
            if not title.strip() or not message.strip():
                st.error("Enter both a title and message.")
            else:
                formatted_title, formatted_message = format_notice(title, message)
                create_notice(formatted_title, formatted_message)
                st.success("Notice sent to students.")
                st.rerun()

    notices = list_notices()
    if not notices:
        st.info("No notices have been sent yet.")
        return

    for notice in notices:
        notice_id = notice["id"]
        edit_key = f"notice_module_edit_{notice_id}"
        with st.container(border=True):
            if st.session_state.get(edit_key):
                edited_title = st.text_input(
                    "Title",
                    value=notice["title"],
                    key=f"notice_module_edit_title_{notice_id}",
                )
                edited_message = st.text_area(
                    "Message",
                    value=notice["message"],
                    key=f"notice_module_edit_message_{notice_id}",
                )
                save_col, cancel_col = st.columns(2)
                with save_col:
                    if st.button("Save edit", key=f"notice_module_save_{notice_id}", use_container_width=True):
                        formatted_title, formatted_message = format_notice(
                            edited_title,
                            edited_message,
                        )
                        update_notice(notice_id, formatted_title, formatted_message)
                        st.session_state.pop(edit_key, None)
                        st.rerun()
                with cancel_col:
                    if st.button("Cancel", key=f"notice_module_cancel_{notice_id}", use_container_width=True):
                        st.session_state.pop(edit_key, None)
                        st.rerun()
            else:
                st.markdown(f"### {notice['title']}")
                st.write(notice["message"])
                edit_col, delete_col = st.columns(2)
                with edit_col:
                    if st.button("✏️ Edit", key=f"notice_module_edit_button_{notice_id}", use_container_width=True):
                        st.session_state[edit_key] = True
                        st.rerun()
                with delete_col:
                    if st.button("🗑️ Delete", key=f"notice_module_delete_{notice_id}", use_container_width=True):
                        delete_notice(notice_id)
                        st.rerun()
