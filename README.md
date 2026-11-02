Prerequisites
Before you begin, you need to install a few external tools on your computer:

Python 3.10+: Download here

FFmpeg (Required for video frame extraction):

Windows: Download from gyan.dev, extract it, and add the bin folder to your System PATH.

Mac: Run brew install ffmpeg

Linux: Run sudo apt install ffmpeg

Meilisearch (Local database):

Download the binary for your OS from Meilisearch Releases.

Extract it to a folder.

yt-dlp & gallery-dl (For URL downloads):

Run pip install yt-dlp gallery-dl

Step 1: Clone the Repository
Open your terminal and run:

bash
git clone https://github.com/YOUR_USERNAME/media-forensics-engine.git
cd media-forensics-engine
Step 2: Set up the Python Environment
bash
# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
Step 3: Get Your Own Apify Token & Configure It
Go to Apify Console and sign up/login.

Copy your API Token.

In the project folder, rename .env.example to .env (or create a new file named .env).

Open it and paste your token:

env
APIFY_TOKEN=your_apify_api_token_here
Step 4: Start Meilisearch
Open a new terminal window and run the Meilisearch binary you downloaded in the prerequisites:

bash
# Windows
.\meilisearch.exe --master-key masterKey

# Mac/Linux
./meilisearch --master-key masterKey
Keep this terminal window open.

Step 5: Start the Backend Server
Go back to your main terminal (where your venv is activated) and run:

bash
uvicorn app:app --host localhost --port 8000
Keep this terminal window open.

Step 6: Start the Dashboard
Open a third terminal window, activate the virtual environment again, and run:

bash
streamlit run dashboard.py
Your browser should automatically open the dashboard at http://localhost:8501. You can now upload files, extract video frames, and trace media across the web!