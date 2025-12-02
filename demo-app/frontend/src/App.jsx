import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import NewsTicker from './components/NewsTicker';
import StreamGrid from './components/StreamGrid';
import AnalyticsPanel from './components/AnalyticsPanel';
import ChatPanel from './components/ChatPanel';
import EventTimeline from './components/EventTimeline';
import TranscriptPanel from './components/TranscriptPanel';
import KGExplorer from './components/KGExplorer';

function App() {
  const [news, setNews] = useState([]);
  const [analytics, setAnalytics] = useState({
    sentiment_score: 0,
    trending_keywords: [],
    active_sources: 0,
    total_mentions: 0
  });
  const [subtitle, setSubtitle] = useState(null);
  const [view, setView] = useState('dashboard');
  const ws = useRef(null);

  useEffect(() => {
    // Connect to WebSocket
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsUrl =
      import.meta.env.VITE_WS_URL ||
      apiUrl.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws/monitor';

    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('Connected to WebSocket');
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'news') {
        setNews(prev => [message.data, ...prev].slice(0, 20)); // Keep last 20 items
      } else if (message.type === 'analytics') {
        setAnalytics(message.data);
      } else if (message.type === 'subtitle') {
        setSubtitle(message.data);
      }
    };

    ws.current.onclose = () => {
      console.log('Disconnected from WebSocket');
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white overflow-hidden font-sans">
      <Header view={view} onChangeView={setView} />

      {view === 'dashboard' && (
        <div className="flex-1 flex gap-2 p-2 overflow-hidden">
          {/* LEFT: Video + Info (75% width) */}
          <div className="flex-[3] flex flex-col gap-2 overflow-hidden">
            {/* Video - Larger height */}
            <div className="flex-[4] min-h-0">
              <StreamGrid subtitle={subtitle} />
            </div>

            {/* Bottom Row - 25% height */}
            <div className="flex-1 flex gap-2 overflow-hidden min-h-0">
              {/* Transcript */}
              <div className="flex-1 overflow-auto">
                <TranscriptPanel news={news} />
              </div>
              {/* Timeline */}
              <div className="flex-1 overflow-hidden">
                <EventTimeline events={news} />
              </div>
            </div>

            {/* News Ticker */}
            <div className="h-12 flex-shrink-0">
              <NewsTicker news={news} />
            </div>
          </div>

          {/* RIGHT: Analytics + Chat (25% width) */}
          <div className="flex-1 flex flex-col gap-2 overflow-hidden">
            {/* Analytics */}
            <div className="flex-1 overflow-auto">
              <AnalyticsPanel data={analytics} />
            </div>

            {/* Chat */}
            <div className="flex-1 overflow-hidden">
              <ChatPanel />
            </div>
          </div>
        </div>
      )}

      {view === 'kg' && (
        <div className="flex-1 p-2 overflow-hidden">
          <KGExplorer />
        </div>
      )}
    </div>
  );
}

export default App;
