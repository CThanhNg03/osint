/** Shared layout with navigation between feature pages. */
import React from 'react';
import { Link } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/news', label: 'News' },
  { to: '/live', label: 'Live Monitor' },
  { to: '/kg', label: 'Knowledge Graph' },
  { to: '/people', label: 'People' },
  { to: '/documents', label: 'Documents' },
  { to: '/asr', label: 'ASR' },
];

const AppLayout: React.FC<React.PropsWithChildren> = ({ children }) => (
  <div className="app-shell">
    <header>
      <h1>OSINT Toolkit</h1>
      <nav>
        <ul className="nav">
          {navItems.map((item) => (
            <li key={item.to}>
              <Link to={item.to}>{item.label}</Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
    <main>{children}</main>
  </div>
);

export default AppLayout;
