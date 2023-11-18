import requests
import os
import re
import json
import requests
import urllib.request
import io
import warnings
from PIL import Image
from bs4 import BeautifulSoup
from m3u8 import M3U8
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urljoin
from summarizer import Summarizer
from nltk.tokenize import sent_tokenize
from typing import Optional
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from uuid import uuid4



class LRCProvider:
    session = requests.Session()
    def __init__(self, user_token: str) -> None:
        self.user_token = user_token
        self.session.headers.update({
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        })
    def get_lrc_by_id(self, track_id: str) -> Optional[str]:
        raise NotImplementedError
    def get_lrc(self) -> Optional[str]:
        raise NotImplementedError
        
class Musixmatch(LRCProvider):
    SEARCH_ENDPOINT = "https://apic-desktop.musixmatch.com/ws/1.1/track.search?format=json&q={q}&page_size=5&page=1&s_track_rating=desc&quorum_factor=1.0&app_id=web-desktop-app-v1.0&usertoken={token}"
    LRC_ENDPOINT = "https://apic-desktop.musixmatch.com/ws/1.1/track.subtitle.get?format=json&track_id={track_id}&subtitle_format=lrc&app_id=web-desktop-app-v1.0&usertoken={token}"
    
    def get_lrc_by_id(self, track_id: str) -> Optional[str]:
        url = self.LRC_ENDPOINT.format(track_id=track_id, token=self.user_token)
        r = self.session.get(url)
        if not r.ok:
            return
        body = r.json().get("message", {}).get("body", {})
        return body.get("subtitle", {}).get("subtitle_body")
    
    def get_lrc(self) -> Optional[str]:
        search_term = input("Enter the song title and/or artist: ")
        url = self.SEARCH_ENDPOINT.format(q=search_term, token=self.user_token)
        r = self.session.get(url)
        if not r.ok:
            return
        body = r.json().get("message", {}).get("body", {})
        if isinstance(body, list):
            print("Received list instead of expected dict. Aborting.")
            return None
        tracks = body.get("track_list", [])
        if not tracks:
            return
        search_term = search_term.lower()
        matches = []
        for track in tracks:
            track_name = f"{track['track']['track_name']} {track['track']['artist_name']}".lower()
            score = fuzz.token_set_ratio(search_term, track_name)
            if "karaoke" in track_name or "cover" in track_name:
                score -= 20  # Deduct 10 points from the score if it's a karaoke or cover version
            if score > 60:  # Increase the threshold to 80
                matches.append((score, track))
        matches.sort(key=lambda x: x[0], reverse=True)  # Sort matches based on score
        for i, match in enumerate(matches[:10], 1):
            print(f"Match {i} (Fuzz Score: {match[0]}): {match[1]['track']['track_name']} by {match[1]['track']['artist_name']}")
        return None
    

musixmatch = Musixmatch("190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95")
musixmatch.get_lrc()