from flask import Flask, request, send_file, render_template_string, jsonify
from flask_cors import CORS
import os, shutil, zipfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_ROOT = "uploads"
MERGED_ROOT = "merged-dataset"
status_log = []  # Global status log list

@app.route("/", methods=["GET"])
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>YOLO Dataset Merger</title>
        <style>
            body { font-family: Arial; margin: 30px auto; max-width: 800px; padding: 20px; background: #f9f9f9; }
            h1, h2 { color: #222; text-align: center; }
            form { background: #fff; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px #ccc; }
            input, button { padding: 10px; margin-top: 10px; width: 100%; }
            input[type="file"] { border: 1px dashed #999; background: #fafafa; padding: 20px; }
            button { background: #007bff; color: white; border: none; }
            button:hover { background: #0056b3; }
            #status-box { background: #eee; padding: 15px; margin-top: 20px; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <h1>SAAHAAS</h1>                          
        <h2>YOLO Dataset Merger</h2>
        <form method="post" action="/merge" enctype="multipart/form-data">
            <label>Number of datasets to merge (2–10):</label>
            <input type="number" name="dataset_count" min="2" max="10" value="2" required>
            <label>Select ZIP files:</label>
            <input type="file" name="files" accept=".zip" multiple required>
            <button type="submit">Merge Datasets</button>
        </form>
        <div id="status-box">📝 Waiting for processing to begin...</div>

        <script>
          function checkStatus() {
            fetch('/status')
              .then(res => res.json())
              .then(data => {
                document.getElementById('status-box').textContent = data.log.join('\\n');
              });
          }
          setInterval(checkStatus, 1500);
        </script>
    </body>
    </html>
    """)

@app.route("/status", methods=["GET"])
def get_status():
    return jsonify({"log": status_log})

@app.route("/merge", methods=["POST"])
def merge():
    try:
        status_log.clear()
        status_log.append("🚀 Starting merge process...")

        files = request.files.getlist("files")
        dataset_count = int(request.form.get("dataset_count", 0))

        if dataset_count < 2 or dataset_count > 10:
            status_log.append("❌ Error: dataset_count must be between 2 and 10.")
            return "Error: dataset_count must be between 2 and 10.", 400
        if len(files) != dataset_count:
            status_log.append(f"❌ Error: Expected {dataset_count} files, got {len(files)}.")
            return f"Error: Expected {dataset_count} files, got {len(files)}.", 400

        if os.path.exists(UPLOAD_ROOT): shutil.rmtree(UPLOAD_ROOT)
        if os.path.exists(MERGED_ROOT): shutil.rmtree(MERGED_ROOT)
        os.makedirs(UPLOAD_ROOT)
        os.makedirs(MERGED_ROOT)

        dataset_dirs, class_names = [], []

        status_log.append("📦 Unzipping files...")
        for i, f in enumerate(files):
            filename = secure_filename(f.filename)
            if not filename.endswith(".zip"):
                status_log.append(f"❌ File {filename} is not a ZIP file.")
                return f"Error: File {filename} is not a .zip file", 400

            save_path = os.path.join(UPLOAD_ROOT, filename)
            f.save(save_path)

            extract_dir = os.path.join(UPLOAD_ROOT, filename.replace(".zip", ""))
            with zipfile.ZipFile(save_path, "r") as zf:
                zf.extractall(extract_dir)

            dataset_dirs.append(extract_dir)
            class_names.append(os.path.splitext(filename)[0].replace("_", " ").title())

        status_log.append("📝 Relabeling YOLO labels...")
        for cid, ddir in enumerate(dataset_dirs):
            for split in ["train", "valid", "test"]:
                lbl_dir = os.path.join(ddir, split, "labels")
                if not os.path.isdir(lbl_dir): continue
                for fname in os.listdir(lbl_dir):
                    if not fname.endswith(".txt"): continue
                    path = os.path.join(lbl_dir, fname)
                    with open(path) as f:
                        lines = [line.strip().split() for line in f if line.strip()]
                    with open(path, "w") as f:
                        for parts in lines:
                            if len(parts) >= 5:
                                parts[0] = str(cid)
                                f.write(" ".join(parts) + "\n")

        status_log.append("🧩 Merging files...")
        for split in ["train", "valid", "test"]:
            for sub in ["images", "labels"]:
                os.makedirs(f"{MERGED_ROOT}/{split}/{sub}", exist_ok=True)

        for ddir in dataset_dirs:
            for split in ["train", "valid", "test"]:
                for sub in ["images", "labels"]:
                    src = os.path.join(ddir, split, sub)
                    dst = os.path.join(MERGED_ROOT, split, sub)
                    if os.path.isdir(src):
                        for f in os.listdir(src):
                            src_path = os.path.join(src, f)
                            dst_path = os.path.join(dst, f)
                            count = 1
                            while os.path.exists(dst_path):
                                name, ext = os.path.splitext(f)
                                dst_path = os.path.join(dst, f"{name}_{count}{ext}")
                                count += 1
                            shutil.copy2(src_path, dst_path)

        status_log.append("📄 Creating data.yaml...")
        with open(os.path.join(MERGED_ROOT, "data.yaml"), "w") as f:
            f.write(f"train: ./train/images\nval: ./valid/images\ntest: ./test/images\n\n")
            f.write(f"nc: {len(class_names)}\nnames: {class_names}\n")

        status_log.append("📦 Creating final ZIP...")
        zip_path = os.path.join(MERGED_ROOT, "merged_dataset.zip")
        shutil.make_archive(zip_path[:-4], "zip", MERGED_ROOT)

        if not os.path.exists(zip_path):
            status_log.append("❌ ZIP file creation failed.")
            return "Error: Failed to create ZIP.", 500

        status_log.append("✅ Merge complete! Sending file to browser...")
        return send_file(zip_path, as_attachment=True, download_name="merged_yolo_dataset.zip")

    except Exception as e:
        status_log.append(f"❌ Exception: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "message": "Flask app is running"}

if __name__ == "__main__":
    os.makedirs(UPLOAD_ROOT, exist_ok=True)
    os.makedirs(MERGED_ROOT, exist_ok=True)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
