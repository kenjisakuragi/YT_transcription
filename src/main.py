import argparse
import time
import random
import logging
from typing import List, Dict, Any, Optional

import pandas as pd
from tqdm import tqdm
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class YouTubeTranscriptFetcher:
    """
    A class to fetch YouTube video metadata and transcripts.
    """

    def __init__(self, languages: List[str] = None):
        """
        Initialize the fetcher.

        Args:
            languages (List[str]): List of language codes to prioritize (e.g., ['ja', 'en']).
        """
        self.languages = languages if languages else ['ja', 'en']

    def get_video_ids(self, url: str, max_videos: int = 10) -> List[Dict[str, Any]]:
        """
        Extract video IDs and metadata from a given URL using yt-dlp.

        Args:
            url (str): The target YouTube URL (video, playlist, channel, search).
            max_videos (int): Maximum number of videos to retrieve.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing video metadata.
        """
        ydl_opts = {
            'extract_flat': True,  # Do not download video files
            'quiet': True,
            'ignoreerrors': True,  # Skip errors
            'playlistend': max_videos, # Limit playlist/search results
        }

        # For search URLs, we might need specific handling if playlistend doesn't apply perfectly,
        # but usually yt-dlp handles "search query" URLs as playlists.
        # If the URL is literally a search query string provided to yt-dlp, it handles it.
        # But if it is a URL like "https://www.youtube.com/results?search_query=foo", yt-dlp also handles it.

        logger.info(f"Extracting video IDs from: {url}")
        
        videos = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if info is None:
                    logger.warning("No information extracted.")
                    return []

                # If it's a single video, 'entries' might not exist or be None
                if 'entries' not in info:
                    # Single video
                    videos.append({
                        'video_id': info.get('id'),
                        'title': info.get('title'),
                        'url': info.get('webpage_url') or info.get('url'),
                        'publish_date': info.get('upload_date'), # Format might need adjustment (YYYYMMDD usually)
                        'duration': info.get('duration')
                    })
                else:
                    # Playlist, Channel, or Search Results
                    entries = info['entries']
                    # entries is a generator or list. 
                    # extract_flat=True usually returns dicts in entries.
                    
                    count = 0
                    for entry in entries:
                        if entry is None:
                            continue
                        
                        # Apply max limit logic again just in case playlistend didn't catch specific cases
                        if count >= max_videos:
                            break

                        v_id = entry.get('id')
                        # Sometimes extract_flat returns minimal info.
                        # We might need 'url' to be constructed if missing.
                        v_url = entry.get('url')
                        if not v_url and v_id:
                            v_url = f"https://www.youtube.com/watch?v={v_id}"

                        videos.append({
                            'video_id': v_id,
                            'title': entry.get('title'),
                            'url': v_url,
                            'publish_date': entry.get('upload_date'),
                            'duration': entry.get('duration')
                        })
                        count += 1
                        
        except Exception as e:
            logger.error(f"Error extracting video IDs: {e}")

        logger.info(f"Found {len(videos)} videos.")
        return videos

    def fetch_transcript_content(self, video_id: str) -> Dict[str, Any]:
        """
        Fetch transcript for a specific video ID.

        Args:
            video_id (str): YouTube Video ID.

        Returns:
            Dict[str, Any]: Dictionary with transcript details or None if failed.
        """
        try:
            # list_transcripts allows us to check for manual vs generated
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Find transcript matching languages
            transcript = transcript_list.find_transcript(self.languages)
            
            # Fetch the actual data
            transcript_data = transcript.fetch()
            
            # Merge text
            full_text = " ".join([item['text'] for item in transcript_data])
            
            return {
                'transcript': full_text,
                'language': transcript.language_code,
                'is_generated': transcript.is_generated
            }

        except (TranscriptsDisabled, NoTranscriptFound):
            logger.warning(f"No suitable transcript found for {video_id}.")
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
            logger.info("No videos to process.")
            return

        print(f"Starting transcript fetch for {len(videos)} videos...")
        
        results = []
        
        # Using tqdm for progress bar
        for video_meta in tqdm(videos, desc="Processing videos"):
            video_id = video_meta.get('video_id')
            if not video_id:
                continue

            # Sleep to avoid rate limiting
            sleep_time = random.uniform(2, 5)
            time.sleep(sleep_time)

            transcript_info = self.fetch_transcript_content(video_id)

            if transcript_info:
                # Merge metadata with transcript info
                record = {**video_meta, **transcript_info}
                results.append(record)
            else:
                # We can optionally record failed videos or just skip.
                # Requirement says: "Error log ... skip and continue".
                pass

        if results:
            df = pd.DataFrame(results)
            # Ensure columns order as requested
            columns = ['video_id', 'title', 'url', 'publish_date', 'duration', 'transcript', 'language', 'is_generated']
            # Add missing columns if any (e.g. if metadata was incomplete, fill na)
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            
            df = df[columns]
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            logger.info(f"Successfully saved {len(results)} transcripts to {output_file}")
        else:
            logger.info("No transcripts were fetched.")


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube video transcripts.")
    parser.add_argument('--url', required=True, help="Target YouTube URL (video, playlist, channel, search)")
    parser.add_argument('--max-videos', type=int, default=10, help="Maximum number of videos to fetch")
    parser.add_argument('--lang', type=str, default="ja,en", help="Comma-separated list of languages to prioritize")

    args = parser.parse_args()

    langs = [l.strip() for l in args.lang.split(',')]

    fetcher = YouTubeTranscriptFetcher(languages=langs)
    fetcher.run(args.url, args.max_videos)

if __name__ == "__main__":
    main()
