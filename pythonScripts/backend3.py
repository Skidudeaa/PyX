
import os
import re
import requests
from bs4 import BeautifulSoup
from m3u8 import M3U8
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin
from PIL import Image
import io
import urllib.request
from summarizer import Summarizer
from nltk.tokenize import sent_tokenize
import warnings
from fuzzywuzzy import fuzz
import json

GENIUS_API_KEY = "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr"
MUSIXMATCH_USER_TOKEN = "190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95"
warnings.filterwarnings("ignore", category=FutureWarning)

# Semantic Truncate Function
def semantic_truncate(text, max_length=450):
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

# Fetch Lyrics with Timestamps Function
def fetch_lyrics_with_timestamps(MUSIXMATCH_USER_TOKEN, search_term):
    musixmatch_provider = musixmatch(user_token)
    lyrics = musixmatch_provider.get_lrc(search_term)
    lyrics_data = None
    if lyrics:
        parsed_lyrics = [{"timestamp": round(float(ts[1:].split(':')[0])*60 + float(ts[1:].split(':')[1]), 1), "lyric": l} for ts, l in (line.split('] ') for line in lyrics.split('\n') if line)]
        lyrics_data = {
            "lyrics": parsed_lyrics
        }
    return lyrics_data

# Get Song Details and Annotations Function
def get_song_details_and_annotations(song_name, api_key):
    song_data = {}
    song_id = get_song_id(song_name, api_key)
    song_details = get_song_details(song_id, api_key)
    referents = get_referents_and_annotations(song_id, api_key)
    song_data['title'] = song_details['title']
    song_data['artist'] = song_details['primary_artist']['name']
    song_data['album'] = song_details['album']['name'] if song_details['album'] else None
    song_data['release_date'] = song_details['release_date']
    song_data['description'] = song_details['description']
    annotations = []
    for referent in referents:
        annotation_text = referent['annotations'][0]['body']['dom']['children']
        annotation_text_str = extract_text(annotation_text)
        semantic_summary = semantic_truncate(annotation_text_str)
        truncated_annotation = semantic_summary[:550]
        annotations.append({
            'referent': referent['fragment'],
            'annotation': truncated_annotation
        })
    song_data['annotations'] = annotations
    return song_data

# Main Function
def main():
    song_name = input("Enter the song name: ")
    artist_name = input("Enter the artist name: ")
    
    lyrics_data = fetch_lyrics_with_timestamps("190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95", song_name + " " + artist_name)
    song_data = get_song_details_and_annotations(song_name, "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr")

    combined_data = {}
    if lyrics_data:
        combined_data.update(lyrics_data)
    if song_data:
        combined_data.update(song_data)

    if combined_data:
        with open("combined_data.json", "w") as f:
            json.dump(combined_data, f, indent=4)
    else:
        print("No data to save.")

if __name__ == "__main__":
    main()
