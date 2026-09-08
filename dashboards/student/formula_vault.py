import streamlit as st
import json

from database.formulas import (
    add_formula as save_formula,
    delete_formula as remove_formula,
    list_formulas,
    update_formula as save_formula_changes,
)


class FormulaVault:

    def __init__(self):

        self.formula_data = [

            # ==================================================
            # 1. PERFECT SQUARES
            # ==================================================

            {
                "id": 1,
                "title": "Perfect Squares (1-20)",
                "content": [
                    "1² = 1",
                    "2² = 4",
                    "3² = 9",
                    "4² = 16",
                    "5² = 25",
                    "6² = 36",
                    "7² = 49",
                    "8² = 64",
                    "9² = 81",
                    "10² = 100",
                    "11² = 121",
                    "12² = 144",
                    "13² = 169",
                    "14² = 196",
                    "15² = 225",
                    "16² = 256",
                    "17² = 289",
                    "18² = 324",
                    "19² = 361",
                    "20² = 400"
                ]
            },

            # ==================================================
            # 2. PERFECT CUBES
            # ==================================================

            {
                "id": 2,
                "title": "Perfect Cubes (1-15)",
                "content": [
                    "1³ = 1",
                    "2³ = 8",
                    "3³ = 27",
                    "4³ = 64",
                    "5³ = 125",
                    "6³ = 216",
                    "7³ = 343",
                    "8³ = 512",
                    "9³ = 729",
                    "10³ = 1000",
                    "11³ = 1331",
                    "12³ = 1728",
                    "13³ = 2197",
                    "14³ = 2744",
                    "15³ = 3375"
                ]
            },

            # ==================================================
            # 3. DIVISIBILITY
            # ==================================================

            {
                "id": 3,
                "title": "Divisibility Rules",
                "content": [
                    "2: Last digit is even: 0, 2, 4, 6, 8",
                    "3: Sum of digits is divisible by 3",
                    "4: Last two digits form a number divisible by 4",
                    "5: Ends in 0 or 5",
                    "6: Divisible by both 2 and 3",
                    "7: Double the last digit and subtract from the rest",
                    "8: Last three digits divisible by 8",
                    "9: Sum of digits is divisible by 9",
                    "10: Ends in 0",
                    "11: Alternating sum of digits is divisible by 11"
                ]
            },

            # ==================================================
            # 4. ARITHMETIC PROGRESSION
            # ==================================================

            {
                "id": 4,
                "title": "Arithmetic Progression",
                "content": [
                    "an = a + (n-1)d",
                    "d = a2 - a1",
                    "Sn = n/2 × (2a + (n-1)d)",
                    "AM = (a+b)/2",
                    "If a,b,c are in AP, then 2b = a+c",
                    "AM ≥ GM ≥ HM"
                ]
            },

            # ==================================================
            # 5. GEOMETRIC PROGRESSION
            # ==================================================

            {
                "id": 5,
                "title": "Geometric Progression",
                "content": [
                    "an = ar^(n-1)",
                    "Sn = a(r^n - 1)/(r - 1)",
                    "S∞ = a/(1-r)",
                    "GM = √ab",
                    "If a,b,c are in GP, then b² = ac"
                ]
            },

            # ==================================================
            # 6. PERCENTAGE AND RATIO
            # ==================================================

            {
                "id": 6,
                "title": "Percentage & Ratio",
                "content": [
                    "% Change = Difference / Original × 100",
                    "Successive % = x + y + xy/100",
                    "Ratio = a/b",
                    "Compounded Ratio = ac/bd"
                ]
            },

            # ==================================================
            # 7. PROFIT LOSS DISCOUNT
            # ==================================================

            {
                "id": 7,
                "title": "Profit, Loss & Discount",
                "content": [
                    "Profit = SP - CP",
                    "Loss = CP - SP",
                    "Profit % = Profit / CP × 100",
                    "Discount = MP - SP",
                    "Discount % = Discount / MP × 100"
                ]
            },

            # ==================================================
            # 8. INTEREST
            # ==================================================

            {
                "id": 8,
                "title": "Interest",
                "content": [
                    "SI = PRT/100",
                    "A = P + SI",
                    "CI: A = P(1 + R/100)^n",
                    "CI = A-P"
                ]
            },

            # ==================================================
            # 9. LOGICAL REASONING
            # ==================================================

            {
                "id": 9,
                "title": "Logical Reasoning Basics",
                "content": [
                    "Blood Relations",
                    "Reverse Alphabet",
                    "Clock Angle = |30h - 5.5m|",
                    "Syllogism"
                ]
            },

            # ==================================================
            # 10. QUADRATIC
            # ==================================================

            {
                "id": 10,
                "title": "Quadratic Formula",
                "content": [
                    "For ax² + bx + c = 0",
                    "x = (-b ± √(b² - 4ac)) / 2a"
                ]
            },

            # ==================================================
            # 11. PERMUTATION COMBINATION
            # ==================================================

            {
                "id": 11,
                "title": "Permutation and Combination",
                "content": [
                    "nC0 = nCn = 1",
                    "nC1 = n",
                    "nCr = nC(n-r)",
                    "P(n,r) = n!/(n-r)!",
                    "C(n,r) = n! / ((n-r)!r!)",
                    "Circular arrangement = (n-1)!"
                ]
            },

            # ==================================================
            # 12. 2D GEOMETRY
            # ==================================================

            {
                "id": 12,
                "title": "2D Geometry",
                "content": [
                    "Square Area = a²",
                    "Rectangle Area = l×b",
                    "Circle Area = πr²",
                    "Triangle Area = 1/2×b×h",
                    "Rhombus Area = 1/2×d1×d2",
                    "Trapezium Area = 1/2(a+b)h"
                ]
            },

            # ==================================================
            # 13. 3D MENSURATION
            # ==================================================

            {
                "id": 13,
                "title": "3D Mensuration",
                "content": [
                    "Cube Volume = a³",
                    "Cuboid Volume = lbh",
                    "Cylinder Volume = πr²h",
                    "Cone Volume = 1/3πr²h",
                    "Sphere Volume = 4/3πr³"
                ]
            },

            # ==================================================
            # 14. COORDINATE GEOMETRY
            # ==================================================

            {
                "id": 14,
                "title": "Coordinate Geometry",
                "content": [
                    "Distance = √[(x2-x1)² + (y2-y1)²]",
                    "Midpoint = ((x1+x2)/2,(y1+y2)/2)",
                    "Slope = (y2-y1)/(x2-x1)",
                    "Parallel lines have equal slopes",
                    "Perpendicular slopes multiply to -1"
                ]
            }
        ]

        self.formula_data.extend(
            {
                "id": f"custom-{item['id']}",
                "title": item["title"],
                "content": json.loads(item["content"]),
            }
            for item in list_formulas()
        )

    # =========================================================
    # SEARCH FORMULAS
    # =========================================================

    def filter_formulas(self, search_query=""):

        filtered = []

        search_query = search_query.lower().strip()

        for item in self.formula_data:

            if not search_query:

                filtered.append(item)

                continue

            matches_search = (

                search_query in item["title"].lower()

                or

                any(
                    search_query in line.lower()
                    for line in item["content"]
                )
            )

            if matches_search:

                filtered.append(item)

        return filtered

    # =========================================================
    # ADD FORMULA
    # =========================================================

    def add_formula(self, title, content):
        lines = [
            line.strip()
            for line in content.split("\n")
            if line.strip()
        ]
        database_id = save_formula(title, lines)
        new_formula = {
            "id": f"custom-{database_id}",

            "title": title.strip(),
            "content": lines,
        }

        self.formula_data.append(new_formula)

    # =========================================================
    # EDIT FORMULA
    # =========================================================

    def edit_formula(
        self,
        formula_id,
        title,
        content
    ):

        for item in self.formula_data:

            if item["id"] == formula_id:

                item["title"] = title.strip()
                item["content"] = [
                    line.strip()
                    for line in content.split("\n")
                    if line.strip()
                ]

                if isinstance(formula_id, str) and formula_id.startswith("custom-"):
                    save_formula_changes(
                        int(formula_id.removeprefix("custom-")),
                        item["title"],
                        item["content"],
                    )

                return True

        return False

    # =========================================================
    # DELETE FORMULA
    # =========================================================

    def delete_formula(self, formula_id):

        if isinstance(formula_id, str) and formula_id.startswith("custom-"):
            remove_formula(int(formula_id.removeprefix("custom-")))

        self.formula_data = [

            item

            for item in self.formula_data

            if item["id"] != formula_id
        ]

    # =========================================================
    # GET FORMULA
    # =========================================================

    def get_formula(self, formula_id):

        for item in self.formula_data:

            if item["id"] == formula_id:

                return item

        return None

    # =========================================================
    # STREAMLIT UI
    # =========================================================

    def render(self):

        st.markdown("## 📚 Formula Vault")

        st.markdown(
            "Store, search and manage your important formulas."
        )

        # =====================================================
        # ADD BUTTON
        # =====================================================

        col1, col2 = st.columns([5, 1])

        with col2:

            if st.button(
                "➕ Add",
                use_container_width=True
            ):

                st.session_state[
                    "show_add_formula"
                ] = True

        # =====================================================
        # ADD FORM
        # =====================================================

        if st.session_state.get(
            "show_add_formula",
            False
        ):

            st.markdown("### ➕ Add New Formula")

            new_title = st.text_input(
                "Formula Name",
                placeholder=(
                    "Example: Newton's Second Law"
                ),
                key="new_formula_title"
            )

            new_content = st.text_area(
                "Formula",
                placeholder=(
                    "Enter formula here...\n"
                    "Example: F = ma"
                ),
                height=150,
                key="new_formula_content"
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "💾 Save Formula",
                    use_container_width=True
                ):

                    if not new_title.strip():

                        st.error(
                            "Please enter a formula name."
                        )

                    elif not new_content.strip():

                        st.error(
                            "Please enter the formula."
                        )

                    else:

                        self.add_formula(
                            new_title,
                            new_content
                        )

                        st.session_state[
                            "show_add_formula"
                        ] = False

                        st.success(
                            "Formula saved successfully!"
                        )

                        st.rerun()

            with col2:

                if st.button(
                    "Cancel",
                    use_container_width=True
                ):

                    st.session_state[
                        "show_add_formula"
                    ] = False

                    st.rerun()

        st.divider()

        # =====================================================
        # SEARCH
        # =====================================================

        search_query = st.text_input(
            "🔍 Search Formula",
            placeholder=(
                "Search by formula name or formula..."
            )
        )

        formulas = self.filter_formulas(
            search_query
        )

        # =====================================================
        # NO RESULTS
        # =====================================================

        if not formulas:

            st.info(
                "No formulas found."
            )

            return

        # =====================================================
        # DISPLAY FORMULAS
        # =====================================================

        for formula in formulas:

            formula_id = formula["id"]

            edit_key = (
                f"edit_formula_{formula_id}"
            )

            delete_key = (
                f"confirm_delete_{formula_id}"
            )

            # =================================================
            # EDIT MODE
            # =================================================

            if st.session_state.get(
                edit_key,
                False
            ):

                st.markdown(
                    f"### ✏️ Edit: {formula['title']}"
                )

                edited_title = st.text_input(
                    "Formula Name",
                    value=formula["title"],
                    key=f"edit_title_{formula_id}"
                )

                edited_content = st.text_area(
                    "Formula",
                    value="\n".join(
                        formula["content"]
                    ),
                    height=150,
                    key=f"edit_content_{formula_id}"
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "💾 Save Changes",
                        key=f"save_{formula_id}",
                        use_container_width=True
                    ):

                        if not edited_title.strip():

                            st.error(
                                "Formula name cannot be empty."
                            )

                        elif not edited_content.strip():

                            st.error(
                                "Formula cannot be empty."
                            )

                        else:

                            self.edit_formula(
                                formula_id,
                                edited_title,
                                edited_content
                            )

                            st.session_state[
                                edit_key
                            ] = False

                            st.success(
                                "Formula updated successfully!"
                            )

                            st.rerun()

                with col2:

                    if st.button(
                        "Cancel",
                        key=f"cancel_{formula_id}",
                        use_container_width=True
                    ):

                        st.session_state[
                            edit_key
                        ] = False

                        st.rerun()

                continue

            # =================================================
            # NORMAL DISPLAY
            # =================================================

            with st.container(border=True):

                st.markdown(
                    f"### 📌 {formula['title']}"
                )

                for line in formula["content"]:

                    st.markdown(
                        f"`{line}`"
                    )

                col1, col2, col3 = st.columns(
                    [1, 1, 4]
                )

                # =============================================
                # EDIT
                # =============================================

                with col1:

                    if st.button(
                        "✏️ Edit",
                        key=(
                            f"edit_button_{formula_id}"
                        ),
                        use_container_width=True
                    ):

                        st.session_state[
                            edit_key
                        ] = True

                        st.rerun()

                # =============================================
                # DELETE
                # =============================================

                with col2:

                    if st.button(
                        "🗑️ Delete",
                        key=(
                            f"delete_button_{formula_id}"
                        ),
                        use_container_width=True
                    ):

                        st.session_state[
                            delete_key
                        ] = True

                        st.rerun()

                # =============================================
                # DELETE CONFIRMATION
                # =============================================

                if st.session_state.get(
                    delete_key,
                    False
                ):

                    st.warning(
                        "Are you sure you want to delete "
                        "this formula?"
                    )

                    c1, c2 = st.columns(2)

                    with c1:

                        if st.button(
                            "Yes, Delete",
                            key=(
                                f"yes_delete_{formula_id}"
                            ),
                            use_container_width=True
                        ):

                            self.delete_formula(
                                formula_id
                            )

                            st.session_state[
                                delete_key
                            ] = False

                            st.success(
                                "Formula deleted."
                            )

                            st.rerun()

                    with c2:

                        if st.button(
                            "Cancel",
                            key=(
                                f"cancel_delete_{formula_id}"
                            ),
                            use_container_width=True
                        ):

                            st.session_state[
                                delete_key
                            ] = False

                            st.rerun()


# =============================================================
# MODULE-LEVEL RENDER FUNCTION
# IMPORTANT:
# This MUST be outside the FormulaVault class.
# =============================================================

def render_formula_vault():

    vault = FormulaVault()

    vault.render()