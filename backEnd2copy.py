import os
import re
import requests
from bs4 import BeautifulSoup
from m3u8 import M3U8
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urljoin
from PIL import Image
import io
import urllib.request
from summarizer import Summarizer
from nltk.tokenize import sent_tokenize
import warnings
from typing import Optional
import json
from fuzzywuzzy import fuzz
from uuid import uuid4  # for generating unique IDs


# Initialization
GENIUS_API_KEY = "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr"
MUSIXMATCH_USER_TOKEN = "190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95"
warnings.filterwarnings("ignore", category=FutureWarning)

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
    song_data = {}
    song_id = get_song_id(song_name, api_key)
    song_details = get_song_details(song_id, api_key)
    referents = get_referents_and_annotations(song_id, api_key)
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
        tracks = body.get("track_list", [])
        if not tracks:
            return
        return self.get_lrc_by_id(tracks[0]["track"]["track_id"])

def fetch_lyrics_with_timestamps(user_token, search_term):
    musixmatch_provider = Musixmatch(user_token)
    lyrics = musixmatch_provider.get_lrc(search_term)
    lyrics_data = None
    if lyrics:
        parsed_lyrics = [{"id": f"{i+1}", "timestamp": round(float(ts[1:].split(':')[0])*60 + float(ts[1:].split(':')[1]), 1), "lyric": l} for i, (ts, l) in enumerate((line.split('] ') for line in lyrics.split('
') if line))]
        lyrics_data = {
            "lyrics": parsed_lyrics
        }
    return lyrics_data


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


def fetch_songs(search_term, client_access_token):
    genius_search_url = f"http://api.genius.com/search?q={search_term}&access_token={client_access_token}"
    response = requests.get(genius_search_url)
    json_data = response.json()
    songs = []  
    for song in json_data['response']['hits']:
    
      full_title = song['result']['full_title']
      song_art_url = song['result']['song_art_image_url']
    
      if 'stats' in song['result'] and 'pageviews' in song['result']['stats']:
        pageviews = song['result']['stats']['pageviews']
      else:
        pageviews = None
    
      songs.append((full_title, pageviews, song_art_url))

    return songs


def save_album_art(songs, search_term):
    if not os.path.exists(search_term):
        os.makedirs(search_term)
    for song in songs:
        song_title, page_views, album_cover_url = song
        filename = f"{search_term}/{song_title.replace('/', '_')}.jpg"
        req = urllib.request.Request(album_cover_url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as url:
                f = io.BytesIO(url.read())
            img = Image.open(f)
            img.save(filename)
            print(f"Saved album cover for '{song_title}'")
        except Exception as e:
            print(f"Could not save album cover for '{song_title}'. Error: {e}")



def get_best_match(input_str, potential_matches):
    """
    Get the best fuzzy match from a list of potential matches.
    """
    best_match_score = 0
    best_match_string = ""

    for potential in potential_matches:
        score = fuzz.ratio(input_str.lower(), potential.lower())
        if score > best_match_score:
            best_match_score = score
            best_match_string = potential

    return best_match_string if best_match_score > 60 else None  # Only return matches that are more than 60% similar


def combine_lyrics_and_annotations(lyrics_data, annotations_data):
    lyrics_and_annotations = []
    for lyric in lyrics_data.get('lyrics', []):
        annotation = None  # Default value if no matching annotation is found
        lyric_text = lyric['lyric']
        
        # Search for a matching annotation based on the referent
        for ann in annotations_data.get('annotations', []):
            referent = ann['referent']
            if referent == lyric_text:  # Match found
                annotation = ann['annotation']
                break
                
        lyrics_and_annotations.append({
            'id': str(uuid4()),
            'lyric': lyric_text,
            'timestamp': lyric['timestamp'],
            'annotation': annotation
        })
        
    return lyrics_and_annotations


def main():
    # Prompt user for song and artist details
    song_and_artist = input("Enter the song followed by the artist name (e.g. 'Shape of You by Ed Sheeran' or 'Shape of You, Ed Sheeran'): ")
    
    # Prompt user for video URL
    video_url = input("Please enter the video URL: ")

    # Allow for both "by" and ","
    delimiter = " by " if " by " in song_and_artist else ","
    song_search_term, artist_name = [s.strip() for s in song_and_artist.split(delimiter)]

    # Fuzzy matching for song and artist names
    songs_from_genius = fetch_songs(song_search_term, GENIUS_API_KEY)
    potential_song_names = [song[0] for song in songs_from_genius]
    matched_song_name = get_best_match(song_search_term, potential_song_names)
    if matched_song_name:
        if " by " in matched_song_name:
            song_search_term, artist_name = matched_song_name.split(" by ")
        else:
            print(f"Unexpected format for matched song name: {matched_song_name}. Using the provided names.")
    else:
        print("Couldn't find a close match for the song and artist. Using the provided names.")

    # Fetch and Save Album Artwork
    songs = fetch_songs(artist_name, GENIUS_API_KEY)
    save_album_art(songs, artist_name)

    # Fetch Video Segments
    playlist_url = fetch_playlist_url(video_url)
    if playlist_url:
        variant_playlist_url = fetch_variant_playlist_url(playlist_url)
        if variant_playlist_url:
            segment_urls = fetch_segment_urls(variant_playlist_url)
            if segment_urls:
                download_video_segments(segment_urls, artist_name)

    # Fetch Lyrics and Song Details
    lyrics_data = fetch_lyrics_with_timestamps(MUSIXMATCH_USER_TOKEN, song_search_term)
    song_data = get_song_details_and_annotations(song_search_term, GENIUS_API_KEY)

    combined_data = {}
    if lyrics_data:
        combined_data.update(lyrics_data)
    if song_data:
        combined_data.update(song_data)
    print(f"Final Combined Data: {combined_data}")  # Debugging line

    if combined_data:
        with open("combined_data.json", "w") as f:
            json.dump(combined_data, f, indent=4)
    else:
        print("No data to save.")

if __name__ == "__main__":
    main()


'''

https://music.apple.com/us/album/candy-paint/1373516902?i=1373517329&uo=4&app=music
'''