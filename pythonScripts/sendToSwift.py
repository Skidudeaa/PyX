
#updated to take song/artist user input and return animated and still albuma artwork as well as all song lyrics, timestamped, with uuid, with song/artist metadata and annotaitons

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
from uuid import uuid4

# Initialization
GENIUS_API_KEY = "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr"
MUSIXMATCH_USER_TOKEN = "190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95"
APPLE_MUSIC_API_KEY = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw"

headers = {'Authorization': 'Bearer ' + APPLE_MUSIC_API_KEY}
warnings.filterwarnings("ignore", category=FutureWarning)

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

def fetch_playlist_url(url):
    content = get_webpage_content(url)
    if content:
        match = re.search(r'src="h([^"]*)', content)
        if match:
            return "h" + match.group(1)
    print("No video URL found.")
    
def fetch_variant_playlist_url(playlist_url):
    content = get_webpage_content(playlist_url)
    if content:
        master_m3u8 = M3U8(content)
        playlists = master_m3u8.playlists
        if playlists:
            playlists.sort(key=lambda p: p.stream_info.resolution[0], reverse=True)
            return urljoin(playlist_url, playlists[0].uri)
    print("No variant playlist found.")

def fetch_segment_urls(variant_playlist_url):
    content = get_webpage_content(variant_playlist_url)
    if content:
        return [urljoin(variant_playlist_url, segment.uri) for segment in M3U8(content).segments]

def download_video_segments(segment_urls, video_dir):
    os.makedirs(video_dir, exist_ok=True)
    session = create_session()
    for i, segment_url in enumerate(set(segment_urls), start=1):
        response = session.get(segment_url)
        if response.status_code == 200:
            with open(os.path.join(video_dir, f"segment_{i}.mp4"), "wb") as f:
                f.write(response.content)
            print(f"Segment {i} downloaded successfully.")
        else:
            print(f"Failed to download segment {i}. Status code: {response.status_code}")

def download_album_artwork(url, save_dir):
    os.makedirs(save_dir, exist_ok=True)
    content = get_webpage_content(url)
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        source = soup.find('source', {'type': 'image/jpeg'})
        if source:
            urls = [url.strip() for url in source['srcset'].split(",")]
            url = max(urls, key=lambda u: int(u.split(" ")[1].rstrip("w"))).split(" ")[0]
            response = create_session().get(url)
            if response.status_code == 200:
                with open(os.path.join(save_dir, 'album_artwork.jpg'), 'wb') as f:
                    f.write(response.content)
                print(f"Album artwork downloaded successfully.")
            else:
                print("Failed to download album artwork.")
        else:
            print("No album artwork found.")

# Apple Music API Functions
def get_song_urls(song_name, artist_name):
  search_api = 'https://api.music.apple.com/v1/catalog/us/search'
  search_params = {'term': song_name + ' ' + artist_name, 'types': 'songs'}
  response = requests.get(search_api, params=search_params, headers=headers)
  
  if response.status_code != 200:
    print(f"Response text: {response.text}")
    return

  search_data = response.json()
  if 'songs' not in search_data['results'] or not search_data['results']['songs']['data']:
    print('No search results found')
    return

  songs_data = search_data['results']['songs']['data']
  return list(set(song['attributes']['url'] for song in songs_data))

# Semantic Truncate Function
def semantic_truncate(text, max_length=700):
    model = Summarizer()
    summary = model(text)
    sentences = sent_tokenize(summary)
    truncated_text = ""
    char_count = 0
    for sentence in sentences:
        new_count = char_count + len(sentence)
        if new_count <= max_length:
            truncated_text += sentence + " "
            char_count = new_count
        else:
            break
    return truncated_text.strip()

# Extract Text Function
def extract_text(content, depth=0):
    if depth > 10:
        return ''
    if isinstance(content, dict):
        children = content.get('children', [])
    elif isinstance(content, list):
        children = content
    else:
        return ''
    return ''.join([extract_text(child, depth + 1) if isinstance(child, (dict, list)) else str(child) if isinstance(child, (str, int, float)) else '' for child in children])

# Genius API Interactions
def get_song_id(search_term, api_key):
    url = "https://api.genius.com/search"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"q": search_term}
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()
    if 'response' not in response_json or 'hits' not in response_json['response'] or not response_json['response']['hits']:
        print(f"No results found for '{search_term}'. Please try again with a different search term.")
        exit()
    song_id = response_json['response']['hits'][0]['result']['id']
    return song_id

# Get Song Details Function
def get_song_details(song_id, api_key):
    url = f"https://api.genius.com/songs/{song_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    song_details = response.json()['response']['song']
    song_description_dom = song_details["description"]["dom"]["children"]
    song_description = ""
    for child in song_description_dom:
        if isinstance(child, dict):
            if child["tag"] == "p":
                for text in child["children"]:
                    if isinstance(text, str):
                        song_description += text + " "
                    elif isinstance(text, dict) and 'children' in text:
                        for subtext in text['children']:
                            if isinstance(subtext, str):
                                song_description += subtext + " "
    song_details['description'] = song_description.strip()
    return song_details

