import re
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import Request, urlopen

import streamlit as st
from langchain_community.tools import DuckDuckGoSearchRun
from googleapiclient.discovery import build

from database.connection import get_connection
from database.resources import list_resources, list_topic_history, save_topic_history, save_user_resource

YOUTUBE_PATTERN = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)")


def youtube_id(url):
    parsed = urlparse(url)
    return parsed.path.strip("/") if parsed.netloc.endswith("youtu.be") else parse_qs(parsed.query).get("v", [""])[0]


def normalize_query(topic):
    language = "Hindi" if any(word in topic.lower() for word in ("hindi", "hinglish", "हिंदी")) else "English"
    clean = re.sub(r"\b(hindi|hinglish|english)\b", "", topic, flags=re.I)
    return " ".join(clean.split()), language


def _discover(topic):
    query, language = normalize_query(topic)
    try:
        evidence = DuckDuckGoSearchRun().run("site:youtube.com/watch {} {} tutorial -shorts".format(query, language))
    except Exception:
        evidence = ""
    videos, seen = [], set()
    for url in YOUTUBE_PATTERN.findall(evidence):
        video = youtube_id(url)
        if video and video not in seen:
            seen.add(video)
            videos.append({"key": video, "url": "https://www.youtube.com/watch?v=" + video, "title": "{} learning video {}".format(query.title(), len(videos) + 1), "channel": "YouTube educational result", "language": language, "duration": "Duration shown in player", "thumbnail": "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video)})
    if not videos:
        try:
            search_url = "https://www.youtube.com/results?search_query=" + quote_plus(query + " " + language + " tutorial -shorts")
            request = Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
            page = urlopen(request, timeout=8).read().decode("utf-8", errors="ignore")
            for video in re.findall(r'"videoId":"([\w-]{11})"', page):
                if video not in seen:
                    seen.add(video)
                    videos.append({"key": video, "url": "https://www.youtube.com/watch?v=" + video, "title": "{} learning video {}".format(query.title(), len(videos) + 1), "channel": "YouTube search result", "language": language, "duration": "Duration shown in player", "thumbnail": "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video)})
                if len(videos) == 12:
                    break
        except Exception:
            pass
    return videos[:12]


def _ensure_progress():
    conn = get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS video_progress (user_id INTEGER, video_key TEXT, position_seconds INTEGER DEFAULT 0, completed INTEGER DEFAULT 0, updated_at TEXT, PRIMARY KEY(user_id, video_key))")
    conn.commit()
    return conn


def _progress(user_id, video_key):
    conn = _ensure_progress()
    row = conn.execute("SELECT * FROM video_progress WHERE user_id = ? AND video_key = ?", (user_id, video_key)).fetchone()
    conn.close()
    return dict(row) if row else {"position_seconds": 0, "completed": 0}


def _save_progress(user_id, video_key, seconds, completed=False):
    conn = _ensure_progress()
    conn.execute("INSERT INTO video_progress (user_id, video_key, position_seconds, completed, updated_at) VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(user_id, video_key) DO UPDATE SET position_seconds = excluded.position_seconds, completed = excluded.completed, updated_at = excluded.updated_at", (user_id, video_key, seconds, int(completed)))
    conn.commit()
    conn.close()


def _video_card(video, index):
    with st.container(border=True):
        st.image(video["thumbnail"], use_container_width=True)
        st.markdown("**{}**".format(video["title"]))
        st.caption("{} · {} · {}".format(video["channel"], video["language"], video["duration"]))
        if st.button("Play in app", key="play_" + video["key"], use_container_width=True):
            st.session_state["selected_resource_video"] = video
            st.rerun()



def playlist_id(playlist_url_or_id):
    """Return the playlist ID from a YouTube playlist URL or a raw ID."""
    value = (playlist_url_or_id or "").strip()
    return parse_qs(urlparse(value).query).get("list", [value])[0]


def get_playlist_videos(playlist_url_or_id):
    """Fetch titles, IDs and thumbnails using the YouTube Data API."""
    api_key = st.secrets.get("YOUTUBE_API_KEY")
    playlist = playlist_id(playlist_url_or_id)
    if not api_key:
        raise RuntimeError("Add YOUTUBE_API_KEY to Streamlit secrets before loading a playlist.")
    if not playlist:
        raise ValueError("Enter a YouTube playlist URL or playlist ID.")
    youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
    videos, page_token = [], None
    while True:
        response = youtube.playlistItems().list(part="snippet", playlistId=playlist, maxResults=50, pageToken=page_token).execute()
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId")
            if not video_id or snippet.get("title") == "Private video":
                continue
            thumbnails = snippet.get("thumbnails", {})
            image = (thumbnails.get("medium") or thumbnails.get("high") or thumbnails.get("default") or {}).get("url")
            videos.append({
                "key": video_id, "url": "https://www.youtube.com/watch?v=" + video_id,
                "title": snippet.get("title", "YouTube lesson"),
                "channel": snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle", "YouTube"),
                "language": "Playlist lesson", "duration": "Open in player",
                "thumbnail": image or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id),
            })
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return videos


def render_playlist_loader():
    with st.expander("Load a YouTube playlist"):
        playlist_ref = st.text_input("Playlist URL or ID", key="youtube_playlist_ref")
        if st.button("Load playlist in this tab", key="load_youtube_playlist"):
            try:
                st.session_state["playlist_videos"] = get_playlist_videos(playlist_ref)
                st.success("Playlist loaded. Select a lesson to play it here.")
            except Exception as error:
                st.error(str(error))
        playlist_videos = st.session_state.get("playlist_videos", [])
        if playlist_videos:
            st.caption("{} playlist lessons available".format(len(playlist_videos)))
            for start in range(0, len(playlist_videos), 3):
                columns = st.columns(3)
                for column, video in zip(columns, playlist_videos[start:start + 3]):
                    with column:
                        st.image(video["thumbnail"])
                        st.caption(video["title"])
                        if st.button("Play in app", key="playlist_" + video["key"]):
                            st.session_state["selected_resource_video"] = video
                            st.rerun()


def render_resources():
    st.markdown("""<style>.resource-hero{background:linear-gradient(120deg,#123d78,#2e6bb2);color:white;padding:1.25rem 1.5rem;border-radius:16px;margin-bottom:1rem}.resource-hero h2{color:white;margin:0}.resource-steps{padding:.6rem;border:1px solid #cfe1fb;border-radius:10px;background:#f7fbff;color:#16467f;text-align:center;font-size:.85rem}</style><div class="resource-hero"><h2>🎯 AI Learning Resources</h2><p>Search → Discover → Filter → Learn → Track progress — without leaving the portal.</p></div>""", unsafe_allow_html=True)
    st.caption("Regular learning videos only. Shorts and external navigation are excluded.")
    steps=st.columns(4)
    for column, label in zip(steps, ("1. Search", "2. Deep Resource Agent", "3. Filter tutorials", "4. Play in this tab")):
        with column: st.markdown("<div class="resource-steps">{}</div>".format(label), unsafe_allow_html=True)
    render_playlist_loader()
    user_id = st.session_state.get("user_id")
    topic = st.text_input("Search a topic", placeholder="Transformers in Hindi", key="mentor_resources_query")
    history = list_topic_history(user_id) if user_id else []
    if history:
        recent = st.selectbox("Continue a topic", [item["topic"] for item in history[:5]])
        if st.button("Resume topic"):
            st.session_state["mentor_resources_query"] = recent
            st.session_state["active_resource_topic"] = recent
            st.rerun()
    if st.button("🔎 Find resources", use_container_width=True) and topic.strip():
        st.session_state["active_resource_topic"] = topic.strip()
        st.session_state["resource_videos"] = _discover(topic.strip())
        st.session_state["carousel_start"] = 0
        if user_id:
            save_topic_history(user_id, topic.strip())
    active_topic = st.session_state.get("active_resource_topic")
    if not active_topic:
        return
    videos = st.session_state.get("resource_videos") or _discover(active_topic)
    st.session_state["resource_videos"] = videos
    mentor_items = list_resources()
    mentor_videos = [item for item in mentor_items if item.get("resource_type", "").lower() in ("youtube", "video")]
    if mentor_videos:
        st.markdown("### ⭐ Mentor Suggested")
        for item in mentor_videos[:3]:
            if st.button("▶ " + item["title"], key="mentor_" + str(item["id"])):
                st.session_state["selected_resource_video"] = {"key": youtube_id(item["url"]), "url": item["url"], "title": item["title"], "channel": "Mentor suggested", "language": "Mentor", "duration": "", "thumbnail": ""}
                st.rerun()
    if not videos:
        st.warning("No safe, playable video links were found. Try a more specific topic.")
        return
    st.markdown("### ▶ YouTube learning carousel")
    start = st.session_state.get("carousel_start", 0)
    left, content, right = st.columns([1, 12, 1])
    with left:
        if st.button("◀", key="carousel_left"):
            st.session_state["carousel_start"] = max(0, start - 4)
            st.rerun()
    with content:
        visible = videos[start:start + 4]
        cols = st.columns(len(visible))
        for col, video in zip(cols, visible):
            with col:
                _video_card(video, start)
    with right:
        if st.button("▶", key="carousel_right"):
            st.session_state["carousel_start"] = min(max(0, len(videos) - 4), start + 4)
            st.rerun()
    selected = st.session_state.get("selected_resource_video")
    if not selected:
        selected = videos[0]
    st.divider()
    st.subheader(selected["title"])
    st.video(selected["url"])
    st.caption("{} · {} · {}".format(selected.get("channel", "YouTube"), selected.get("language", ""), selected.get("duration", "")))
    progress = _progress(user_id, selected["key"]) if user_id else {"position_seconds": 0, "completed": 0}
    minutes = int(progress.get("position_seconds", 0)) // 60
    st.progress(1.0 if progress.get("completed") else 0.0, text="Completed" if progress.get("completed") else "Resume from {}:{:02d}".format(minutes, int(progress.get("position_seconds", 0)) % 60))
    save_col, complete_col = st.columns(2)
    with save_col:
        if st.button("Save for later", use_container_width=True):
            if user_id:
                save_user_resource(user_id, selected["key"], "video", selected["title"], selected["url"], active_topic)
            st.success("Saved for later")
    with complete_col:
        if st.button("Mark as completed", use_container_width=True):
            if user_id:
                _save_progress(user_id, selected["key"], progress.get("position_seconds", 0), True)
            st.success("Marked completed")
    st.markdown("### ✨ Suggested next lessons")
    suggested = videos[1:4] or videos
    cols = st.columns(len(suggested))
    for col, video in zip(cols, suggested):
        with col:
            _video_card(video, 0)
