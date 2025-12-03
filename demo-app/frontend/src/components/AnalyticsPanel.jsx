import React from 'react';

const AnalyticsPanel = ({ data }) => {
    if (!data) return <div className="p-4 text-gray-500">Waiting for data...</div>;

    return (
        <div className="bg-gray-900 border-l border-gray-800 p-4 w-full flex flex-col gap-6 h-full overflow-y-auto">
            <div>
                <h3 className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-3">Real-time Sentiment</h3>
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-300">Global Score</span>
                    <span className={`text-lg font-bold ${data.sentiment_score > 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {data.sentiment_score > 0 ? '+' : ''}{data.sentiment_score}
                    </span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2">
                    <div
                        className={`h-2 rounded-full transition-all duration-500 ${data.sentiment_score > 0 ? 'bg-green-500' : 'bg-red-500'}`}
                        style={{ width: `${Math.min(Math.abs(data.sentiment_score) * 100, 100)}%` }}
                    ></div>
                </div>
            </div>

            <div>
                <h3 className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-3">Trending Keywords</h3>
                <div className="flex flex-wrap gap-2">
                    {data.trending_keywords?.map((keyword, idx) => (
                        <span key={idx} className="bg-gray-800 text-gray-300 text-xs px-2 py-1 rounded border border-gray-700">
                            #{keyword}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default AnalyticsPanel;
