import requests
from bs4 import BeautifulSoup

def search_genius(term):
    genius_url = f"https://genius.com/search?q={term}"
    response = requests.get(genius_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    songs = soup.select(".tracks-list .title")
    if not songs:
        print("No search results found.")
    else:
        for song in songs:
            print(song.text)

if __name__ == "__main__":
    term = input("Enter a search term: ")
    search_genius(term)