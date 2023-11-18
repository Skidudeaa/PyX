#!/usr/bin/env python3



import requests
import json

GENIUS_API_KEY = "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr"

def get_song_id(search_term, api_key):
	url = "https://api.genius.com/search"
	headers = {"Authorization": f"Bearer {api_key}"}
	params = {"q": search_term}
	response = requests.get(url, headers=headers, params=params)
	response_json = response.json()
	if 'response' not in response_json or 'hits' not in response_json['response'] or not response_json['response']['hits']:
		print(f"No results found for '{search_term}'. Please try again with a different search term.")
		return None
	song_id = response_json['response']['hits'][0]['result']['id']
	return song_id

def get_song_details(song_id, api_key):
	url = f"https://api.genius.com/songs/{song_id}"
	headers = {"Authorization": f"Bearer {api_key}"}
	response = requests.get(url, headers=headers)
	song_details = response.json()['response']['song']
	return song_details

def main():
	artist_name = input("Enter artist name: ")
	song_title = input("Enter song title: ")
	search_term = f"{artist_name} {song_title}"
	song_id = get_song_id(search_term, GENIUS_API_KEY)
	if song_id is not None:
		song_details = get_song_details(song_id, GENIUS_API_KEY)
		with open('song_details.json', 'w') as f:
			json.dump(song_details, f, indent=4)
			
if __name__ == "__main__":
	main()