

import os
import re
import json
import requests
import io
import warnings
import shutil
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urljoin
from PIL import Image
from bs4 import BeautifulSoup
from m3u8 import M3U8
from uuid import uuid4
from summarizer import Summarizer
from nltk.tokenize import sent_tokenize
from typing import Optional
from fuzzywuzzy import fuzz
from fuzzywuzzy import process


# Initialization
GENIUS_API_KEY = "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr"
MUSIXMATCH_USER_TOKEN = "190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95"
APPLE_MUSIC_API_KEY = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw"

headers = {'Authorization': 'Bearer ' + APPLE_MUSIC_API_KEY}
warnings.filterwarnings("ignore", category=FutureWarning)

# Semantic Truncate Function
def semantic_truncate(text, max_length=600):
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
def get_song_id(search_term, artist_name, api_key):
    url = "https://api.genius.com/search"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"q": f"{search_term} {artist_name}"}
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()
    if 'response' not in response_json or 'hits' not in response_json['response'] or not response_json['response']['hits']:
        print(f"No results found for '{search_term} by {artist_name}'. Please try again with a different search term.")
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
def get_referents_and_annotations(song_id, api_key, limit=8):
    url = f"https://api.genius.com/referents?song_id={song_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    referents = response.json()['response']['referents']
    verified_annotations = [r for r in referents if r['annotations'][0]['verified']]
    community_annotations = [r for r in referents if not r['annotations'][0]['verified']]
    top_referents = sorted(verified_annotations + community_annotations, key=lambda x: x['annotations'][0]['votes_total'], reverse=True)[:limit]
    return top_referents

# Get Song Details and Annotations Function
def get_song_details_and_annotations(song_name, artist_name, api_key):
    # Initialize an empty dictionary to store the song details and annotations
    song_data = {}
    song_id = get_song_id(song_name, artist_name, api_key)
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
    truncated_description = semantic_summary[:400]
    song_data['description'] = truncated_description
    annotations = []
    for referent in referents:
        annotation_text = referent['annotations'][0]['body']['dom']['children']
        annotation_text_str = extract_text(annotation_text)
        semantic_summary = semantic_truncate(annotation_text_str)
        truncated_annotation = semantic_summary[:400]  
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


    def get_lrc(self, search_term: str, artist_name: str) -> Optional[str]:
        url = self.SEARCH_ENDPOINT.format(q=f"{search_term} {artist_name}", token=self.user_token)
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

        # Normalize the search term and track names
        search_term = f"{search_term} {artist_name}".lower()
        track_names = [f"{track['track']['track_name']} {track['track']['artist_name']}".lower() for track in tracks]

        # Use FuzzyWuzzy to find the best match
        best_match = None
        best_score = 0
        for track in tracks:
            track_name = f"{track['track']['track_name']} {track['track']['artist_name']}".lower()
            score = fuzz.ratio(search_term, track_name)
            if score > best_score and score > 70:  # Increase the threshold to ...
                best_score = score
                best_match = track

        if best_match is None:
            return

        return self.get_lrc_by_id(best_match["track"]["track_id"])

def fetch_lyrics_with_timestamps(user_token, search_term, artist_name):
    musixmatch_provider = Musixmatch(user_token)
    lyrics = musixmatch_provider.get_lrc(search_term, artist_name)
    lyrics_data = None
    if lyrics:
        parsed_lyrics = [{"id": f"{i+1}", "timestamp": round(float(ts[1:].split(':')[0])*60 + float(ts[1:].split(':')[1]), 1), "lyric": l} for i, (ts, l) in enumerate((line.split('] ') for line in lyrics.split('\n') if line))]
        lyrics_data = {
            "lyrics": parsed_lyrics
        }
    return lyrics_data

def combine_lyrics_and_annotations(lyrics_data, annotations_data):
    if lyrics_data is None or annotations_data is None:
        return []

    lyrics_and_annotations = []
    added_annotations = set()  # Set to keep track of added annotations
    last_lyric_had_annotation = False  # Flag to check if the last lyric had an annotation

    for lyric in lyrics_data.get('lyrics', []):
        annotation = None  # Default value if no matching annotation is found
        lyric_text = lyric['lyric']
        
        # Search for a matching annotation based on the referent
        for ann in annotations_data.get('annotations', []):
            referent = ann['referent']
            annotation_text = ann['annotation']

            # Check if the annotation has already been added or if the last lyric had an annotation
            if annotation_text in added_annotations or last_lyric_had_annotation:
                continue

            if fuzz.ratio(referent.lower(), lyric_text.lower()) > 40:  # You can adjust the threshold
                annotation = annotation_text
                added_annotations.add(annotation_text)  # Add the annotation to the set of added annotations
                break
                
        lyrics_and_annotations.append({
            'id': str(uuid4()),
            'lyric': lyric_text,
            'timestamp': lyric['timestamp'],
            'annotation': annotation
        })

        # Update the flag for the next iteration
        last_lyric_had_annotation = annotation is not None
        
    return lyrics_and_annotations


