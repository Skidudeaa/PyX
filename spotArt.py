import os                                                                                                                                           
import requests                                                                                                                                     
from PIL import Image                                                                                                                               
import spotipy                                                                                                                                      
from spotipy.oauth2 import SpotifyOAuth                                                                                                             
                                                                                                                                                       
   # Set your Spotify Developer account's client_id, client_secret, and redirect_uri                                                                   
os.environ['SPOTIPY_CLIENT_ID'] = '4f30d594b2e04de7bf3e52debefc6e40'                                                                                                  
os.environ['SPOTIPY_CLIENT_SECRET'] = 'c6ebf2fc5e8f406c9bb7be72f0779751'                                                                                          
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:3000/'                                                                                            
                                                                                                                                                       
   # Set your Spotify username                                                                                                                         
username = '1249386873'                                                                                                                          
                                                                                                                                                       
   # Set the artist name                                                                                                                               
artist_name = 'Taylor Swift'                                                                                                                     
      
      # Create a SpotifyOAuth object                                                                                                                      
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope='user-library-read'))                                                                          
      
      # Search for the artist                                                                                                                             
results = sp.search(q='artist:' + artist_name, type='artist')                                                                                       
      
      # Get the artist data                                                                                                                               
artist = results['artists']['items'][0]                                                                                                             
      
      # Get the images                                                                                                                                    
images = artist['images']                                                                                                                           
      
      # Save the images                                                                                                                                   
for i, image in enumerate(images):                                                                                                                  
   filename = f'artist_image_{i}.jpg'                                                                                                              
   response = requests.get(image['url'], stream=True)                                                                                              
   with open(filename, 'wb') as out_file:                                                                                                          
            out_file.write(response.content)                                                                                                            
   img = Image.open(filename)                                                                                                                      
   img.show()                                                                                                                                      
   print(f'Saved image: {filename}')  