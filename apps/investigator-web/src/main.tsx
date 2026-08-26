import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import './graph.css';
import './app.css';
import './pattern.css';
import './risk.css';
import './risk-overlay.css';
import './realtime.css';
import './cross-chain.css';

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
