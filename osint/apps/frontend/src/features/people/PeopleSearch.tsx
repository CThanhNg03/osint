/** Feature component for people search. */
import React, { useState } from 'react';

const PeopleSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);

  const search = async () => {
    const res = await fetch(`/people/search?query=${encodeURIComponent(query)}`);
    const data = await res.json();
    setResults(data.people || []);
  };

  return (
    <div>
      <h3>People</h3>
      <div className="controls">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name" />
        <button type="button" onClick={search}>Search</button>
      </div>
      <ul>
        {results.map((person) => (
          <li key={person.name}>{person.name}</li>
        ))}
      </ul>
    </div>
  );
};

export default PeopleSearch;
