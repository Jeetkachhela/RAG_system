import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Database, Loader2, Bot, PlusSquare, MessageSquare, Trash2, Menu, X, User, Download, Copy, StopCircle, RefreshCw, Cloud, CloudOff, Settings, ShieldCheck, Zap, BarChart3, Upload } from 'lucide-react';
import AnalyticsDashboard from './AnalyticsDashboard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import toast, { Toaster } from 'react-hot-toast';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import './index.css';

const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://127.0.0.1:8001/api').replace(/\/$/, '');
const SYSTEM_MSG = { role: 'assistant', content: 'Hello! I am Kanan, your conversational agent assistant. You can ask me about our agents, their ranks, zones, cities, and more!' };

const KananIcon = ({ size = 24, className = "" }) => {
  const isLarge = size > 28;
  return (
    <div className={className} style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
      <img 
        src="/kanan_logo.png" 
        alt="Kanan.co" 
        style={{ width: size, height: size, borderRadius: '6px', objectFit: 'contain' }} 
      />
      {isLarge && (
        <span style={{ fontFamily: 'Inter, sans-serif', fontWeight: 800, fontSize: size * 0.75, color: '#0f172a', letterSpacing: '-1px', lineHeight: 1 }}>
          kanan<small style={{ color: '#4f46e5', fontSize: '0.6em', verticalAlign: 'middle', marginLeft: '2px' }}>.co</small>
        </span>
      )}
    </div>
  );
};

