# ai_top_repos.py

import streamlit as st
import requests
from typing import Optional

st.set_page_config(page_title="Top AI Repos", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0A3D91 !important; color: white !important; }
    [data-testid="stAppViewContainer"]{background-color:#0A3D91!important;}
    [data-testid="stApp"]{background-color:#0A3D91!important;}
    h1 { text-align:center!important; color:white!important; font-weight:800; }
    .subtitle { text-align:center; font-size:1.2rem; margin-top:-10px; margin-bottom:35px; color:#e6e6e6; }
    .repo-tile { border:1px solid #ccc; border-radius:12px; padding:18px; margin-bottom:25px; background-color:white; color:black!important; transition:all .2s; }
    .repo-tile:hover { box-shadow:0 4px 14px rgba(0,0,0,0.25); transform:translateY(-3px); }
    .repo-tile p, .repo-tile div, .repo-tile span { color: black !important; }
    .repo-tile a { color:#1a0dab !important; font-weight:600; text-decoration:none; font-size:1.1rem; }
    .repo-tile a:hover { text-decoration:underline; }
    .block-container { max-width: 1200px; margin-left:auto; margin-right:auto; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>Top Curated AI Repos</h1>", unsafe_allow_html=True)
st.markdown('<div class="subtitle">Popular GitHub projects related to Artificial Intelligence (AI/ML/NLP).</div>', unsafe_allow_html=True)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
secret_token: Optional[str] = st.secrets.get("GITHUB_TOKEN")

def gh_headers(token: Optional[str]):
    hdr = {"Accept": "application/vnd.github.v3+json"}
    if token:
        hdr["Authorization"] = f"token {token}"
    return hdr

@st.cache_data(ttl=300)
def fetch_ai_repos(per_page: int = 30, token: Optional[str] = None):
    # Search for "artificial intelligence" OR "AI" in name/description/readme
    # Use a combined query; we URL-encode via requests params automatically.
    q = '"artificial intelligence" in:name,description,readme OR AI in:name,description,readme'
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": per_page, "page": 1}
    resp = requests.get(GITHUB_SEARCH_URL, params=params, headers=gh_headers(token), timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])

with st.sidebar:
    per_page = st.selectbox("Number of repos", [10, 20, 30, 50], index=2)
    st.caption("Showing repo link, stars, and forks only.")
    if secret_token:
        st.success("Using GITHUB_TOKEN from Streamlit secrets")
    else:
        st.info("No GITHUB_TOKEN found (unauthenticated requests).")
    try:
        rate_resp = requests.get("https://api.github.com/rate_limit", headers=gh_headers(secret_token), timeout=7)
        if rate_resp.ok:
            rate = rate_resp.json().get("rate", {})
            st.write(f"API rate limit: {rate.get('remaining')}/{rate.get('limit')} remaining")
    except Exception:
        pass

items = fetch_ai_repos(per_page=per_page, token=secret_token)

cols_per_row = 2
rows = (len(items) + cols_per_row - 1) // cols_per_row
for r in range(rows):
    cols = st.columns(cols_per_row)
    for c in range(cols_per_row):
        idx = r * cols_per_row + c
        if idx >= len(items):
            break
        repo = items[idx]
        name = repo.get("full_name", "")
        html_url = repo.get("html_url", "#")
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        with cols[c]:
            tile_html = f"""
            <div class="repo-tile">
                <h3><a href="{html_url}" target="_blank" rel="noopener">{name}</a></h3>
                <div style="display:flex; gap:40px; margin-top:15px;">
                    <div><strong>⭐ Stars</strong><br>{stars:,}</div>
                    <div><strong>🍴 Forks</strong><br>{forks:,}</div>
                </div>
            </div>
            """
            st.markdown(tile_html, unsafe_allow_html=True)
