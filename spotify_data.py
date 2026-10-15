"""Small Spotify Web API wrapper: auth, playlists, tracks and artist genres.

Tokens only live in memory: create one SpotifyData object per user/session.
"""
import time
import urllib.parse

import pandas as pd
import requests

from settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

API_URL = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTH_URL = "https://accounts.spotify.com/authorize"
SCOPE = "playlist-read-private playlist-read-collaborative"


class SpotifyData:
    # Artist genres are public data, so this cache is shared by all users
    _genre_cache = {}  # artist_id -> list of genres

    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def is_authorized(self):
        return self.access_token is not None

    def get_auth_url(self):
        """URL the user opens to log in and grant access."""
        query = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
        }
        return f"{AUTH_URL}?{urllib.parse.urlencode(query)}"

    def request_token(self, code):
        """Exchange the authorization code (from the redirect URL) for tokens."""
        self._token_request({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        })

    def _token_request(self, payload):
        payload = {**payload, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
        resp = requests.post(TOKEN_URL, data=payload)
        resp.raise_for_status()
        info = resp.json()

        self.access_token = info["access_token"]
        # Spotify doesn't always send a new refresh token; keep the old one then
        self.refresh_token = info.get("refresh_token", self.refresh_token)
        self.expires_at = time.time() + info.get("expires_in", 3600)

    def _headers(self):
        # Refresh the access token shortly before it expires
        if time.time() > self.expires_at - 30:
            self._token_request({
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            })
        return {"Authorization": f"Bearer {self.access_token}"}

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _get(self, url, params=None):
        resp = requests.get(url, headers=self._headers(), params=params)
        if resp.status_code == 429:  # rate limited: wait once, then retry
            time.sleep(int(resp.headers.get("Retry-After", 1)))
            resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def _get_all(self, url, params=None):
        """Follow Spotify's `next` links and return every item of a paged endpoint."""
        items = []
        while url:
            page = self._get(url, params)
            items += page["items"]
            url, params = page.get("next"), None  # `next` already contains the params
        return items

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def get_my_playlists(self):
        """Return the user's playlists as a list of {"id", "name", "image"} dicts."""
        playlists = self._get_all(f"{API_URL}/me/playlists", {"limit": 50})
        return [
            {
                "id": p["id"],
                "name": p["name"],
                # First image is the cover (playlists without one have an empty list)
                "image": p["images"][0]["url"] if p.get("images") else None,
            }
            for p in playlists
        ]

    def get_artist_genres(self, artist_id):
        """Genres of one artist (cached, so each artist is only requested once)."""
        if artist_id not in self._genre_cache:
            artist = self._get(f"{API_URL}/artists/{artist_id}")
            self._genre_cache[artist_id] = artist.get("genres", [])
        return self._genre_cache[artist_id]

    def get_playlist_data(self, playlist_id):
        """Return a DataFrame with one row per track, including the artist's genres."""
        # Since Feb 2026 the endpoint is /items (it used to be /tracks)
        entries = self._get_all(f"{API_URL}/playlists/{playlist_id}/items", {"limit": 50})

        rows = []
        for entry in entries:
            # The track sits under "item" now; older responses used "track"
            track = entry.get("item") or entry.get("track")
            # Skip removed tracks, podcast episodes and local files
            if not track or not track.get("artists") or not track["artists"][0].get("id"):
                continue
            artist = track["artists"][0]  # main artist only
            # release_date is "YYYY", "YYYY-MM" or "YYYY-MM-DD", so take the first 4 chars
            release_date = track.get("album", {}).get("release_date")
            rows.append({
                "track_name": track["name"],
                "artist_name": artist["name"],
                "artist_id": artist["id"],
                "release_year": int(release_date[:4]) if release_date else None,
                "added_at": entry.get("added_at"),
                "genres": self.get_artist_genres(artist["id"]),
            })

        return pd.DataFrame(
            rows,
            columns=["track_name", "artist_name", "artist_id", "release_year", "added_at", "genres"],
        )
