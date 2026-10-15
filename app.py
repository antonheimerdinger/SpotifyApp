import streamlit as st

from spotify_data import SpotifyData

TOP_N = 15  # how many genres / artists to show

st.set_page_config(page_title="Playlist Genres", page_icon="🎧", layout="wide")
st.title("🎧 Playlist Genres")

# Every visitor gets their own SpotifyData object (and so their own login).
# Never share it between sessions with st.cache_resource.
if "spotify" not in st.session_state:
    st.session_state.spotify = SpotifyData()
spotify = st.session_state.spotify

# ---------------------------------------------------------------- login
if not spotify.is_authorized():
    # After logging in, Spotify sends the user back here with ?code=... in the URL
    if "error" in st.query_params:
        st.error("Spotify login was cancelled or failed.")
    elif "code" in st.query_params:
        try:
            spotify.request_token(st.query_params["code"])
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")
        st.query_params.clear()

    st.info("Log in with Spotify to see your playlists.")
    st.link_button("Log in with Spotify", spotify.get_auth_url())
    st.stop()

with st.sidebar:
    if st.button("Log out"):
        st.session_state.clear()
        st.rerun()


# ---------------------------------------------------------------- data loading
# Results are cached per session (not with st.cache_data, which is shared by all users).
def load_playlists():
    if "playlists" not in st.session_state:
        with st.spinner("Loading your playlists..."):
            st.session_state.playlists = spotify.get_my_playlists()
    return st.session_state.playlists


def load_tracks(playlist_id):
    cache = st.session_state.setdefault("tracks", {})
    if playlist_id not in cache:
        with st.spinner("Loading tracks and genres..."):
            cache[playlist_id] = spotify.get_playlist_data(playlist_id)
    return cache[playlist_id]


# ---------------------------------------------------------------- playlist selection
playlists = {p["name"]: p for p in load_playlists()}

# Create the columns first so the cover sits left of the select box,
# then fill them in order: select box first (we need its value for the cover)
cover_col, select_col = st.columns([1, 5], vertical_alignment="center")

with select_col:
    playlist_name = st.selectbox("Select playlist", list(playlists))
if not playlist_name:
    st.stop()

playlist = playlists[playlist_name]

with cover_col:
    if playlist["image"]:
        st.image(playlist["image"], width=150)
    else:
        # Placeholder for playlists without a cover
        st.markdown(
            "<div style='width:150px;height:150px;display:flex;align-items:center;"
            "justify-content:center;font-size:56px;background:#80808033;"
            "border-radius:4px'>🎧</div>",
            unsafe_allow_html=True,
        )

try:
    tracks = load_tracks(playlist["id"])
except Exception as e:
    # e.g. Spotify only returns items for playlists you own or collaborate on
    st.warning(f"Could not load '{playlist_name}': {e}")
    st.stop()

# ---------------------------------------------------------------- counts
# value_counts() is already sorted, so head() gives the top entries
genre_counts = tracks.explode("genres")["genres"].dropna().value_counts().head(TOP_N)
artist_counts = tracks["artist_name"].value_counts().head(TOP_N)


def bar_chart(series, label):
    """Horizontal bar chart with the biggest bar on top."""
    df = series.rename_axis(label).reset_index(name="count")
    # sort="-count" stops Streamlit from re-sorting the bars alphabetically
    st.bar_chart(df, x=label, y="count", horizontal=True, sort="-count")


# ---------------------------------------------------------------- charts
left, right = st.columns(2)

with left:
    st.subheader(f"Top {TOP_N} genres")
    if genre_counts.empty:
        st.warning(
            "No genres found. Spotify's 2026 API changes may return empty "
            "genres for new developer apps."
        )
    else:
        bar_chart(genre_counts, "genre")

with right:
    st.subheader(f"Top {TOP_N} artists")
    bar_chart(artist_counts, "artist")

# ---------------------------------------------------------------- release years
st.subheader("Release years")
years = tracks["release_year"].dropna().astype(int)

if years.empty:
    st.warning("No release dates found.")
else:
    # Count tracks per year and include years with 0 tracks so gaps stay visible
    year_counts = years.value_counts().reindex(range(years.min(), years.max() + 1), fill_value=0)
    df = year_counts.rename_axis("year").reset_index(name="count")
    df["year"] = df["year"].astype(str)  # as text so the axis doesn't show "1,998"
    st.bar_chart(df, x="year", y="count", sort="year")
