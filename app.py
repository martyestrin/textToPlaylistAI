from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import openai
import os
from flask_cors import CORS
from dotenv import load_dotenv
import requests

app = Flask(__name__)

app.config['SESSION_COOKIE_NAME'] = 'Spotify OpenAI Cookie'
app.secret_key = os.urandom(24)
TOKEN_INFO = 'token_info'

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
CORS(app, resources={r"*": {"origins": "https://aispotifyplaylists.martinestrin.com"}})

@app.route('/')
def home():
    if 'token_info' in session:
        return redirect(url_for('generate_playlist'))
    else:
        auth_url = create_spotify_oauth().get_authorize_url()
        return redirect(auth_url)

@app.route('/redirect')
def redirect_page():
    code = request.args.get('code')
    token_info = create_spotify_oauth().get_access_token(code)

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_info = sp.me()
    user_id = user_info['id']

    session[TOKEN_INFO] = token_info
    session['user_id'] = user_id

    

    code2 = request.args.get('code')
    if code2:
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': os.getenv('SPOTIFY_REDIRECT_URI'),
            'client_id': os.getenv('SPOTIFY_CLIENT_ID'),
            'client_secret': os.getenv('SPOTIFY_CLIENT_SECRET')
        }
        token_response = requests.post('https://accounts.spotify.com/api/token', data=token_data)
        token_info = token_response.json()
        session['access_token'] = token_info.get('access_token')
        access_token = session.get('access_token')
        user_data = get_user_data(access_token)
        print("USER DATA")
        print(user_data)

    
    
    
    

    return redirect(url_for('generate_playlist', _external=True))

def get_user_data(access_token):
    url = 'https://api.spotify.com/v1/me'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    return response.json()

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=os.getenv('SPOTIPY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
        redirect_uri=url_for('redirect_page', _external=True),
        scope='user-library-read playlist-modify-private playlist-modify-public'
    )

@app.route('/generate_playlist', methods=['GET', 'POST'])
def generate_playlist():
    if 'token_info' not in session:
        return redirect(url_for('home'))
    
    token_info = session[TOKEN_INFO]
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    if request.method == 'POST':
        playlist_name = request.form.get('playlist_name')
        prompt = request.form.get('prompt')

        try:
            completion = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=
                [
                    {
                        "role": "system",
                        "content": ("Return a playlist of songs that fits the following description:\n" + prompt +
                                    "Do not provide anything in your response besides the names of the songs, each seperated by a comma. " +
                                    "No other punctuation, newline characters or text.")
                    }
                ]
            )
            response = completion.choices[0].message.content

            songs = response.strip().split(',')
            songs = set(response.split(','))
            playlist_id = create_playlist(sp, songs, playlist_name)
            
            return redirect(url_for('display_playlist', playlist_id=playlist_id))
        
        except Exception as e:
            return jsonify({"error": str(e)})

    return render_template('index.html')

def create_playlist(sp, songs, playlist_name):
    user_info = sp.me()
    print("USER INFO")
    print(user_info)
    print("MY USER INFO")
    user_id = session['user_id']
    print(user_id)
    playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False, collaborative=False)

    track_uris = []
    for song in songs:
        track_result = sp.search(q=song, type='track', limit=1)
        if track_result['tracks']['items']:
            track_uri = track_result['tracks']['items'][0]['uri']
            track_uris.append(track_uri)

    if track_uris:
        sp.user_playlist_add_tracks(user=user_id, playlist_id=playlist['id'], tracks=track_uris)
        return playlist['id']
    else:
        return "No valid songs found. Please check the song list and try again."

@app.route('/display_playlist/<playlist_id>', methods=['GET'])
def display_playlist(playlist_id):
    if 'token_info' not in session:
        return redirect(url_for('home'))
    
    token_info = session[TOKEN_INFO]
    sp = spotipy.Spotify(auth=token_info['access_token'])
    playlist = sp.playlist(playlist_id)
    return render_template('playlist.html', playlist=playlist)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8888))
    app.run(debug=True, port=port)

