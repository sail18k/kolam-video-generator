import os
import sys
import re
import pickle
from pathlib import Path

# Reconfigure stdout and stderr for UTF-8 on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes needed for uploading video and setting custom thumbnails
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube"
]

CLIENT_SECRETS_GUIDE = """
================================================================================
⚠️  YOUTUBE OAUTH CREDENTIALS REQUIRED (One-Time Quick Setup)
================================================================================
To upload directly to YouTube via the official API:

1. Open Google Cloud Console:
   👉 https://console.cloud.google.com/

2. Create a new project (e.g., "AK Kolam Automation").

3. Enable YouTube API:
   👉 Go to 'APIs & Services' -> 'Library'
   👉 Search for 'YouTube Data API v3' and click ENABLE.

4. Set up OAuth Consent Screen:
   👉 Go to 'APIs & Services' -> 'OAuth consent screen'
   👉 Select 'External' -> Create
   👉 App name: 'AK Kolam Uploader', add your email
   👉 Under 'Test users', click '+ ADD USERS' and add your YouTube Google account email!

5. Generate Credentials:
   👉 Go to 'APIs & Services' -> 'Credentials'
   👉 Click 'Create Credentials' -> 'OAuth client ID'
   👉 Application type: 'Desktop app'
   👉 Name: 'AK Kolam Desktop Uploader' -> Create
   👉 Download the JSON file!

6. Save the downloaded file as:
   👉 client_secrets.json (inside this project folder: {folder})

Once saved, run the upload again. A browser window will open once to sign in.
Future uploads will happen automatically using the saved session token!
================================================================================
"""


def find_client_secrets_file(explicit_path=None):
    """Locate client_secrets.json in root or engine directory."""
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path

    search_dirs = [
        Path("."),
        Path(__file__).parent.parent,
        Path(__file__).parent
    ]

    names = ["client_secrets.json", "client_secret.json"]

    for d in search_dirs:
        for name in names:
            p = d / name
            if p.exists():
                return str(p.resolve())

        # Also look for any client_secret_*.json
        matches = list(d.glob("client_secret*.json"))
        if matches:
            return str(matches[0].resolve())

    return None


