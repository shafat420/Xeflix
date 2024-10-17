from flask import Flask, request, jsonify
import requests
import logging
import os

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TMDB_API_KEY = "61e2290429798c561450eb56b26de19b"
TMDB_API_READ_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI2MWUyMjkwNDI5Nzk4YzU2MTQ1MGViNTZiMjZkZTE5YiIsInN1YiI6IjY2YjNjYmFlNjJjZWY5NDg1ZmI1MWRmYiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.Zze5HI8HKcaXn6QacG9adcK6J_4AptnGCoF0b4kvst4"

ANILIST_API_URL = "https://graphql.anilist.co"

def get_tmdb_data(endpoint, params=None):
    base_url = "https://api.themoviedb.org/3"
    headers = {
        "Authorization": f"Bearer {TMDB_API_READ_ACCESS_TOKEN}",
        "accept": "application/json"
    }
    
    if params is None:
        params = {}
    params['api_key'] = TMDB_API_KEY
    
    try:
        response = requests.get(f"{base_url}{endpoint}", headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching data from TMDB: {e}")
        return None

def get_anilist_data(query, variables=None):
    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from AniList: {e}")
        return None

@app.route('/')
def home():
    trending = get_tmdb_data("/trending/all/week")
    popular_movies = get_tmdb_data("/movie/popular")
    popular_tv = get_tmdb_data("/tv/popular")
    
    anime_query = '''
    query {
        Page(page: 1, perPage: 10) {
            media(type: ANIME, sort: TRENDING_DESC) {
                id
                title {
                    romaji
                    english
                }
                coverImage {
                    large
                }
            }
        }
    }
    '''
    trending_anime = get_anilist_data(anime_query)
    
    manga_query = '''
    query {
        Page(page: 1, perPage: 10) {
            media(type: MANGA, sort: TRENDING_DESC) {
                id
                title {
                    romaji
                    english
                }
                coverImage {
                    large
                }
            }
        }
    }
    '''
    trending_manga = get_anilist_data(manga_query)
    
    if not all([trending, popular_movies, popular_tv, trending_anime, trending_manga]):
        return jsonify({"error": "Unable to fetch data"}), 500
    
    return jsonify({
        "trending": trending.get('results', [])[:10],
        "popular_movies": popular_movies.get('results', [])[:10],
        "popular_tv": popular_tv.get('results', [])[:10],
        "trending_anime": trending_anime['data']['Page']['media'],
        "trending_manga": trending_manga['data']['Page']['media']
    })

@app.route('/search')
def search():
    query = request.args.get('query', '')
    if not query:
        return jsonify({"results": [], "query": ''})

    tmdb_results = get_tmdb_data("/search/multi", params={"query": query})
    
    anilist_query = '''
    query ($search: String) {
        anime: Page(page: 1, perPage: 10) {
            media(type: ANIME, search: $search) {
                id
                title {
                    romaji
                    english
                }
                coverImage {
                    large
                    medium
                }
                type
            }
        }
        manga: Page(page: 1, perPage: 10) {
            media(type: MANGA, search: $search) {
                id
                title {
                    romaji
                    english
                }
                coverImage {
                    large
                    medium
                }
                type
            }
        }
    }
    '''
    anilist_results = get_anilist_data(anilist_query, {"search": query})

    combined_results = []
    if tmdb_results and 'results' in tmdb_results:
        for item in tmdb_results['results']:
            if item['media_type'] in ['movie', 'tv']:
                combined_results.append({
                    'id': item['id'],
                    'title': item.get('title') or item.get('name'),
                    'image': f"https://image.tmdb.org/t/p/w200{item['poster_path']}" if item.get('poster_path') else None,
                    'type': item['media_type'].upper()
                })

    if anilist_results and 'data' in anilist_results:
        for media_type in ['anime', 'manga']:
            for item in anilist_results['data'][media_type]['media']:
                combined_results.append({
                    'id': item['id'],
                    'title': item['title']['english'] or item['title']['romaji'],
                    'image': item['coverImage']['large'],
                    'type': item['type']
                })

    return jsonify({"results": combined_results, "query": query})

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Page not found"}), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
