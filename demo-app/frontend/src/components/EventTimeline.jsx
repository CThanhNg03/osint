import React from 'react';

const EventTimeline = ({ events, onEventClick }) => {
  if (!events || events.length === 0) {
    return (
      <div className="p-4 text-gray-500 text-sm text-center">
        Đang chờ dữ liệu phân tích...
      </div>
    );
  }

  const handleClick = (item) => {
    if (onEventClick) {
      onEventClick(item);
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 h-full overflow-y-auto">
      <h3 className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-3 sticky top-0 bg-gray-900 pb-2">
        Event Timeline
      </h3>
      <div className="space-y-3">
        {events.slice(0, 10).map((event, idx) => (
          <button
            key={event.id || idx}
            onClick={() => handleClick(event)}
            className="w-full text-left border-l-2 border-blue-500 pl-3 pb-2 hover:bg-gray-800 transition rounded"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-white text-sm font-medium">{event.title}</p>
                <p className="text-gray-400 text-xs mt-1 line-clamp-2">{event.summary}</p>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  event.sentiment === 'Positive'
                    ? 'bg-green-900/30 text-green-400'
                    : event.sentiment === 'Negative'
                    ? 'bg-red-900/30 text-red-400'
                    : 'bg-gray-800 text-gray-400'
                }`}
              >
                {event.sentiment}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-500">
                {new Date(event.timestamp).toLocaleTimeString('vi-VN')}
              </span>
              <span className="text-xs text-blue-400">• {event.source}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default EventTimeline;
