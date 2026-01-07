import React from 'react';
const TranscriptPanel = ({ news }) => {
  const latestNews = news && news.length > 0 ? news[0] : null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-3">
        Transcript & Translation
      </h3>

      {latestNews ? (
        <div className="space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-blue-400 uppercase tracking-wider">Headline (OCR)</span>
              <div className="flex-1 h-px bg-blue-900/30"></div>
            </div>
            <p className="text-blue-100 text-sm leading-relaxed font-medium">
              {latestNews.ocr_text || latestNews.title || 'No text detected'}
            </p>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-gray-500 uppercase tracking-wider">Summary (English)</span>
              <div className="flex-1 h-px bg-gray-800"></div>
            </div>
            <p className="text-gray-300 text-sm leading-relaxed">
              {latestNews.english_summary || latestNews.summary || latestNews.ocr_text || 'No summary available'}
            </p>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-yellow-500 uppercase tracking-wider">Vietnamese translation</span>
              <div className="flex-1 h-px bg-yellow-900/30"></div>
            </div>
            <p className="text-yellow-100 text-sm leading-relaxed font-medium">
              {latestNews.vietnamese_translation || latestNews.subtitle_vi || 'Waiting for translation...'}
            </p>
          </div>

          <div className="flex items-center gap-4 pt-2 border-t border-gray-800">
            <span className="text-xs text-gray-500">
              {new Date(latestNews.timestamp).toLocaleTimeString('vi-VN')}
            </span>
            <span className="text-xs text-blue-400">Source: {latestNews.source}</span>
          </div>
        </div>
      ) : (
        <div className="p-4 text-gray-500 text-sm text-center bg-gray-950 border border-gray-800 rounded">
          Waiting for analysis...
        </div>
      )}
        </div>
    );
};

export default TranscriptPanel;
