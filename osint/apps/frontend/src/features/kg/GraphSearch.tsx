/** Feature component for searching the knowledge graph. */
import React, { useState } from 'react';

const GraphSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<string>('');

  const search = async () => {
    const response = await fetch(`/kg/search?query=${encodeURIComponent(query)}`);
    const data = await response.json();
    setResult(JSON.stringify(data.graph));
  };

  return (
    <div>
      <h3>Knowledge Graph</h3>
      <div className="controls">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Entity" />
        <button type="button" onClick={search}>Search</button>
      </div>
      <pre>{result}</pre>
    </div>
  );
};

export default GraphSearch;
