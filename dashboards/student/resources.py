import re
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import Request, urlopen

import streamlit as st
from googleapiclient.discovery import build
from langchain_community.tools import DuckDuckGoSearchRun
from database.resources import get_user_resource, list_resources, list_topic_history, save_topic_history, save_user_resource, save_video_progress

YOUTUBE_PATTERN = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)")


def youtube_id(url):
    parsed = urlparse(url)
    return parsed.path.strip("/") if parsed.netloc.endswith("youtu.be") else parse_qs(parsed.query).get("v", [""])[0]


def normalize_query(topic):
    language = "Hindi" if any(word in topic.lower() for word in ("hindi", "hinglish", "हिंदी")) else "English"
    return re.sub(r"\b(hindi|hinglish|english)\b", "", topic, flags=re.I).strip(), language


def _video(video_id, title, channel, language, thumbnail=None):
    return {"key": video_id, "url": "https://www.youtube.com/watch?v=" + video_id, "title": title, "channel": channel, "language": language, "duration": "Duration shown in player", "thumbnail": thumbnail or "https://i.ytimg.com/vi/{}/hqdefault.jpg".format(video_id)}


def _discover(topic):
    query, language = normalize_query(topic)
    videos, seen = [], set()
    api_key = st.secrets.get("YOUTUBE_API_KEY", "")
    if api_key:
        try:
            response = build("youtube", "v3", developerKey=api_key, cache_discovery=False).search().list(part="snippet", q="{} {} tutorial -shorts".format(query, language), type="video", videoEmbeddable="true", maxResults=12).execute()
            for item in response.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if not video_id or "shorts" in snippet.get("title", "").lower() or video_id in seen:
                    continue
                seen.add(video_id)
                image = (snippet.get("thumbnails", {}).get("medium") or {}).get("url")
                videos.append(_video(video_id, snippet.get("title", "YouTube lesson"), snippet.get("channelTitle", "YouTube"), language, image))
        except Exception:
            pass
    if not videos:
        try:
            evidence = DuckDuckGoSearchRun().run("site:youtube.com/watch {} {} tutorial -shorts".format(query, language))
        except Exception:
            evidence = ""
        for url in YOUTUBE_PATTERN.findall(evidence):
            video_id = youtube_id(url)
            if video_id and video_id not in seen:
                seen.add(video_id)
                videos.append(_video(video_id, "{} learning lesson {}".format(query.title(), len(videos)+1), "YouTube educational result", language))
    if not videos:
        try:
            page = urlopen(Request("https://www.youtube.com/results?search_query=" + quote_plus(query + " " + language + " tutorial -shorts"), headers={"User-Agent": "Mozilla/5.0"}), timeout=8).read().decode("utf-8", errors="ignore")
            for video_id in re.findall(r'"videoId":"([\w-]{11})"', page):
                if video_id not in seen:
                    seen.add(video_id)
                    videos.append(_video(video_id, "{} learning lesson {}".format(query.title(), len(videos)+1), "YouTube search result", language))
                if len(videos) >= 12: break
        except Exception:
            pass
    return videos[:12]


def playlist_id(value):
    value = (value or "").strip()
    return parse_qs(urlparse(value).query).get("list", [value])[0]


def get_playlist_videos(value):
    api_key = st.secrets.get("YOUTUBE_API_KEY", "")
    playlist = playlist_id(value)
    if not api_key: raise RuntimeError("Add YOUTUBE_API_KEY in Streamlit Secrets to load playlists.")
    if not playlist: raise ValueError("Enter a YouTube playlist URL or ID.")
    results, token = [], None
    youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
    while True:
        response = youtube.playlistItems().list(part="snippet", playlistId=playlist, maxResults=50, pageToken=token).execute()
        for item in response.get("items", []):
            snippet = item.get("snippet", {}); video_id = snippet.get("resourceId", {}).get("videoId")
            if video_id and snippet.get("title") != "Private video":
                image = (snippet.get("thumbnails", {}).get("medium") or {}).get("url")
                results.append(_video(video_id, snippet.get("title", "YouTube lesson"), snippet.get("videoOwnerChannelTitle") or "YouTube", "Playlist lesson", image))
        token = response.get("nextPageToken")
        if not token: return results


