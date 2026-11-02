import streamlit as st
import requests
import time

st.set_page_config(page_title="Live Media Origin Forensics Dashboard", page_icon="🛡️", layout="wide")

st.title("🛡️ Live Media Origin Forensics Dashboard")
st.markdown("Standalone operational tracker running on hard-data parsing and Meilisearch index routing.")

BACKEND_URL = "http://localhost:8000"

# Sidebar Configuration
st.sidebar.header("Configuration")
upload_mode = st.sidebar.radio("Select Input Mode", ["Upload File", "Image/Video URL"])

if upload_mode == "Upload File":
    uploaded_file = st.sidebar.file_uploader("Upload Target Picture or Video Variant", type=["jpg", "jpeg", "png", "mp4", "mkv", "avi", "mov"])
else:
    target_url = st.sidebar.text_input("Enter Target URL", placeholder="https://example.com/video.mp4")

frame_offset = st.sidebar.number_input("Select frame timestamp (Seconds into video)", min_value=0, value=3, step=1)

if st.sidebar.button("🔍 Execute Forensic Query", use_container_width=True):
    if upload_mode == "Upload File" and uploaded_file is not None:
        with st.spinner("Analyzing media and querying external databases..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            headers = {"x-offset-seconds": str(frame_offset)}
            
            try:
                response = requests.post(f"{BACKEND_URL}/verify/upload", files=files, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    st.success(f"✅ Analysis Complete for {data.get('media_type', 'unknown').upper()}!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("SHA-256 Hash", data.get("sha256", "N/A"))
                    with col2:
                        st.metric("Media Type", data.get("media_type", "N/A").upper())
                    
                    st.divider()
                    
                    # Deep Web / Meilisearch Results
                    st.subheader("🕸️ Internal Data Lake Hits (Meilisearch)")
                    earliest = data.get("earliest_matches", [])
                    if earliest:
                        for match in earliest:
                            st.info(f"**Match Found:** {match}")
                    else:
                        st.warning("No matching historical records found in your local Meilisearch index database.")
                    
                    st.divider()
                    
                    # Surface Web / Apify Results
                    st.subheader("🌐 Surface Web Match Traces (Google Lens)")
                    surface = data.get("surface_web_matches", [])
                    
                    if surface and "error" not in surface[0]:
                        for match in surface:
                            with st.expander(f"🔗 {match.get('found_metadata_context', 'Source Link')}"):
                                st.write(f"**Source:** {match.get('source_title', 'Unknown')}")
                                st.write(f"**Engine:** {match.get('engine', 'Unknown')}")
                                st.markdown(f"[Open Link]({match.get('info_link', '#')})")
                    elif surface and "error" in surface[0]:
                        st.error(f"Apify Error: {surface[0]['error']}")
                    else:
                        st.info("Google Lens processed the image, but no visual or exact matches were found on the surface web.")
                        
                else:
                    st.error(f"Error ({response.status_code}): {response.json().get('detail', 'Unknown error')}")
            except requests.exceptions.ConnectionError:
                st.error("Failed to connect to the backend. Is FastAPI running on port 8000?")
                
    elif upload_mode == "Image/Video URL" and target_url:
        with st.spinner("Downloading media, extracting data, and querying databases..."):
            payload = {"url": target_url}
            headers = {"x-offset-seconds": str(frame_offset)}
            
            try:
                response = requests.post(f"{BACKEND_URL}/verify/url", json=payload, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✅ Analysis Complete for {data.get('media_type', 'unknown').upper()}!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("SHA-256 Hash", data.get("sha256", "N/A"))
                    with col2:
                        st.metric("Media Type", data.get("media_type", "N/A").upper())
                        
                    st.divider()
                    
                    st.subheader("🕸️ Internal Data Lake Hits (Meilisearch)")
                    earliest = data.get("earliest_matches", [])
                    if earliest:
                        for match in earliest:
                            st.info(f"**Match Found:** {match}")
                    else:
                        st.warning("No matching historical records found in your local Meilisearch index database.")
                    
                    st.divider()
                    
                    st.subheader("🌐 Surface Web Match Traces (Google Lens)")
                    surface = data.get("surface_web_matches", [])
                    
                    if surface and "error" not in surface[0]:
                        for match in surface:
                            with st.expander(f"🔗 {match.get('found_metadata_context', 'Source Link')}"):
                                st.write(f"**Source:** {match.get('source_title', 'Unknown')}")
                                st.write(f"**Engine:** {match.get('engine', 'Unknown')}")
                                st.markdown(f"[Open Link]({match.get('info_link', '#')})")
                    elif surface and "error" in surface[0]:
                        st.error(f"Apify Error: {surface[0]['error']}")
                    else:
                        st.info("Google Lens processed the image, but no visual or exact matches were found on the surface web.")
                        
                else:
                    st.error(f"Error ({response.status_code}): {response.json().get('detail', 'Unknown error')}")
            except requests.exceptions.ConnectionError:
                st.error("Failed to connect to the backend. Is FastAPI running on port 8000?")