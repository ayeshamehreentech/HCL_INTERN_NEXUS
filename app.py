import os
from datetime import datetime
from html import escape

import requests
import streamlit as st
from dotenv import load_dotenv

from authentication import login_page, signup_page, logout
from database.connection import init_db, get_connection

from dashboards.student.dashboard import render_student_dashboard
from dashboards.mentor.dashboard import render_mentor_dashboard
from dashboards.admin.dashboard import render_admin_dashboard



init_db()

load_dotenv()

st.set_page_config(
    page_title="HCLTech GenAI Forge",
    page_icon="✦",
    layout="wide"
)

init_db()


# ============================================================
# SESSION STATE
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "meeting_transcript" not in st.session_state:
    st.session_state.meeting_transcript = ""

if "meeting_summary" not in st.session_state:
    st.session_state.meeting_summary = ""


# ============================================================
# ACTIVITY TRACKING
# ============================================================

def start_activity():

    if st.session_state.get("activity_id"):
        return

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO activity(user_id, started_at)
        VALUES (?, ?)
        """,
        (
            st.session_state.user_id,
            datetime.now().isoformat(timespec="seconds")
        )
    )

    conn.commit()
    conn.close()

    st.session_state.activity_id = cursor.lastrowid


def stop_activity():

    activity_id = st.session_state.pop(
        "activity_id",
        None
    )

    if not activity_id:
        return

    conn = get_connection()

    row = conn.execute(
        """
        SELECT started_at
        FROM activity
        WHERE id = ?
        """,
        (activity_id,)
    ).fetchone()

    if row:

        seconds = max(
            0,
            int(
                (
                    datetime.now()
                    - datetime.fromisoformat(
                        row["started_at"]
                    )
                ).total_seconds()
            )
        )

        conn.execute(
            """
            UPDATE activity
            SET ended_at = ?, seconds = ?
            WHERE id = ?
            """,
            (
                datetime.now().isoformat(
                    timespec="seconds"
                ),
                seconds,
                activity_id
            )
        )

        conn.commit()

    conn.close()


# ============================================================
# AUTHENTICATION SCREEN
# ============================================================

def apply_aesthetic_theme():
    """Apply the warm academic palette throughout the portal."""

    st.markdown(
        """
        <style>
        :root { --charcoal:#444345; --tan:#b69472; --sage:#8c9186; --ochre:#d3b67f; --blush:#f5ebeb; --cream:#faf6f1; --line:#dacabc; }
        .stApp { background:radial-gradient(circle at 94% 0%,#e0caad 0,transparent 27%),linear-gradient(145deg,#f5ebeb 0%,#faf6f1 46%,#ece9dc 100%); color:var(--charcoal); }
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"] { background:linear-gradient(180deg,#414143 0%,#666a60 100%); }
        [data-testid="stSidebar"] * { color:#fffdf8!important; }
        [data-testid="stSidebar"] .stRadio label { padding:.35rem .15rem; border-radius:7px; }
        [data-testid="stSidebar"] .stButton button { background:rgba(245,235,235,.16); border:1px solid rgba(255,255,255,.22); color:#fffdf8; border-radius:10px; }
        [data-testid="stMainBlockContainer"] { max-width:1320px; padding-top:2rem; }
        [data-testid="stMainBlockContainer"] label,
        [data-testid="stMainBlockContainer"] label p,
        [data-testid="stMainBlockContainer"] [data-testid="stWidgetLabel"] p { color:#5b4b43!important; font-weight:700; }
        [data-testid="stMainBlockContainer"] input,
        [data-testid="stMainBlockContainer"] textarea { color:#332b28!important; caret-color:#8b5d42; }
        [data-testid="stMainBlockContainer"] input::placeholder,
        [data-testid="stMainBlockContainer"] textarea::placeholder { color:#9a877d!important; opacity:1; }
        h1,h2,h3 { color:#444345; letter-spacing:-.025em; }
        [data-testid="stMetric"] { background:#fffdf9; border:1px solid var(--line); border-radius:16px; padding:1rem; box-shadow:0 7px 18px rgba(68,67,69,.07); }
        [data-testid="stMetricLabel"] { color:#727368; font-size:.76rem; text-transform:uppercase; letter-spacing:.06em; font-weight:750; }
        [data-testid="stMetricValue"] { color:#444345; font-weight:800; }
        [data-baseweb="tab-list"] { gap:.45rem; border-bottom:1px solid var(--line); }
        [data-baseweb="tab"] { color:#6b5146!important; font-weight:750; padding:0 14px; height:43px; }
        [data-baseweb="tab"] p { color:#6b5146!important; }
        [data-baseweb="tab"][aria-selected="true"] { color:#4b2e24!important; }
        [data-baseweb="tab"][aria-selected="true"] p { color:#4b2e24!important; }
        .stButton > button { background:#4b2e24!important; border:1px solid #3a2119!important; border-radius:10px; color:#fffdf9!important; font-weight:750; min-height:2.7rem; }
        .stButton > button p { color:#fffdf9!important; }
        .stButton > button:hover { background:#6b4332!important; color:#fffdf9!important; }
        .stButton > button:hover p { color:#fffdf9!important; }
        .stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div { background:#fffdf9; border-color:#d4c0ad; border-radius:9px; }
        .stProgress > div > div > div { background:#8c9186; }
        .stAlert { border-radius:12px; border-color:#d7c3ae; }
        .quote-window { overflow:hidden; margin:1.4rem 0 .3rem; border:1px solid #dcc9b9; border-radius:15px; background:rgba(255,253,249,.82); box-shadow:0 8px 18px rgba(68,67,69,.06); }
        .quote-track { display:flex; width:max-content; animation:quote-slide 28s linear infinite; }
        .quote-window:hover .quote-track { animation-play-state:paused; }
        .quote-item { width:330px; min-height:94px; padding:1rem 1.15rem; box-sizing:border-box; border-right:1px solid #eadcd1; }
        .quote-mark { color:#b69472; font-size:1.45rem; font-family:Georgia,serif; line-height:.8; }
        .quote-copy { color:#535254; font-family:Georgia,serif; font-size:.9rem; line-height:1.45; }
        .quote-source { margin-top:.35rem; color:#85877c; font-size:.68rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
        .forge-banner { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:1.05rem 1.25rem; margin:0 0 1.2rem; border:1px solid #d8c5b3; border-radius:16px; background:linear-gradient(100deg,#fffdf9,#eee5d7); box-shadow:0 8px 18px rgba(68,67,69,.05); }
        .forge-banner strong { display:block; color:#444345; font-size:1rem; letter-spacing:-.015em; }.forge-banner span { color:#74746e; font-size:.82rem; }.forge-badge { background:#d3b67f; color:#49453f!important; border-radius:999px; padding:.28rem .58rem; white-space:nowrap; font-size:.68rem!important; font-weight:800; letter-spacing:.06em; }
        @keyframes quote-slide { from { transform:translateX(0); } to { transform:translateX(-50%); } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def quote_carousel():
    """A lightweight, auto-sliding quote strip; pause it by hovering."""

    quotes = [
        ("The art of the possible begins with a question.", "HCLTech GenAI Forge"),
        ("Build with curiosity. Explain with clarity. Deliver with impact.", "GenAI internship principle"),
        ("Every prototype is a chance to learn something real.", "Learning mindset"),
    ]
    quote_cards = "".join(
        f'<div class="quote-item"><div class="quote-mark">“</div><div class="quote-copy">{quote}</div><div class="quote-source">{source}</div></div>'
        for quote, source in quotes * 2
    )
    st.markdown(
        f'<div class="quote-window" aria-label="Inspiring internship quotes"><div class="quote-track">{quote_cards}</div></div>',
        unsafe_allow_html=True,
    )


def auth_screen():

    st.title("✦ HCLTech GenAI Forge")

    st.caption(
        "GenAI Internship Experience"
    )

    quote_carousel()

    login_tab, signup_tab = st.tabs(
        [
            "Login",
            "Create Account"
        ]
    )

    with login_tab:
        login_page()

    with signup_tab:
        signup_page()

# ============================================================
# ABOUT HCLTECH
# ============================================================

@st.cache_data(ttl=86400, show_spinner=False)
def get_person_thumbnail(page_title):
    """Find a public portrait through Wikimedia's search and media APIs."""
    try:
        response = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title}",
            headers={"User-Agent": "HCLTech-GenAI-Forge/1.0"},
            timeout=10,
        )
        if response.ok:
            thumbnail = response.json().get("thumbnail", {}).get("source")
            if thumbnail:
                return thumbnail

        search_response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": page_title.replace("_", " "),
                "gsrnamespace": 6,
                "gsrlimit": 1,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 640,
                "format": "json",
            },
            headers={"User-Agent": "HCLTech-GenAI-Forge/1.0"},
            timeout=10,
        )
        pages = search_response.json().get("query", {}).get("pages", {})
        return next(
            (
                page.get("imageinfo", [{}])[0].get("thumburl")
                for page in pages.values()
                if page.get("imageinfo")
            ),
            None,
        )
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def render_hcl_about():
    """Render the HCLTech story for logged-in users."""

    founding_year = 1976
    completion_year = datetime.now().year - founding_year

    st.markdown(
        """
        <style>
        .about-hero { position:relative; padding:2.5rem 2.7rem; border-radius:24px; color:#fffaf5; background:linear-gradient(120deg,#251b17,#6c452d 70%,#9e765b); box-shadow:0 18px 38px rgba(65,39,25,.22); margin-bottom:1.4rem; overflow:hidden; }
        .about-medal { position:absolute; right:1.5rem; top:1rem; width:152px; height:152px; display:flex; align-items:center; justify-content:center; text-align:center; color:#5b3711; background:radial-gradient(circle at 35% 28%,#fff4ae 0,#e9bc45 35%,#a96b12 70%,#6f3c08 100%); border:6px solid #f8d979; border-radius:50%; box-shadow:0 0 0 5px #9a5d0e, inset 0 0 0 4px #fff0a1, 0 10px 18px rgba(20,10,5,.3); }
        .medal-copy { position:relative; z-index:2; display:flex; width:100%; height:100%; align-items:center; justify-content:center; flex-direction:column; padding:0 12px; box-sizing:border-box; color:#5b3711; font-size:.86rem; font-weight:950; line-height:1.2; letter-spacing:.07em; text-transform:uppercase; }
        .medal-copy strong { display:block; font-size:1.25rem; line-height:1.05; white-space:nowrap; }.medal-copy small { display:block; margin-top:.25rem; font-size:.58rem; letter-spacing:.08em; }
        .about-medal:before, .about-medal:after { content:""; position:absolute; z-index:-1; top:92px; width:34px; height:65px; background:linear-gradient(135deg,#c3881d,#6d3909); clip-path:polygon(0 0,100% 0,78% 100%,50% 82%,22% 100%); }
        .about-medal:before { left:18px; transform:rotate(8deg); }.about-medal:after { right:18px; transform:rotate(-8deg); }
        .about-kicker { color:#e6c7ae; font-size:.72rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
        .about-hero h1 { margin:.45rem 0; font-size:2.65rem; letter-spacing:-.05em; }
        .about-hero p { margin:0; max-width:720px; color:#f4e6da; font-size:1.02rem; }
        .about-card { height:100%; min-height:210px; box-sizing:border-box; padding:1.5rem; border-radius:18px; border:1px solid #e5d4c6; background:#fffaf6; box-shadow:0 7px 20px rgba(76,46,29,.06); }
        .about-card h3 { margin:.55rem 0 .45rem; color:#3e291f; }.about-card p { color:#736159; line-height:1.55; }
        .person-card { min-height:440px; padding:1.15rem; border-radius:18px; border:1px solid #e5d4c6; background:#fffaf6; box-shadow:0 7px 20px rgba(76,46,29,.06); overflow:hidden; }
        .person-card img, .person-placeholder { display:block; width:100%; height:230px; object-fit:cover; object-position:center top; border-radius:12px; background:#eadfd4; }
        .person-placeholder { display:flex; align-items:center; justify-content:center; color:#fff8ef; background:linear-gradient(135deg,#5b382a,#b47c58); font-family:Georgia,serif; font-size:3.2rem; font-weight:700; }
        .person-card h3 { margin:.7rem 0 .25rem; color:#3e291f; }.person-card p { color:#736159; line-height:1.5; margin:.2rem 0 .7rem; }
        .person-links a { color:#8b5d42; font-size:.8rem; font-weight:750; margin-right:.7rem; text-decoration:none; }
        .about-year { color:#9b7153; font-size:1.65rem; font-weight:800; letter-spacing:-.05em; }
        .about-label { display:inline-block; background:#e9e4d7; color:#68634e; border-radius:999px; padding:.25rem .6rem; font-size:.72rem; font-weight:800; letter-spacing:.05em; }
        </style>
        <section class="about-hero">
                    <div class="about-medal"><div class="medal-copy"><strong>{completion_year}</strong><span>years complete</span><span>HCLTech</span><small>since {founding_year}</small></div></div>
          <div class="about-kicker">HCLTech · About</div>
          <h1>Built on the art of the possible.</h1>
          <p>From an Indian computing start-up to a global technology company, HCLTech has been shaped by curiosity, courage and a belief in what technology can make possible.</p>
        </section>
        """.replace(
            "{completion_year}",
            str(completion_year),
        ).replace(
            "{founding_year}",
            str(founding_year),
        ),
        unsafe_allow_html=True,
    )

    history, founder, ceo = st.columns(3, gap="large")
    with history:
        st.markdown(
            f'<div class="about-card"><div class="about-year">Founded in {founding_year}</div><h3>The beginning</h3><p>HCL was founded in India at the start of the country’s modern computing journey, with an ambition to build world-class technology.</p><p><strong>{completion_year} years completed in {datetime.now().year}.</strong><br>Our journey continues into the next chapter.</p></div>',
            unsafe_allow_html=True,
        )
    with founder:
        shiv_image = get_person_thumbnail("Shiv_Nadar")
        shiv_portrait = (
            f'<img src="{escape(shiv_image)}" alt="Portrait of Shiv Nadar">'
            if shiv_image
            else '<div class="person-placeholder">SN</div>'
        )
        st.markdown(
            f'<div class="person-card">{shiv_portrait}<span class="about-label">FOUNDER · 1976</span><h3>Shiv Nadar</h3><p>Founder of HCL Group, Chairman Emeritus and education philanthropist.</p><div class="person-links"><a href="https://www.hcltech.com/leadership" target="_blank">HCL profile</a><a href="https://www.linkedin.com/search/results/people/?keywords=Shiv%20Nadar" target="_blank">LinkedIn</a><a href="https://www.shivnadarfoundation.org/" target="_blank">Foundation</a></div></div>',
            unsafe_allow_html=True,
        )
    with ceo:
        vijay_image = get_person_thumbnail("C_Vijayakumar")
        vijay_portrait = (
            f'<img src="{escape(vijay_image)}" alt="Portrait of C Vijayakumar">'
            if vijay_image
            else '<div class="person-placeholder">CV</div>'
        )
        st.markdown(
            f'<div class="person-card">{vijay_portrait}<span class="about-label">CEO &amp; MANAGING DIRECTOR</span><h3>C Vijayakumar</h3><p>Leads HCLTech through its next chapter of technology, AI and global growth.</p><div class="person-links"><a href="https://www.hcltech.com/leadership" target="_blank">HCL profile</a><a href="https://www.linkedin.com/search/results/people/?keywords=C%20Vijayakumar%20HCLTech" target="_blank">LinkedIn</a><a href="https://github.com/search?q=C+Vijayakumar+HCLTech&type=users" target="_blank">GitHub search</a></div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Why this matters to your internship")
    st.info("Your GenAI project is part of the same mindset: understand a real problem, build responsibly, measure the outcome and keep improving.")
    st.caption("Leadership and history details are based on HCLTech’s official company and leadership pages.")
    quote_carousel()


# ============================================================
# MAIN APPLICATION
# ============================================================

def main():

    apply_aesthetic_theme()

    # --------------------------------------------------------
    # USER NOT LOGGED IN
    # --------------------------------------------------------

    if not st.session_state.authenticated:

        auth_screen()

        return


    # --------------------------------------------------------
    # START ACTIVITY
    # --------------------------------------------------------

    start_activity()


    # --------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------

    with st.sidebar:

        st.success(
            f"Logged in as "
            f"{st.session_state.user_name}"
        )

        st.caption(
            f"Role: "
            f"{st.session_state.user_role.title()}"
        )

        st.divider()

        view = st.radio(
            "Navigate",
            ["Dashboard", "About HCLTech"],
            label_visibility="collapsed",
        )

        if st.button(
            "Logout",
            use_container_width=True
        ):

            stop_activity()

            logout()

            st.rerun()


    if view == "About HCLTech":

        render_hcl_about()

        return

    st.markdown(
        '<div class="forge-banner"><div><strong>HCLTech GenAI Forge</strong><span>Internship dashboard · Learn, build and demonstrate impact.</span></div><div class="forge-badge">DEMO WORKSPACE</div></div>',
        unsafe_allow_html=True,
    )


    # --------------------------------------------------------
    # ROLE BASED ROUTING
    # --------------------------------------------------------

    role = st.session_state.user_role

    if role == "student":

        render_student_dashboard()

    elif role == "mentor":

        render_mentor_dashboard()

    elif role == "admin":

        render_admin_dashboard()

    else:

        st.error(
            "Unknown user role."
        )

        logout()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
