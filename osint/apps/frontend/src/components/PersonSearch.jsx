import React, { useEffect, useState } from 'react';

const resolveApiUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl.replace(/\/$/, '');
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.host}`;
  }
  return 'http://localhost:8000';
};

// Person API is proxied by the gateway; use API_URL unless explicitly overridden
const resolvePersonApiUrl = () => {
  const envUrl = import.meta.env.VITE_PERSON_API_URL || import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl.replace(/\/$/, '');
  return resolveApiUrl();
};

const PersonSearch = ({ initialImage, onBack, onExploreKG }) => {
  const [imagePreview, setImagePreview] = useState(initialImage?.preview || '');
  const [imageFile, setImageFile] = useState(initialImage?.file || null);
  const [faces, setFaces] = useState([]);
  const [requestId, setRequestId] = useState('');
  const [personInfo, setPersonInfo] = useState(null);
  const [personMatches, setPersonMatches] = useState([]);
  const [statusMsg, setStatusMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [crawlLoading, setCrawlLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedFaceId, setSelectedFaceId] = useState('');
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [hasSocialPreview, setHasSocialPreview] = useState(false);

  const personApi = resolvePersonApiUrl();

  const detectImage = async (file) => {
    if (!file) return;
    setLoading(true);
    setError('');
    setFaces([]);
    setPersonInfo(null);
    setPersonMatches([]);
    setStatusMsg('Detecting faces...');
    try {
      const form = new FormData();
      form.append('file', file, file.name || 'capture.jpg');
      const resp = await fetch(`${personApi}/image/detect`, {
        method: 'POST',
        body: form,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Detection failed');
      setRequestId(data.request_id || '');
      setFaces(data.faces || (data.face ? [data.face] : []));
      setStatusMsg(data.message || data.status || '');
      if (data.person) {
        setPersonInfo(data.person);
      }
      setPersonMatches([]);
    } catch (err) {
      setError(err.message || 'Detect failed');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
  };

  const handleSelectFace = async (faceId) => {
    setLoading(true);
    setError('');
    setStatusMsg('Searching faces...');
    setSelectedFaceId(faceId);
    setPersonMatches([]);
    try {
      const face = faces.find((f) => f.face_id === faceId);
      let blob;
      if (face?.preview) {
        const bin = atob(face.preview);
        const buf = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i += 1) buf[i] = bin.charCodeAt(i);
        blob = new Blob([buf], { type: 'image/jpeg' });
      } else if (imageFile) {
        blob = imageFile;
      } else {
        throw new Error('No face preview or image to search');
      }

      const fd = new FormData();
      fd.append('file', blob, 'face.jpg');
      const resp = await fetch(`${personApi}/people/search/face?limit=5`, {
        method: 'POST',
        body: fd,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Lookup failed');
      const best = data.result || (Array.isArray(data.results) ? data.results[0] : null);
      const results = data.result ? [data.result] : data.results || [];
      setPersonMatches(results);
      setPersonInfo(best || null);
      setStatusMsg(best ? 'Match found' : data.message || 'No match found');
    } catch (err) {
      setError(err.message || 'Lookup failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGetSocial = async () => {
    if (!personInfo?.name) return;
    setCrawlLoading(true);
    setStatusMsg('Fetching social preview...');
    setError('');
    try {
      const resp = await fetch(
        `${import.meta.env.VITE_API_URL?.replace(/\/$/, '') || `${window.location.protocol}//${window.location.host}`}/people/social/preview?person_id=${encodeURIComponent(personInfo.id || '')}`
      );
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }
      const primaryAcc = data.social_graph?.accounts?.[0];
      if (primaryAcc) {
        setSelectedAccount(primaryAcc);
        setStatusMsg(`Using X account ${primaryAcc.handle || primaryAcc.display_name || primaryAcc.id}`);
      }
      setHasSocialPreview(true);
    } catch (err) {
      setError(err.message || 'Crawl failed');
    } finally {
      setCrawlLoading(false);
      setStatusMsg('');
    }
  };

  const handleExplore = async () => {
    if (!personInfo?.name || !hasSocialPreview) return;
    setCrawlLoading(true);
    setStatusMsg('Crawling social/KG...');
    setError('');
    try {
      const gateway =
        import.meta.env.VITE_API_URL?.replace(/\/$/, '') ||
        `${window.location.protocol}//${window.location.host}`;
      const resp = await fetch(
        `${gateway}/people/social/crawl?person_id=${encodeURIComponent(personInfo.id || '')}`,
        { method: 'POST' }
      );
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }
      const primaryAcc = data.social_graph?.accounts?.[0];
      if (primaryAcc) {
        setSelectedAccount(primaryAcc);
        setStatusMsg(`Using X account ${primaryAcc.handle || primaryAcc.display_name || primaryAcc.id}`);
      }
      const fallbackCypher = `
        MATCH (p:Person)
        WHERE toLower(p.name) = toLower("${(personInfo.name || '').replace(/"/g, '\\"')}")
        OPTIONAL MATCH (p)-[r1:POSTED]->(po:Post)
        OPTIONAL MATCH (po)<-[r2:COMMENTED_ON]-(a:Account)
        RETURN p, po, r1, r2, a
        LIMIT 200
      `;
      onExploreKG?.({
        ...personInfo,
        social_graph: data.social_graph,
        cypher: data.cypher || fallbackCypher,
        message: data.message,
      });
    } catch (err) {
      setError(err.message || 'Crawl failed');
    } finally {
      setCrawlLoading(false);
      setStatusMsg('');
    }
  };

  useEffect(() => {
    if (initialImage?.file) {
      detectImage(initialImage.file);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialImage?.file]);

  return (
    <div className="h-full bg-gray-900 text-white p-4 flex flex-col gap-4 overflow-hidden">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Human Search</h2>
          <p className="text-sm text-gray-400">Upload or capture a frame, pick a face, retrieve info.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setFaces([]);
              setPersonInfo(null);
              setStatusMsg('');
              setError('');
            }}
            className="px-3 py-2 text-sm rounded border border-gray-700 hover:bg-gray-800"
          >
            Reset
          </button>
          <button
            onClick={onBack}
            className="px-3 py-2 text-sm rounded bg-gray-800 hover:bg-gray-700 border border-gray-700"
          >
            Back
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
        <div className="col-span-1 flex flex-col gap-3">
          <div className="bg-gray-850 border border-gray-800 rounded-lg p-3 flex-1">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold">Image</h4>
              <label className="text-xs cursor-pointer bg-indigo-600 hover:bg-indigo-500 px-3 py-1 rounded font-semibold">
                Upload
                <input type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
              </label>
            </div>
            {imagePreview ? (
              <img
                src={imagePreview}
                alt="preview"
                className="w-full max-h-64 object-contain rounded border border-gray-800"
              />
            ) : (
              <div className="text-sm text-gray-500">No image selected.</div>
            )}
            <button
              onClick={() => detectImage(imageFile)}
              disabled={!imageFile || loading}
              className="mt-3 w-full bg-indigo-600 hover:bg-indigo-500 rounded px-3 py-2 text-sm font-semibold disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Detect faces'}
            </button>
            {statusMsg && <div className="text-xs text-gray-400 mt-2">{statusMsg}</div>}
            {error && <div className="text-xs text-red-400 mt-2">{error}</div>}
          </div>
        </div>

        <div className="col-span-1 bg-gray-850 border border-gray-800 rounded-lg p-3 overflow-auto">
          <h4 className="text-sm font-semibold mb-2">Detected faces</h4>
          {faces.length === 0 && <div className="text-sm text-gray-500">No faces yet.</div>}
          <div className="space-y-2">
            {faces.map((f) => (
              <div
                key={f.face_id}
                className={`p-2 rounded border ${
                  selectedFaceId === f.face_id ? 'border-indigo-500' : 'border-gray-800'
                } bg-gray-900 flex gap-2`}
              >
                {f.preview ? (
                  <img
                    src={`data:image/jpeg;base64,${f.preview}`}
                    alt={f.face_id}
                    className="w-20 h-20 object-cover rounded border border-gray-800"
                  />
                ) : (
                  <div className="w-20 h-20 rounded border border-gray-800 bg-gray-800 text-[10px] text-gray-500 flex items-center justify-center">
                    No preview
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold truncate">ID: {f.face_id}</div>
                  <div className="text-xs text-gray-400">
                    BBox: {Array.isArray(f.bbox) ? f.bbox.join(', ') : 'n/a'}
                  </div>
                  <button
                    onClick={() => handleSelectFace(f.face_id)}
                    className="mt-2 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 rounded text-xs font-semibold"
                    disabled={loading}
                  >
                    {loading && selectedFaceId === f.face_id ? 'Working...' : 'Select & search'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-1 bg-gray-850 border border-gray-800 rounded-lg p-3 overflow-auto">
          <h4 className="text-sm font-semibold mb-2">Person info</h4>
          {!personInfo && <div className="text-sm text-gray-500">Select a face to see info.</div>}
          {personInfo && (
            <div className="bg-gray-900 rounded p-3 text-sm space-y-2 border border-gray-800">
              <div className="font-semibold text-white">{personInfo.name || 'Unknown'}</div>
              <div className="text-gray-400 text-xs">
                {personInfo.nationality && <span>{personInfo.nationality}</span>}
                {personInfo.nationality && personInfo.date_of_birth && <span> · </span>}
                {personInfo.date_of_birth && <span>DOB: {personInfo.date_of_birth}</span>}
              </div>
              {personInfo.id_number && (
                <div className="text-xs text-gray-300">
                  <span className="font-semibold text-gray-200">ID:</span> {personInfo.id_number}
                </div>
              )}
              {personInfo.aliases?.length > 0 && (
                <div className="text-xs text-gray-300">
                  <span className="font-semibold text-gray-200">Aliases:</span> {personInfo.aliases.join(', ')}
                </div>
              )}
              {personInfo.note && <div className="text-xs text-gray-300">{personInfo.note}</div>}
              {typeof personInfo.score === 'number' && (
                <div className="text-[11px] text-gray-400">Match score: {personInfo.score.toFixed(3)}</div>
              )}
              {selectedAccount && (
                <div className="text-xs text-gray-300">
                  X account: {selectedAccount.handle || selectedAccount.display_name || selectedAccount.id}
                </div>
              )}
              {statusMsg && <div className="text-[11px] text-yellow-400">{statusMsg}</div>}
              {!hasSocialPreview && (
                <button
                  onClick={handleGetSocial}
                  className="mt-1 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-xs font-semibold w-full disabled:opacity-50"
                  disabled={!personInfo.name || crawlLoading}
                >
                  {crawlLoading ? 'Fetching...' : 'Get Social'}
                </button>
              )}
              {hasSocialPreview && (
                <button
                  onClick={handleExplore}
                  className="mt-1 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-xs font-semibold w-full disabled:opacity-50"
                  disabled={!personInfo.name || crawlLoading}
                >
                  {crawlLoading ? 'Crawling...' : 'Crawl & Explore KG'}
                </button>
              )}
            </div>
          )}
          {personMatches.length > 0 && (
            <div className="mt-3 space-y-1 text-xs text-gray-300">
              <div className="text-gray-400 text-[11px]">Matches</div>
              {personMatches.map((m) => (
                <div key={m.id || m.name} className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded px-2 py-1">
                  <span className="truncate">{m.name || m.id}</span>
                  <span className="text-[11px] text-gray-500">score: {m.score?.toFixed(3)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PersonSearch;
