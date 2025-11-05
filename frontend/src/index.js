import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  // Temporarily disable StrictMode to prevent WebSocket double-mounting in development
  // StrictMode intentionally mounts components twice to detect side effects
  // This causes multiple WebSocket connections which we want to avoid
  <App />
);
