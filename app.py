from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import shutil
from zipfile import ZipFile
import tempfile
from urllib.parse import urlparse, parse_qs
from flask import abort


app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Convert watch?v=...&list=... URL to playlist URL if needed
def fix_youtube_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    # If playlist exists in URL, convert to playlist URL
    if 'list' in query:
        playlist_id = query['list'][0]
        return f"https://www.youtube.com/playlist?list={playlist_id}"
    return url

# Fetch videos info from a URL (playlist or single video)
def get_videos_from_url(url):
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'ignoreerrors': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = None
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"Error fetching video/playlist: {e}")
            return []

        if not info:
            return []

        # If it's a playlist, entries exist
        if 'entries' in info:
            videos = [v for v in info['entries'] if v]
        else:
            # Single video: wrap it in a list
            videos = [info]

        # Ensure thumbnail and URL exist
        for v in videos:
            if 'thumbnail' not in v or not v['thumbnail']:
                v['thumbnail'] = f"https://img.youtube.com/vi/{v['id']}/hqdefault.jpg"
            if 'url' not in v:
                v['url'] = f"https://www.youtube.com/watch?v={v['id']}"
        return videos

# Download selected videos as MP3 into temp folder and return path
def download_videos_mp3(video_urls):
    temp_dir = tempfile.mkdtemp()
    for url in video_urls:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'ignoreerrors': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.extract_info(url, download=True)
            except Exception as e:
                print(f"Error downloading {url}: {e}")
    return temp_dir

# Zip folder
def zip_folder(folder_path):
    zip_path = folder_path + ".zip"
    with ZipFile(zip_path, 'w') as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), arcname=file)
    return zip_path

@app.route('/', methods=['GET', 'POST'])
def index():
    videos = []
    message = ""
    download_link = None

    if request.method == 'POST':
        # Check if user submitted a URL to fetch videos
        if 'playlist_url' in request.form:
            url = request.form['playlist_url'].strip()
            url = fix_youtube_url(url)
            videos = get_videos_from_url(url)
            if not videos:
                message = "No videos found or URL unavailable."

        # Check if user submitted videos to download
        elif 'download_urls[]' in request.form:
            urls = request.form.getlist('download_urls[]')
            if urls:
                temp_dir = download_videos_mp3(urls)
                zip_path = zip_folder(temp_dir)
                shutil.rmtree(temp_dir)  # clean temp files
                download_link = os.path.basename(zip_path)
                message = "File ready! Click the button below to download."
                shutil.move(zip_path, os.path.join(DOWNLOAD_FOLDER, download_link))
            else:
                message = "No videos selected for download."

    return render_template('index.html', videos=videos, message=message, download_link=download_link)

@app.route('/downloads/<filename>')
def download_file(filename):
    path = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    pass
