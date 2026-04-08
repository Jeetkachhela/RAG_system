import React, { useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Mail, KeyRound, ArrowRight, ShieldCheck, HelpCircle } from 'lucide-react';
import toast, { Toaster } from 'react-hot-toast';

const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://127.0.0.1:8001/api').replace(/\/$/, '');

export default function AuthScreen({ onLoginSuccess }) {
  const [view, setView] = useState('login'); // 'login', 'register', 'forgot-password-1', 'forgot-password-2'
  const [isLoading, setIsLoading] = useState(false);
  
  // Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('What city were you born in?');
  const [securityAnswer, setSecurityAnswer] = useState('');
  
  // Reset Password State
  const [fetchedQuestion, setFetchedQuestion] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/auth/login`, { email, password });
      toast.success("Login successful!");
      localStorage.setItem('kanan_auth_token', res.data.access_token);
      onLoginSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Invalid credentials");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/auth/register`, {
        email,
        password,
        security_question: securityQuestion,
        security_answer: securityAnswer
      });
      toast.success("Registration successful!");
      localStorage.setItem('kanan_auth_token', res.data.access_token);
      onLoginSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPasswordStep1 = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/auth/forgot-password-step1`, { email });
      setFetchedQuestion(res.data.security_question);
      setView('forgot-password-2');
    } catch (err) {
      toast.error(err.response?.data?.detail || "Email not found");
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPasswordStep2 = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await axios.post(`${API_BASE}/auth/reset-password`, {
        email,
        security_answer: securityAnswer,
        new_password: newPassword
      });
      toast.success("Password reset securely!");
      setPassword(newPassword); // Help auto-fill
      setView('login');
      setSecurityAnswer('');
      setNewPassword('');
    } catch (err) {
      toast.error(err.response?.data?.detail || "Incorrect answer");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-overlay">
      <Toaster position="top-right" toastOptions={{
        style: { background: '#ffffff', color: '#1e293b', border: '1px solid #cbd5e1' }
      }} />
      <div className="auth-bg-decor1"></div>
      <div className="auth-bg-decor2"></div>
      
      <motion.div 
        className="auth-card"
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        <div className="auth-header">
          <div className="auth-logo-box">
            <ShieldCheck size={28} className="auth-logo-icon" />
          </div>
          <h2>Kanan RAG</h2>
          <p>Secure Intelligence Platform</p>
        </div>

        <AnimatePresence mode="wait">
          {view === 'login' && (
            <motion.form 
              key="login"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.2 }}
              onSubmit={handleLogin} 
              className="auth-form"
            >
              <div className="input-group">
                <Mail size={18} className="input-icon" />
                <input type="email" placeholder="Email Address" required value={email} onChange={e => setEmail(e.target.value)} />
              </div>
              <div className="input-group">
                <Lock size={18} className="input-icon" />
                <input type="password" placeholder="Password" required value={password} onChange={e => setPassword(e.target.value)} />
              </div>
              
              <button type="submit" disabled={isLoading} className="auth-btn">
                {isLoading ? <span className="auth-spinner"></span> : "Sign In"}
              </button>
              
              <div className="auth-footer">
                <button type="button" onClick={() => setView('forgot-password-1')} className="text-btn">Forgot Password?</button>
                <div className="auth-divider"></div>
                <button type="button" onClick={() => setView('register')} className="text-btn outline">Create new account</button>
              </div>
            </motion.form>
          )}

          {view === 'register' && (
            <motion.form 
              key="register"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              onSubmit={handleRegister} 
              className="auth-form"
            >
              <div className="input-group">
                <Mail size={18} className="input-icon" />
                <input type="email" placeholder="Email Address" required value={email} onChange={e => setEmail(e.target.value)} />
              </div>
              <div className="input-group">
                <Lock size={18} className="input-icon" />
                <input type="password" placeholder="Create Password" required value={password} onChange={e => setPassword(e.target.value)} />
              </div>
              
              <div className="security-section">
                <p className="security-label">Security Question (For Password Resets)</p>
                <select className="security-select" value={securityQuestion} onChange={e => setSecurityQuestion(e.target.value)}>
                  <option>What city were you born in?</option>
                  <option>What was your first pet's name?</option>
                  <option>What is your mother's maiden name?</option>
                  <option>What high school did you attend?</option>
                </select>
                <div className="input-group">
                  <KeyRound size={18} className="input-icon" />
                  <input type="text" placeholder="Your Answer" required value={securityAnswer} onChange={e => setSecurityAnswer(e.target.value)} />
                </div>
              </div>

              <button type="submit" disabled={isLoading} className="auth-btn">
                {isLoading ? <span className="auth-spinner"></span> : "Register"}
              </button>
              
              <div className="auth-footer center">
                <button type="button" onClick={() => setView('login')} className="text-btn light">Already have an account? Sign in</button>
              </div>
            </motion.form>
          )}

          {view === 'forgot-password-1' && (
            <motion.form 
              key="fp1"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onSubmit={handleForgotPasswordStep1} 
              className="auth-form"
            >
              <p className="auth-instructions">Enter your email to reset your password.</p>
              <div className="input-group">
                <Mail size={18} className="input-icon" />
                <input type="email" placeholder="Registered Email" required value={email} onChange={e => setEmail(e.target.value)} />
              </div>

              <button type="submit" disabled={isLoading} className="auth-btn">
                {isLoading ? <span className="auth-spinner"></span> : <>Continue <ArrowRight size={16} /></>}
              </button>
              
              <div className="auth-footer center">
                <button type="button" onClick={() => setView('login')} className="text-btn light">Back to Sign In</button>
              </div>
            </motion.form>
          )}

          {view === 'forgot-password-2' && (
            <motion.form 
              key="fp2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onSubmit={handleForgotPasswordStep2} 
              className="auth-form"
            >
              <div className="security-section highlight">
                <HelpCircle size={20} className="q-icon" />
                <p className="q-text">{fetchedQuestion}</p>
              </div>
              <div className="input-group">
                <KeyRound size={18} className="input-icon" />
                <input type="text" placeholder="Type your answer..." required value={securityAnswer} onChange={e => setSecurityAnswer(e.target.value)} />
              </div>
              
              <div className="input-group mt-3">
                <Lock size={18} className="input-icon" />
                <input type="password" placeholder="New Password" required value={newPassword} onChange={e => setNewPassword(e.target.value)} />
              </div>

              <button type="submit" disabled={isLoading} className="auth-btn highlight">
                {isLoading ? <span className="auth-spinner"></span> : "Reset Password"}
              </button>
              
              <div className="auth-footer center">
                <button type="button" onClick={() => { setView('login'); setSecurityAnswer(''); setNewPassword(''); }} className="text-btn light">Cancel</button>
              </div>
            </motion.form>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
