/** Hook to fetch news items from the backend. */
import { useState } from 'react';
import { getNews } from '../../shared/api/endpoints';
import { NewsItem } from '../../shared/types/news';

const useNews = () => {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [query, setQuery] = useState('');

  const fetchNews = async () => {
    const response = await getNews(query || 'latest');
    setItems(response.items || []);
  };

  return { items, query, setQuery, fetchNews };
};

export default useNews;
