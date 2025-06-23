import React, { useState } from 'react';
import axios from 'axios';

const UploadForm = () => {
  const [datasetCount, setDatasetCount] = useState(2);
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState("");

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length !== datasetCount) {
      alert(`Please upload exactly ${datasetCount} zip files.`);
      return;
    }

    const formData = new FormData();
    files.forEach(file => formData.append("files", file));
    formData.append("dataset_count", datasetCount);

    try {
      setStatus("Processing...");
      const response = await axios.post("http://localhost:5000/merge", formData, {
        responseType: "blob"
      });

      const blob = new Blob([response.data], { type: "application/zip" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "merged.zip";
      a.click();
      setStatus("Download ready ✅");
    } catch (error) {
      console.error(error);
      setStatus("Error during merging ❌");
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <label>
          Choose number of datasets to merge:
          <select value={datasetCount} onChange={(e) => setDatasetCount(Number(e.target.value))}>
            {Array.from({ length: 9 }, (_, i) => i + 2).map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <br /><br />
        <input type="file" multiple accept=".zip" onChange={handleFileChange} />
        <br /><br />
        <button type="submit">Merge and Download</button>
      </form>
      <p>{status}</p>
    </div>
  );
};

export default UploadForm;

