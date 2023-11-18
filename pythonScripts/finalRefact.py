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
def semantic_truncate(text, max_length=1000):
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
def get_referents_and_annotations(song_id, api_key, limit=8):
    url = f"https://api.genius.com/referents?song_id={song_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    referents = response.json()['response']['referents']
    verified_annotations = [r for r in referents if r['annotations'][0]['verified']]
    community_annotations = [r for r in referents if not r['annotations'][0]['verified']]
    top_referents = sorted(verified_annotations + community_annotations, key=lambda x: x['annotations'][0]['votes_total'], reverse=True)[:limit]
    return top_referents


def get_song_details_and_annotations(song_title, api_key):
      """
      Fetch song details and annotations from Genius API.
      
      Parameters:
      song_title (str): The title of the song.
      api_key (str): The Genius API key.

      Returns:
      dict: A dictionary containing song details and annotations.
      """
      try:
          # Create a Genius API client
          genius = Genius(api_key)
          genius.remove_section_headers = True
          genius.skip_non_songs = False
          genius.excluded_terms = ["(Remix)", "(Live)", "(Edit)", "(Mix)", "(Version)"]                                                                  

          # Search for the song
          song = genius.search_song(song_title)                                                                                                          
          if song is None:
              print(f"No results found for '{song_title}'.")
              return None

          # Fetch song details
          song_details = {
              'title': song.title,
              'artist': song.artist,
              'album': song.album,
              'release_date': song.year,
              'description': song.description,
          }                                                                                         # Fetch song annotations                                                                            
          song_annotations = genius.get_annotations(song.id)                                                                               
          return {'details': song_details, 'annotations': song_annotations}                                                                        
      except Exception as e:    
          print(f"An error occurred while fetching song details and annotations: {e}")                                                                   
          return None               
      
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
            if score > best_score and score > 60:  # Increase the threshold to 60
                best_score = score
                best_match = track

        if best_match is None:
            return

        return self.get_lrc_by_id(best_match["track"]["track_id"])      
      
def fetch_lyrics_with_timestamps(api_key, song_title, artist_name):
      """
      Fetch lyrics with timestamps from MusixMatch API.

      Parameters:
      api_key (str): The MusixMatch API key.
      song_title (str): The title of the song.
      artist_name (str): The name of the artist.

      Returns:
      dict: A dictionary containing lyrics with timestamps.
      """
      try:
          # Create a MusixMatch API client
          musixmatch = Musixmatch(api_key)

          # Search for the song
          result = musixmatch.matcher_lyrics_get(q_track=song_title, q_artist=artist_name)
          if result['message']['header']['status_code'] != 200:
              print(f"No results found for '{song_title}' by '{artist_name}'.")
              return None
      except
          # Fetch lyrics with timestamps
          lyrics = result['message']['body']['lyrics']['lyrics_body']
          lyrics_with_timestamps = re.findall(r'\[(.*?)\](.*?)\n', lyrics)

          return lyrics_with_timestamps
      except Exception as e:
          print(f"An error occurred while fetching lyrics with timestamps: {e}")
          return None
      
      
      
      
def combine_lyrics_and_annotations(lyrics_data, song_data):
      """
      Combine lyrics and annotations into a single dictionary.
      Parameters:
      lyrics_data (dict): The lyrics data.
      song_data (dict): The song data.
      Returns:
      dict: A dictionary containing combined lyrics and annotations.
      """
      try:
          # Combine lyrics and annotations
          combined_data = {}
          for i, (timestamp, lyrics) in enumerate(lyrics_data):
              annotation = song_data['annotations'].get(i, '')
              combined_data[timestamp] = {'lyrics': lyrics, 'annotation': annotation}

          return combined_data
      except Exception as e:
          print(f"An error occurred while combining lyrics and annotations: {e}")
          return 
      
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
    print("No video URL found.")
    return None

# Functions for Apple Music interactions
def download_image(image_url, image_path):
        response = requests.get(image_url, stream=True)
        
        # Create the finalOutput directory if it doesn't exist
        output_dir = os.path.join(os.getcwd(), 'finalOutput')
        os.makedirs(output_dir, exist_ok=True)

        # Save the image in the finalOutput directory
        with open(os.path.join(output_dir, image_path), 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response
      
      
def search_song(song_title, api_key):
      """
      Fetch album artwork and color data from Apple Music API.

      Parameters:
      song_title (str): The title of the song.
      api_key (str): The Apple Music API key.

      Returns:
      tuple: A tuple containing the background color and text colors.
      """
      try:
          # Create an Apple Music API client
          apple_music = AppleMusic(api_key)

          # Search for the song
          result = apple_music.search(song_title, types=['songs'], limit=1)
          if not result['results']['songs']['data']:
              print(f"No results found for '{song_title}'.")
              return None

          # Fetch album artwork
          artwork_url = result['results']['songs']['data'][0]['attributes']['artwork']['url']

          # Fetch color data
          color_thief = ColorThief(artwork_url)
          bg_color = color_thief.get_color(quality=1)
          text_colors = color_thief.get_palette(color_count=2)

          return bg_color, text_colors
      except Exception as e:
          print(f"An error occurred while fetching album artwork and color data: {e}")
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
    # Create the finalOutput directory if it doesn't exist
    output_dir = os.path.join(os.getcwd(), 'finalOutput')
    os.makedirs(output_dir, exist_ok=True)

    session = create_session()
    segment_url = segment_urls[0]  # Get the first segment URL
    response = session.get(segment_url)
    if response.status_code == 200:
        # Save the video in the finalOutput directory
        with open(os.path.join(output_dir, f"segment_1.mp4"), "wb") as f:
            f.write(response.content)
        print("Segment 1 downloaded successfully.")
    else:
        print(f"Failed to download segment 1. Status code: {response.status_code}")
      
      
def main():
      """
      The entry point of the script.
      """
      try:
          # Get user input
          song_title = input("Enter song title: ")
          artist_name = input("Enter artist name: ")

          # Fetch song details, annotations, and lyrics
          song_data = get_song_details_and_annotations(song_title, GENIUS_API_KEY)
          lyrics_data = fetch_lyrics_with_timestamps(MUSIXMATCH_USER_TOKEN, song_title, artist_name)
          combined_lyrics_and_annotations = combine_lyrics_and_annotations(lyrics_data, song_data)

          # Fetch album artwork and color data
          bg_color, text_colors = search_song(song_title, APPLE_MUSIC_API_KEY)

          # Combine all data
          final_data = {
              'title': song_data['details']['title'],
              'artist': song_data['details']['artist'],
              'album': song_data['details']['album'],
              'release_date': song_data['details']['release_date'],
              'description': song_data['details']['description'],
              'bgColor': bg_color,
              'textColors': text_colors,
              'lyrics_and_annotations': combined_lyrics_and_annotations
          }

          # Save the final data to a JSON file
          with open('final_data.json', 'w') as f:
              json.dump(final_data, f, indent=4)
      except Exception as e:
          print(f"An error occurred: {e}")