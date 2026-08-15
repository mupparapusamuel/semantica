# Semantica Upload Demo

Open `index.html` in a browser and select up to 5 files. The page will extract basic semantics (metadata, preview, top words) client-side and let you download a JSON semantics file per upload.

No server is required; open the file directly or serve with a simple HTTP server:

```powershell
python -m http.server 8000 --directory "G:\My Drive\Projects\semantica-agi\semantica\upload_demo"
```

Server-backed mode (recommended)
 - Install requirements and run the Flask server which will accept uploads
	 and process them with the local Semantica package.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
# Open http://localhost:5000 in your browser
```
