#!/usr/bin/env python3

import requests

def get_artist_songs(artist_name, num_songs):
	# Replace 'YOUR_ACCESS_TOKEN' with your actual Genius API access token
	access_token = '6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr'
	
	# Set the API endpoint URL
	url = f'https://api.genius.com/search?q={artist_name}'
	
	# Set the request headers with the access token
	headers = {'Authorization': f'Bearer {access_token}'}
	
	# Send the GET request to the API
	response = requests.get(url, headers=headers)
	
	# Check if the request was successful
	if response.status_code == 200:
		# Get the JSON response
		data = response.json()
		
		# Get the list of songs from the response
		songs = data['response']['hits']
		
		# Sort the songs by popularity
		songs.sort(key=lambda x: x['result']['stats']['pageviews'], reverse=True)
		
		# Return the specified number of popular songs
		return [song['result']['full_title'] for song in songs[:num_songs]]
	
	else:
		# Print an error message if the request failed
		print(f'Request failed with status code {response.status_code}')
		return []
	
# Example usage
artist_name = 'Coldplay'
num_songs = 5

popular_songs = get_artist_songs(artist_name, num_songs)
for song in popular_songs:
	print(song)