function App() {


  const [sessions, setSessions] = useState(() => {
    try {
      const saved = localStorage.getItem('kanan_sessions');
      return (saved && saved !== 'null') ? JSON.parse(saved) : {};
    } catch (e) {
      console.error("Failed to parse sessions:", e);
      return {};
    }
  });
  const [sessionSearch, setSessionSearch] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState(() => {
    // V4: Always start with a new session on launch
    return crypto.randomUUID();
  });
  const [messages, setMessages] = useState([SYSTEM_MSG]);
  
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [appMode, setAppMode] = useState('online'); // 'online' or 'offline'
  const [systemStatus, setSystemStatus] = useState({ internet: true, ollama: false });
  const [lastChatMeta, setLastChatMeta] = useState({ mode: null, sources: [], warnings: '' });
  
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);



  useEffect(() => {
    // Only persist sessions that have actual user messages (not just the welcome msg)
    if (messages.length <= 1) return;
    const sessionData = {
      ...sessions,
      [currentSessionId]: {
        id: currentSessionId,
        title: messages.length > 1 ? messages[1].content.substring(0, 30) + '...' : 'New Chat',
        updatedAt: new Date().toISOString(),
        messages
      }
    };
    setSessions(sessionData);
    localStorage.setItem('kanan_sessions', JSON.stringify(sessionData));
    localStorage.setItem('kanan_current_session', currentSessionId);
  }, [messages, currentSessionId]);

  const scrollToBottom = (behavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    if (shouldAutoScroll) {
      scrollToBottom('auto');
      setShowJumpToLatest(false);
    } else if (isLoading) {
      setShowJumpToLatest(true);
    }
  }, [messages, isLoading]);

  useEffect(() => {
    const el = chatContainerRef.current;
    if (!el) return;

    const onScroll = () => {
      const threshold = 120;
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      const atBottom = distanceFromBottom <= threshold;
      setShouldAutoScroll(atBottom);
      if (atBottom) setShowJumpToLatest(false);
    };

    el.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  const autoResizeInput = () => {
    if (inputRef.current) {
        inputRef.current.style.height = 'auto';
        inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`;
    }
  };

  useEffect(() => {
      autoResizeInput();
  }, [input]);

  const createNewChat = () => {
    const newId = crypto.randomUUID();
    setCurrentSessionId(newId);
    setMessages([SYSTEM_MSG]);
    setSidebarOpen(false);
    if(abortControllerRef.current) abortControllerRef.current.abort();
    setIsLoading(false);
  };

  const renameSession = (e, id) => {
    e.stopPropagation();
    const newTitle = prompt("Rename chat", sessions[id]?.title || "Chat");
    if (!newTitle) return;
    const updated = {
      ...sessions,
      [id]: { ...sessions[id], title: newTitle.trim(), updatedAt: new Date().toISOString() }
    };
    setSessions(updated);
    localStorage.setItem('kanan_sessions', JSON.stringify(updated));
    toast.success("Chat renamed");
  };

  const togglePinSession = (e, id) => {
    e.stopPropagation();
    const updated = {
      ...sessions,
      [id]: { ...sessions[id], pinned: !sessions[id]?.pinned, updatedAt: new Date().toISOString() }
    };
    setSessions(updated);
    localStorage.setItem('kanan_sessions', JSON.stringify(updated));
  };

  const loadSession = (id) => {
    setCurrentSessionId(id);
    setMessages(sessions[id].messages);
    setSidebarOpen(false);
    if(abortControllerRef.current) abortControllerRef.current.abort();
    setIsLoading(false);
  };

  const confirmDelete = (e, id) => {
    e.stopPropagation();
    setSessionToDelete(id);
  };

  const executeDelete = () => {
    if (!sessionToDelete) return;
    const id = sessionToDelete;
    
    const newSessions = { ...sessions };
    delete newSessions[id];
    setSessions(newSessions);
    localStorage.setItem('kanan_sessions', JSON.stringify(newSessions));
    
    if (currentSessionId === id && Object.keys(newSessions).length > 0) {
      loadSession(Object.keys(newSessions)[0]);
    } else if (Object.keys(newSessions).length === 0) {
      createNewChat();
    }
    toast.success("Chat deleted");
    setSessionToDelete(null);
  };

  // Pull system status on mount and when mode changes
  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/status`);
      setSystemStatus(res.data);
      setAppMode(res.data.mode);
    } catch (e) {
      console.error("Status fetch failed", e);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  const toggleMode = async () => {
    const newMode = appMode === 'online' ? 'offline' : 'online';
    try {
      await axios.post(`${API_BASE}/config/mode`, { mode: newMode });
      setAppMode(newMode);
      toast.success(`Switched to ${newMode.toUpperCase()} mode`);
      fetchStatus();
    } catch (e) {
      toast.error("Failed to switch mode");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const setSuggestedInput = (text) => {
    setInput(text);
  };

  const stopGenerating = () => {
      if (abortControllerRef.current) {
          abortControllerRef.current.abort();
          setIsLoading(false);
          toast("Stopped generating.", { icon: "🛑" });
      }
  };

  const regenerateLastResponse = () => {
      if (messages.length < 2) return;
      // find the last user message
      let lastUserMsgIdx = -1;
      for (let i = messages.length -1; i >= 0; i--) {
          if (messages[i].role === 'user') {
               lastUserMsgIdx = i;
               break;
          }
      }
      if (lastUserMsgIdx === -1) return;
      
      const newHistory = messages.slice(0, lastUserMsgIdx + 1);
      setMessages(newHistory);
      sendQuery(newHistory);
  };

  const handleSend = () => {
    if (!input.trim() || isLoading) return;

    const userMsg = { role: 'user', content: input.trim() };
    const newHistory = [...messages, userMsg];
    
    setMessages(newHistory);
    setInput('');
    if(inputRef.current) inputRef.current.style.height = 'auto'; // reset height

    sendQuery(newHistory);
  };

  const sendQuery = async (newHistory) => {
    setIsLoading(true);
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ messages: newHistory }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const meta = {
        mode: response.headers.get('X-Kanan-Mode'),
        sources: (response.headers.get('X-Kanan-Sources') || '').split(',').filter(Boolean),
        warnings: response.headers.get('X-Kanan-Warnings') || ''
      };
      setLastChatMeta(meta);

      let assistantMsg = { role: 'assistant', content: '' };
      setMessages([...newHistory, assistantMsg]);
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          assistantMsg = { ...assistantMsg, content: assistantMsg.content + chunk };
          setMessages((prevMsgs) => {
             const updated = [...prevMsgs];
             updated[updated.length - 1] = assistantMsg;
             return updated;
          });
        }
      }
    } catch (err) {
        if (err.name === 'AbortError') {
             console.log("Fetch aborted");
        } else {
             console.error(err);
             toast.error('Failed to communicate with Kanan AI');
             setMessages([...newHistory, { role: 'assistant', content: `Error: ${err.message}` }]);
        }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const copyToClipboard = (text) => {
      navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard!");
  };

  const downloadPDF = async () => {
      const target = chatContainerRef.current;
      if (!target) return;
      setIsExporting(true);
      const toastId = toast.loading("Generating PDF...");
      
      try {
          // Hide non-printable UI elements
          const elementsToHide = document.querySelectorAll('.hide-on-pdf');
          elementsToHide.forEach(el => el.style.display = 'none');

          // Temporarily unlock ALL overflow constraints in the ancestor chain
          const chatContainer = target.closest('.chat-container');
          const mainContent = target.closest('.main-content');
          
          const saved = [];
          [target, chatContainer, mainContent].forEach(el => {
            if (el) {
              saved.push({ el, overflow: el.style.overflow, height: el.style.height, maxHeight: el.style.maxHeight, flex: el.style.flex });
              el.style.overflow = 'visible';
              el.style.height = 'auto';
              el.style.maxHeight = 'none';
              el.style.flex = 'none';
            }
          });

          // Wait a tick for layout to recalculate
          await new Promise(r => setTimeout(r, 100));

          const canvas = await html2canvas(target, {
              backgroundColor: '#f8fafc',
              scale: 2,
              useCORS: true,
              scrollX: 0,
              scrollY: 0,
          });

          // Restore all saved styles
          saved.forEach(({ el, overflow, height, maxHeight, flex }) => {
            el.style.overflow = overflow;
            el.style.height = height;
            el.style.maxHeight = maxHeight;
            el.style.flex = flex;
          });
          elementsToHide.forEach(el => el.style.display = '');

          const imgData = canvas.toDataURL('image/png');
          const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

          const pdfWidth = pdf.internal.pageSize.getWidth();
          const pageHeight = pdf.internal.pageSize.getHeight();
          const imgHeight = (canvas.height * pdfWidth) / canvas.width;
          
          let heightLeft = imgHeight;
          let position = 0;

          pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight);
          heightLeft -= pageHeight;

          while (heightLeft > 0) {
              position -= pageHeight;
              pdf.addPage();
              pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight);
              heightLeft -= pageHeight;
          }

          pdf.save(`Kanan-Chat-${new Date().toISOString().split('T')[0]}.pdf`);
          toast.success("PDF Downloaded!", { id: toastId });
      } catch (e) {
          console.error(e);
          toast.error("Failed to generate PDF", { id: toastId });
      } finally {
          setIsExporting(false);
      }
  };

  const exportMarkdown = () => {
    const md = messages.map(m => `**${m.role.toUpperCase()}**\n\n${m.content}\n`).join('\n---\n\n');
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Kanan-Chat-${new Date().toISOString().split('T')[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Markdown downloaded");
  };

  const exportJSON = () => {
    const payload = {
      exportedAt: new Date().toISOString(),
      sessionId: currentSessionId,
      messages
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Kanan-Chat-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("JSON downloaded");
  };

  const handleIngest = async () => {
    setIsIngesting(true);
    const toastId = toast.loading('Updating database in the cloud. This handles vectors natively now...');
    try {
      const resp = await axios.post(`${API_BASE}/ingest`);
      toast.success(resp.data.message || 'Database updated!', { id: toastId });
    } catch (err) {
      toast.error('Failed to update database.', { id: toastId });
    } finally {
      setIsIngesting(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      toast.error('Only Excel files (.xlsx, .xls) are allowed.');
      return;
    }

    setIsIngesting(true);
    const toastId = toast.loading('Uploading and processing new dataset...');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await axios.post(`${API_BASE}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      toast.success(resp.data.message || 'Database successfully replaced!', { id: toastId });
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to replace database.', { id: toastId });
    } finally {
      setIsIngesting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };



  return (
    <div className="layout">
      <Toaster position="top-right" toastOptions={{
        style: { background: '#ffffff', color: '#1e293b', border: '1px solid #cbd5e1' }
      }} />
      
      <div className="mobile-header">
         <button className="icon-btn" onClick={() => setSidebarOpen(true)}>
            <Menu size={24} />
         </button>
         <div className="header-title mobile">
            <KananIcon size={24} />
            <h1>Kanan</h1>
         </div>
         <button className="icon-btn empty"></button>
      </div>

      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
           <button className="new-chat-btn" onClick={createNewChat}>
             <PlusSquare size={18} /> New Chat
           </button>
           <button className="close-sidebar icon-btn" onClick={() => setSidebarOpen(false)}>
             <X size={20} />
           </button>
        </div>
        
        <div className="session-list">
          <div className="session-label">Recent Chats</div>
          <div className="discovery-section hide-on-pdf">
            <input
              className="form-input"
              placeholder="Search chats..."
              value={sessionSearch}
              onChange={(e) => setSessionSearch(e.target.value)}
              style={{ marginBottom: '0.5rem' }}
            />
          </div>
          {Object.values(sessions)
            .filter(s => !sessionSearch.trim() || (s.title || '').toLowerCase().includes(sessionSearch.trim().toLowerCase()))
            .sort((a, b) => {
              const ap = a.pinned ? 1 : 0;
              const bp = b.pinned ? 1 : 0;
              if (ap !== bp) return bp - ap;
              return new Date(b.updatedAt) - new Date(a.updatedAt);
            })
            .map(session => (
            <div 
              key={session.id} 
              className={`session-item ${currentSessionId === session.id ? 'active' : ''}`}
              onClick={() => loadSession(session.id)}
            >
              <MessageSquare size={16} className="session-icon" />
              <span className="session-title">{session.title}</span>
              <button
                className="delete-session-btn"
                onClick={(e) => togglePinSession(e, session.id)}
                title={session.pinned ? "Unpin" : "Pin"}
              >
                {session.pinned ? "★" : "☆"}
              </button>
              <button
                className="delete-session-btn"
                onClick={(e) => renameSession(e, session.id)}
                title="Rename"
              >
                ✎
              </button>
              <button 
                className="delete-session-btn"
                onClick={(e) => confirmDelete(e, session.id)}
                title="Delete Chat"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <button
            className={`ingest-btn-small ${showAnalytics ? 'active-analytics' : ''}`}
            onClick={() => { setShowAnalytics(!showAnalytics); setSidebarOpen(false); }}
          >
            <BarChart3 size={16} />
            {showAnalytics ? 'Back to Chat' : 'Analytics'}
          </button>
          <div className="mode-toggle-container">
            <div className="mode-info">
              <span className={`status-dot ${systemStatus.internet ? 'online' : 'offline'}`} />
              <span className="mode-text">{appMode === 'online' ? 'Online Mode' : 'Offline Mode'}</span>
            </div>
            <button className={`mode-toggle-btn ${appMode}`} onClick={toggleMode}>
              {appMode === 'online' ? <Zap size={14} /> : <ShieldCheck size={14} />}
              {appMode === 'online' ? 'Go Offline' : 'Go Online'}
            </button>
          </div>
          <button 
            className={`ingest-btn-small ${isIngesting ? 'loading' : ''}`}
            onClick={handleIngest}
            disabled={isIngesting}
            title="Sync using local file"
          >
            {isIngesting ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
            {isIngesting ? 'Syncing...' : 'Sync Local'}
          </button>
          
        </div>
      </aside>

      <main className="main-content">
        <header className="header desktop-only">
          <div className="header-title">
            <KananIcon size={28} />
            <h1>Kanan Ops Platform</h1>
          </div>
          <div className="header-actions">
              <div className={`status-badge ${appMode}`}>
                {appMode === 'online' ? <Cloud size={14} /> : <CloudOff size={14} />}
                <span>{appMode === 'online' ? 'Cloud Sync' : 'Local Only'}</span>
              </div>
              <div className="header-menu hide-on-pdf">
                <button className="header-menu-trigger" onClick={() => document.getElementById('header-dropdown')?.classList.toggle('show')}>
                  <Settings size={16} />
                </button>
                <div id="header-dropdown" className="header-dropdown">
                  <button onClick={() => { exportMarkdown(); document.getElementById('header-dropdown')?.classList.remove('show'); }} disabled={messages.length < 2}>
                    <Download size={14} /> Export MD
                  </button>
                  <button onClick={() => { exportJSON(); document.getElementById('header-dropdown')?.classList.remove('show'); }} disabled={messages.length < 2}>
                    <Download size={14} /> Export JSON
                  </button>
                  <button onClick={() => { downloadPDF(); document.getElementById('header-dropdown')?.classList.remove('show'); }} disabled={isExporting || messages.length < 2}>
                    <Download size={14} /> Export PDF
                  </button>
                  <div className="dropdown-divider" />
                </div>
              </div>
          </div>
        </header>

        {showAnalytics ? (
          <AnalyticsDashboard onBack={() => setShowAnalytics(false)} />
        ) : (
        <div className="chat-container">
          <div className="chat-messages" ref={chatContainerRef}>
            {showJumpToLatest && (
              <div className="stop-container">
                <button className="stop-btn" onClick={() => { scrollToBottom(); setShowJumpToLatest(false); }}>
                  Jump to latest
                </button>
              </div>
            )}
            {messages.length === 1 && (
              <div className="welcome-screen">
                 <KananIcon size={48} className="welcome-icon" />
                 <h2>Hi, what can I help with?</h2>
                 <p>Ask anything about our study abroad services or agent network. Powered by MongoDB Atlas.</p>
                 <div className="suggestion-chips hide-on-pdf">
                    <button onClick={() => setSuggestedInput("List all Platinum agents in Gujarat")}>"Platinum agents in Gujarat"</button>
                    <button onClick={() => setSuggestedInput("Show me active subagents in East Zone")}>"Active East Zone agents"</button>
                    <button onClick={() => setSuggestedInput("Latest Canada Study Permit updates")}>"Canada Visa updates"</button>
                    <button onClick={() => setSuggestedInput("Who heads the departments at Kanan?")}>"Meet the team"</button>
                    <button onClick={() => setSuggestedInput("How to partner with Kanan as a franchise?")}>"Franchise Partnership"</button>
                    <button onClick={() => setSuggestedInput("What countries does Kanan help students study in?")}>"Study Destinations"</button>
                 </div>
              </div>
            )}
            
            <div className="messages-list">
                {messages.map((msg, idx) => (
                <div 
                    key={idx} 
                    className={`message-wrapper ${msg.role} ${idx === 0 && messages.length === 1 ? 'hidden' : ''}`}
                >
                    <div className="message-container">
                        <div className={`message-avatar ${msg.role}`}>
                            {msg.role === 'assistant' ? <KananIcon size={20} /> : <User size={20} />}
                        </div>
                        <div className={`message ${msg.role}`}>
                        {msg.role === 'assistant' ? (
                            <>
                                <ReactMarkdown 
                                    className="markdown-pro" 
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        code({node, inline, className, children, ...props}) {
                                            const match = /language-(\w+)/.exec(className || '');
                                            return !inline && match ? (
                                                <SyntaxHighlighter
                                                    style={atomDark}
                                                    language={match[1]}
                                                    PreTag="div"
                                                    customStyle={{ borderRadius: '8px', margin: '1em 0' }}
                                                    {...props}
                                                >
                                                    {String(children).replace(/\n$/, '')}
                                                </SyntaxHighlighter>
                                            ) : (
                                                <code className={className} {...props}>
                                                    {children}
                                                </code>
                                            )
                                        }
                                    }}
                                >
                                {msg.content}
                                </ReactMarkdown>
                                
                                {idx === messages.length - 1 && !isLoading && (
                                    <div className="message-actions hide-on-pdf">
                                        <button className="action-btn" onClick={() => copyToClipboard(msg.content)} title="Copy message">
                                            <Copy size={16} />
                                        </button>
                                        <button className="action-btn" onClick={regenerateLastResponse} title="Regenerate response">
                                            <RefreshCw size={16} />
                                        </button>
                                    </div>
                                )}
                            </>
                        ) : (
                            msg.content
                        )}
                        </div>
                    </div>
                </div>
                ))}
            </div>
            
            {isLoading && (
              <div 
                 className="message-wrapper ai"
               >
                 <div className="message-container">
                    <div className="message-avatar ai">
                        <KananIcon size={20} />
                    </div>
                    <div className="message ai">
                        <div className="typing-indicator">
                            <div className="typing-dot"></div>
                            <div className="typing-dot"></div>
                            <div className="typing-dot"></div>
                        </div>
                    </div>
                 </div>
              </div>
            )}
            <div ref={messagesEndRef} className="pb-8" />
          </div>

          <div className="chat-input-wrapper hide-on-pdf">
             {!isLoading ? null : (
                <div className="stop-container">
                    <button className="stop-btn" onClick={stopGenerating}>
                        <StopCircle size={16}/> Stop generating
                    </button>
                </div>
             )}
             <form className="chat-input-container" onSubmit={(e) => { e.preventDefault(); handleSend(); }}>
               <textarea
                 ref={inputRef}
                 className="chat-input"
                 value={input}
                 onChange={(e) => setInput(e.target.value)}
                 onKeyDown={handleKeyDown}
                 placeholder="Message Kanan..."
                 disabled={isLoading}
                 rows={1}
               />
                <div className="input-actions-left">
                  <input 
                    type="file" 
                    accept=".xlsx, .xls" 
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                  />
                  <button 
                    type="button"
                    className={`icon-upload-btn ${isIngesting ? 'loading' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isIngesting || isLoading}
                    title="Upload Excel to replace database"
                  >
                    {isIngesting ? <Loader2 size={16} className="animate-spin" /> : <Database size={18} />}
                  </button>
                </div>
                <button type="submit" className="send-btn" disabled={!input.trim() || isLoading}>
                  <Send size={18} />
                </button>
               <div className="quick-actions">
                  <button type="button" className="action-tag" onClick={() => setSuggestedInput("Search internal database for agents...")} title="Local DB">
                    <img src="/kanan_logo.png" alt="" style={{ width: 14, height: 14, borderRadius: '2px' }} /> <span>Query DB</span>
                  </button>
                  <button type="button" className="action-tag" onClick={() => setSuggestedInput("Search online for...")} title="Search Web">
                    <Bot size={14} style={{ color: '#4f46e5' }} /> <span>Search Web</span>
                  </button>
                  <button type="button" className="action-tag" onClick={() => setSuggestedInput("Kanan International common FAQs...")} title="FAQs">
                    <MessageSquare size={14} style={{ color: '#4f46e5' }} /> <span>FAQs</span>
                  </button>
               </div>
             </form>
             <div className="input-footer">Kanan AI can make mistakes. Verify important information.</div>
          </div>
        </div>
        )}
      </main>
      
      
      {sessionToDelete && (
        <div className="modal-overlay" onClick={() => setSessionToDelete(null)}>
           <div className="modal-content" onClick={e => e.stopPropagation()}>
             <h3>Delete Chat</h3>
             <p>Are you sure you want to permanently delete this chat? This cannot be undone.</p>
             <div className="modal-actions">
               <button className="modal-btn cancel" onClick={() => setSessionToDelete(null)}>Cancel</button>
               <button className="modal-btn confirm" onClick={executeDelete}>Delete</button>
             </div>
           </div>
        </div>
      )}
    </div>
  );
}

export default App;
