#!/usr/bin/env python3

import requests
import json
from summarizer.bert import Summarizer
from summarizer import Summarizer
from nltk.tokenize import sent_tokenize
import warnings
from typing import Optional
warnings.filterwarnings("ignore", category=FutureWarning)

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

# Function definitions for Genius API interactions 
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


def get_song_details(song_id, api_key):
	url = f"https://api.genius.com/songs/{song_id}"
	headers = {"Authorization": f"Bearer {api_key}"}
	response = requests.get(url, headers=headers)
	song_details = response.json()['response']['song']
	
	# Extract the song description from the response
	song_description_dom = song_details["description"]["dom"]["children"]
	
	# Initialize an empty string to hold the song description
	song_description = ""
	
	# Traverse the 'children' list
	for child in song_description_dom:
		# Check if the child is a dictionary (i.e., a 'tag')
		if isinstance(child, dict):
			# Check if the 'tag' is a 'p' (i.e., a paragraph)
			if child["tag"] == "p":
				# Append the text of the paragraph to the song description
				for text in child["children"]:
					if isinstance(text, str):
						song_description += text + " "
					elif isinstance(text, dict) and 'children' in text:
						for subtext in text['children']:
							if isinstance(subtext, str):
								song_description += subtext + " "
								
	# Add the song description to the song details
	song_details['description'] = song_description.strip()
	
	return song_details


def get_referents_and_annotations(song_id, api_key, limit=7):
	url = f"https://api.genius.com/referents?song_id={song_id}"
	headers = {"Authorization": f"Bearer {api_key}"}
	response = requests.get(url, headers=headers)
	referents = response.json()['response']['referents']
	verified_annotations = [r for r in referents if r['annotations'][0]['verified']]
	community_annotations = [r for r in referents if not r['annotations'][0]['verified']]
	top_referents = sorted(verified_annotations + community_annotations, key=lambda x: x['annotations'][0]['votes_total'], reverse=True)[:limit]
	return top_referents

def get_song_details_and_annotations(song_name, api_key):
	# Initialize an empty dictionary to store the song details and annotations
	song_data = {}
	song_id = get_song_id(song_name, api_key)
	song_details = get_song_details(song_id, api_key)
	referents = get_referents_and_annotations(song_id, api_key)
	# Populate the song details into the dictionary
	song_data['title'] = song_details['title']
	song_data['artist'] = song_details['primary_artist']['name']
	song_data['album'] = song_details['album']['name'] if song_details['album'] else None
	song_data['release_date'] = song_details['release_date']
	song_data['description'] = song_details['description']  # Add the song description
	annotations = []
	# Loop through each referent to extract and store annotations
	for referent in referents:
		annotation_text = referent['annotations'][0]['body']['dom']['children']
		annotation_text_str = extract_text(annotation_text)
		semantic_summary = semantic_truncate(annotation_text_str)
		truncated_annotation = semantic_summary[:600]  # Limit to 600 characters
		annotations.append({
			'referent': referent['fragment'],
			'annotation': truncated_annotation
		})
		
	song_data['annotations'] = annotations
	return song_data


# Musixmatch class definitions and functions
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
		parsed_lyrics = [{"timestamp": round(float(ts[1:].split(':')[0])*60 + float(ts[1:].split(':')[1]), 1), "lyric": l} for ts, l in (line.split('] ') for line in lyrics.split('\n') if line)]
		lyrics_data = {
			"lyrics": parsed_lyrics
		}
	return lyrics_data


if __name__ == "__main__":
	user_token = "190523f77464fba06fa5f82a9bfab0aa9dc201244ecf5124a06d95"
	api_key = "6IJtS4Xta8IPcEPwmC-8YVOXf5Eoc4RHwbhWINDbzomMcFVXQVxbVQapsFxzKewr"
	search_term = input("Enter the song search term: ")
	
	lyrics_data = fetch_lyrics_with_timestamps(user_token, search_term)
	song_data = get_song_details_and_annotations(search_term, api_key)
	
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
		
		