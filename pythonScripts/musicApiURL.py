
#Code works to use api token and return song information. one of the song versions URL matches to animated album cover art


import requests 

# API credentials
api_key = 'eyJhbGciOiJFUzI1NiIsImtpZCI6IjYyMlcyTVVVV1EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJVNEdMUUdGTlQzIiwiaWF0IjoxNjk3MjQ4NDQ4LCJleHAiOjE3MTAyMDg0NDh9.XMe-WEuuAJS_LOirXG6yU8CZW1RL6Lw4cwxhc405rvZm_LesEsaLoqNnZ9l_n3SQ0eOqUQEsWXEPNZYJ5wdZXw'
headers = {'Authorization': 'Bearer ' + api_key}

import json

def get_song_url(song_name, artist_name):

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

  # Save the JSON response to a file
  with open('response.json', 'w') as f:
    json.dump(search_data, f)

  # Print the keys in the 'results' dictionary
  print(f"Keys in 'results': {search_data['results'].keys()}")

  # Handle no results
  if 'songs' not in search_data['results'] or not search_data['results']['songs']['data']:
    print('No search results found')
    return

  # Print the 'songs' data
  print(f"Songs data: {search_data['results']['songs']}")

  # Print details of each song in the search results
  songs_data = search_data['results']['songs']['data']
  for song in songs_data:
    print(f"Song ID: {song['id']}")
    print(f"Song Name: {song['attributes']['name']}")
    print(f"Artist Name: {song['attributes']['artistName']}")
    print(f"Album Name: {song['attributes']['albumName']}")
    print(f"Song URL: {song['attributes']['url']}")
    print(f"Artwork URL: {song['attributes']['artwork']['url']}")
    print(f"Release Date: {song['attributes']['releaseDate']}")
    print(f"Duration (in ms): {song['attributes']['durationInMillis']}")
    print(f"Genre: {', '.join(song['attributes']['genreNames'])}")
    print(f"Composer Name: {song['attributes']['composerName']}")
    print(f"Preview URL: {song['attributes']['previews'][0]['url']}")
    print("\n")




if __name__ == '__main__':

  song_title = input("Enter song title: ")
  artist_name = input("Enter artist name: ")

  print(get_song_url(song_title, artist_name))
