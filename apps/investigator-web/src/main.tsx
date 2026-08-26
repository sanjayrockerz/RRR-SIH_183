import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import './graph.css';
import './app.css';
import './pattern.css';

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
