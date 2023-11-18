

import os
import requests
import shutil
import json
import re
from m3u8 import M3U8
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urljoin

# Initialization
APPLE_MUSIC_API_KEY = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw"
OUTPUT_DIR = 'november23output'

# Create output directory if it doesn't exist
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

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

def fetch_playlist_url(song_url):
    content = get_webpage_content(song_url)
    if content:
        match = re.search(r'src="h([^"]*)', content)
        if match:
            return "h" + match.group(1)
    print("No playlist URL found.")
    return None

def fetch_variant_playlist_url(playlist_url):
    content = get_webpage_content(playlist_url)
    if content:
        playlists = M3U8(content).playlists
        if playlists:
            playlists.sort(key=lambda p: p.stream_info.resolution[0], reverse=True)
            return urljoin(playlist_url, playlists[0].uri)
    print("No variant playlist found.")
    return None

def download_static_cover_art(song, song_id):
    artwork_url = song['attributes']['artwork']['url'].replace('{w}', '3000').replace('{h}', '3000')
    response = requests.get(artwork_url, stream=True)
    if response.status_code == 200:
        file_path = os.path.join(OUTPUT_DIR, f'static_artwork_{song_id}.jpg')
        with open(file_path, 'wb') as file:
            shutil.copyfileobj(response.raw, file)
        print(f'Static cover art downloaded successfully: {file_path}')
    else:
        print(f'Failed to download static cover art. Status code: {response.status_code}')

def download_animated_cover_art(song_url, song_id):
    playlist_url = fetch_playlist_url(song_url)
    if playlist_url:
        variant_playlist_url = fetch_variant_playlist_url(playlist_url)
        if variant_playlist_url:
            content = get_webpage_content(variant_playlist_url)
            if content:
                segments = M3U8(content).segments
                segment_url = urljoin(variant_playlist_url, segments[0].uri)
                response = create_session().get(segment_url)
                if response.status_code == 200:
                    file_path = os.path.join(OUTPUT_DIR, f'animated_cover_{song_id}.mp4')
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    print(f"Animated cover art downloaded successfully: {file_path}")
                    return True
                else:
                    print(f"Failed to download segment. Status code: {response.status_code}")
    return False

def search_song(title, artist, api_key):
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {
        'term': f'{title} {artist}',
        'types': 'songs',
        'limit': 10
    }
    response = make_api_request('https://api.music.apple.com/v1/catalog/us/search', headers=headers, params=params)

    if response.status_code == 200:
        return response.json()['results']['songs']['data']
    else:
        raise Exception(f"Failed to search for the song. Status code: {response.status_code}")

def make_api_request(url, headers, params):
    # Implement logic to handle API request, including error handling and caching if needed
    response = requests.get(url, headers=headers, params=params)
    # Add error handling logic here if needed
    return response

def process_search_results(songs, song_title, song_artist):
    log = {"searched_songs": [], "selected_match": None, "static_cover_match": None, "animated_cover_match": None, "color_data": None}
    animated_cover_downloaded = False
    selected_match_found = False

    for song in songs:
        song_id = f"{song['attributes']['name']}_{song['attributes']['artistName']}".replace(" ", "_")
        bg_color = song['attributes']['artwork']['bgColor']
        text_colors = {
            'textColor1': song['attributes']['artwork']['textColor1'],
            'textColor2': song['attributes']['artwork']['textColor2'],
            'textColor3': song['attributes']['artwork']['textColor3'],
            'textColor4': song['attributes']['artwork']['textColor4'],
        }

        song_info = {
            "title": song['attributes']['name'],
            "artist": song['attributes']['artistName'],
            "album": song['attributes'].get('albumName', 'N/A'),
            "has_lyrics": song['attributes'].get('lyrics', False),
            "color_data": {
                'bgColor': bg_color,
                'textColors': text_colors
            },
            "song_id": song_id
        }
        log["searched_songs"].append(song_info)

        if song['attributes']['name'].lower() == song_title.lower() and song['attributes']['artistName'].lower() == song_artist.lower():
            if not selected_match_found:
                log["selected_match"] = song_info
                log["color_data"] = song_info["color_data"]
                selected_match_found = True

            download_static_cover_art(song, song_id)
            log["static_cover_match"] = song_info

            if download_animated_cover_art(song['attributes']['url'], song_id):
                animated_cover_downloaded = True
                log["animated_cover_match"] = song_info
                break

    if not animated_cover_downloaded and selected_match_found:
        print("No animated cover art found for the correct match.")
    
    return log

def main():
    song_title = input("Enter song title: ")
    song_artist = input("Enter artist name: ")
    songs = search_song(song_title, song_artist, APPLE_MUSIC_API_KEY)

    if songs:
        log = process_search_results(songs, song_title, song_artist)
        with open(os.path.join(OUTPUT_DIR, 'song_search_log.json'), 'w') as log_file:
            json.dump(log, log_file, indent=4)
        print(f"Log file created: {os.path.join(OUTPUT_DIR, 'song_search_log.json')}")
    else:
        print("No song found.")

