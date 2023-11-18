"""
This script provides a set of utilities for music data retrieval and processing. It fetches song data, 
including artwork and color data, from the Apple Music API based on a user-provided song title and artist. 
The script also includes functions for downloading video content from a given URL, parsing .m3u8 files, 
and returning the URLs of the video segments. Additionally, it provides functionality to download song artwork 
and the first video segment if an animated cover is found. The color data and artwork are stored locally.


you will    
  need to replace with actual code based on the structure of the Apple Music API response and the specifics of    
  your environment.                                                                                               
                                                                                                                  
                                                                                                                  
   import requests                                                                                                
   import os                                                                                                      
   from urllib.parse import urljoin                                                                               
                                                                                                                  
   # Define the helper functions required for the modifications                                                   
                                                                                                                  
   def is_correct_song(song, title, artist):                                                                      
       # Check if the song title and artist match the user input                                                  
       return song['attributes']['name'].lower() == title.lower() and song['attributes']['artistName'].lower()    
   artist.lower()                                                                                                 
                                                                                                                  
   def download_static_cover_art(song):                                                                           
       # Download the highest quality static artwork                                                              
       artwork_url = song['attributes']['artwork']['url'].replace('{w}', '3000').replace('{h}', '3000')           
       response = requests.get(artwork_url, stream=True)                                                          
       if response.status_code == 200:                                                                            
           with open('static_artwork.jpg', 'wb') as file:                                                         
               for chunk in response.iter_content(chunk_size=128):                                                
                   file.write(chunk)                                                                              
           print('Static cover art downloaded successfully.')                                                     
       else:                                                                                                      
           print(f'Failed to download static cover art. Status code: {response.status_code}')                     
                                                                                                                  
   def find_animated_cover_art(song):                                                                             
       # Placeholder function to find animated cover art URL                                                      
       # The actual implementation will depend on how the animated cover art is identified in the API response    
       # This might involve checking for a specific attribute or pattern in the song data                         
       # Example: return song.get('attributes', {}).get('animatedArtworkUrl')                                     
       return None                                                                                                
                                                                                                                  
   def is_same_song(song1, song2):                                                                                
       # Check if two song entries refer to the same song                                                         
       return song1['attributes']['name'].lower() == song2['attributes']['name'].lower() and                      
   song1['attributes']['artistName'].lower() == song2['attributes']['artistName'].lower()                         
                                                                                                                  
   def download_animated_cover_art(url):                                                                          
       # Download the animated cover art                                                                          
       response = requests.get(url, stream=True)                                                                  
       if response.status_code == 200:                                                                            
           with open('animated_artwork.mp4', 'wb') as file:                                                       
               for chunk in response.iter_content(chunk_size=128):                                                
                   file.write(chunk)                                                                              
           print('Animated cover art downloaded successfully.')                                                   
       else:                                                                                                      
           print(f'Failed to download animated cover art. Status code: {response.status_code}')                   
                                                                                                                  
   # Sample user input for testing                                                                                
   user_input_title = 'Drowning'                                                                                  
   user_input_artist = 'A Boogie Wit da Hoodie'                                                                   
                                                                                                                  
   # Make the API call to the Apple Music API search endpoint                                                     
   # Replace 'headers' and 'params' with actual data required for the API call                                    
   response = requests.get('https://api.music.apple.com/v1/catalog/us/search', headers=headers, params=params)    
                                                                                                                  
   # Process the API response                                                                                     
   if response.status_code == 200:                                                                                
       json_response = response.json()                                                                            
       song_data = json_response['results']['songs']['data']                                                      
                                                                                                                  
       # Implement the modified script logic                                                                      
       correct_song = None                                                                                        
       animated_cover_art_url = None                                                                              
                                                                                                                  
       # Identify the correct song match                                                                          
       for song in song_data:                                                                                     
           if is_correct_song(song, user_input_title, user_input_artist):                                         
               correct_song = song                                                                                
               break                                                                                              
                                                                                                                  
       # Download static cover art for the correct match                                                          
       if correct_song:                                                                                           
           download_static_cover_art(correct_song)                                                                
                                                                                                                  
           # Check for animated cover art for the correct match                                                   
           animated_cover_art_url = find_animated_cover_art(correct_song)                                         
                                                                                                                  
       # If no animated cover art for the correct match, find in subsequent matches                               
       if not animated_cover_art_url:                                                                             
           for song in song_data:                                                                                 
               if song != correct_song and is_same_song(song, correct_song):                                      
                   animated_cover_art_url = find_animated_cover_art(song)                                         
                   if animated_cover_art_url:                                                                     
                       break                                                                                      
                                                                                                                  
       # Download only the animated cover from the subsequent match if it exists                                  
       if animated_cover_art_url:                                                                                 
           download_animated_cover_art(animated_cover_art_url)                                                    
   else:                                                                                                          
       print(f"Failed to make API call. Status code: {response.status_code}")                                     
       # Handle error appropriately                                                                               
                                                                                                                  
                                                                                                                  
  This script includes the logic for making an API call to the Apple Music API, processing the response to        
  identify the correct song match, downloading static cover art, checking for animated cover art, and handling    
  subsequent matches if necessary.                                                                                
                                                                                                                  
  Please make sure to replace the placeholders with actual data and code as needed, and implement the             
  find_animated_cover_art function based on the actual response from the Apple Music API. Test the script         
  thoroughly with various inputs to ensure it operates as expected. 

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

# Initialization
GENIUS_API_KEY = "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr"
MUSIXMATCH_USER_TOKEN = "190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95"
APPLE_MUSIC_API_KEY = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw"

headers = {'Authorization': 'Bearer ' + APPLE_MUSIC_API_KEY}
warnings.filterwarnings("ignore", category=FutureWarning)


import os
import re
import requests
import shutil
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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

# Download image
def download_image(image_url, image_path):
    response = requests.get(image_url, stream=True)
    with open(image_path, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)
    del response

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


# Search song and get artwork and color data
def search_song(song_title, developer_token):
    headers = {
        'Authorization': 'Bearer ' + developer_token,
    }

    params = (
        ('term', song_title),
        ('limit', '10'),
    )

    response = requests.get('https://api.music.apple.com/v1/catalog/us/search', headers=headers, params=params)
    json_response = response.json()
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

    # Save color data to JSON file
    color_data = {
        'bgColor': bg_color,
        'textColors': text_colors
    }

    with open('color_data.json', 'w') as json_file:
        json.dump(color_data, json_file)

    return bg_color, text_colors


# Main Function
developer_token = 'eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw'  # Replace with your actual developer token
song_title = input("Enter the song title and artist (e.g., 'paranoid by post malone'): ")
bg_color, text_colors = search_song(song_title, developer_token)

print("Background Color:", bg_color)
print("Text Colors:", text_colors)
