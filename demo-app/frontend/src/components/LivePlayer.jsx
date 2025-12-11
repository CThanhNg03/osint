import React, { useEffect, useMemo, useState } from 'react';

export const defaultSources = [
  {
    id: 'euronews',
    label: 'Euronews',
    type: 'youtube',
    videoId: 'pykpO5kQJ98',
    match: 'pykpO5kQJ98',
  },
  {
    id: 'aljazeera',
    label: 'Al Jazeera English',
    type: 'youtube',
    videoId: 'gCNeDWCI0vo',
    match: 'gCNeDWCI0vo',
    embedUrl: 'https://www.youtube.com/embed/gCNeDWCI0vo?si=xvJK9TU-L6FAnKjp',
  },
  {
    id: 'cnn-audio',
    label: 'CNN Audio (TuneIn)',
    type: 'audio',
    url: 'https://tunein.cdnstream1.com/2868_96.mp3?aw_0_1st.playerid=SLb0WwgW&aw_0_1st.skey=1765272278&aw_0_1st.abtest=&partnerId=SLb0WwgW&aw_0_1st.stationId=s20407&aw_0_1st.premium=false&source=TuneIn&aw_0_1st.platform=tunein&aw_0_1st.genre_id=g3124&aw_0_1st.class=talk&aw_0_1st.ads_partner_alias=emb.CNN&aw_0_azn.planguage=en&aw_0_1st.is_ondemand=false&aw_0_1st.topicId=na&aw_0_1st.programId=p4648826&aw_0_1st.affiliateIds=a38460%2ca33291%2ca39100%2ca40075%2ca39163&aw_0_1st.bandId=16',
    match: 'tunein.cdnstream1.com/2868_96.mp3',
  },
];

const LivePlayer = ({
  sources = defaultSources,
  selectedSourceId,
  onChangeSource,
  playerRef,
  onCapture,
}) => {
  const [selected, setSelected] = useState(selectedSourceId || sources[0]?.id || '');

  useEffect(() => {
    if (selectedSourceId && selectedSourceId !== selected) {
      setSelected(selectedSourceId);
    }
  }, [selectedSourceId, selected]);

  const current = useMemo(
    () => sources.find((s) => s.id === selected) || sources[0],
    [selected, sources]
  );

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg h-full flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800 gap-3">
        <div className="flex items-center gap-2">
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Live Monitor</div>
            <div className="text-sm font-semibold text-white">{current?.label || 'Live source'}</div>
          </div>
          <div className="flex gap-1">
            {sources.map((src) => (
              <button
            key={src.id}
            onClick={() => {
              setSelected(src.id);
              onChangeSource?.(src.id);
            }}
            className={`px-2 py-1 rounded text-[11px] font-semibold border ${
              selected === src.id
                ? 'bg-indigo-600 border-indigo-500 text-white'
                : 'bg-gray-800 border-gray-700 text-gray-200 hover:bg-gray-750'
            }`}
              >
                {src.label}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={onCapture}
          className="px-3 py-1.5 rounded text-xs font-semibold bg-purple-700 hover:bg-purple-600 border border-purple-500"
        >
          Capture & Search
        </button>
      </div>

      <div className="flex-1 relative" ref={playerRef}>
        {current?.type === 'youtube' && current?.videoId && (
          <iframe
            title={current.label}
            src={
              current.embedUrl ||
              `https://www.youtube.com/embed/${current.videoId}?autoplay=1&mute=0&controls=1&showinfo=0&rel=0`
            }
            className="w-full h-full"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerPolicy="strict-origin-when-cross-origin"
            allowFullScreen
          />
        )}
        {current?.type === 'audio' && current?.url && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="text-sm text-gray-300 font-semibold">{current.label}</div>
            <audio controls autoPlay className="w-2/3">
              <source src={current.url} type="audio/mpeg" />
              Your browser does not support the audio element.
            </audio>
          </div>
        )}
      </div>
    </div>
  );
};

export default LivePlayer;
