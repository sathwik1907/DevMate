from __future__ import annotations

import streamlit as st

from llm import (
    ask_llm,
    explain_bug,
    generate_commit_message,
    generate_readme,
    get_openrouter_model,
    openrouter_is_configured,
    review_code,
)
from memory import MemoryError, cognee_is_configured, get_memory, recall, remember


st.set_page_config(
    page_title="DevMate",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }
    .devmate-title {
        font-size: 2.4rem;
        font-weight: 760;
        line-height: 1.1;
        margin-bottom: 0.2rem;
    }
    .devmate-caption {
        color: #65758b;
        margin-bottom: 1rem;
    }
    div[data-testid="stMetric"] {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
        background: #ffffff;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding-left: 0.75rem;
        padding-right: 0.75rem;
    }
    textarea, input {
        border-radius: 8px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialise_state() -> None:
    defaults = {
        "messages": [],
        "last_memory_result": "",
        "last_code_review": "",
        "last_bug_fix": "",
        "last_readme": "",
        "last_commit_message": "",
        "last_note_search": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_error(message: str) -> None:
    st.error(message, icon="⚠️")


def safe_memory_context(query: str) -> str:
    return get_memory(query) if query.strip() else "No relevant Cognee memory found."


def save_memory_block(label: str, category: str, placeholder: str, key: str) -> None:
    with st.form(f"{key}_form", clear_on_submit=True):
        text = st.text_area(label, placeholder=placeholder, height=130, key=f"{key}_text")
        submitted = st.form_submit_button("Save to Cognee", use_container_width=True)

    if submitted:
        if not text.strip():
            st.warning("Enter something before saving.", icon="✍️")
            return
        with st.spinner("Saving memory with Cognee..."):
            try:
                message = remember(text, category=category)
                st.success(message, icon="✅")
            except MemoryError as exc:
                show_error(str(exc))


def render_recall_results(results) -> None:
    if not results:
        st.info("No matching Cognee memories found yet.", icon="ℹ️")
        return

    for index, result in enumerate(results, start=1):
        label = f"Memory {index}"
        if result.score is not None:
            label = f"{label} · score {result.score:.2f}"
        with st.expander(label, expanded=index == 1):
            st.markdown(result.text)
            st.caption(f"Source: {result.source}")


initialise_state()

with st.sidebar:
    st.title("🚀 DevMate")
    st.caption("AI Developer Companion")
    st.divider()

    openrouter_ready = openrouter_is_configured()
    cognee_ready = cognee_is_configured()

    st.subheader("Status")
    st.success(f"OpenRouter ready · {get_openrouter_model()}", icon="✅") if openrouter_ready else st.error(
        "OpenRouter API key missing", icon="⚠️"
    )
    st.success("Cognee memory ready", icon="✅") if cognee_ready else st.error(
        "Cognee unavailable", icon="⚠️"
    )

    st.divider()
    st.subheader("Workspace")
    st.write("💬 AI Chat")
    st.write("🧠 Persistent Memory")
    st.write("📚 Learning Notes")
    st.write("🐛 Bug Fix Assistant")
    st.write("📝 README + Commits")
    st.write("📂 Project Memory")

    st.divider()
    if st.button("Clear Session Chat", use_container_width=True):
        st.session_state.messages = []
        st.success("Chat history cleared.", icon="✅")

    st.info("OpenRouter reasons over each request. Cognee supplies long-term context.")

st.markdown('<div class="devmate-title">🚀 DevMate</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="devmate-caption">Your AI Developer Companion powered by OpenRouter + Cognee</div>',
    unsafe_allow_html=True,
)

metric_cols = st.columns(3)
metric_cols[0].metric("Session Messages", len(st.session_state.messages))
metric_cols[1].metric("OpenRouter", "Ready" if openrouter_is_configured() else "Needs key")
metric_cols[2].metric("Cognee", "Ready")

tabs = st.tabs(
    [
        "💬 Chat",
        "🧠 Memory",
        "🧪 Code Review",
        "🐛 Bug Fix",
        "📝 README",
        "🌿 Commit",
        "📚 Notes & Project",
    ]
)

with tabs[0]:
    st.subheader("AI Chat")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Ask DevMate about your code, tools, plans, or memories...")

    if user_input is not None:
        if not user_input.strip():
            st.warning("Ask a question before sending.", icon="✍️")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant"):
                with st.spinner("Searching Cognee and asking OpenRouter..."):
                    memory_context = safe_memory_context(user_input)
                    response = ask_llm(prompt=user_input, memory=memory_context)
                    st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})

