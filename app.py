from flask import Flask, render_template, request, redirect, url_for, jsonify
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
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching data from TMDB: {e}")
        logger.error(f"URL: {response.url}")
        logger.error(f"Status Code: {response.status_code}")
        logger.error(f"Response Text: {response.text}")
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
    
    # Fetch trending anime
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
    
    # Fetch trending manga
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
        return render_template('error.html', message="Unable to fetch data"), 500
    
    return render_template('home.html', 
                           trending=trending.get('results', [])[:10],
                           popular_movies=popular_movies.get('results', [])[:10],
                           popular_tv=popular_tv.get('results', [])[:10],
                           trending_anime=trending_anime['data']['Page']['media'],
                           trending_manga=trending_manga['data']['Page']['media'])

@app.route('/movies')
def movies():
    page = request.args.get('page', 1, type=int)
    popular_movies = get_tmdb_data("/movie/popular", params={"page": page})
    
    if not popular_movies:
        return render_template('error.html', message="Unable to fetch movie data"), 500
    
    return render_template('movies.html', 
                           movies=popular_movies.get('results', []),
                           current_page=page,
                           total_pages=popular_movies.get('total_pages', 1))

@app.route('/series')
def series():
    page = request.args.get('page', 1, type=int)
    popular_tv = get_tmdb_data("/tv/popular", params={"page": page})
    
    if not popular_tv:
        return render_template('error.html', message="Unable to fetch TV series data"), 500
    
    return render_template('series.html', 
                           series=popular_tv.get('results', []),
                           current_page=page,
                           total_pages=popular_tv.get('total_pages', 1))

@app.route('/search')
def search():
    query = request.args.get('query', '')
    if not query:
        return render_template('search.html', results=[], query='')

    # Search for movies and TV shows
    tmdb_results = get_tmdb_data("/search/multi", params={"query": query})

    # Updated AniList query
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
                bannerImage
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
                bannerImage
                type
            }
        }
    }
    '''
    anilist_variables = {'search': query}
    anilist_results = get_anilist_data(anilist_query, anilist_variables)

    # Combine and process results
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
                    'image': {
                        'large': item['coverImage']['large'],
                        'medium': item['coverImage']['medium'],
                        'banner': item['bannerImage']
                    },
                    'type': item['type']
                })

    return render_template('search.html', results=combined_results, query=query)

# Add this route for debugging
@app.route('/debug_search')
def debug_search():
    query = request.args.get('query', '')
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
                    medium
                }
                type
            }
        }
    }
    '''
    anilist_variables = {'search': query}
    anilist_results = get_anilist_data(anilist_query, anilist_variables)
    
    debug_info = {
        'query': query,
        'tmdb_results': tmdb_results,
        'anilist_results': anilist_results
    }
    return jsonify(debug_info)

@app.route('/watch/<string:media_type>/<int:id>')
def watch(media_type, id):
    if media_type not in ['movie', 'tv']:
        return render_template('error.html', message="Invalid media type"), 400
    
    # Fetch detailed item information including credits, videos, reviews, and similar content
    item = get_tmdb_data(f"/{media_type}/{id}", params={"append_to_response": "credits,videos,reviews,similar"})
    if not item:
        return render_template('error.html', message="Item not found"), 404
    
    return render_template('watch.html', item=item, media_type=media_type)

@app.route('/stream/<string:media_type>/<int:id>')
def stream(media_type, id):
    if media_type not in ['movie', 'tv']:
        return render_template('error.html', message="Invalid media type"), 400
    
    item = get_tmdb_data(f"/{media_type}/{id}")
    if not item:
        return render_template('error.html', message="Item not found"), 404
    
    stream_url = f"https://embed.su/embed/{media_type}/{id}"
    if media_type == 'tv':
        stream_url += "/1/1"  # Default to first season, first episode
    
    return render_template('stream.html', item=item, stream_url=stream_url, media_type=media_type)

@app.route('/anime')
def anime():
    page = request.args.get('page', 1, type=int)
    
    anime_query = '''
    query ($page: Int) {
        Page(page: $page, perPage: 20) {
            pageInfo {
                total
                currentPage
                lastPage
                hasNextPage
                perPage
            }
            media(type: ANIME, sort: POPULARITY_DESC) {
                id
                title {
                    romaji
                    english
                }
                coverImage {
                    large
                }
                episodes
                genres
                averageScore
            }
        }
    }
    '''
    variables = {'page': page}
    anime_data = get_anilist_data(anime_query, variables)
    
    if not anime_data:
        return render_template('error.html', message="Unable to fetch anime data"), 500
    
    return render_template('anime.html', 
                           anime_list=anime_data['data']['Page']['media'],
                           page_info=anime_data['data']['Page']['pageInfo'])

