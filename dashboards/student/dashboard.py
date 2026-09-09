from datetime import datetime
from html import escape

import streamlit as st

from database.users import get_user
from database.admin import (
    request_deletion,
    list_notices
)
from ai.chains import MiddlewareTrace, run_middleware_step
from database.messages import count_unread_messages
from dashboards.shared_messages import render_student_messages

from .learning import render_learning
from .meetings import render_meetings
from .resources import render_resources
from .formula_vault import render_formula_vault
from .helping_bot import render_helping_bot_tab
from .coding_lab import render_coding_lab


def render_notifications(notices):
    """Render mentor notices inside the dedicated notices tab."""
    st.markdown(
        f"<div class='notice-alert'>🔔 <strong>{len(notices)} notice"
        f"{'s' if len(notices) != 1 else ''}</strong> from your mentor</div>",
        unsafe_allow_html=True,
    )
    if not notices:
        st.info("No notices yet.")
        return

    st.markdown(
        """
        <style>
        .notice-alert { margin:.8rem 0; padding:.75rem 1rem; border-left:5px solid #b47c32; border-radius:8px; color:#5b382a; background:#f8edce; }
        .notice-board { margin:1rem 0 1.5rem; padding:1.35rem; border:12px solid #6f4935; border-radius:8px; background:linear-gradient(135deg,#9b6c46,#5f3d2d); box-shadow:0 16px 30px rgba(62,39,28,.2); }
        .notice-board-title { padding:.7rem 1rem; color:#fff8e9; text-align:center; font-family:Georgia,serif; font-size:1.35rem; letter-spacing:.08em; text-transform:uppercase; background:#714733; border:1px solid #d3a66f; }
        .notice-paper { position:relative; margin:1rem auto 0; max-width:880px; padding:2.25rem 2.4rem; color:#493524; background:#f8edce; border:1px solid #c39a62; box-shadow:0 10px 20px rgba(48,30,20,.18); transform:rotate(-.35deg); overflow:hidden; }
        .notice-paper:before, .notice-paper:after { content:""; position:absolute; width:70px; height:70px; background:#e1c18a; opacity:.55; }
        .notice-paper:before { top:-35px; left:-35px; transform:rotate(45deg); }.notice-paper:after { bottom:-35px; right:-35px; transform:rotate(45deg); }
        .notice-ribbon { display:inline-block; margin-bottom:.65rem; padding:.25rem .7rem; color:#fff8e9; background:#9b3f32; font-size:.68rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }
        .notice-paper h3 { margin:.2rem 0 .7rem; color:#593523; font-family:Georgia,serif; font-size:1.6rem; }.notice-paper p { white-space:pre-wrap; line-height:1.65; font-family:Georgia,serif; font-size:1rem; }.notice-date { color:#87684d; font-size:.76rem; font-style:italic; }
        </style>
        <section class="notice-board"><div class="notice-board-title">📜 Mentor Notice Board</div>
        """,
        unsafe_allow_html=True,
    )
    for notice in notices:
        title = escape(str(notice.get("title", "Notice")))
        message = escape(str(notice.get("message", "")))
        created_at = escape(str(notice.get("created_at", ""))[:10])
        st.markdown(
            f"<article class='notice-paper'><span class='notice-ribbon'>Official Notice</span>"
            f"<h3>{title}</h3><p>{message}</p><div class='notice-date'>Issued {created_at}</div></article>",
            unsafe_allow_html=True,
        )
    st.markdown("</section>", unsafe_allow_html=True)


def render_student_dashboard():

    student_trace = MiddlewareTrace()

    user = get_user(
        st.session_state.user_email
    )


    # ========================================================
    # HEADER
    # ========================================================

    st.header(
        f"Welcome back, "
        f"{st.session_state.user_name}!"
    )


    # ========================================================
    # TOP INFORMATION
    # ========================================================

    col1, col2 = st.columns(2)
    internship_end_date = (
        user.get("end_date")
        if user
        else None
    )


    with col1:

        if (
            internship_end_date
        ):

            end_date = datetime.strptime(
                internship_end_date,
                "%Y-%m-%d"
            ).date()


            days_left = max(
                0,
                (
                    end_date
                    - datetime.now().date()
                ).days
            )


            st.metric(
                "Days Left",
                days_left
            )

        else:

            st.metric(
                "Days Left",
                "Not Set"
            )


    with col2:

        st.metric(
            "Meetings",
            "Tue & Thu"
        )


    st.divider()


    # ========================================================
    # NOTICES
    # ========================================================

    notices = run_middleware_step(
        student_trace,
        "load mentor notices",
        lambda _: list_notices(),
    )


    # ========================================================
    # TABS
    # ========================================================

    tabs = st.tabs(
        [
            "📌 Notices",
            f"📝 Doubt Clarification ({count_unread_messages(st.session_state.get('user_id'))})",
            "📚 Learning",
            "📅 Meetings",
            "🔗 Resources",
            "⚡ Formula Vault",
            "🤝 Helping Bot",
            "🧪 Coding Lab"
        ]
    )


    # ========================================================
    # NOTIFICATIONS
    # ========================================================

    with tabs[0]:

        run_middleware_step(
            student_trace,
            "render notifications tab",
            lambda _: render_notifications(notices),
        )


    # ========================================================
    # LEARNING
    # ========================================================

    with tabs[1]:

        run_middleware_step(
            student_trace,
            "render private mentor chat",
            lambda _: render_student_messages(),
        )


    # ========================================================
    # LEARNING
    # ========================================================

    with tabs[2]:

        run_middleware_step(
            student_trace,
            "render learning tab",
            lambda _: render_learning(user_id=user["id"]),
        )


    # ========================================================
    # MEETINGS
    # ========================================================

    with tabs[3]:

        run_middleware_step(
            student_trace,
            "render meetings tab",
            lambda _: render_meetings(),
        )


    # ========================================================
    # RESOURCES
    # ========================================================

    with tabs[4]:

        run_middleware_step(
            student_trace,
            "render resources tab",
            lambda _: render_resources(),
        )


    # ========================================================
    # FORMULA VAULT
    # ========================================================

    with tabs[5]:

        run_middleware_step(
            student_trace,
            "render formula vault tab",
            lambda _: render_formula_vault(),
        )


    # ========================================================
    # HELPING BOT
    # ========================================================

    with tabs[6]:

        run_middleware_step(
            student_trace,
            "render helping bot tab",
            lambda _: render_helping_bot_tab(),
        )

    with tabs[7]:

        run_middleware_step(
            student_trace,
            "render coding lab tab",
            lambda _: render_coding_lab(),
        )

    with st.expander("View student dashboard middleware trace"):
        st.json(student_trace.events)


    # ========================================================
    # ACCOUNT MANAGEMENT
    # ========================================================

    st.divider()

    st.subheader(
        "Account"
    )


    if st.button(
        "Request Account Deletion"
    ):

        request_deletion(
            st.session_state.user_id
        )

        st.warning(
            "Your deletion request has been "
            "sent to the administrator."
        )
