import React, { useEffect, useState } from 'react';

const resolveApiUrl = () => {
  const envUrl = import.meta.env.VITE_PERSON_API_URL || import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl.replace(/\/$/, '').replace(/:\d+$/, ':8001');
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8001`;
  }
  return 'http://localhost:8001';
};

const PeopleManager = () => {
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: '',
    nationality: '',
    date_of_birth: '',
    id_number: '',
    aliases: '',
    note: '',
    file: null,
  });
  const [saving, setSaving] = useState(false);

  const personApi = resolveApiUrl();

  const loadPeople = async () => {
    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${personApi}/people`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setPeople(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Failed to load people');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPeople();
  }, []);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    setForm((prev) => ({ ...prev, file }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.file) {
      setError('Name and image are required');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('name', form.name.trim());
      fd.append('nationality', form.nationality || '');
      fd.append('date_of_birth', form.date_of_birth || '');
      fd.append('id_number', form.id_number || '');
      fd.append('aliases', form.aliases || '');
      fd.append('note', form.note || '');
      fd.append('file', form.file, form.file.name || 'person.jpg');
      const resp = await fetch(`${personApi}/people`, {
        method: 'POST',
        body: fd,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
      setForm({
        name: '',
        nationality: '',
        date_of_birth: '',
        id_number: '',
        aliases: '',
        note: '',
        file: null,
      });
      await loadPeople();
    } catch (err) {
      setError(err.message || 'Failed to save person');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!id) return;
    try {
      const resp = await fetch(`${personApi}/people/${id}`, { method: 'DELETE' });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }
      setPeople((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err.message || 'Failed to delete');
    }
  };

  return (
    <div className="h-full w-full bg-gray-900 text-white p-4 flex flex-col gap-4 overflow-hidden">
      <div>
        <h2 className="text-lg font-semibold">People Dataset</h2>
        <p className="text-sm text-gray-400">Upload faces with metadata for lookup/testing.</p>
      </div>

      <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
        <form
          onSubmit={handleSubmit}
          className="col-span-1 bg-gray-850 border border-gray-800 rounded-lg p-3 flex flex-col gap-2"
        >
          <div className="text-sm font-semibold mb-1">Add person</div>
          <label className="text-xs text-gray-300 flex flex-col gap-1">
            Name *
            <input
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm"
              required
            />
          </label>
          <label className="text-xs text-gray-300 flex flex-col gap-1">
            Nationality
            <input
              value={form.nationality}
              onChange={(e) => setForm((p) => ({ ...p, nationality: e.target.value }))}
              className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm"
            />
          </label>
          <label className="text-xs text-gray-300 flex flex-col gap-1">
            Date of birth
            <input
              type="date"
              value={form.date_of_birth}
              onChange={(e) => setForm((p) => ({ ...p, date_of_birth: e.target.value }))}
              className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm"
            />
          </label>
          <label className="text-xs text-gray-300 flex flex-col gap-1">
            ID / Passport number
            <input
              value={form.id_number}
              onChange={(e) => setForm((p) => ({ ...p, id_number: e.target.value }))}
              className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm"
            />
          </label>
          <label className="text-xs text-gray-300 flex flex-col gap-1">
            Aliases (comma separated)
            <input
              value={form.aliases}
              onChange={(e) => setForm((p) => ({ ...p, aliases: e.target.value }))}
              className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm"
            />
          </label>
          <label className="text-xs text-gray-300 flex flex-col gap-1">
            Note
            <textarea
              value={form.note}
              onChange={(e) => setForm((p) => ({ ...p, note: e.target.value }))}
              rows={3}
              className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm resize-none"
            />
          </label>
          <label className="text-xs text-gray-300 flex flex-col gap-1">
            Image *
            <input type="file" accept="image/*" onChange={handleFileChange} className="text-sm" required />
          </label>
          <button
            type="submit"
            disabled={saving}
            className="mt-1 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-semibold disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Upload'}
          </button>
          {error && <div className="text-xs text-red-400">{error}</div>}
        </form>

        <div className="col-span-2 bg-gray-850 border border-gray-800 rounded-lg p-3 overflow-auto">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-semibold">People</div>
            {loading && <div className="text-xs text-gray-500">Loading...</div>}
          </div>
          {people.length === 0 && !loading && (
            <div className="text-sm text-gray-500">No people yet. Add one to get started.</div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {people.map((p) => (
              <div key={p.id || p.name} className="bg-gray-900 border border-gray-800 rounded-lg p-2 flex flex-col gap-2">
                <div className="h-32 bg-gray-800 rounded overflow-hidden flex items-center justify-center">
                  <img
                    src={`${personApi}/people/${p.id}/image`}
                    alt={p.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                </div>
                <div className="text-sm font-semibold truncate">{p.name}</div>
                {(p.nationality || p.date_of_birth) && (
                  <div className="text-[11px] text-gray-400">
                    {p.nationality && <span>{p.nationality}</span>}
                    {p.nationality && p.date_of_birth && <span> · </span>}
                    {p.date_of_birth && <span>{p.date_of_birth}</span>}
                  </div>
                )}
                {p.id_number && <div className="text-[11px] text-gray-400 truncate">ID: {p.id_number}</div>}
                {p.aliases?.length > 0 && (
                  <div className="text-[11px] text-gray-400 truncate">Aliases: {p.aliases.join(', ')}</div>
                )}
                {p.note && <div className="text-xs text-gray-500 line-clamp-2">{p.note}</div>}
                <button
                  onClick={() => handleDelete(p.id)}
                  className="px-2 py-1 text-xs rounded border border-red-500 text-red-300 hover:bg-red-500/10"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PeopleManager;
