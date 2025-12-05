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
  const resolveApiUrl = () => {
    const envUrl = import.meta.env.VITE_API_URL;
    if (envUrl) return envUrl.replace(/\/$/, '');
    if (typeof window !== 'undefined') {
      return `${window.location.protocol}//${window.location.host}`;
    }
    if (typeof __VITE_API_URL_REQUIRED__ !== 'undefined' && __VITE_API_URL_REQUIRED__ === false) {
      // Should not happen in build because we guard in vite.config, but keep fallback for dev
      return 'http://localhost:8000';
    }
    throw new Error('VITE_API_URL is required at build time');
  };

  const [news, setNews] = useState([]);
  const [analytics, setAnalytics] = useState({
    sentiment_score: 0,
    trending_keywords: [],
    active_sources: 0,
    total_mentions: 0
  });
  const [subtitle, setSubtitle] = useState(null);
  const [view, setView] = useState('dashboard');
  const [kgTerms, setKgTerms] = useState([]);
  const [processingEnabled, setProcessingEnabled] = useState(true);
  const ws = useRef(null);

  const apiUrl = resolveApiUrl();
  const wsBase = (import.meta.env.VITE_WS_URL || apiUrl).replace(/^http/, 'ws').replace(/\/$/, '');
  const wsUrl = `${wsBase}/ws/monitor`;

  useEffect(() => {
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('Connected to WebSocket');
    };

    ws.current.onmessage = (event) => {
      if (!processingEnabled) return;
      const message = JSON.parse(event.data);

      if (message.type === 'news') {
        setNews(prev => [message.data, ...prev].slice(0, 20));
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
  }, [processingEnabled]);

  const toggleProcessing = async () => {
    try {
      const resp = await fetch(`${apiUrl}/live/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !processingEnabled }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setProcessingEnabled(Boolean(data.enabled));
    } catch (e) {
      console.error('Toggle live processing failed', e);
    }
  };

  return (
    <div className='flex flex-col h-screen bg-gray-950 text-white overflow-hidden font-sans'>
      <Header
        view={view}
        onChangeView={setView}
        processingEnabled={processingEnabled}
        onToggleProcessing={toggleProcessing}
      />

      {view === 'dashboard' && (
        <div className='flex-1 flex gap-2 p-2 overflow-hidden'>
          <div className='flex-[3] flex flex-col gap-2 overflow-hidden'>
            <div className='flex-[4] min-h-0'>
              <StreamGrid subtitle={subtitle} />
            </div>

            <div className='flex-1 flex gap-2 overflow-hidden min-h-0'>
              <div className='flex-1 overflow-auto'>
                <TranscriptPanel news={news} />
              </div>
              <div className='flex-1 overflow-hidden'>
                <EventTimeline
                  events={news}
                  onEventClick={(item) => {
                    const terms = item.keywords && item.keywords.length > 0
                      ? item.keywords
                      : (item.title ? [item.title] : []);
                    setKgTerms(terms);
                    setView('kg');
                  }}
                />
              </div>
            </div>

            <div className='h-12 flex-shrink-0'>
              <NewsTicker news={news} />
            </div>
          </div>

          <div className='flex-1 flex flex-col gap-2 overflow-hidden'>
            <div className='flex-1 overflow-auto'>
              <AnalyticsPanel data={analytics} />
            </div>

            <div className='flex-1 overflow-hidden'>
              <ChatPanel />
            </div>
          </div>
        </div>
      )}

      {view === 'kg' && (
        <div className='flex-1 p-2 overflow-hidden'>
          <KGExplorer externalTerms={kgTerms} />
        </div>
      )}
    </div>
  );
}

export default App;

