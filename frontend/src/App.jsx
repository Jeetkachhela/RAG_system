import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Database, Loader2, Bot, PlusSquare, MessageSquare, Trash2, Menu, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import toast, { Toaster } from 'react-hot-toast';
import { v4 as uuidv4 } from 'uuid';
import './index.css';

const API_BASE = 'http://127.0.0.1:8000/api';
const SYSTEM_MSG = { role: 'assistant', content: 'Hello! I am Kanan, your conversational agent assistant. You can ask me about our agents, their ranks, zones, cities, and more!' };

function App() {
  const [sessions, setSessions] = useState(() => {
    const saved = localStorage.getItem('kanan_sessions');
    return saved ? JSON.parse(saved) : {};
  });
  const [currentSessionId, setCurrentSessionId] = useState(() => {
    return localStorage.getItem('kanan_current_session') || uuidv4();
  });
  const [messages, setMessages] = useState(() => {
    if (sessions[currentSessionId]) return sessions[currentSessionId].messages;
    return [SYSTEM_MSG];
  });
  
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const createNewChat = () => {
    const newId = uuidv4();
    setCurrentSessionId(newId);
    setMessages([SYSTEM_MSG]);
    setSidebarOpen(false);
  };

  const loadSession = (id) => {
    setCurrentSessionId(id);
    setMessages(sessions[id].messages);
    setSidebarOpen(false);
  };

  const deleteSession = (e, id) => {
    e.stopPropagation();
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

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg = { role: 'user', content: input.trim() };
    const newHistory = [...messages, userMsg];
    
    setMessages(newHistory);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newHistory })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

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
      console.error(err);
      toast.error('Failed to communicate with Kanan AI');
      setMessages([...newHistory, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleIngest = async () => {
    setIsIngesting(true);
    const toastId = toast.loading('Updating knowledge base...');
    try {
      const resp = await axios.post(`${API_BASE}/ingest`);
      toast.success(resp.data.message, { id: toastId });
    } catch (err) {
      toast.error('Failed to update knowledge base.', { id: toastId });
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="layout">
      <Toaster position="top-right" toastOptions={{
        style: { background: '#1e293b', color: '#fff', border: '1px solid #475569' }
      }} />
      
      <div className="mobile-header">
         <button className="icon-btn" onClick={() => setSidebarOpen(true)}>
            <Menu size={24} />
         </button>
         <div className="header-title mobile">
            <Bot size={24} color="#8b5cf6" />
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
          {Object.values(sessions).sort((a,b) => new Date(b.updatedAt) - new Date(a.updatedAt)).map(session => (
            <div 
              key={session.id} 
              className={`session-item ${currentSessionId === session.id ? 'active' : ''}`}
              onClick={() => loadSession(session.id)}
            >
              <MessageSquare size={16} className="session-icon" />
              <span className="session-title">{session.title}</span>
              <button 
                className="delete-session-btn"
                onClick={(e) => deleteSession(e, session.id)}
                title="Delete Chat"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <button 
            className={`ingest-btn-small ${isIngesting ? 'loading' : ''}`}
            onClick={handleIngest}
            disabled={isIngesting}
          >
            {isIngesting ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
            {isIngesting ? 'Updating DB...' : 'Sync Database'}
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="header desktop-only">
          <div className="header-title">
            <Bot size={28} color="#8b5cf6" />
            <h1>Kanan Ops Platform</h1>
          </div>
        </header>

        <div className="chat-container">
          <div className="chat-messages">
            {messages.length === 1 && (
              <div className="welcome-screen">
                 <Bot size={48} color="#8b5cf6" className="welcome-icon" />
                 <h2>Hi, what can I help with?</h2>
                 <p>Ask anything about our study abroad services or agent network.</p>
                 <div className="suggestion-chips">
                    <button onClick={() => setSuggestedInput("List all Platinum agents in Gujarat")}>"List Platinum agents in Gujarat"</button>
                    <button onClick={() => setSuggestedInput("What are Kanan's core services?")}>"What are Kanan's core services?"</button>
                    <button onClick={() => setSuggestedInput("Who heads the USA and Canada departments?")}>"Who heads the departments?"</button>
                    <button onClick={() => setSuggestedInput("Show me diamond rank agents in Mumbai")}>"Show me Diamond agents"</button>
                 </div>
              </div>
            )}
            
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-wrapper ${msg.role} ${idx === 0 && messages.length === 1 ? 'hidden' : ''}`}>
                <div className={`message ${msg.role}`}>
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown className="markdown-pro" remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="message-wrapper ai">
                <div className="message ai">
                  <div className="typing-indicator">
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-wrapper">
             <form className="chat-input-container" onSubmit={handleSend}>
               <textarea
                 className="chat-input"
                 value={input}
                 onChange={(e) => setInput(e.target.value)}
                 onKeyDown={handleKeyDown}
                 placeholder="Message Kanan..."
                 disabled={isLoading}
                 rows={1}
               />
               <button type="submit" className="send-btn" disabled={!input.trim() || isLoading}>
                 <Send size={18} />
               </button>
             </form>
             <div className="input-footer">Kanan AI can make mistakes. Verify important information.</div>
          </div>
        </div>
      </main>
      
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)}></div>}
    </div>
  );
}

export default App;
