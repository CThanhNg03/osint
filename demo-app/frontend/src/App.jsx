import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import NewsTicker from './components/NewsTicker';
import StreamGrid from './components/StreamGrid';
import AnalyticsPanel from './components/AnalyticsPanel';
import ChatPanel from './components/ChatPanel';
import EventTimeline from './components/EventTimeline';
import TranscriptPanel from './components/TranscriptPanel';
import KGExplorer from './components/KGExplorer';
import PersonSearch from './components/PersonSearch';
import PeopleManager from './components/PeopleManager';
import DocumentManager from './components/DocumentManager';
import PersonReport from './components/PersonReport';
import { defaultSources } from './components/LivePlayer';

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
  const [togglingLive, setTogglingLive] = useState(false);
  const [subtitle, setSubtitle] = useState(null);
  const [view, setView] = useState('dashboard');
  const [kgTerms, setKgTerms] = useState([]);
  const [kgCypher, setKgCypher] = useState(null);
  const [kgMode, setKgMode] = useState('person'); // person | entity
  const [processingEnabled, setProcessingEnabled] = useState(false);
  const [personImage, setPersonImage] = useState(null);
  const [selectedSourceId, setSelectedSourceId] = useState(defaultSources[0]?.id || '');
  const [personReportTarget, setPersonReportTarget] = useState(null);
  const livePlayerRef = useRef(null);
  const ws = useRef(null);

  const apiUrl = resolveApiUrl();
  const rawWs = import.meta.env.VITE_WS_URL || apiUrl;
  const wsBaseNormalized = rawWs.replace(/^http/, 'ws');
  const hasPath = /\/ws\/monitor\/?$/.test(wsBaseNormalized);
  const wsBase = wsBaseNormalized.replace(/\/$/, '');
  const wsUrl = hasPath ? wsBase : `${wsBase}/ws/monitor`;

  // Fetch initial live state from backend
  useEffect(() => {
    const fetchState = async () => {
      try {
        const resp = await fetch(`${apiUrl}/live/state`);
        if (!resp.ok) return;
        const data = await resp.json();
        setProcessingEnabled(Boolean(data.enabled));
      } catch (e) {
        console.warn('Failed to fetch live state', e);
      }
    };
    fetchState();
  }, [apiUrl]);

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

  useEffect(() => {
    if (view !== 'personSearch' && personImage) {
      setPersonImage(null);
    }
  }, [view, personImage]);

  const toggleProcessing = async () => {
    if (togglingLive) return;
    setTogglingLive(true);
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
    } finally {
      setTogglingLive(false);
    }
  };

  const captureScreenForPersonSearch = async () => {
    // Prefer a source snapshot (YouTube thumbnail) to avoid screen-share prompts.
    const source = selectedSource;
    if (source?.type === 'youtube' && source.videoId) {
      const thumbUrl = `https://img.youtube.com/vi/${source.videoId}/0.jpg`;
      try {
        const resp = await fetch(thumbUrl, { mode: 'cors' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const file = new File([blob], `${source.videoId}.jpg`, { type: 'image/jpeg' });
        const preview = URL.createObjectURL(blob);
        setPersonImage({ file, preview });
        setView('personSearch');
        return;
      } catch (err) {
        console.error('Thumbnail capture failed, falling back to screen capture', err);
      }
    }

    // Fallback: screen capture if allowed.
    if (!navigator.mediaDevices?.getDisplayMedia) {
      alert('Screen capture not supported in this browser. Upload a frame instead.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const track = stream.getVideoTracks()[0];
      const imageCapture = new ImageCapture(track);
      const bitmap = await imageCapture.grabFrame();

      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(bitmap, 0, 0);

      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
      track.stop();
      const preview = URL.createObjectURL(blob);
      setPersonImage({ file: new File([blob], 'capture.jpg', { type: 'image/jpeg' }), preview });
      setView('personSearch');
    } catch (err) {
      console.error('Screen capture failed', err);
      alert('Screen capture cancelled or failed.');
    }
  };

  const selectedSource = defaultSources.find((s) => s.id === selectedSourceId) || defaultSources[0];

  const matchesSource = (itemSource = '') => {
    if (!itemSource || !selectedSource) return true;
    const lower = itemSource.toLowerCase();
    const candidates = [selectedSource.match, selectedSource.videoId, selectedSource.url, selectedSource.label]
      .filter(Boolean)
      .map((s) => s.toLowerCase());
    return candidates.some((c) => lower.includes(c));
  };

  const filteredNews = (news || []).filter((n) => matchesSource(n.source));
  const newsForPanels = filteredNews.length ? filteredNews : news;

  const handleWhisperNews = (transcript, newsFromApi) => {
    const text = (transcript && transcript.text) || (newsFromApi && newsFromApi.title) || '';
    if (!text) return;

    const now = new Date().toISOString();
    const sourceLabel =
      (selectedSource && (selectedSource.label || selectedSource.name || selectedSource.id)) ||
      'Live Channel';
    const newsItem = newsFromApi || {
      id: `whisper-${Date.now()}`,
      source: sourceLabel,
      title: text.slice(0, 120),
      ocr_text: text,
      english_summary: text,
      vietnamese_translation: '',
      timestamp: now,
      sentiment: 'Neutral',
      keywords: [],
      summary: text,
    };

    setNews((prev) => [newsItem, ...prev].slice(0, 20));
  };

  return (
    <div className='flex flex-col h-screen bg-gray-950 text-white overflow-hidden font-sans'>
      <Header
        view={view}
        onChangeView={setView}
        processingEnabled={processingEnabled}
        togglingLive={togglingLive}
        onToggleProcessing={toggleProcessing}
      />

      {view === 'dashboard' && (
        <div className='flex-1 flex gap-2 p-2 overflow-hidden'>
          <div className='flex-[3] flex flex-col gap-2 overflow-hidden'>
            <div className='flex-[4] min-h-0'>
              <StreamGrid
                subtitle={subtitle}
                livePlayerRef={livePlayerRef}
                sources={defaultSources}
                selectedSourceId={selectedSourceId}
                onChangeSource={setSelectedSourceId}
                onCapture={captureScreenForPersonSearch}
              />
            </div>

            <div className='flex-1 flex gap-2 overflow-hidden min-h-0'>
              <div className='flex-1 overflow-auto'>
                <TranscriptPanel news={newsForPanels} />
              </div>
              <div className='flex-1 overflow-hidden'>
              <EventTimeline
                events={newsForPanels}
                onEventClick={(item) => {
                  const terms = item.keywords && item.keywords.length > 0
                    ? item.keywords
                    : (item.title ? [item.title] : []);
                  setKgTerms(terms);
                  setKgCypher(null);
                  setKgMode('entity');
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
          <KGExplorer
            externalTerms={kgTerms}
            externalCypher={kgCypher}
            externalMode={kgMode}
            onShowPersonReport={(node) => {
              if (!node) return;
              setPersonReportTarget(node);
              setView('personReport');
            }}
          />
        </div>
      )}

      {view === 'people' && (
        <div className='flex-1 overflow-hidden'>
          <PeopleManager />
        </div>
      )}

      {view === 'documents' && (
        <div className='flex-1 overflow-hidden'>
          <DocumentManager
            onOpenPersonSearch={(imagePayload) => {
              if (!imagePayload) return;
              setPersonImage(imagePayload);
              setView('personSearch');
            }}
          />
        </div>
      )}

      {view === 'personSearch' && (
        <div className='flex-1 overflow-hidden'>
            <PersonSearch
              initialImage={personImage}
              onBack={() => setView('dashboard')}
              onExploreKG={(person) => {
                if (!person?.name) return;
                const name = person.name;
                setKgTerms([name]);
                const escaped = name.replace(/"/g, '\\"');
                const fallback = `
                  MATCH (p:Person)
                  WHERE toLower(p.name) CONTAINS toLower("${escaped}")
                  OPTIONAL MATCH (p)-[r1:POSTED]->(po:Post)
                  WITH p, po, r1 LIMIT 5
                  OPTIONAL MATCH (po)<-[r2:COMMENTED_ON]-(a:Account)
                  WITH p, po, r1, r2, a LIMIT 5
                  RETURN p, po, r1, r2, a
                `;
                setKgCypher(person.cypher || fallback);
                setView('kg');
              }}
            />
        </div>
      )}

      {view === 'personReport' && (
        <div className='flex-1 overflow-hidden bg-gray-950'>
          <PersonReport
            target={personReportTarget}
            onBack={() => setView('kg')}
          />
        </div>
      )}
    </div>
  );
}

export default App;