if __name__ == "__main__":
    main()



'''

import os
import requests
import shutil
import json
import re
from m3u8 import M3U8
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urljoin

# Initialization
APPLE_MUSIC_API_KEY = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw"
OUTPUT_DIR = 'november23output'

# Create output directory if it doesn't exist
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

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

def fetch_playlist_url(song_url):
    content = get_webpage_content(song_url)
    if content:
        match = re.search(r'src="h([^"]*)', content)
        if match:
            return "h" + match.group(1)
    print("No playlist URL found.")
    return None

def fetch_variant_playlist_url(playlist_url):
    content = get_webpage_content(playlist_url)
    if content:
        playlists = M3U8(content).playlists
        if playlists:
            playlists.sort(key=lambda p: p.stream_info.resolution[0], reverse=True)
            return urljoin(playlist_url, playlists[0].uri)
    print("No variant playlist found.")
    return None

def download_animated_cover_art(song_url):
    playlist_url = fetch_playlist_url(song_url)
    if playlist_url:
        variant_playlist_url = fetch_variant_playlist_url(playlist_url)
        if variant_playlist_url:
            content = get_webpage_content(variant_playlist_url)
            if content:
                segments = M3U8(content).segments
                segment_url = urljoin(variant_playlist_url, segments[0].uri)
                response = create_session().get(segment_url)
                if response.status_code == 200:
                    with open(os.path.join(OUTPUT_DIR, 'animated_cover.mp4'), 'wb') as f:
                        f.write(response.content)
                    print("Animated cover art downloaded successfully.")
                    return True
                else:
                    print(f"Failed to download segment. Status code: {response.status_code}")
    return False

def search_song(title, artist, api_key):
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {
        'term': f'{title} {artist}',
        'types': 'songs',
        'limit': 25
    }
    response = requests.get('https://api.music.apple.com/v1/catalog/us/search', headers=headers, params=params)

    if response.status_code == 200:
        return response.json()['results']['songs']['data']
    else:
        print(f"Failed to search for the song. Status code: {response.status_code}")
        return None

def download_static_cover_art(song):
    artwork_url = song['attributes']['artwork']['url'].replace('{w}', '3000').replace('{h}', '3000')
    response = requests.get(artwork_url, stream=True)
    if response.status_code == 200:
        with open(os.path.join(OUTPUT_DIR, 'static_artwork.jpg'), 'wb') as file:
            shutil.copyfileobj(response.raw, file)
        print('Static cover art downloaded successfully.')
    else:
        print(f'Failed to download static cover art. Status code: {response.status_code}')

def process_search_results(songs, song_title, song_artist):
    log = {"searched_songs": [], "selected_match": None, "static_cover_match": None, "animated_cover_match": None}
    animated_cover_downloaded = False
    selected_match_found = False

    for song in songs:
        bg_color = song['attributes']['artwork']['bgColor']
        text_colors = {
            'textColor1': song['attributes']['artwork']['textColor1'],
            'textColor2': song['attributes']['artwork']['textColor2'],
            'textColor3': song['attributes']['artwork']['textColor3'],
            'textColor4': song['attributes']['artwork']['textColor4'],
        }

        song_info = {
            "title": song['attributes']['name'],
            "artist": song['attributes']['artistName'],
            "album": song['attributes'].get('albumName', 'N/A'),
            "has_lyrics": song['attributes'].get('lyrics', False),
            "color_data": {
                'bgColor': bg_color,
                'textColors': text_colors
            }
        }
        log["searched_songs"].append(song_info)

        if song['attributes']['name'].lower() == song_title.lower() and song['attributes']['artistName'].lower() == song_artist.lower():
            if not selected_match_found:
                log["selected_match"] = song_info
                selected_match_found = True

            download_static_cover_art(song)
            log["static_cover_match"] = song_info

            if download_animated_cover_art(song['attributes']['url']):
                animated_cover_downloaded = True
                log["animated_cover_match"] = song_info
                break

    if not animated_cover_downloaded and selected_match_found:
        print("No animated cover art found for the correct match.")
    
    return log

def main():
    song_title = input("Enter song title: ")
    song_artist = input("Enter artist name: ")
    songs = search_song(song_title, song_artist, APPLE_MUSIC_API_KEY)

    if songs:
        log = process_search_results(songs, song_title, song_artist)
    else:
        print("No song found.")
        log = {}

    with open(os.path.join(OUTPUT_DIR, 'song_search_log.json'), 'w') as log_file:
        json.dump(log, log_file, indent=4)
    print(f"Log file created: {os.path.join(OUTPUT_DIR, 'song_search_log.json')}")

if __name__ == "__main__":
    main()
'''