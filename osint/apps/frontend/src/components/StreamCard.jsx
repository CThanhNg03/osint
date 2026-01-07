import React from 'react';

const StreamCard = ({ source, subtitle }) => {
    const videoId = "pykpO5kQJ98";

    return (
        <div className="relative bg-black rounded-lg overflow-hidden border border-gray-800 h-full w-full">
            {/* YouTube Embed - FULL SIZE */}
            <div className="absolute inset-0">
                <iframe
                    width="100%"
                    height="100%"
                    src={`https://www.youtube.com/embed/${videoId}?autoplay=1&mute=0&controls=0&showinfo=0&rel=0`}
                    title="Live Stream"
                    frameBorder="0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                ></iframe>
            </div>

            {/* Live Indicator */}
            <div className="absolute top-2 right-2 flex items-center gap-1 bg-red-600 px-2 py-0.5 rounded text-xs font-bold text-white z-10">
                <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
                LIVE
            </div>

            {/* Source Label */}
            <div className="absolute top-2 left-2 bg-black/60 px-2 py-1 rounded text-xs text-white font-mono border border-white/10 z-10">
                CAM-01 | {source}
            </div>
        </div>
    );
};

export default StreamCard;
