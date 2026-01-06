/** Feature component for the news page. */
import React from 'react';
import useNews from './useNews';

const NewsPanel: React.FC = () => {
  const { items, query, setQuery, fetchNews } = useNews();

  return (
    <div>
      <h3>News</h3>
      <div className="controls">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search topic" />
        <button type="button" onClick={fetchNews}>Search</button>
      </div>
      <ul>
        {items.map((item) => (
          <li key={item.url}>
            <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default NewsPanel;
