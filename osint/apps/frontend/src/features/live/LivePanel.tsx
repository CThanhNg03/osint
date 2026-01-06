/** Feature component for live monitoring control. */
import React, { useEffect, useState } from 'react';
import { getLiveState, setLiveState } from '../../shared/api/endpoints';
import { LiveState } from '../../shared/types/live';

const LivePanel: React.FC = () => {
  const [state, setState] = useState<LiveState>({ enabled: false });

  useEffect(() => {
    getLiveState().then(setState).catch(() => setState({ enabled: false }));
  }, []);

  const toggle = async () => {
    const updated = await setLiveState(!state.enabled);
    setState(updated);
  };

  return (
    <div>
      <h3>Live Monitor</h3>
      <p>Status: {state.enabled ? 'Enabled' : 'Disabled'}</p>
      <button type="button" onClick={toggle}>{state.enabled ? 'Disable' : 'Enable'}</button>
    </div>
  );
};

export default LivePanel;
