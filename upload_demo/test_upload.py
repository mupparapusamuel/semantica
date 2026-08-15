import io
import os
import requests

SERVER = "http://127.0.0.1:5000/upload"


def make_sample_files(folder):
    os.makedirs(folder, exist_ok=True)
    paths = []
    a = os.path.join(folder, "sample1.txt")
    b = os.path.join(folder, "sample2.txt")
    with open(a, "w", encoding="utf-8") as f:
        f.write("This is a sample text file. It mentions semantica and parsing.\n" * 3)
    with open(b, "w", encoding="utf-8") as f:
        f.write("Another sample file with some repeated words: apple apple apple banana.\n" * 2)
    return [a, b]


def upload_files(file_paths):
    files = []
    for p in file_paths:
        files.append(("files", (os.path.basename(p), open(p, "rb"))))

    try:
        resp = requests.post(SERVER, files=files, timeout=30)
    finally:
        for _, fp in files:
            try:
                fp[1].close()
            except Exception:
                pass

    print("Status:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    tmp = os.path.join(os.path.dirname(__file__), "_test_files")
    fps = make_sample_files(tmp)
    print("Uploading:", fps)
    upload_files(fps)