def get_authenticated_service(client_secrets_file=None, token_pickle="youtube_token.pickle"):
    """
    Authenticate with YouTube Data API v3 using OAuth 2.0.
    Caches token in youtube_token.pickle for instant subsequent uploads.
    """
    creds = None
    token_path = Path(token_pickle)

    if token_path.exists():
        try:
            with open(token_path, "rb") as token_file:
                creds = pickle.load(token_file)
        except Exception as e:
            print(f"[AUTH] Could not load cached token: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("[AUTH] Refreshing expired YouTube access token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"[AUTH] Token refresh failed: {e}. Re-authenticating...")
                creds = None

        if not creds:
            secrets_path = find_client_secrets_file(client_secrets_file)
            if not secrets_path:
                current_dir = os.path.abspath(".")
                print(CLIENT_SECRETS_GUIDE.format(folder=current_dir))
                return None

            print(f"[AUTH] Found credentials: {secrets_path}")
            print("[AUTH] Launching browser to select your Google Account / YouTube Channel...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
                creds = flow.run_local_server(port=0, prompt="select_account")
            except Exception as e:
                print(f"[AUTH] OAuth authentication error: {e}")
                return None

        # Save token for future runs
        try:
            with open(token_path, "wb") as token_file:
                pickle.dump(creds, token_file)
            print(f"[AUTH] Authorization token saved to {token_path}")
        except Exception as e:
            print(f"[AUTH] Warning: Failed to save token: {e}")

    service = build("youtube", "v3", credentials=creds)
    try:
        ch_resp = service.channels().list(part="snippet", mine=True).execute()
        if ch_resp.get("items"):
            ch_name = ch_resp["items"][0]["snippet"]["title"]
            print(f"[AUTH] Connected to YouTube Channel: 🎬 {ch_name}")
    except Exception:
        pass

    return service


def parse_metadata_file(metadata_path):
    """
    Parses dynamic bilingual metadata file generated by generate.py.
    Extracts Title, Description, Tags, Video path, and Thumbnail path.
    """
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Title
    title = ""
    title_match = re.search(r"📌 TITLE[^\n]*\n+([^\n]+)", content)
    if title_match:
        title = title_match.group(1).strip()

    # 2. Description
    desc = ""
    desc_match = re.search(r"📝 DESCRIPTION[^\n]*\n+(.*?)(?=\n-{3,}|\n🏷️ TAGS)", content, re.DOTALL)
    if desc_match:
        desc = desc_match.group(1).strip()

    # 3. Tags
    tags_list = []
    tags_match = re.search(r"🏷️ TAGS[^\n]*\n+([^\n]+)", content)
    if tags_match:
        raw_tags = tags_match.group(1).strip()
        tags_list = [t.strip() for t in raw_tags.split(",") if t.strip()]

    # 4. Video Path
    video_path = ""
    video_match = re.search(r"Video:\s*([^\n]+)", content)
    if video_match:
        video_path = video_match.group(1).strip()

    # 5. Thumbnail Path
    thumbnail_path = ""
    thumb_match = re.search(r"Thumbnail:\s*([^\n]+)", content)
    if thumb_match:
        thumbnail_path = thumb_match.group(1).strip()

    # Resolve relative paths relative to metadata file or working directory
    base_dir = os.path.dirname(os.path.abspath(metadata_path))
    if video_path and not os.path.isabs(video_path):
        candidate = os.path.join(base_dir, video_path)
        if os.path.exists(candidate):
            video_path = candidate

    if thumbnail_path and not os.path.isabs(thumbnail_path):
        candidate = os.path.join(base_dir, thumbnail_path)
        if os.path.exists(candidate):
            thumbnail_path = candidate

    return {
        "title": title,
        "description": desc,
        "tags": tags_list,
        "video_path": video_path,
        "thumbnail_path": thumbnail_path
    }


def smart_trim_title(title, max_len=100):
    """
    Ensures title is within YouTube's 100 character limit without breaking words,
    preserving #shorts hashtag if present.
    """
    if len(title) <= max_len:
        return title

    has_shorts = "#shorts" in title.lower()
    suffix = " #shorts" if has_shorts else ""
    target_len = max_len - len(suffix)

    # Trim to last word boundary
    truncated = title[:target_len].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]

    return truncated + suffix


