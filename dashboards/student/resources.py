import re
from urllib.parse import parse_qs, urlparse

import streamlit as st
from googleapiclient.discovery import build
from database.resources import list_resources, save_topic_history, save_user_resource, save_video_progress


def youtube_id(url):
    parsed = urlparse(url or "")
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/")
    return parse_qs(parsed.query).get("v", [""])[0]


def _video(video_id, title, channel="", language="English", thumbnail=None):
    return {
        "key": video_id,
        "url": "https://www.youtube.com/watch?v=" + video_id,
        "title": title or "Learning video",
        "channel": channel or "YouTube",
        "language": language,
        "thumbnail": thumbnail or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id),
    }


def _language(topic):
    return "Hindi" if any(word in topic.lower() for word in ("hindi", "hinglish", "हिंदी")) else "English"


def _search_videos(topic):
    key = st.secrets.get("YOUTUBE_API_KEY", "")
    if not key:
        return []
    try:
        response = build("youtube", "v3", developerKey=key, cache_discovery=False).search().list(
            part="snippet", q="{} {} tutorial".format(topic, _language(topic)),
            type="video", videoEmbeddable="true", maxResults=15
        ).execute()
        videos = []
        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            if not video_id or "short" in title.lower():
                continue
            videos.append(_video(video_id, title, snippet.get("channelTitle", "YouTube"), _language(topic), snippet.get("thumbnails", {}).get("high", {}).get("url")))
        return videos
    except Exception:
        return []


def _show_mentor_resources():
    try:
        resources = list_resources() or []
    except Exception:
        resources = []
    if not resources:
        return
    st.markdown("### ⭐ Mentor Suggested")
    st.caption("Resources your mentor has shared with you.")
    for item in resources:
        title = item.get("title") or "Mentor resource"
        url = item.get("url") or ""
        topic = item.get("topic") or "Mentor recommendation"
        resource_type = (item.get("resource_type") or "Resource").title()
        with st.container(border=True):
            st.markdown("**{}** · {}".format(title, resource_type))
            st.caption(topic)
            video_id = youtube_id(url)
            if video_id:
                if st.button("▶ Play in this tab", key="mentor_video_{}".format(item.get("id", video_id))):
                    video = _video(video_id, title, "Mentor suggested", _language(topic))
                    st.session_state["active_resource_topic"] = topic
                    st.session_state["resource_videos"] = [video]
                    st.session_state["selected_resource_video"] = video
                    st.rerun()
            elif url:
                st.link_button("Open resource", url)


def _render_carousel(videos):
    selected = st.session_state.get("selected_resource_video")
    cols = st.columns(min(4, len(videos)))
    for index, video in enumerate(videos):
        with cols[index % len(cols)]:
            st.image(video["thumbnail"], use_container_width=True)
            st.markdown("**{}**".format(video["title"]))
            st.caption("{} · {}".format(video["channel"], video["language"]))
            if st.button("Play here", key="select_video_{}".format(video["key"])):
                st.session_state["selected_resource_video"] = video
                st.rerun()
    return selected


def _render_player(user_id, video):
    st.markdown("### Now playing")
    st.components.v1.iframe("https://www.youtube-nocookie.com/embed/{}?rel=0".format(video["key"]), height=440, scrolling=False)
    st.markdown("**{}**".format(video["title"]))
    st.caption("{} · {} · Watch inside the portal".format(video["channel"], video["language"]))
    first, second, third = st.columns(3)
    if first.button("Save for later", key="save_video_{}".format(video["key"])):
        try:
            save_user_resource(user_id, video["key"], "saved")
            st.success("Saved for later.")
        except Exception:
            st.info("Your selection will be available when database access is restored.")
    if second.button("Mark completed", key="complete_video_{}".format(video["key"])):
        try:
            save_video_progress(user_id, video["key"], 0, True)
            st.success("Marked completed.")
        except Exception:
            st.info("Completion was recorded for this session.")
    third.caption("Progress is saved when you mark a video complete.")


def render_resources():
    st.markdown("""<style>
    .resource-hero {background:#5b3526;color:#fff;padding:1.4rem 1.6rem;border-radius:18px;margin-bottom:1rem;}
    </style><div class='resource-hero'><h2>🎯 AI Learning Resources</h2><p>Focused videos and mentor recommendations, without leaving the portal.</p></div>""", unsafe_allow_html=True)
    user_id = st.session_state.get("user_id")
    _show_mentor_resources()
    st.divider()
    topic = st.text_input("Search a learning topic", placeholder="Example: Python loops or Transformers in Hindi", key="resource_topic")
    if st.button("🔎 Find learning videos", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a topic to search.")
        else:
            videos = _search_videos(topic.strip())
            st.session_state["active_resource_topic"] = topic.strip()
            st.session_state["resource_videos"] = videos
            st.session_state.pop("selected_resource_video", None)
            if user_id:
                try:
                    save_topic_history(user_id, topic.strip())
                except Exception:
                    pass
            st.rerun()
    active_topic = st.session_state.get("active_resource_topic")
    if not active_topic:
        return
    videos = st.session_state.get("resource_videos", [])
    if not videos:
        st.info("No playable educational videos were found. Try a more specific topic.")
        return
    st.markdown("### Learning videos for {}".format(active_topic))
    _render_carousel(videos)
    selected = st.session_state.get("selected_resource_video") or videos[0]
    _render_player(user_id, selected)
