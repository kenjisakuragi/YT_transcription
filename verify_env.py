import sys
import pkg_resources

print(f"Python version: {sys.version}")

try:
    import youtube_transcript_api
    from youtube_transcript_api import YouTubeTranscriptApi
    
    print(f"youtube-transcript-api imported from: {youtube_transcript_api.__file__}")
    
    try:
        version = pkg_resources.get_distribution("youtube-transcript-api").version
        print(f"Package version: {version}")
    except Exception as e:
        print(f"Could not get package version via pkg_resources: {e}")

    if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
        print("SUCCESS: YouTubeTranscriptApi.list_transcripts exists.")
    else:
        print("FAILURE: YouTubeTranscriptApi.list_transcripts DOES NOT EXIST.")
        print(f"Available attributes: {dir(YouTubeTranscriptApi)}")

except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
