"""Effort Tracker.

    uv run streamlit run app.py

This file is deliberately thin: page setup and navigation only. Loading,
validation, the points engine and the rewards ledger all live in src/effort/.
"""

import streamlit as st

st.set_page_config(
    page_title="Effort Tracker",
    page_icon="⭐",
    layout="centered",  # centred, not wide — it has to read well on a phone
    initial_sidebar_state="collapsed",
)

from effort.ui import rewards, this_week, trends  # noqa: E402  (after set_page_config)

# url_path is explicit because all three page functions are called render(),
# and Streamlit would otherwise infer the same pathname for each and refuse.
PAGES = [
    st.Page(this_week.render, title="This Week", icon="⭐", url_path="this-week", default=True),
    st.Page(trends.render, title="Trends", icon="📈", url_path="trends"),
    st.Page(rewards.render, title="Rewards", icon="🎁", url_path="rewards"),
]

st.navigation(PAGES).run()