with tabs[1]:
    st.subheader("Persistent Memory")
    left, right = st.columns([1, 1])

    with left:
        save_memory_block(
            label="Save a developer memory",
            category="developer-profile",
            placeholder="What do you want to save?",
            key="profile_memory",
        )

    with right:
        st.markdown("#### Recall from Cognee")
        with st.form("memory_recall_form"):
            memory_query = st.text_input(
                "Ask a memory question",
                placeholder="What editor do I use?",
            )
            submitted = st.form_submit_button("Search Cognee", use_container_width=True)

        if submitted:
            if not memory_query.strip():
                st.warning("Enter a question to search memory.", icon="✍️")
            else:
                with st.spinner("Searching Cognee..."):
                    try:
                        results = recall(memory_query)
                        st.session_state.last_memory_result = results
                        st.success("Memory search complete.", icon="✅")
                        render_recall_results(results)
                    except MemoryError as exc:
                        show_error(str(exc))
        elif st.session_state.last_memory_result:
            render_recall_results(st.session_state.last_memory_result)

with tabs[2]:
    st.subheader("Code Review")
    with st.form("code_review_form"):
        language = st.text_input("Language", value="python")
        code = st.text_area(
            "Paste code",
            height=280,
            placeholder="def hello(name):\n    print('Hello ' + name)",
        )
        submitted = st.form_submit_button("Review Code", use_container_width=True)

    if submitted:
        if not code.strip():
            st.warning("Paste code before requesting a review.", icon="✍️")
        else:
            with st.spinner("OpenRouter is reviewing the code..."):
                memory_context = safe_memory_context(f"code review preferences {language}")
                st.session_state.last_code_review = review_code(code, language, memory_context)
                st.success("Review ready.", icon="✅")

    if st.session_state.last_code_review:
        st.markdown(st.session_state.last_code_review)

with tabs[3]:
    st.subheader("Bug Fix Assistant")
    with st.form("bug_fix_form"):
        traceback_text = st.text_area(
            "Paste traceback or bug report",
            height=260,
            placeholder="Traceback (most recent call last): ...",
        )
        submitted = st.form_submit_button("Explain Fix", use_container_width=True)

    if submitted:
        if not traceback_text.strip():
            st.warning("Paste an error before asking for a fix.", icon="✍️")
        else:
            with st.spinner("OpenRouter is tracing the failure..."):
                memory_context = safe_memory_context(traceback_text[:500])
                st.session_state.last_bug_fix = explain_bug(traceback_text, memory_context)
                st.success("Fix explanation ready.", icon="✅")

    if st.session_state.last_bug_fix:
        st.markdown(st.session_state.last_bug_fix)

with tabs[4]:
    st.subheader("README Generator")
    with st.form("readme_form"):
        description = st.text_area(
            "Describe your project",
            height=250,
            placeholder="DevMate is an AI Developer Companion built with Streamlit, OpenRouter, and Cognee...",
        )
        submitted = st.form_submit_button("Generate README", use_container_width=True)

    if submitted:
        if not description.strip():
            st.warning("Describe the project before generating a README.", icon="✍️")
        else:
            with st.spinner("Generating README.md..."):
                memory_context = safe_memory_context("project goals features future work")
                st.session_state.last_readme = generate_readme(description, memory_context)
                st.success("README generated.", icon="✅")

    if st.session_state.last_readme:
        st.download_button(
            "Download README.md",
            st.session_state.last_readme,
            file_name="README.md",
            mime="text/markdown",
            use_container_width=True,
        )
        st.markdown(st.session_state.last_readme)

with tabs[5]:
    st.subheader("Commit Message Generator")
    with st.form("commit_form"):
        changes = st.text_area(
            "Paste a diff or describe your changes",
            height=240,
            placeholder="Added Cognee memory recall and improved Streamlit error handling.",
        )
        submitted = st.form_submit_button("Generate Commit Message", use_container_width=True)

    if submitted:
        if not changes.strip():
            st.warning("Enter a change description before generating commits.", icon="✍️")
        else:
            with st.spinner("Writing commit messages..."):
                st.session_state.last_commit_message = generate_commit_message(changes)
                st.success("Commit suggestions ready.", icon="✅")

    if st.session_state.last_commit_message:
        st.markdown(st.session_state.last_commit_message)

with tabs[6]:
    st.subheader("Learning Notes & Project Memory")
    note_col, project_col = st.columns(2)

    with note_col:
        save_memory_block(
            label="Save a learning note",
            category="learning-note",
            placeholder="In Python, list comprehensions create lists from iterables in a compact syntax.",
            key="learning_note",
        )

    with project_col:
        save_memory_block(
            label="Save project progress or tasks",
            category="project-memory",
            placeholder="Today I finished memory recall. Next I need to polish the README.",
            key="project_memory",
        )

    st.divider()
    with st.form("notes_search_form"):
        notes_query = st.text_input(
            "Search saved notes and project memory",
            placeholder="What is left to do?",
        )
        submitted = st.form_submit_button("Search Notes", use_container_width=True)

    if submitted:
        if not notes_query.strip():
            st.warning("Enter a search query.", icon="✍️")
        else:
            with st.spinner("Searching Cognee notes..."):
                try:
                    st.session_state.last_note_search = recall(notes_query)
                    st.success("Search complete.", icon="✅")
                    render_recall_results(st.session_state.last_note_search)
                except MemoryError as exc:
                    show_error(str(exc))
    elif st.session_state.last_note_search:
        render_recall_results(st.session_state.last_note_search)
