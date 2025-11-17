# python_top_repos.py

import streamlit as st
import requests
from typing import Optional

# ------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------
st.set_page_config(page_title="Top Python Repos", layout="wide")

# ------------------------------------------------------
# CUSTOM CSS FOR BLUE BACKGROUND + TILES
# ------------------------------------------------------
st.markdown("""
<style>

    /* Force entire background blue */
    .main {
        background-color: #0A3D91 !important;
        color: white !important;
    }

    [data-testid="stAppViewContainer"] {
        background-color: #0A3D91 !important;
    }
    [data-testid="stApp"] {
        background-color: #0A3D91 !important;
    }

    /* Title centered */
    h1 {
        text-align: center !important;
        color: white !important;
        font-weight: 800;
    }

    /* Subtitle */
    .subtitle {
        text-align: center;
        font-size: 1.2rem;
        margin-top: -10px;
        margin-bottom: 35px;
        color: #e6e6e6;
    }

    /* Repo tile/card styling */
    .repo-tile {
        border: 1px solid #ccc;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 25px;
        background-color: white;
        color: black !important;
        transition: all 0.2s ease-in-out;
    }

    /* Hover animation */
    .repo-tile:hover {
        box-shadow: 0px 4px 14px rgba(0,0,0,0.25);
        transform: translateY(-3px);
    }

    /* Tile internal text */
    .repo-tile p, .repo-tile div, .repo-tile span {
        color: black !important;
    }

    /* Links */
    .repo-tile a {
        color: #1a0dab !important;
        font-weight: 600;
        text-decoration: none;
        font-size: 1.1rem;
    }
    .repo-tile a:hover {
        text-decoration: underline;
    }

</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------
# HEADER
# ------------------------------------------------------
st.markdown("<h1>Top Curated Python Repos for Developers</h1>", unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Handpicked list of trending Python projects on GitHub.</div>',
    unsafe_allow_html=True
)

# ------------------------------------------------------
# GITHUB API
# ------------------------------------------------------
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

def gh_headers(token: Optional[str]):
    hdr = {"Accept": "application/vnd.github.v3+json"}
    if token:
        hdr["Authorization"] = f"token {token}"
    return hdr

@st.cache_data(ttl=300)
def fetch_top_python_repos(per_page: int = 20, token: Optional[str] = None):
    params = {
        "q": "language:Python",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": 1
    }
    resp = requests.get(GITHUB_SEARCH_URL, params=params, headers=gh_headers(token), timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])

# ------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------
with st.sidebar:
    token = st.text_input("GitHub token (optional)", type="password")
    per_page = st.selectbox("Number of repos", [10, 20, 30, 50], index=1)
    st.caption("This dashboard shows repo link, stars, and forks only.")

# ------------------------------------------------------
# FETCH DATA
# ------------------------------------------------------
items = fetch_top_python_repos(per_page=per_page, token=token)

# ------------------------------------------------------
# DISPLAY IN GRID
# ------------------------------------------------------
cols_per_row = 2
rows = (len(items) + cols_per_row - 1) // cols_per_row

for r in range(rows):
    cols = st.columns(cols_per_row)

    for c in range(cols_per_row):
        idx = r * cols_per_row + c
        if idx >= len(items):
            break

        repo = items[idx]
        name = repo["full_name"]
        html_url = repo["html_url"]
        stars = repo["stargazers_count"]
        forks = repo["forks_count"]

        with cols[c]:
            tile_html = f"""
            <div class="repo-tile">
                <h3><a href="{html_url}" target="_blank">{name}</a></h3>
                <div style="display:flex; gap:40px; margin-top:15px;">
                    <div><strong>⭐ Stars</strong><br>{stars:,}</div>
                    <div><strong>🍴 Forks</strong><br>{forks:,}</div>
                </div>
            </div>
            """
            st.markdown(tile_html, unsafe_allow_html=True)