def upload_video_to_youtube(
    video_path,
    title,
    description,
    tags=None,
    thumbnail_path=None,
    privacy_status="public",
    category_id="26",  # 26: Howto & Style (Standard for arts/crafts/kolam)
    youtube=None
):
    """
    Uploads a video to YouTube, reports progress, and sets the custom thumbnail.
    """
    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found: {video_path}")
        return None

    if youtube is None:
        youtube = get_authenticated_service()
        if youtube is None:
            return None

    clean_title = smart_trim_title(title, max_len=100)

    # Format tags: list of strings, max total length ~450 chars
    valid_tags = []
    total_tag_chars = 0
    if tags:
        for t in tags:
            t = t.strip()
            if t and (total_tag_chars + len(t) + 1) < 450:
                valid_tags.append(t)
                total_tag_chars += len(t) + 1

    body = {
        "snippet": {
            "title": clean_title,
            "description": description[:5000],
            "tags": valid_tags,
            "categoryId": str(category_id),  # 26: Howto & Style
            "defaultLanguage": "ta",
            "defaultAudioLanguage": "ta"
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,     # Only for child: NO (Not Made for Kids)
            "containsSyntheticMedia": False,     # AI Generated / Altered realistic content: NO
            "embeddable": True,                  # Allow embedding on websites
            "publicStatsViewable": True,         # Public metrics visible
            "license": "youtube"                 # Standard YouTube License
        }
    }

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"\n[UPLOAD] Initiating YouTube upload for: {os.path.basename(video_path)}")
    print(f"  • File size:            {file_size_mb:.2f} MB")
    print(f"  • Title ({len(clean_title)} chars):    {clean_title}")
    print(f"  • Tags:                 {len(valid_tags)} tags included")
    print(f"  • Category:             Howto & Style (26)")
    print(f"  • Made for Kids:        NO (Not made for children)")
    print(f"  • AI / Altered Content: NO (Standard art creation)")
    print(f"  • Paid Promotion:       NO (None)")
    print(f"  • License:              Standard YouTube License")
    print(f"  • Privacy status:       {privacy_status.upper()}")

    media = MediaFileUpload(video_path, chunksize=1024 * 1024 * 2, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    last_reported = -1

    while response is None:
        try:
            status, response = request.next_chunk()
        except Exception as e:
            # If YouTube API rejects containsSyntheticMedia on older clusters, retry without it
            if "containsSyntheticMedia" in str(e):
                print("  -> Adapting status parameters to account tier...")
                body["status"].pop("containsSyntheticMedia", None)
                media = MediaFileUpload(video_path, chunksize=1024 * 1024 * 2, resumable=True)
                request = youtube.videos().insert(
                    part="snippet,status",
                    body=body,
                    media_body=media
                )
                status, response = request.next_chunk()
            else:
                raise e

        if status:
            pct = int(status.progress() * 100)
            if pct != last_reported and pct % 10 == 0:
                print(f"  -> Upload progress: {pct}%")
                last_reported = pct

    video_id = response.get("id")
    if not video_id:
        print("[ERROR] Failed to get uploaded video ID from YouTube response.")
        return None

    print(f"  -> Video upload completed! Video ID: {video_id}")

    # Set custom thumbnail if provided
    thumbnail_success = False
    if thumbnail_path and os.path.exists(thumbnail_path):
        print(f"  -> Uploading custom thumbnail: {os.path.basename(thumbnail_path)}...")
        try:
            thumb_media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=thumb_media
            ).execute()
            thumbnail_success = True
            print("  -> Custom thumbnail uploaded successfully!")
        except Exception as e:
            print(f"  -> Note: Custom thumbnail upload notice: {e}")
            print("     (Note: YouTube requires phone-verified channel status to set custom thumbnails.)")

    watch_url = f"https://youtu.be/{video_id}"
    shorts_url = f"https://youtube.com/shorts/{video_id}"

    print("\n" + "=" * 60)
    print("🎉 YOUTUBE UPLOAD SUCCESSFUL!")
    print("=" * 60)
    print(f"📺 Watch URL:   {watch_url}")
    print(f"📱 Shorts URL:  {shorts_url}")
    print(f"🔒 Privacy:     {privacy_status.upper()}")
    print("=" * 60 + "\n")

    return {
        "video_id": video_id,
        "watch_url": watch_url,
        "shorts_url": shorts_url,
        "thumbnail_uploaded": thumbnail_success,
        "privacy": privacy_status
    }


def upload_from_metadata_file(metadata_path, privacy_status="public", youtube=None):
    """
    Helper function that parses a metadata text file and uploads the video and thumbnail directly.
    """
    print(f"\n[UPLOAD] Reading metadata from: {metadata_path}")
    try:
        data = parse_metadata_file(metadata_path)
    except Exception as e:
        print(f"[ERROR] Failed to parse metadata file: {e}")
        return None

    video_path = data["video_path"]
    if not video_path or not os.path.exists(video_path):
        print(f"[ERROR] Target video file does not exist: {video_path}")
        return None

    return upload_video_to_youtube(
        video_path=video_path,
        title=data["title"],
        description=data["description"],
        tags=data["tags"],
        thumbnail_path=data["thumbnail_path"],
        privacy_status=privacy_status,
        youtube=youtube
    )
