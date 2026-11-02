from dotenv import load_dotenv
load_dotenv()import os
import hashlib
import subprocess
import time
import uuid
from datetime import timedelta
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import meilisearch
from apify_client import ApifyClient

app = FastAPI(title="Media Forensics Core Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize local database index layers
client = meilisearch.Client('http://localhost:7700', 'masterKey')
INDEX_NAME = 'media_dumps'

try:
    index = client.get_index(INDEX_NAME)
except Exception:
    client.create_index(INDEX_NAME, {'primaryKey': 'id'})
    time.sleep(1)
    index = client.index(INDEX_NAME)

# ---------------------------------------------------------
# APIFY CLIENT CONFIGURATION
# ---------------------------------------------------------
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
apify_client = ApifyClient(APIFY_TOKEN)

class UrlPayload(BaseModel):
    url: str

class LinkVerificationReport(BaseModel):
    status: str
    media_type: str
    sha256: str
    downloaded_path: str
    earliest_matches: List[Dict[str, Any]]
    surface_web_matches: List[Dict[str, Any]]

def compute_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_video_keyframe(video_path: str, offset_seconds: int = 3) -> str:
    out_dir = os.path.dirname(video_path)
    frame_path = os.path.join(out_dir, f"frame_{os.path.basename(video_path)}.jpg")
    
    if os.path.exists(frame_path):
        try:
            os.remove(frame_path)
        except Exception:
            pass
        
    try:
        time_str = f"00:00:{offset_seconds:02d}"
        print(f"[FFMPEG] 🛠️ Extracting thumbnail frame from: {video_path} at timestamp {time_str}")
        
        cmd = ["ffmpeg", "-y", "-ss", time_str, "-i", video_path, "-vframes", "1", "-f", "image2", frame_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        if os.path.exists(frame_path):
            print(f"[FFMPEG] ✅ Frame extracted successfully at: {frame_path}")
            return frame_path
    except Exception as e:
        print(f"[FFMPEG] ❌ Failed to run extraction: {str(e)}")
        
    return ""

def extract_links_recursively(data: Any, engine_name: str) -> List[Dict[str, Any]]:
    """Recursively search the JSON to find any valid links"""
    results = []
    if isinstance(data, dict):
        # If this dict has a link, we found a match
        link = data.get("link") or data.get("url")
        if link and isinstance(link, str) and link.startswith("http"):
            # Filter out the Apify key-value store URL (our own upload)
            if "api.apify.com" not in link:
                results.append({
                    "engine": engine_name,
                    "found_metadata_context": data.get("title") or data.get("text") or "Untitled Match",
                    "source_title": data.get("source") or data.get("siteName") or data.get("displayLink") or "Public Web",
                    "info_link": link
                })
        
        # Continue searching deeper into the dict
        for value in data.values():
            results.extend(extract_links_recursively(value, engine_name))
            
    elif isinstance(data, list):
        for item in data:
            results.extend(extract_links_recursively(item, engine_name))
            
    return results

def track_surface_web_via_apify(file_path: str) -> List[Dict[str, Any]]:
    surface_matches = []
    
    if not APIFY_TOKEN or APIFY_TOKEN == "YOUR_APIFY_API_TOKEN":
        print("[APIFY ENGINE] ❌ Error: APIFY_TOKEN variable is blank or unconfigured!")
        return [{"engine": "Apify Google Lens", "error": "Apify Token not configured in app.py"}]
        
    try:
        print(f"[APIFY ENGINE] 🛰️ Initializing Key-Value Store bucket allocation...")
        kvs = apify_client.key_value_stores().get_or_create(name="forensic-temp-assets")
        store_id = kvs.get("id") if isinstance(kvs, dict) else kvs.id
        
        # Generate a safe filename
        ext = os.path.splitext(file_path)[1].lower()
        safe_file_name = f"target_{uuid.uuid4().hex}{ext}"
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        content_type = "image/png" if ext == '.png' else "image/jpeg"
        
        print(f"[APIFY ENGINE] 📤 Pushing frame to Apify Cloud as: {safe_file_name}")
        apify_client.key_value_store(store_id).set_record(safe_file_name, file_bytes, content_type=content_type)
        
        time.sleep(2)
        
        store_client = apify_client.key_value_store(store_id)
        public_image_url = store_client.get_record_public_url(safe_file_name)
        
        print(f"[APIFY ENGINE] ✅ Cloud Asset Loopback established: {public_image_url}")
        
        print("[APIFY ENGINE] 🚀 Executing 'borderline/google-lens' run configuration...")
        actor_input = {
            "searchTypes": ["exact-match", "visual-match"],
            "imageUrls": [
                {
                    "url": public_image_url
                }
            ],
            "language": "en"
        }
        
        run = apify_client.actor("borderline/google-lens").call(run_input=actor_input, timeout=timedelta(seconds=90))
        
        dataset_id = run.default_dataset_id
        print(f"[APIFY ENGINE] ✨ Cloud Job Complete! Extracting Dataset: {dataset_id}")
        
        dataset_items = apify_client.dataset(dataset_id).list_items().items
        print(f"[APIFY ENGINE] 📥 Retrieved {len(dataset_items)} parent entries from dataset.")
        
        # Exhaustive recursive extraction
        raw_matches = extract_links_recursively(dataset_items, "Google Lens")
        
        # Deduplicate by URL
        seen_links = set()
        for match in raw_matches:
            if match["info_link"] not in seen_links:
                seen_links.add(match["info_link"])
                surface_matches.append(match)
                    
        print(f"[APIFY ENGINE] 📊 Parsing complete. Sending {len(surface_matches)} unique links to dashboard panels.")
                    
    except Exception as e:
        print(f"[APIFY ENGINE] ❌ CONNECTION RUNTIME EXCEPTION: {str(e)}")
        surface_matches.append({"error": f"Apify routing layer failure: {str(e)}"})
        
    return surface_matches

def download_media_from_url(url: str) -> Dict[str, str]:
    out_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(out_dir, exist_ok=True)
    
    video_template = os.path.join(out_dir, "vid_%(id)s.%(ext)s")
    try:
        cmd = ["yt-dlp", "-o", video_template, "--get-filename", url]
        expected_filename = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, shell=True).strip()
        if expected_filename:
            subprocess.run(["yt-dlp", "-o", video_template, url], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
            return {"path": os.path.join(out_dir, os.path.basename(expected_filename)), "type": "video"}
    except Exception:
        pass

    try:
        subprocess.run(["gallery-dl", "--directory", out_dir, url], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        all_files = []
        for root, _, files in os.walk(out_dir):
            for file in files:
                all_files.append(os.path.join(root, file))
        if all_files:
            return {"path": max(all_files, key=os.path.getmtime), "type": "image"}
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Local extraction failed. Try downloading it manually.")

# ---------------------------------------------------------
# CORE FORENSIC ROUTING ENDPOINTS
# ---------------------------------------------------------
@app.post("/verify/url", response_model=LinkVerificationReport)
async def verify_url(payload: UrlPayload, x_offset_seconds: Optional[str] = Header(None)):
    offset = 3
    if x_offset_seconds:
        try:
            offset = int(x_offset_seconds)
        except ValueError:
            pass

    media_data = download_media_from_url(payload.url)
    file_path = media_data["path"]
    media_type = media_data["type"]
    
    sha256 = compute_sha256(file_path)
    
    earliest_matches = []
    try:
        search_res = index.search(sha256)
        earliest_matches = search_res.get("hits", [])
    except Exception as e:
        print(f"[MEILISEARCH] ❌ Query error: {str(e)}")
        
    target_path = file_path
    if media_type == "video":
        frame_path = extract_video_keyframe(file_path, offset_seconds=offset)
        if frame_path:
            target_path = frame_path

    surface_web_matches = track_surface_web_via_apify(target_path)
    
    return {
        "status": "success",
        "media_type": media_type,
        "sha256": sha256,
        "downloaded_path": file_path,
        "earliest_matches": earliest_matches,
        "surface_web_matches": surface_web_matches
    }

@app.post("/verify/file")
async def verify_file(file: UploadFile = File(...), x_offset_seconds: Optional[str] = Header(None)):
    offset = 3
    if x_offset_seconds:
        try:
            offset = int(x_offset_seconds)
        except ValueError:
            pass

    upload_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    sha256 = compute_sha256(file_path)
    
    ext = file.filename.lower()
    media_type = "video" if ext.endswith(('.mp4', '.mkv', '.avi', '.mov')) else "image"
    
    earliest_matches = []
    try:
        search_res = index.search(sha256)
        earliest_matches = search_res.get("hits", [])
    except Exception as e:
        print(f"[MEILISEARCH] ❌ Query error: {str(e)}")

    target_path = file_path
    if media_type == "video":
        frame_path = extract_video_keyframe(file_path, offset_seconds=offset)
        if frame_path:
            target_path = frame_path

    surface_web_matches = track_surface_web_via_apify(target_path)

    return {
        "status": "success",
        "media_type": media_type,
        "sha256": sha256,
        "downloaded_path": file_path,
        "earliest_matches": earliest_matches,
        "surface_web_matches": surface_web_matches
    }

# ---------------------------------------------------------
# FRONTEND COMPATIBILITY ALIAS
# ---------------------------------------------------------
@app.post("/verify/upload", include_in_schema=False)
async def verify_upload_alias(file: UploadFile = File(...), x_offset_seconds: Optional[str] = Header(None)):
    return await verify_file(file=file, x_offset_seconds=x_offset_seconds)