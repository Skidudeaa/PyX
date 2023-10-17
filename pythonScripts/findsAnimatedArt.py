


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

# API credentials
api_key = 'eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw'
headers = {'Authorization': 'Bearer ' + api_key}

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
            # Sort the playlists by resolution (from highest to lowest)
            playlists.sort(key=lambda p: p.stream_info.resolution[0], reverse=True)
            # Return the playlist with the highest resolution
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

def get_song_urls(song_name, artist_name):
  # Search for song  
  search_api = 'https://api.music.apple.com/v1/catalog/us/search'
  search_params = {'term': song_name + ' ' + artist_name, 'types': 'songs'}
  response = requests.get(search_api, params=search_params, headers=headers)
  
  # Check the status code of the response
  print(f"Response status code: {response.status_code}")

  # If the status code is not 200, print the response text and return
  if response.status_code != 200:
    print(f"Response text: {response.text}")
    return

  search_data = response.json()

  # Handle no results
  if 'songs' not in search_data['results'] or not search_data['results']['songs']['data']:
    print('No search results found')
    return

  # Return all unique song URLs
  songs_data = search_data['results']['songs']['data']
  return list(set(song['attributes']['url'] for song in songs_data))

if __name__ == '__main__':
    song_title = input("Enter song title: ")
    artist_name = input("Enter artist name: ")

    # Get all song URLs
    song_urls = get_song_urls(song_title, artist_name)

    # Iterate over song URLs
    for url in song_urls:
        # Fetch the playlist URL
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
                    break  # Stop after successfully downloading a video segment