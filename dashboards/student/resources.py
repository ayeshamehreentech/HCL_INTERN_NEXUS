import re
from urllib.parse import parse_qs, quote_plus, urlparse, urlunparse

import streamlit as st
import streamlit.components.v1 as components
from langchain_community.tools import DuckDuckGoSearchRun

from database.resources import (
    list_resources,
    list_saved_resources,
    list_topic_history,
    mark_resource_viewed,
    save_topic_history,
    save_user_resource,
)

YOUTUBE_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)"
)
BLOG_PATTERN = re.compile(
    r"https?://[^\s<>]+(?:\.com|\.org|\.dev|\.io|\.ai|\.net)[^\s<>]*"
)


def normalize_query(topic):
    """Infer search language without asking the student to choose it."""
    lowered = topic.lower()
    language = "Hindi" if any(word in lowered for word in (" hindi", " hinglish", "हिंदी")) else "English"
    clean_topic = re.sub(r"\b(in|tutorial|explained)?\s*(hindi|hinglish|english)\b", " ", topic, flags=re.I)
    return " ".join(clean_topic.split()), language


def youtube_id(url):
    parsed = urlparse(url)
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/")
    return parse_qs(parsed.query).get("v", [""])[0]


def canonical_url(url):
    video_id = youtube_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def search_web(query):
    try:
        return DuckDuckGoSearchRun().run(query)
    except Exception:
        return ""


def extract_urls(text, pattern):
    urls = [match.rstrip(".,);\"'") for match in pattern.findall(text)]
    return list(dict.fromkeys(canonical_url(url) for url in urls))


def youtube_search(query, language):
    # DuckDuckGo is the API-free, server-side discovery path. It does not
    # require a YouTube key and never scrapes YouTube HTML in the browser.
    evidence = search_web(
        f"site:youtube.com/watch {query} {language} tutorial explained "
        "CampusX CodeWithHarry Piyush Garg"
    )
    return [
        {
            "key": youtube_id(url),
            "type": "video",
            "title": f"{query} learning video {index + 1}",
            "description": "Educational video found from the learning search.",
            "url": url,
            "thumbnail": f"https://i.ytimg.com/vi/{youtube_id(url)}/mqdefault.jpg",
            "source": "YouTube",
            "language": language,
        }
        for index, url in enumerate(extract_urls(evidence, YOUTUBE_PATTERN)[:8])
    ]


def article_search(query, language):
    evidence = search_web(
        f"{query} {language} educational article tutorial documentation "
        "attention architecture official"
    )
    urls = [
        url for url in extract_urls(evidence, BLOG_PATTERN)
        if "youtube.com" not in url and "youtu.be" not in url
    ][:5]
    return [
        {
            "key": url,
            "type": "article",
            "title": f"{query} article {index + 1}",
            "description": "Educational article or documentation result.",
            "url": url,
            "thumbnail": None,
            "source": urlparse(url).netloc,
            "language": language,
        }
        for index, url in enumerate(urls)
    ]


def find_resources(topic):
    normalized_topic, language = normalize_query(topic)
    return youtube_search(normalized_topic, language) + article_search(normalized_topic, language)


def _resource_card(resource, user_id, topic):
    with st.container(border=True):
        if resource.get("thumbnail"):
            st.image(resource["thumbnail"], use_container_width=True)
        st.markdown(f"### {resource['title']}")
        st.caption(f"{resource['source']} · {resource['language']}")
        st.write(resource["description"][:220])
        watch_col, save_col = st.columns(2)
        with watch_col:
            label = "▶ Watch video" if resource["type"] == "video" else "Read article"
            if st.button(label, key=f"open_resource_{resource['key']}", use_container_width=True):
                if resource["type"] == "video":
                    st.session_state["selected_resource_video"] = resource["url"]
                mark_resource_viewed(
                    user_id, resource["key"], resource["type"], resource["title"], resource["url"], topic
                )
        if resource["type"] == "article":
            st.link_button("↗ Open article", resource["url"], use_container_width=True)
        with save_col:
            if st.button("☆ Save", key=f"save_resource_{resource['key']}", use_container_width=True):
                save_user_resource(
                    user_id, resource["key"], resource["type"], resource["title"], resource["url"], topic
                )
                st.success("Saved")


