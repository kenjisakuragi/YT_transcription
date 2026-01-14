import argparse
import time
import random
import logging
import os
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

import pandas as pd
from tqdm import tqdm
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Debug: Check installed version
try:
    import youtube_transcript_api
    logger.info(f"youtube-transcript-api version: {youtube_transcript_api.__version__}")
    logger.info(f"YouTubeTranscriptApi attributes: {dir(YouTubeTranscriptApi)}")
except Exception as e:
    logger.error(f"Debug import failed: {e}")

class YouTubeTranscriptFetcher:
    """
    A class to fetch YouTube video metadata using YouTube Data API and transcripts using youtube-transcript-api.
    """

    def __init__(self, api_key: str, languages: List[str] = None):
        """
        Initialize the fetcher.

        Args:
            api_key (str): YouTube Data API Key.
            languages (List[str]): List of language codes to prioritize (e.g., ['ja', 'en']).
        """
        self.languages = languages if languages else ['ja', 'en']
        self.youtube = build('youtube', 'v3', developerKey=api_key)

    def _extract_id_from_url(self, url: str) -> Dict[str, str]:
        """
        Parse URL to determine type (video, playlist, channel) and ID.
        """
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        
        # Video ID
        if 'v' in query:
            return {'type': 'video', 'id': query['v'][0]}
        if 'youtu.be' in parsed.netloc:
            return {'type': 'video', 'id': parsed.path.lstrip('/')}
        
        # Playlist ID
        if 'list' in query:
            return {'type': 'playlist', 'id': query['list'][0]}
        
        # Channel ID (handle legacy user/ and new channel/ and @handle)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'channel':
            return {'type': 'channel', 'id': path_parts[1]}
        
        # Handle custom URL or handle (requiers search or resolving)
        if len(path_parts) >= 1 and (path_parts[0].startswith('@') or path_parts[0] == 'c' or path_parts[0] == 'user'):
            # For brevity, treating as 'handle' or custom which necessitates search
            return {'type': 'handle', 'id': path_parts[-1]}  

        # Return None or treat as search query if simple string? 
        # For now assume it's a search keyword if not a URL structure
        if not parsed.netloc:
             return {'type': 'search', 'id': url} # treat the whole string as search query

        return {'type': 'unknown', 'id': url}

    def get_video_ids(self, url_or_query: str, max_videos: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve video metadata using YouTube Data API.
        """
        target = self._extract_id_from_url(url_or_query)
        videos = []
        
        logger.info(f"Target identified: {target}")

        try:
            if target['type'] == 'video':
                videos = self._get_video_details([target['id']])
            
            elif target['type'] == 'playlist':
                videos = self._get_playlist_items(target['id'], max_videos)
            
            elif target['type'] == 'channel':
                # First get uploads playlist ID of the channel
                uploads_playlist_id = self._get_channel_uploads_id(target['id'])
                if uploads_playlist_id:
                     videos = self._get_playlist_items(uploads_playlist_id, max_videos)
            
            elif target['type'] == 'handle':
                 # Search for channel by handle/custom url to get ID
                 channel_id = self._search_channel_id(target['id'])
                 if channel_id:
                     uploads_playlist_id = self._get_channel_uploads_id(channel_id)
                     if uploads_playlist_id:
                         videos = self._get_playlist_items(uploads_playlist_id, max_videos)
            
            elif target['type'] == 'search':
                 videos = self._search_videos(target['id'], max_videos)

            else:
                 # Fallback: treat as search query
                 videos = self._search_videos(url_or_query, max_videos)

        except HttpError as e:
            logger.error(f"YouTube API Error: {e}")
            return []

        return videos[:max_videos]

    def _get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        if not video_ids:
            return []
        
        results = []
        # API allows up to 50 IDs per request
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i:i+50]
            request = self.youtube.videos().list(
                part="snippet,contentDetails",
                id=','.join(chunk)
            )
            response = request.execute()
            
            for item in response.get('items', []):
                results.append({
                    'video_id': item['id'],
                    'title': item['snippet']['title'],
                    'url': f"https://www.youtube.com/watch?v={item['id']}",
                    'publish_date': item['snippet']['publishedAt'],
                    'duration': item['contentDetails']['duration'] # ISO 8601 format
                })
        return results

    def _get_playlist_items(self, playlist_id: str, max_results: int) -> List[Dict[str, Any]]:
        video_ids = []
        next_page_token = None
        
        while len(video_ids) < max_results:
            request = self.youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, max_results - len(video_ids)),
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get('items', []):
                video_ids.append(item['contentDetails']['videoId'])
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
                
        return self._get_video_details(video_ids)

    def _get_channel_uploads_id(self, channel_id: str) -> Optional[str]:
        request = self.youtube.channels().list(
            part="contentDetails",
            id=channel_id
        )
        response = request.execute()
        items = response.get('items', [])
        if items:
            return items[0]['contentDetails']['relatedPlaylists']['uploads']
        return None
    
    def _search_channel_id(self, query: str) -> Optional[str]:
         # Rough search for a channel ID by query (handle)
         # Note: Searching by handle isn't directly supported in 'channels' list until resolved, 
         # but 'search' resource can find it.
         request = self.youtube.search().list(
             part="snippet",
             q=query,
             type="channel",
             maxResults=1
         )
         response = request.execute()
         items = response.get('items', [])
         if items:
             return items[0]['snippet']['channelId']
         return None

    def _search_videos(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        video_ids = []
        next_page_token = None
        
        while len(video_ids) < max_results:
            request = self.youtube.search().list(
                part="id",
                q=query,
                type="video",
                maxResults=min(50, max_results - len(video_ids)),
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get('items', []):
                video_ids.append(item['id']['videoId'])
                
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        return self._get_video_details(video_ids)

    def fetch_transcript_content(self, video_id: str) -> Dict[str, Any]:
        """
        Fetch transcript for a specific video ID.
        """
        try:
            # list_transcripts allows us to check for manual vs generated
            if hasattr(self, 'cookies') and self.cookies:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id, cookies=self.cookies)
            else:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # 1. Try to find preferred languages (manual or generated)
            try:
                transcript = transcript_list.find_transcript(self.languages)
            except NoTranscriptFound:
                # 2. Fallback: try ANY generated transcript (usually 'en' auto-generated)
                # or just take the first available one from the list
                possible_transcripts = list(transcript_list)
                if possible_transcripts:
                    transcript = possible_transcripts[0]
                    logger.info(f"Preferred languages {self.languages} not found. Falling back to {transcript.language_code}.")
                else:
                    raise NoTranscriptFound(video_id)
            transcript_data = transcript.fetch()
            full_text = " ".join([item['text'] for item in transcript_data])
            
            return {
                'transcript': full_text,
                'language': transcript.language_code,
                'is_generated': transcript.is_generated
            }
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            logger.warning(f"No suitable transcript for {video_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            return None

    def run(self, url: str, max_videos: int, output_file: str = "transcripts.csv"):
        """
        Main execution flow.
        """
        videos = self.get_video_ids(url, max_videos)
        if not videos:
            logger.warning("No videos found. Generating empty CSV.")
            df = pd.DataFrame(columns=['video_id', 'title', 'url', 'publish_date', 'duration', 'transcript', 'language', 'is_generated'])
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            return

        print(f"Starting transcript fetch for {len(videos)} videos...")
        
        results = []
        
        for video_meta in tqdm(videos, desc="Processing videos"):
            video_id = video_meta.get('video_id')
            
            # Rate limit politeness
            time.sleep(random.uniform(1, 3))

            transcript_info = self.fetch_transcript_content(video_id)

            if transcript_info:
                record = {**video_meta, **transcript_info}
                results.append(record)
            else:
                pass

        # Always generate CSV
        if results:
            df = pd.DataFrame(results)
        else:
            logger.warning("No transcripts were fetched. Generating empty CSV.")
            df = pd.DataFrame(columns=['video_id', 'title', 'url', 'publish_date', 'duration', 'transcript', 'language', 'is_generated'])

        columns = ['video_id', 'title', 'url', 'publish_date', 'duration', 'transcript', 'language', 'is_generated']
        for col in columns:
            if col not in df.columns:
                df[col] = None
        
        df = df[columns]
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logger.info(f"Saved results to {output_file} (Records: {len(results)})")


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube video transcripts.")
    parser.add_argument('--url', required=True, help="Target YouTube URL (video, playlist, channel, search)")
    parser.add_argument('--max-videos', type=int, default=10, help="Maximum number of videos to fetch")
    parser.add_argument('--lang', type=str, default="ja,en", help="Comma-separated list of languages to prioritize")
    parser.add_argument('--api-key', type=str, required=False, help="YouTube Data API Key")
    parser.add_argument('--cookies', type=str, required=False, help="Path to cookies.txt file for authenticated requests")

    args = parser.parse_args()
    
    # Prioritize argument, fall back to environment variable
    api_key = args.api_key or os.environ.get("YOUTUBE_API_KEY")
    
    if not api_key:
        raise ValueError("YouTube API Key is required. Set YOUTUBE_API_KEY env var or pass --api-key.")

    langs = [l.strip() for l in args.lang.split(',')]

    fetcher = YouTubeTranscriptFetcher(api_key=api_key, languages=langs)
    # Inject cookies if provided via arg or environment variable
    cookies_path = args.cookies
    
    # If no file path provided, check for content in env var (GitHub Secrets friendly)
    if not cookies_path and os.environ.get("YOUTUBE_COOKIES"):
        import tempfile
        logger.info("Found YOUTUBE_COOKIES in environment variables. Creating temporary cookies file.")
        
        # Create a temp file for cookies. 
        # Note: Delete=False so we can read it, but ideally we should clean it up. 
        # For this script run, letting OS clean up /tmp or just leaving it is acceptable for now.
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tf:
                tf.write(os.environ.get("YOUTUBE_COOKIES"))
                cookies_path = tf.name
        except Exception as e:
            logger.error(f"Failed to create temp cookies file: {e}")

    if cookies_path:
        fetcher.cookies = cookies_path
    else:
        fetcher.cookies = None
        
    try:
        fetcher.run(args.url, args.max_videos, output_file="transcripts.csv")
    finally:
        # Cleanup temp file if it was created from env var
        if not args.cookies and cookies_path and os.path.exists(cookies_path):
            try:
                os.remove(cookies_path)
            except:
                pass

if __name__ == "__main__":
    main()
