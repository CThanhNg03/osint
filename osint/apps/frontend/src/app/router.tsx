/** Client-side routing configuration using React Router. */
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HomePage from '../pages/HomePage';
import NewsPage from '../pages/NewsPage';
import LiveMonitorPage from '../pages/LiveMonitorPage';
import KnowledgeGraphPage from '../pages/KnowledgeGraphPage';
import PeoplePage from '../pages/PeoplePage';
import DocumentsPage from '../pages/DocumentsPage';
import AsrPage from '../pages/AsrPage';

const AppRouter: React.FC = () => (
  <Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/news" element={<NewsPage />} />
    <Route path="/live" element={<LiveMonitorPage />} />
    <Route path="/kg" element={<KnowledgeGraphPage />} />
    <Route path="/people" element={<PeoplePage />} />
    <Route path="/documents" element={<DocumentsPage />} />
    <Route path="/asr" element={<AsrPage />} />
  </Routes>
);

export default AppRouter;