@app.route('/anime/<int:id>')
def anime_details(id):
    anime_query = '''
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            id
            title {
                romaji
                english
            }
            coverImage {
                large
            }
            bannerImage
            description
            episodes
            genres
            averageScore
            startDate {
                year
                month
                day
            }
            endDate {
                year
                month
                day
            }
            status
            studios {
                nodes {
                    name
                }
            }
            characters(sort: ROLE, perPage: 6) {
                nodes {
                    name {
                        full
                    }
                    image {
                        medium
                    }
                }
            }
        }
    }
    '''
    variables = {'id': id}
    anime_data = get_anilist_data(anime_query, variables)
    
    if not anime_data or 'errors' in anime_data:
        return render_template('error.html', message="Unable to fetch anime details"), 500
    
    return render_template('anime_details.html', anime=anime_data['data']['Media'])

@app.route('/anime/watch/<int:id>/<int:episode>')
def watch_anime(id, episode):
    anime_query = '''
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            id
            title {
                romaji
                english
            }
            episodes
            coverImage {
                large
            }
        }
    }
    '''
    variables = {'id': id}
    anime_data = get_anilist_data(anime_query, variables)
    
    if not anime_data or 'errors' in anime_data:
        return render_template('error.html', message="Unable to fetch anime details"), 500
    
    anime = anime_data['data']['Media']
    
    # If episodes is None, set it to a default value (e.g., 12 or 13)
    if anime['episodes'] is None:
        anime['episodes'] = 13  # You can adjust this default value

    stream_url = f"https://vidsrc.icu/embed/anime/{id}/{episode}"
    
    return render_template('watch_anime.html', anime=anime, episode=episode, stream_url=stream_url)

@app.route('/manga')
def manga():
    page = request.args.get('page', 1, type=int)
    
    manga_query = '''
    query ($page: Int) {
        Page(page: $page, perPage: 20) {
            pageInfo {
                total
                currentPage
                lastPage
                hasNextPage
                perPage
            }
            media(type: MANGA, sort: POPULARITY_DESC) {
                id
                title {
                    romaji
                    english
                }
                coverImage {
                    large
                }
                chapters
                volumes
                genres
                averageScore
            }
        }
    }
    '''
    variables = {'page': page}
    manga_data = get_anilist_data(manga_query, variables)
    
    if not manga_data:
        return render_template('error.html', message="Unable to fetch manga data"), 500
    
    return render_template('manga.html', 
                           manga_list=manga_data['data']['Page']['media'],
                           page_info=manga_data['data']['Page']['pageInfo'])

@app.route('/manga/<int:id>')
def manga_details(id):
    manga_query = '''
    query ($id: Int) {
        Media(id: $id, type: MANGA) {
            id
            title {
                romaji
                english
            }
            coverImage {
                large
            }
            bannerImage
            description
            chapters
            volumes
            genres
            averageScore
            startDate {
                year
                month
                day
            }
            endDate {
                year
                month
                day
            }
            status
            staff {
                edges {
                    node {
                        name {
                            full
                        }
                    }
                    role
                }
            }
            characters(sort: ROLE, perPage: 6) {
                nodes {
                    name {
                        full
                    }
                    image {
                        medium
                    }
                }
            }
        }
    }
    '''
    variables = {'id': id}
    manga_data = get_anilist_data(manga_query, variables)
    
    if not manga_data or 'errors' in manga_data:
        return render_template('error.html', message="Unable to fetch manga details"), 500
    
    return render_template('manga_details.html', manga=manga_data['data']['Media'])

@app.route('/manga/read/<int:id>/<int:chapter>')
def read_manga(id, chapter):
    manga_query = '''
    query ($id: Int) {
        Media(id: $id, type: MANGA) {
            id
            title {
                romaji
                english
            }
            coverImage {
                large
            }
            chapters
        }
    }
    '''
    variables = {'id': id}
    manga_data = get_anilist_data(manga_query, variables)
    
    if not manga_data:
        return render_template('error.html', message="Unable to fetch manga details. Please try again later."), 500
    
    manga = manga_data.get('data', {}).get('Media')
    if not manga:
        return render_template('error.html', message="Manga not found"), 404
    
    # Ensure chapter is within valid range
    total_chapters = manga.get('chapters') or 9999  # Use a large number if chapters are unknown
    chapter = max(1, min(chapter, total_chapters))  # Clamp chapter between 1 and total_chapters
    
    read_url = f"https://vidsrc.icu/embed/manga/{id}/{chapter}"
    
    return render_template('read_manga.html', manga=manga, chapter=chapter, read_url=read_url)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message="Page not found"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', message="Internal server error"), 500

if __name__ == '__main__':
    # Use the PORT environment variable provided by the deployment platform, or default to 5000
    port = int(os.environ.get("PORT", 5000))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port)
