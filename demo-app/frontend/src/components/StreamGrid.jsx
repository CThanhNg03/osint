import React from 'react';
import LivePlayer from './LivePlayer';

const StreamGrid = ({
  subtitle,
  livePlayerRef,
  onCapture,
  sources,
  selectedSourceId,
  onChangeSource,
}) => {
  return (
    <div className="h-full flex flex-col gap-2">
      <div className="flex-[3] min-h-0">
        <LivePlayer
          sources={sources}
          selectedSourceId={selectedSourceId}
          onChangeSource={onChangeSource}
          playerRef={livePlayerRef}
          onCapture={onCapture}
        />
      </div>
    </div>
  );
};

export default StreamGrid;
