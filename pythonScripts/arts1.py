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

    songs = [(song['result']['full_title'], song['result']['stats']['pageviews'], song['result']['song_art_image_url'])
             for song in json_data['response']['hits']]
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

def main():
    client_access_token = 'aSlsYtH2i1gJvJSnUHeGzmEf93JrrsGJGPA4cNc78L0cFnSKvIhBKDMsDquTHE7q'
    artist_name = input("Please enter the artist name: ")
    url = input("Please enter the video URL: ")

    # Fetch and save the album art for the artist
    songs = fetch_songs(artist_name, client_access_token)
    save_album_art(songs, artist_name)

    # Download the video and album art for the video
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

if __name__=="__main__":
    main()

    
   
