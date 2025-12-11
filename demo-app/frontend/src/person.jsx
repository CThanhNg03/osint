import React from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import PersonSearch from './components/PersonSearch';

const App = () => {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <PersonSearch onBack={() => (window.location.href = '/')} />
    </div>
  );
};

const root = document.getElementById('person-root');
createRoot(root).render(<App />);
