from flask import Flask, request, send_file, abort, render_template_string
from flask_cors import CORS
import os, shutil, zipfile, tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_ROOT = "uploads"
MERGED_ROOT = "merged-dataset"

# Single homepage route (removed duplicate)
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
            .upload-form { background: #fff; padding: 20px; border-radius: 5px; margin: 20px 0; }
            input[type="file"] { margin: 10px 0; }
            button { background: #2196f3; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #1976d2; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 YOLO Models Dataset Merger App</h1>
            
            <div class="info">
                <h3>✅ App Status: Running Successfully!</h3>
                <p>Your Flask application is deployed and ready to merge YOLO datasets.</p>
            </div>

            <div class="upload-form">
                <h3>📤 Upload Datasets</h3>
                <form action="/merge" method="post" enctype="multipart/form-data">
                    <label for="dataset_count">Number of datasets (2-10):</label><br>
                    <input type="number" id="dataset_count" name="dataset_count" min="2" max="10" value="2" required><br><br>
                    
                    <label for="files">Select ZIP files:</label><br>
                    <input type="file" id="files" name="files" multiple accept=".zip" required><br><br>
                    
                    <button type="submit">Merge Datasets</button>
                </form>
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
            <p>1. Use the form above to upload your datasets, or</p>
            <p>2. Send a POST request to <code>/merge</code> with your YOLO dataset ZIP files.</p>
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
    try:
        files = request.files.getlist("files")
        dataset_count = int(request.form.get("dataset_count", 0))

        # Validation
        if dataset_count < 2 or dataset_count > 10:
            return "Error: dataset_count must be between 2 and 10.", 400
        if len(files) != dataset_count:
            return f"Error: Expected {dataset_count} files, got {len(files)}.", 400
        
        # Check if all files are ZIP files
        for file in files:
            if not file.filename.lower().endswith('.zip'):
                return f"Error: All files must be ZIP files. '{file.filename}' is not a ZIP file.", 400

        # Clear and recreate folders
        if os.path.exists(UPLOAD_ROOT):
            shutil.rmtree(UPLOAD_ROOT)
        if os.path.exists(MERGED_ROOT):
            shutil.rmtree(MERGED_ROOT)
        os.makedirs(UPLOAD_ROOT, exist_ok=True)
        os.makedirs(MERGED_ROOT, exist_ok=True)

        dataset_dirs, class_names = [], []

        # Save and unzip each dataset
        for i, f in enumerate(files):
            if not f.filename:
                return f"Error: File {i+1} has no filename.", 400
                
            filename = secure_filename(f.filename)
            if not filename:
                return f"Error: Invalid filename for file {i+1}.", 400
                
            save_path = os.path.join(UPLOAD_ROOT, filename)
            f.save(save_path)

            # Extract dataset
            extract_dir = os.path.join(UPLOAD_ROOT, filename.replace(".zip", ""))
            try:
                with zipfile.ZipFile(save_path, "r") as zf:
                    zf.extractall(extract_dir)
            except zipfile.BadZipFile:
                return f"Error: '{filename}' is not a valid ZIP file.", 400

            dataset_dirs.append(extract_dir)
            class_names.append(os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title())

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
                    try:
                        with open(path, 'r') as f:
                            lines = [line.strip().split() for line in f if line.strip()]
                        with open(path, "w") as f:
                            for parts in lines:
                                if len(parts) >= 5:  # Valid YOLO format: class x y w h
                                    parts[0] = str(cid)
                                    f.write(" ".join(parts) + "\n")
                    except Exception as e:
                        print(f"Warning: Could not process {path}: {e}")

        # Prepare merged folders
        for split in ["train", "valid", "test"]:
            for sub in ["images", "labels"]:
                os.makedirs(os.path.join(MERGED_ROOT, split, sub), exist_ok=True)

        # Copy files into merged folder
        for ddir in dataset_dirs:
            for split in ["train", "valid", "test"]:
                for sub in ["images", "labels"]:
                    src = os.path.join(ddir, split, sub)
                    dst = os.path.join(MERGED_ROOT, split, sub)
                    if os.path.isdir(src):
                        for f in os.listdir(src):
                            src_file = os.path.join(src, f)
                            dst_file = os.path.join(dst, f)
                            # Handle duplicate filenames
                            counter = 1
                            original_dst = dst_file
                            while os.path.exists(dst_file):
                                name, ext = os.path.splitext(original_dst)
                                dst_file = f"{name}_{counter}{ext}"
                                counter += 1
                            shutil.copy2(src_file, dst_file)

        # Create data.yaml
        yaml_content = f"""train: ./train/images
val: ./valid/images
test: ./test/images

nc: {len(class_names)}
names: {class_names}
"""
        with open(os.path.join(MERGED_ROOT, "data.yaml"), "w") as f:
            f.write(yaml_content)

        # Create README with merge info
        readme_content = f"""# Merged YOLO Dataset

This dataset was created by merging {len(class_names)} datasets:
{chr(10).join([f"- Class {i}: {name}" for i, name in enumerate(class_names)])}

## Dataset Structure
- train/: Training images and labels
- valid/: Validation images and labels  
- test/: Test images and labels
- data.yaml: Dataset configuration file

## Classes
Total classes: {len(class_names)}
{chr(10).join([f"{i}: {name}" for i, name in enumerate(class_names)])}
"""
        with open(os.path.join(MERGED_ROOT, "README.md"), "w") as f:
            f.write(readme_content)

        # Create ZIP file
        zip_path = os.path.join(tempfile.gettempdir(), "merged_dataset.zip")
        shutil.make_archive(zip_path[:-4], "zip", MERGED_ROOT)
        
        return send_file(zip_path, as_attachment=True, download_name="merged_yolo_dataset.zip")

    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}", 500

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "healthy", "message": "YOLO Dataset Merger API is running"}

if __name__ == "__main__":
    # Create directories if they don't exist
    os.makedirs(UPLOAD_ROOT, exist_ok=True)
    os.makedirs(MERGED_ROOT, exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)