/** Shared types for news feature. */
export type NewsItem = {
  title?: string;
  url?: string;
  source?: string;
};

export type NewsResponse = {
  items: NewsItem[];
};