# Utility Functions
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
    content = create_session().get(url).text
    if content:
        match = re.search(r'src="h([^"]*)', content)
        if match:
            return "h" + match.group(1)
    #print("No video URL found.")
    return None

# Your existing functions for Apple Music interactions
def download_image(image_url, image_path):
        response = requests.get(image_url, stream=True)
        
        # Create the finalOutput directory if it doesn't exist
        output_dir = os.path.join(os.getcwd(), 'finalOutput')
        os.makedirs(output_dir, exist_ok=True)

        # Save the image in the finalOutput directory
        with open(os.path.join(output_dir, image_path), 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response

def search_song(song_title, artist_name, developer_token):
    headers = {
        'Authorization': 'Bearer ' + developer_token,
    }

    params = (
        ('term', song_title + ' ' + artist_name),
        ('limit', '5'),
        ('types', 'songs')  # This ensures that only songs are searched
    )

    response = requests.get('https://api.music.apple.com/v1/catalog/us/search', headers=headers, params=params)
    json_response = response.json()
    
    # Check if any song data is returned
    if 'songs' not in json_response['results']:
        print("No songs found.")
        return None, None

    song_data = json_response['results']['songs']['data']
    
    # Initialize variables to store color data
    bg_color, text_colors = None, None
    
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

    return bg_color, text_colors


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
    # Create the finalOutput directory if it doesn't exist
    output_dir = os.path.join(os.getcwd(), 'finalOutput')
    os.makedirs(output_dir, exist_ok=True)

    session = create_session()
    segment_url = segment_urls[0]  # Get the first segment URL
    response = session.get(segment_url)
    if response.status_code == 200:
        # Save the video in the finalOutput directory
        with open(os.path.join(output_dir, f"AnimatedArt.mp4"), "wb") as f:
            f.write(response.content)
        print("animatedCoverArt downloaded.")
    else:
        print(f"No animatedCoverArt. Status code: {response.status_code}")




def main(song_title, artist_name):
    # Fetching song details, annotations, and lyrics
    song_data = get_song_details_and_annotations(song_title, artist_name, GENIUS_API_KEY)
    lyrics_data = fetch_lyrics_with_timestamps(MUSIXMATCH_USER_TOKEN, song_title, artist_name)
    combined_lyrics_and_annotations = combine_lyrics_and_annotations(lyrics_data, song_data)

    # Fetching album artwork and color data from Apple Music
    bg_color, text_colors = search_song(song_title, artist_name, APPLE_MUSIC_API_KEY)

    # Combine all data
    final_1 = {
        'title': song_data.get('title', ''),
        'artist': song_data.get('artist', ''),
        'album': song_data.get('album', ''),
        'release_date': song_data.get('release_date', ''),
        'description': song_data.get('description', ''),
        'bgColor': bg_color,
        'textColors': text_colors,
        'lyrics_and_annotations': combined_lyrics_and_annotations
    }

    # Create the finalOutput directory if it doesn't exist
    output_dir = os.path.join(os.getcwd(), 'finalOutput')
    os.makedirs(output_dir, exist_ok=True)

    # Save the final data to a JSON file in the finalOutput directory
    with open(os.path.join(output_dir, 'final_1.json'), 'w') as f:
        json.dump(final_1, f, indent=4)




'''
# Your main function
def main():
    song_title = input("Enter song title: ")
    artist_name = input("Enter artist name: ")

    # Fetching song details, annotations, and lyrics
    song_data = get_song_details_and_annotations(song_title, artist_name, GENIUS_API_KEY)
    lyrics_data = fetch_lyrics_with_timestamps(MUSIXMATCH_USER_TOKEN, song_title, artist_name)
    combined_lyrics_and_annotations = combine_lyrics_and_annotations(lyrics_data, song_data)

    # Fetching album artwork and color data from Apple Music
    bg_color, text_colors = search_song(song_title, artist_name, APPLE_MUSIC_API_KEY)
    # Combine all data
    final_1 = {
        'title': song_data.get('title', ''),
        'artist': song_data.get('artist', ''),
        'album': song_data.get('album', ''),
        'release_date': song_data.get('release_date', ''),
        'description': song_data.get('description', ''),
        'bgColor': bg_color,
        'textColors': text_colors,
        'lyrics_and_annotations': combined_lyrics_and_annotations
    }

    # Create the finalOutput directory if it doesn't exist
    output_dir = os.path.join(os.getcwd(), 'finalOutput')
    os.makedirs(output_dir, exist_ok=True)

    # Save the final data to a JSON file in the finalOutput directory
    with open(os.path.join(output_dir, 'final_1.json'), 'w') as f:
        json.dump(final_1, f, indent=4)

if __name__ == "__main__":
    main()
  '''