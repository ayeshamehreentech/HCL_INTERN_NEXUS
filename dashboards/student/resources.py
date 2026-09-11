"""Focused, in-portal YouTube learning resources backed by Supabase."""
from urllib.parse import parse_qs, urlparse

import streamlit as st
from googleapiclient.discovery import build

from database.resources import (get_user_resource, list_resources, list_topic_history,
                                save_topic_history, save_user_resource, save_video_progress)


def youtube_id(url):
    parsed = urlparse(url or "")
    return parsed.path.strip("/") if parsed.netloc.endswith("youtu.be") else parse_qs(parsed.query).get("v", [""])[0]


def playlist_id(value):
    value = (value or "").strip()
    return parse_qs(urlparse(value).query).get("list", [value])[0]


def _language(topic):
    return "Hindi" if any(word in topic.lower() for word in ("hindi", "hinglish", "हिंदी")) else "English"


def _video(video_id, title, channel="YouTube", language="English", thumbnail=None):
    return {"key": video_id, "url": "https://www.youtube.com/watch?v=" + video_id,
            "title": title or "Learning video", "channel": channel or "YouTube",
            "language": language, "duration": "Play in portal",
            "thumbnail": thumbnail or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id)}


def _youtube_client():
    key = st.secrets.get("YOUTUBE_API_KEY", "")
    return build("youtube", "v3", developerKey=key, cache_discovery=False) if key else None


def _search_videos(topic):
    """Return regular, embeddable tutorials. Shorts are deliberately excluded."""
    youtube = _youtube_client()
    if not youtube:
        return []
    language = _language(topic)
    try:
        response = youtube.search().list(part="snippet", q="{} {} tutorial".format(topic, language),
            type="video", videoEmbeddable="true", maxResults=16).execute()
    except Exception:
        return []
    videos, seen = [], set()
    for item in response.get("items", []):
        snippet, video_id = item.get("snippet", {}), item.get("id", {}).get("videoId", "")
        title = snippet.get("title", "")
        if not video_id or video_id in seen or "short" in title.lower():
            continue
        seen.add(video_id)
        image = (snippet.get("thumbnails", {}).get("high") or snippet.get("thumbnails", {}).get("medium") or {}).get("url")
        videos.append(_video(video_id, title, snippet.get("channelTitle", "YouTube"), language, image))
    return videos


