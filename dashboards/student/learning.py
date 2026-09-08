import streamlit as st

from database.learning import (
    save_learning_plan,
    get_latest_plan,
    save_checklist,
    get_checklist,
    set_checklist_item,
    get_learning_progress,
)

from ai.learning_agent import generate_learning_plan


def render_learning(user_id):
    """
    Student Learning Planner
    """

    st.title("Learning Planner")

    # ========================================================
    # CREATE LEARNING PLAN
    # ========================================================

    st.subheader("Create Your Learning Plan")

    topic = st.text_input(
        "What do you want to learn?",
        placeholder="Example: LangGraph"
    )

    col1, col2 = st.columns(2)

    with col1:
        level = st.selectbox(
            "Your Level",
            [
                "Beginner",
                "Intermediate",
                "Advanced",
            ]
        )

    with col2:
        hours_per_day = st.number_input(
            "Hours per Day",
            min_value=0.5,
            max_value=12.0,
            value=2.0,
            step=0.5,
        )

    days = st.number_input(
        "Number of Days",
        min_value=1,
        max_value=90,
        value=7,
        step=1,
    )

    if st.button(
        "Generate Learning Plan",
        use_container_width=True,
    ):

        if not topic.strip():
            st.warning(
                "Please enter a topic first."
            )
        else:

            with st.spinner(
                "Creating your personalized learning plan..."
            ):

                plan, error = generate_learning_plan(
                    topic=topic.strip(),
                    level=level,
                    hours_per_day=hours_per_day,
                    days=days,
                )

            if error:
                st.error(
                    f"Could not generate plan: {error}"
                )

            else:

                save_learning_plan(
                    user_id=user_id,
                    topic=topic.strip(),
                    level=level,
                    hours_per_day=hours_per_day,
                    days=days,
                    plan=plan,
                )

                st.session_state[
                    "learning_plan_generated"
                ] = True

                st.success(
                    "Learning plan created successfully!"
                )

                st.rerun()

    # ========================================================
    # CURRENT LEARNING PLAN
    # ========================================================

    st.divider()

    st.subheader("Your Current Learning Plan")

    latest_plan = get_latest_plan(user_id)

    if not latest_plan:

        st.info(
            "You haven't created a learning plan yet."
        )

    else:

        plan = latest_plan.get(
            "plan",
            latest_plan.get("plan_json")
        )

        st.write(
            f"### {latest_plan['topic']}"
        )

        st.write(
            f"**Level:** {latest_plan['level']}"
        )

        st.write(
            f"**Hours per day:** "
            f"{latest_plan['hours_per_day']}"
        )

        st.write(
            f"**Duration:** "
            f"{latest_plan['days']} days"
        )

        # ----------------------------------------------------
        # DAYS
        # ----------------------------------------------------

        if isinstance(plan, dict):

            plan_days = plan.get(
                "days",
                []
            )

            for day in plan_days:

                day_number = day.get(
                    "day",
                    ""
                )

                title = day.get(
                    "title",
                    f"Day {day_number}"
                )

                with st.expander(
                    f"Day {day_number}: {title}"
                ):

                    topics = day.get(
                        "topics",
                        []
                    )

                    if topics:
                        st.write("**Topics:**")

                        for item in topics:
                            st.write(
                                f"- {item}"
                            )

                    tasks = day.get(
                        "tasks",
                        []
                    )

                    if tasks:
                        st.write("**Tasks:**")

                        for task in tasks:
                            st.write(
                                f"- {task}"
                            )

                    if day.get("hours"):
                        st.write(
                            f"**Hours:** "
                            f"{day['hours']}"
                        )

            # ------------------------------------------------
            # FINAL PROJECT
            # ------------------------------------------------

            final_project = plan.get(
                "final_project"
            )

            if final_project:

                st.write(
                    "### Final Project"
                )

                st.info(
                    final_project
                )

            # ------------------------------------------------
            # INTERVIEW TOPICS
            # ------------------------------------------------

            interview_topics = plan.get(
                "interview_topics",
                []
            )

            if interview_topics:

                st.write(
                    "### Interview Topics"
                )

                for item in interview_topics:
                    st.write(
                        f"- {item}"
                    )

    # ========================================================
    # CHECKLIST
    # ========================================================

    st.divider()

    st.subheader("Learning Checklist")

    if not latest_plan:

        st.info(
            "Generate a learning plan first."
        )
        return

    current_topic = latest_plan["topic"]

    checklist = get_checklist(
        user_id,
        current_topic
    )

    # --------------------------------------------------------
    # CREATE CHECKLIST FROM PLAN
    # --------------------------------------------------------

    if not checklist:

        plan = latest_plan.get(
            "plan",
            {}
        )

        items = []

        if isinstance(plan, dict):

            for day in plan.get(
                "days",
                []
            ):

                day_number = day.get(
                    "day",
                    ""
                )

                for task in day.get(
                    "tasks",
                    []
                ):

                    items.append(
                        f"Day {day_number}: {task}"
                    )

                for topic_item in day.get(
                    "topics",
                    []
                ):

                    items.append(
                        f"Day {day_number}: Learn {topic_item}"
                    )

        if items:

            save_checklist(
                user_id,
                current_topic,
                items,
            )

            checklist = get_checklist(
                user_id,
                current_topic
            )

    # --------------------------------------------------------
    # PROGRESS
    # --------------------------------------------------------

    progress = get_learning_progress(
        user_id
    )

    st.progress(
        progress["percentage"] / 100
    )

    st.write(
        f"**Progress: "
        f"{progress['completed']} / "
        f"{progress['total']} tasks completed "
        f"({progress['percentage']}%)**"
    )

    # --------------------------------------------------------
    # CHECKBOXES
    # --------------------------------------------------------

    for item in checklist:

        checked = st.checkbox(
            item["item"],
            value=bool(item["completed"]),
            key=f"learning_item_{item['id']}",
        )

        if checked != bool(
            item["completed"]
        ):

            set_checklist_item(
                item["id"],
                checked,
            )

            st.rerun()