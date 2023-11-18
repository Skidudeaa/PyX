"""
This script provides a set of utilities for music data retrieval and processing. It fetches song data, 
including artwork and color data, from the Apple Music API based on a user-provided song title and artist. 
The script also includes functions for downloading video content from a given URL, parsing .m3u8 files, 
and returning the URLs of the video segments. Additionally, it provides functionality to download song artwork 
and the first video segment if an animated cover is found.
"""

import os
import re
import json
import requests
import urllib.request
import io
import warnings
import shutil
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

APPLE_MUSIC_API_KEY = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw"


# Utility Functions for Video Downloading
def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def get_webpage_content(url):
    try:
        response = create_session().get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while fetching page: {e}")
        return None

def fetch_playlist_url(url):
    content = get_webpage_content(url)
    if content:
        match = re.search(r'src="h([^"]*)', content)
        if match:
            return "h" + match.group(1)
    print("No video URL found.")
    return None

def fetch_variant_playlist_url(playlist_url):
    content = get_webpage_content(playlist_url)
    if content:
        # Assume you have an M3U8 parser here
        playlists = M3U8(content).playlists
        if playlists:
            playlists.sort(key=lambda p: p.stream_info.resolution[0], reverse=True)
            return urljoin(playlist_url, playlists[0].uri)
    print("No variant playlist found.")
    return None

def fetch_segment_urls(variant_playlist_url):
    content = get_webpage_content(variant_playlist_url)
    if content:
        # Assume you have an M3U8 parser here
        return [urljoin(variant_playlist_url, segment.uri) for segment in M3U8(content).segments]
    return None

# Download only the first video segment
def download_video_segments(segment_urls, video_dir):
    os.makedirs(video_dir, exist_ok=True)
    session = create_session()
    segment_url = segment_urls[0]  # Get the first segment URL
    response = session.get(segment_url)
    if response.status_code == 200:
        with open(os.path.join(video_dir, f"segment_1.mp4"), "wb") as f:
            f.write(response.content)
        print("Segment 1 downloaded successfully.")
    else:
        print(f"Failed to download segment 1. Status code: {response.status_code}")

# Loop through each song to find animated cover and download static cover
    for song in song_data:
        song_url = song['attributes']['url']
        playlist_url = fetch_playlist_url(song_url)
        
        if playlist_url:
            variant_playlist_url = fetch_variant_playlist_url(playlist_url)
            if variant_playlist_url:
                segment_urls = fetch_segment_urls(variant_playlist_url)
                if segment_urls:
                    download_video_segments(segment_urls, 'video_segments')
                    break  # Stop once a video is downloaded

# Search song and get artwork and color data
    # Download the highest quality static artwork and get color data
    artwork_url = song_data[0]['attributes']['artwork']['url']
    artwork_url = artwork_url.replace('{w}', '3000').replace('{h}', '3000')
    download_image(artwork_url, 'artwork.jpg')

    bg_color = song_data[0]['attributes']['artwork']['bgColor']
    text_colors = {
        'textColor1': song_data[0]['attributes']['artwork']['textColor1'],
        'textColor2': song_data[0]['attributes']['artwork']['textColor2'],
        'textColor3': song_data[0]['attributes']['artwork']['textColor3'],
        'textColor4': song_data[0]['attributes']['artwork']['textColor4'],
    }

    # Save color data to JSON file
    color_data = {
        'bgColor': bg_color,
        'textColors': text_colors
    }