# Get Referents and Annotations Function
def get_referents_and_annotations(song_id, api_key, limit=6):
    url = f"https://api.genius.com/referents?song_id={song_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    referents = response.json()['response']['referents']
    verified_annotations = [r for r in referents if r['annotations'][0]['verified']]
    community_annotations = [r for r in referents if not r['annotations'][0]['verified']]
    top_referents = sorted(verified_annotations + community_annotations, key=lambda x: x['annotations'][0]['votes_total'], reverse=True)[:limit]
    return top_referents

# Get Song Details and Annotations Function
def get_song_details_and_annotations(song_name, api_key):
    # Initialize an empty dictionary to store the song details and annotations
    song_data = {}
    song_id = get_song_id(song_name, api_key)
    song_details = get_song_details(song_id, api_key)
    referents = get_referents_and_annotations(song_id, api_key)
    # Populate the song details into the dictionary
    song_data['title'] = song_details['title']
    song_data['artist'] = song_details['primary_artist']['name']
    song_data['album'] = song_details['album']['name'] if song_details['album'] else None
    song_data['release_date'] = song_details['release_date']
    song_data['description'] = song_details['description']
    # Semantically truncate description
    full_description = song_details['description']
    semantic_summary = semantic_truncate(full_description)
    truncated_description = semantic_summary[:600]
    song_data['description'] = truncated_description
    annotations = []
    for referent in referents:
        annotation_text = referent['annotations'][0]['body']['dom']['children']
        annotation_text_str = extract_text(annotation_text)
        semantic_summary = semantic_truncate(annotation_text_str)
        truncated_annotation = semantic_summary[:500]  
        annotations.append({
            'referent': referent['fragment'],
            'annotation': truncated_annotation
        })
    song_data['annotations'] = annotations
    return song_data


# Musixmatch Interactions
class LRCProvider:
    session = requests.Session()
    def __init__(self, user_token: str) -> None:
        self.user_token = user_token
        self.session.headers.update({
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        })
    def get_lrc_by_id(self, track_id: str) -> Optional[str]:
        raise NotImplementedError
    def get_lrc(self, search_term: str) -> Optional[str]:
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


    def get_lrc(self, search_term: str) -> Optional[str]:
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
        return self.get_lrc_by_id(tracks[0]["track"]["track_id"])


def fetch_lyrics_with_timestamps(user_token, search_term):
    musixmatch_provider = Musixmatch(user_token)
    lyrics = musixmatch_provider.get_lrc(search_term)
    lyrics_data = None
    if lyrics:
        parsed_lyrics = [{"id": f"{i+1}", "timestamp": round(float(ts[1:].split(':')[0])*60 + float(ts[1:].split(':')[1]), 1), "lyric": l} for i, (ts, l) in enumerate((line.split('] ') for line in lyrics.split('\n') if line))]
        lyrics_data = {
            "lyrics": parsed_lyrics
        }
    return lyrics_data

def combine_lyrics_and_annotations(lyrics_data, annotations_data):
    lyrics_and_annotations = []
    for lyric in lyrics_data.get('lyrics', []):
        annotation = None  # Default value if no matching annotation is found
        lyric_text = lyric['lyric']
        
        # Search for a matching annotation based on the referent
        for ann in annotations_data.get('annotations', []):
            referent = ann['referent']
            if fuzz.ratio(referent.lower(), lyric_text.lower()) > 60:  # You can adjust the threshold
                annotation = ann['annotation']
                break
                
        lyrics_and_annotations.append({
            'id': str(uuid4()),
            'lyric': lyric_text,
            'timestamp': lyric['timestamp'],
            'annotation': annotation
        })
        
    return lyrics_and_annotations

# Main Function
def main():
    # User input for song and artist
    song_title = input("Enter song title: ")
    artist_name = input("Enter artist name: ")

    # Apple Music API: Fetch and Download Video
    song_urls = get_song_urls(song_title, artist_name)
    for url in song_urls:
        playlist_url = fetch_playlist_url(url)
        if playlist_url is None:
            download_album_artwork(url, artist_name)
        else:
            variant_playlist_url = fetch_variant_playlist_url(playlist_url)
            if variant_playlist_url is None:
                download_album_artwork(url, artist_name)
            else:
                segment_urls = fetch_segment_urls(variant_playlist_url)
                if not segment_urls:
                    download_album_artwork(url, artist_name)
                else:
                    download_video_segments(segment_urls, artist_name)
        
        # Download album artwork irrespective of video availability
        download_album_artwork(url, artist_name)

        break  # Stop after successfully downloading a video or artwork


    # Genius and Musixmatch Functionality
    # Use `song_title` and `artist_name` to fetch Genius and Musixmatch data
    lyrics_data = fetch_lyrics_with_timestamps(MUSIXMATCH_USER_TOKEN, song_title)
    song_data = get_song_details_and_annotations(song_title, GENIUS_API_KEY)
    combined_lyrics_and_annotations = combine_lyrics_and_annotations(lyrics_data, song_data)

    final_data = {
        'title': song_data.get('title', ''),
        'artist': song_data.get('artist', ''),
        'album': song_data.get('album', ''),
        'release_date': song_data.get('release_date', ''),
        'description': song_data.get('description', ''),
        'lyrics_and_annotations': combined_lyrics_and_annotations
    }

    if final_data:
        with open("sendTo.json", "w") as f:
            json.dump(final_data, f, indent=4)
    else:
        print("No data to save.")

if __name__ == "__main__":
    main()