def get_playlist_videos(value):
    youtube, playlist = _youtube_client(), playlist_id(value)
    if not youtube:
        raise RuntimeError("Add YOUTUBE_API_KEY to Streamlit secrets before loading a playlist.")
    if not playlist:
        raise ValueError("Enter a YouTube playlist URL or playlist ID.")
    videos, token = [], None
    while True:
        response = youtube.playlistItems().list(part="snippet", playlistId=playlist, maxResults=50, pageToken=token).execute()
        for item in response.get("items", []):
            snippet, video_id = item.get("snippet", {}), item.get("snippet", {}).get("resourceId", {}).get("videoId", "")
            title = snippet.get("title", "")
            if not video_id or title == "Private video" or "short" in title.lower():
                continue
            image = (snippet.get("thumbnails", {}).get("medium") or snippet.get("thumbnails", {}).get("high") or {}).get("url")
            videos.append(_video(video_id, title, snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle", "YouTube"), "Playlist lesson", image))
        token = response.get("nextPageToken")
        if not token:
            return videos


def _play_button(video, key):
    if st.button("▶ Play here", key=key, use_container_width=True):
        st.session_state["selected_resource_video"] = video
        st.rerun()


def _card(video, key):
    with st.container(border=True):
        st.image(video["thumbnail"], use_container_width=True)
        st.markdown("**{}**".format(video["title"]))
        st.caption("{} · {}".format(video["channel"], video["language"]))
        _play_button(video, key)


def _show_mentor_resources():
    try:
        resources = list_resources() or []
    except Exception:
        resources = []
    if not resources:
        return
    st.markdown("### ⭐ Mentor Suggested")
    st.caption("Resources shared by your mentor appear here automatically.")
    for item in resources[:6]:
        title, url = item.get("title") or "Mentor resource", item.get("url") or ""
        video = youtube_id(url)
        with st.container(border=True):
            st.markdown("**{}** · {}".format(title, (item.get("resource_type") or "resource").title()))
            st.caption(item.get("topic") or "Mentor recommendation")
            if video:
                _play_button(_video(video, title, "Mentor suggested", "Mentor"), "mentor_{}".format(item.get("id", video)))
            elif url:
                st.link_button("Open resource", url)


def render_resources():
    st.markdown("""<style>.resource-hero{background:#5b3526;color:#f5ead7;padding:1.35rem 1.6rem;border-radius:18px;margin-bottom:1rem}.resource-hero h2{color:#f5ead7;margin:0}.resource-step{padding:.55rem;border:1px solid #a97855;border-radius:9px;text-align:center;color:#5b3526;background:#fff8ec}</style><div class='resource-hero'><h2>🎯 AI Learning Resources</h2><p>Search → select → learn inside the portal. Regular tutorials only; no Shorts.</p></div>""", unsafe_allow_html=True)
    for column, text in zip(st.columns(4), ("1. Search", "2. Discover", "3. Choose", "4. Play here")):
        with column:
            st.markdown("<div class='resource-step'>{}</div>".format(text), unsafe_allow_html=True)
    user_id = st.session_state.get("user_id")
    _show_mentor_resources()
    with st.expander("Load a YouTube playlist"):
        playlist_ref = st.text_input("Playlist URL or ID", key="youtube_playlist_ref")
        if st.button("Load playlist in this tab", key="load_youtube_playlist"):
            try:
                st.session_state["resource_videos"] = get_playlist_videos(playlist_ref)
                st.session_state["active_resource_topic"] = "Playlist"
                st.session_state.pop("selected_resource_video", None)
                st.success("Playlist loaded. Choose a lesson below.")
            except Exception as error:
                st.error(str(error))
    topic = st.text_input("Search a learning topic", placeholder="Example: Python loops or Transformers in Hindi", key="resource_topic")
    history = list_topic_history(user_id) if user_id else []
    if history:
        recent = st.selectbox("Continue a topic", [row["topic"] for row in history[:5]])
        if st.button("Resume topic"):
            st.session_state["resource_topic"] = recent
            st.session_state["active_resource_topic"] = recent
            st.session_state["resource_videos"] = _search_videos(recent)
            st.rerun()
    if st.button("🔎 Find learning videos", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a topic to search.")
        else:
            st.session_state["active_resource_topic"] = topic.strip()
            st.session_state["resource_videos"] = _search_videos(topic.strip())
            st.session_state.pop("selected_resource_video", None)
            if user_id:
                save_topic_history(user_id, topic.strip())
            st.rerun()
    active_topic, videos = st.session_state.get("active_resource_topic"), st.session_state.get("resource_videos", [])
    if not active_topic:
        return
    if not videos:
        st.info("No playable educational videos were found. Check the YouTube key or try a more specific topic.")
        return
    st.markdown("### Learning videos for {}".format(active_topic))
    start = st.session_state.get("resource_carousel_start", 0)
    back, cards, forward = st.columns([1, 12, 1])
    with back:
        if st.button("◀", key="resource_back"):
            st.session_state["resource_carousel_start"] = max(0, start - 4); st.rerun()
    with cards:
        visible = videos[start:start + 4]
        for column, video in zip(st.columns(len(visible)), visible):
            with column:
                _card(video, "resource_{}".format(video["key"]))
    with forward:
        if st.button("▶", key="resource_forward"):
            st.session_state["resource_carousel_start"] = min(max(0, len(videos) - 4), start + 4); st.rerun()
    selected = st.session_state.get("selected_resource_video") or videos[0]
    st.divider(); st.subheader(selected["title"])
    st.components.v1.iframe("https://www.youtube-nocookie.com/embed/{}?rel=0".format(selected["key"]), height=440, scrolling=False)
    st.caption("{} · {} · Plays inside InternNexus".format(selected["channel"], selected["language"]))
    state = get_user_resource(user_id, selected["key"]) if user_id else None
    state = state or {"progress_seconds": 0, "completed": 0}; seconds = int(state.get("progress_seconds", 0))
    st.progress(1.0 if state.get("completed") else 0.0, text="Completed" if state.get("completed") else "Resume from {}:{:02d}".format(seconds // 60, seconds % 60))
    save, complete = st.columns(2)
    with save:
        if st.button("Save for later", use_container_width=True):
            if user_id: save_user_resource(user_id, selected["key"], "video", selected["title"], selected["url"], active_topic)
            st.success("Saved for later.")
    with complete:
        if st.button("Mark as completed", use_container_width=True):
            if user_id: save_video_progress(user_id, selected["key"], selected["title"], selected["url"], active_topic, seconds, True)
            st.success("Marked as completed.")
    st.markdown("### Suggested next lessons")
    for column, video in zip(st.columns(min(3, len(videos))), videos[1:4] or videos[:3]):
        with column:
            _card(video, "suggested_{}".format(video["key"]))
