from flask import Flask, request, send_file, abort
from flask_cors import CORS
import os, shutil, zipfile, tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_ROOT = "uploads"
MERGED_ROOT = "merged-dataset"

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
