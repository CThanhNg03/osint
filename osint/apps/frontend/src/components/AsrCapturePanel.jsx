import React, { useEffect, useState } from 'react';

const resolveApiUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl.replace(/\/$/, '');
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.host}`;
  }
  return 'http://localhost:8000';
};

const emptySources = ['', '', ''];

const AsrCapturePanel = () => {
  const [sources, setSources] = useState(emptySources);
  const [captureSeconds, setCaptureSeconds] = useState(20);
  const [breakSeconds, setBreakSeconds] = useState(10);
  const [captureRate, setCaptureRate] = useState(1);
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const loadStatus = async () => {
    try {
      const resp = await fetch(`${resolveApiUrl()}/asr/status`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Failed to load status');
      setStatus(data);
      setSources(data.sources && data.sources.length ? data.sources : emptySources);
      setCaptureSeconds(data.capture_seconds ?? 20);
      setBreakSeconds(data.break_seconds ?? 10);
      setCaptureRate(data.capture_rate ?? 1);
      setError('');
    } catch (err) {
      setError(err.message || 'Unable to load ASR status');
    }
  };

  useEffect(() => {
    loadStatus();
    const id = setInterval(loadStatus, 15000);
    return () => clearInterval(id);
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = {
        sources,
        capture_seconds: Number(captureSeconds),
        break_seconds: Number(breakSeconds),
        capture_rate: Number(captureRate),
      };
      const resp = await fetch(`${resolveApiUrl()}/asr/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Update failed');
      setStatus(data);
    } catch (err) {
      setError(err.message || 'Unable to update ASR config');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="h-full bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-white font-semibold text-sm uppercase tracking-wide">Whisper ASR Capture</h3>
          <p className="text-xs text-gray-400">Auto-record audio clips instead of CV frame capture.</p>
        </div>
        <span
          className={`text-xs px-2 py-1 rounded ${
            status?.running ? 'bg-green-900/40 text-green-200' : 'bg-gray-800 text-gray-400'
          }`}
        >
          {status?.running ? 'Running' : 'Stopped'}
        </span>
      </div>

      <form onSubmit={handleSave} className="space-y-3 flex-1 flex flex-col">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {sources.map((src, idx) => (
            <div key={idx} className="flex flex-col">
              <label className="text-xs text-gray-400 mb-1">Source #{idx + 1}</label>
              <input
                value={src}
                onChange={(e) => {
                  const next = [...sources];
                  next[idx] = e.target.value;
                  setSources(next);
                }}
                placeholder="https://www.youtube.com/watch?v=..."
                className="bg-gray-800 border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Capture time (seconds)</label>
            <input
              type="number"
              min="5"
              value={captureSeconds}
              onChange={(e) => setCaptureSeconds(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Break time (seconds)</label>
            <input
              type="number"
              min="0"
              value={breakSeconds}
              onChange={(e) => setBreakSeconds(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Capture rate (clips per source)</label>
            <input
              type="number"
              min="1"
              value={captureRate}
              onChange={(e) => setCaptureRate(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="flex items-center gap-2 mt-auto">
          <button
            type="submit"
            disabled={saving}
            className="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded text-sm font-semibold disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save & apply'}
          </button>
          <button
            type="button"
            onClick={loadStatus}
            className="px-3 py-2 rounded text-sm border border-gray-700 text-gray-300 hover:bg-gray-800"
          >
            Refresh
          </button>
          {error && <span className="text-xs text-red-400">{error}</span>}
        </div>
      </form>

      {status?.last_result && (
        <div className="mt-3 border-t border-gray-800 pt-3">
          <div className="text-xs text-gray-400 mb-1">Last capture</div>
          <div className="text-sm text-gray-100 font-semibold">
            {status.last_result.source} — {status.last_result.timestamp}
          </div>
          <div className="text-sm text-gray-300 line-clamp-2">{status.last_result.text}</div>
        </div>
      )}
    </div>
  );
};

export default AsrCapturePanel;
