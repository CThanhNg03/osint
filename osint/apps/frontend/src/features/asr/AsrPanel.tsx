/** Feature component for ASR uploads. */
import React, { useState } from 'react';

const AsrPanel: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');

  const upload = async () => {
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/asr/transcribe', { method: 'POST', body: form });
    const data = await res.json();
    setText(data.text);
  };

  return (
    <div>
      <h3>ASR</h3>
      <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <button type="button" onClick={upload}>Transcribe</button>
      <p>{text}</p>
    </div>
  );
};

export default AsrPanel;
