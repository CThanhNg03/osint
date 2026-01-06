/** Typed endpoint helpers mapping to backend routes. */
import { getJson, postJson } from './http';
import { NewsResponse } from '../types/news';
import { LiveState } from '../types/live';

export const getNews = (query: string) => getJson<NewsResponse>(`/crawl?query=${encodeURIComponent(query)}`);
export const getLiveState = () => getJson<LiveState>('/live/state');
export const setLiveState = (enabled: boolean) => postJson<LiveState>('/live/toggle', { enabled });