def render_resources():
    st.subheader("🧭 Mentor Resources")
    st.caption("Find videos and articles selected to support your learning.")
    user_id = st.session_state.get("user_id")
    topic = st.text_input(
        "What do you want to learn?",
        placeholder="Transformers in Hindi",
        key="mentor_resources_query",
    )

    history = list_topic_history(user_id) if user_id else []
    if history:
        st.caption("Recently searched")
        recent = st.selectbox(
            "Continue a topic",
            [item["topic"] for item in history[:5]],
            key="mentor_resources_history",
        )
        if st.button("Resume topic", key="resume_resource_topic"):
            st.session_state["mentor_resources_query"] = recent
            st.rerun()

    if st.button("🔎 Find resources", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a topic first.")
        else:
            with st.spinner("Finding the best resources for you..."):
                results = find_resources(topic.strip())
            st.session_state["mentor_resource_results"] = results
            st.session_state["mentor_resource_topic"] = topic.strip()
            if user_id:
                save_topic_history(user_id, topic.strip())

    current_topic = st.session_state.get("mentor_resource_topic")
    curated = list_resources() if current_topic else []
    curated_results = [
        {
            "key": item["url"],
            "type": "video" if item["resource_type"].lower() == "youtube" else "article",
            "title": item["title"],
            "description": "Mentor suggested resource.",
            "url": item["url"],
            "thumbnail": f"https://i.ytimg.com/vi/{youtube_id(item['url'])}/mqdefault.jpg" if youtube_id(item["url"]) else None,
            "source": "Mentor suggestion",
            "language": "Mentor",
        }
        for item in curated
    ]
    results = curated_results + st.session_state.get("mentor_resource_results", [])
    unique_results = {item["key"]: item for item in results}.values()
    filter_choice = st.segmented_control(
        "Filter resources",
        ["All", "Videos", "Articles", "Saved"],
        default="All",
        key="mentor_resource_filter",
    )
    if filter_choice == "Saved":
        saved_keys = {item["resource_key"] for item in list_saved_resources(user_id)}
        results = [item for item in unique_results if item["key"] in saved_keys]
    elif filter_choice == "Videos":
        results = [item for item in unique_results if item["type"] == "video"]
    elif filter_choice == "Articles":
        results = [item for item in unique_results if item["type"] == "article"]
    else:
        results = list(unique_results)

    selected_video = st.session_state.get("selected_resource_video")
    if selected_video:
        st.subheader("Selected video")
        st.video(selected_video)
        if st.button("Close video", key="close_selected_resource"):
            st.session_state.pop("selected_resource_video", None)
            st.rerun()

    videos = [item for item in results if item["type"] == "video"]
    articles = [item for item in results if item["type"] == "article"]
    if videos:
        st.subheader("DuckDuckGo video suggestions")
        video_labels = [resource["title"] for resource in videos]
        selected_label = st.select_slider(
            "Slide through video suggestions",
            options=video_labels,
            key="mentor_resource_video_slider",
        )
        selected_resource = videos[video_labels.index(selected_label)]
        st.video(selected_resource["url"])
        st.caption("Playing inside the Resources tab: " + selected_label)

    if videos:
        st.subheader("Recommended videos")
        video_columns = st.columns(min(3, len(videos)))
        for index, resource in enumerate(videos):
            with video_columns[index % len(video_columns)]:
                _resource_card(resource, user_id, current_topic or topic)
    if articles:
        st.subheader("Recommended articles")
        for resource in articles:
            _resource_card(resource, user_id, current_topic or topic)
    if current_topic and not results:
        clean_query = quote_plus(current_topic + " tutorial -shorts")
        st.subheader("YouTube learning results")
        st.caption("Clean learning-only search: no Shorts feed or unrelated recommendations.")
        components.html(
            f'<iframe width="100%" height="430" src="https://www.youtube-nocookie.com/embed?listType=search&list={clean_query}&rel=0&modestbranding=1" title="YouTube learning search" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>',
            height=440,
        )