def _progress(user_id, video_key):
    return get_user_resource(user_id, video_key) or {"progress_seconds": 0, "completed": 0}


def _save_progress(user_id, selected, topic, completed=False):
    prior = _progress(user_id, selected["key"])
    save_video_progress(user_id, selected["key"], selected["title"], selected["url"], topic, int(prior.get("progress_seconds", 0)), completed)


def _card(video, key):
    with st.container(border=True):
        st.image(video["thumbnail"], use_container_width=True)
        st.markdown("**{}**".format(video["title"]))
        st.caption("{} · {}".format(video["channel"], video["language"]))
        if st.button("Play in app", key=key, use_container_width=True):
            st.session_state["selected_resource_video"] = video
            st.rerun()


def render_resources():
    st.markdown("""<style>.resource-hero{background:linear-gradient(120deg,#4a2517,#8a4d2d);color:white;padding:1.25rem 1.5rem;border-radius:16px;margin-bottom:1rem}.resource-hero h2{color:white;margin:0}.resource-steps{padding:.6rem;border:1px solid #d7b69d;border-radius:10px;background:#fffaf5;color:#5c301e;text-align:center;font-size:.85rem}</style><div class='resource-hero'><h2>🎯 AI Learning Resources</h2><p>Search → Discover → Filter → Learn → Track progress — without leaving the portal.</p></div>""", unsafe_allow_html=True)
    st.caption("Regular learning videos only. Shorts and external navigation are excluded.")
    for column, label in zip(st.columns(4), ("1. Search", "2. Deep Resource Agent", "3. Filter tutorials", "4. Play in this tab")):
        with column: st.markdown("<div class='resource-steps'>{}</div>".format(label), unsafe_allow_html=True)
    with st.expander("Load a YouTube playlist"):
        ref = st.text_input("Playlist URL or ID", key="youtube_playlist_ref")
        if st.button("Load playlist in this tab"):
            try: st.session_state["playlist_videos"] = get_playlist_videos(ref)
            except Exception as error: st.error(str(error))
        for video in st.session_state.get("playlist_videos", [])[:12]:
            if st.button("▶ " + video["title"], key="playlist_" + video["key"]):
                st.session_state["selected_resource_video"] = video; st.rerun()
    user_id = st.session_state.get("user_id")
    topic = st.text_input("Search a topic", placeholder="Transformers in Hindi", key="mentor_resources_query")
    if st.button("🔎 Find resources", use_container_width=True) and topic.strip():
        st.session_state["active_resource_topic"] = topic.strip(); st.session_state["resource_videos"] = _discover(topic.strip())
        if user_id: save_topic_history(user_id, topic.strip())
    active_topic = st.session_state.get("active_resource_topic")
    if not active_topic: return
    videos = st.session_state.get("resource_videos") or _discover(active_topic)
    if not videos:
        st.warning("No safe, playable video links were found. Try a more specific topic."); return
    st.markdown("### ▶ YouTube learning carousel")
    for column, video in zip(st.columns(min(4, len(videos))), videos[:4]):
        with column: _card(video, "video_" + video["key"])
    selected = st.session_state.get("selected_resource_video", videos[0])
    st.divider(); st.subheader(selected["title"]); st.video(selected["url"])
    st.caption("{} · {} · {}".format(selected["channel"], selected["language"], selected["duration"]))
    state = _progress(user_id, selected["key"]) if user_id else {"completed": 0, "progress_seconds": 0}
    seconds = int(state.get("progress_seconds", 0)); st.progress(1.0 if state.get("completed") else 0.0, text="Completed" if state.get("completed") else "Resume from {}:{:02d}".format(seconds//60, seconds%60))
    save, complete = st.columns(2)
    with save:
        if st.button("Save for later", use_container_width=True) and user_id:
            save_user_resource(user_id, selected["key"], "video", selected["title"], selected["url"], active_topic); st.success("Saved for later")
    with complete:
        if st.button("Mark as completed", use_container_width=True) and user_id:
            _save_progress(user_id, selected, active_topic, True); st.success("Marked completed")
