from flask import Flask, request, send_file, abort, render_template_string
from flask_cors import CORS
import os, shutil, zipfile, tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)
@app.route("/")
def home():
    return "YOLO Dataset Merger API is running!"

UPLOAD_ROOT = "uploads"
MERGED_ROOT = "merged-dataset"

# Add homepage route
@app.route("/", methods=["GET"])
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>YOLO Models Dataset Merger</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            .container { background: #f5f5f5; padding: 30px; border-radius: 10px; }
            h1 { color: #333; text-align: center; }
            .info { background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .endpoint { background: #fff; padding: 10px; margin: 10px 0; border-left: 4px solid #2196f3; }
            code { background: #f0f0f0; padding: 2px 5px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 YOLO Models Dataset Merger App</h1>
            
            <div class="info">
                <h3>✅ App Status: Running Successfully!</h3>
                <p>Your Flask application is deployed and ready to merge YOLO datasets.</p>
            </div>

            <h3>📡 Available API Endpoints:</h3>
            
            <div class="endpoint">
                <h4>POST /merge</h4>
                <p><strong>Purpose:</strong> Merge multiple YOLO datasets into one</p>
                <p><strong>Parameters:</strong></p>
                <ul>
                    <li><code>files</code>: List of ZIP files containing YOLO datasets</li>
                    <li><code>dataset_count</code>: Number of datasets (2-10)</li>
                </ul>
                <p><strong>Returns:</strong> ZIP file with merged dataset</p>
            </div>

            <h3>🚀 How to Use:</h3>
            <p>Send a POST request to <code>/merge</code> with your YOLO dataset ZIP files.</p>
            <p>The app will automatically relabel classes and create a merged dataset with proper YOLO format.</p>

            <h3>📁 Expected Dataset Structure:</h3>
            <pre>
dataset.zip
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
            </pre>
        </div>
    </body>
    </html>
    """)

@app.route("/merge", methods=["POST"])
def merge():
    files = request.files.getlist("files")
    dataset_count = int(request.form.get("dataset_count", 0))

    if dataset_count < 2 or dataset_count > 10:
        abort(400, "dataset_count must be between 2 and 10.")
    if len(files) != dataset_count:
        abort(400, f"Expected {dataset_count} files, got {len(files)}.")

    # Clear and recreate folders
    shutil.rmtree(UPLOAD_ROOT, ignore_errors=True)
    shutil.rmtree(MERGED_ROOT, ignore_errors=True)
    os.makedirs(UPLOAD_ROOT)
    os.makedirs(MERGED_ROOT)

    dataset_dirs, class_names = [], []

    # Save and unzip each dataset
    for f in files:
        filename = secure_filename(f.filename)
        save_path = os.path.join(UPLOAD_ROOT, filename)
        f.save(save_path)

        extract_dir = os.path.join(UPLOAD_ROOT, filename.replace(".zip", ""))
        with zipfile.ZipFile(save_path, "r") as zf:
            zf.extractall(extract_dir)

        dataset_dirs.append(extract_dir)
        class_names.append(os.path.splitext(filename)[0].title())

    # Relabel each dataset
    for cid, ddir in enumerate(dataset_dirs):
        for split in ["train", "valid", "test"]:
            lbl_dir = os.path.join(ddir, split, "labels")
            if not os.path.isdir(lbl_dir):
                continue
            for fname in os.listdir(lbl_dir):
                if not fname.endswith(".txt"):
                    continue
                path = os.path.join(lbl_dir, fname)
                with open(path) as f:
                    lines = [line.strip().split() for line in f]
                with open(path, "w") as f:
                    for parts in lines:
                        if parts:
                            parts[0] = str(cid)
                            f.write(" ".join(parts) + "\n")

    # Prepare merged folders
    for split in ["train", "valid", "test"]:
        for sub in ["images", "labels"]:
            os.makedirs(f"{MERGED_ROOT}/{split}/{sub}", exist_ok=True)

    # Copy files into merged folder
    for ddir in dataset_dirs:
        for split in ["train", "valid", "test"]:
            for sub in ["images", "labels"]:
                src = os.path.join(ddir, split, sub)
                dst = os.path.join(MERGED_ROOT, split, sub)
                if os.path.isdir(src):
                    for f in os.listdir(src):
                        shutil.copy(os.path.join(src, f), dst)

    # Create data.yaml
    with open(os.path.join(MERGED_ROOT, "data.yaml"), "w") as f:
        f.write(f"train: ./train/images\nval: ./valid/images\ntest: ./test/images\n\n")
        f.write(f"nc: {len(class_names)}\n")
        f.write(f"names: {class_names}\n")

    # Zip and send
    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    shutil.make_archive(tmp_zip.name[:-4], "zip", MERGED_ROOT)
    return send_file(tmp_zip.name, as_attachment=True, download_name="merged.zip")

if __name__ == "__main__":
    app.run(debug=True)
