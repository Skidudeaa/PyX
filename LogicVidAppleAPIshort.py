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

