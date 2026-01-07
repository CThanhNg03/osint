import React from 'react';

const NewsTicker = ({ news }) => {
    return (
        <div className="bg-blue-900/20 border-y border-blue-900/50 p-2 overflow-hidden flex items-center">
            <div className="bg-blue-600 text-white text-xs font-bold px-2 py-1 rounded mr-3 whitespace-nowrap">
                LATEST INTEL
            </div>
            <div className="flex-1 overflow-hidden relative h-6">
                <div className="animate-marquee-slow whitespace-nowrap absolute top-0 text-blue-100 text-sm">
                    {news.map((item, index) => (
                        <span key={item.id || index} className="mx-8">
                            <span className="text-blue-400 font-bold">[{item.source}]</span> {item.title}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default NewsTicker;
