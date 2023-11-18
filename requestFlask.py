#

import requests

url = 'http://127.0.0.1:5000/get-song-data'
params = {
    'title': 'wishing well',
    'artist': 'juice wrld'
}

response = requests.get(url, params=params)
print(response.json())
