/** Feature component for managing documents. */
import React, { useState, useEffect } from 'react';

const DocumentsPanel: React.FC = () => {
  const [files, setFiles] = useState<any[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const load = async () => {
    const res = await fetch('/documents/');
    const data = await res.json();
    setFiles(data || []);
  };

  useEffect(() => {
    load();
  }, []);

  const upload = async () => {
    if (!selectedFile) return;
    const form = new FormData();
    form.append('file', selectedFile);
    await fetch('/documents/upload', { method: 'POST', body: form });
    load();
  };

  return (
    <div>
      <h3>Documents</h3>
      <input type="file" onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} />
      <button type="button" onClick={upload}>Upload</button>
      <ul>
        {files.map((file) => (
          <li key={file.id}>{file.filename}</li>
        ))}
      </ul>
    </div>
  );
};

export default DocumentsPanel;
