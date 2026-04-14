import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Loader2, Users, Activity, ArrowLeft, TrendingUp, MapPin } from 'lucide-react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

// Use same API_BASE logic as App.jsx — includes Render fallback
const API_BASE = (import.meta?.env?.VITE_API_BASE || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:8001/api' : 'https://rag-system-834m.onrender.com/api')).replace(/\/$/, '');

const COLORS = ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16', '#e11d48'];

// Pick a relevant icon based on field name
const getFieldIcon = (fieldName) => {
  const lower = fieldName.toLowerCase();
  if (lower.includes('zone') || lower.includes('region')) return MapPin;
  if (lower.includes('active')) return Activity;
  if (lower.includes('team') || lower.includes('type') || lower.includes('category')) return Users;
  return TrendingUp;
};

const KpiCard = ({ icon: Icon, label, value, color }) => (
  <motion.div 
    className="kpi-card"
    variants={{
      hidden: { opacity: 0, y: 20 },
      show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
    }}
  >
    <div className="kpi-icon" style={{ background: `${color}15`, color }}>
      <Icon size={22} />
    </div>
    <div className="kpi-info">
      <span className="kpi-value">{value}</span>
      <span className="kpi-label">{label}</span>
    </div>
  </motion.div>
);

const ChartCard = ({ title, children }) => (
  <motion.div 
    className="chart-card"
    variants={{
      hidden: { opacity: 0, scale: 0.95 },
      show: { opacity: 1, scale: 1, transition: { type: "spring", stiffness: 300, damping: 24 } }
    }}
  >
    <h3 className="chart-title">{title}</h3>
    <div className="chart-body">{children}</div>
  </motion.div>
);

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="custom-tooltip">
        <p className="tooltip-label">{label || payload[0].name}</p>
        <p className="tooltip-value">{payload[0].value} agents</p>
      </div>
    );
  }
  return null;
};

export default function AnalyticsDashboard({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const fetchAnalytics = async () => {
      try {
        console.log(`[Analytics] Fetching from: ${API_BASE}/analytics`);
        const res = await axios.get(`${API_BASE}/analytics`);
        console.log('[Analytics] Response:', res.data);
        if (isMounted) {
          setData(res.data);
          setError(null);
          setLoading(false);
        }
      } catch (e) {
        console.error("[Analytics] API failed:", e);
        if (isMounted) {
          setError(e.message || "Failed to load analytics");
          toast.error(`Analytics failed: ${e.response?.data?.detail || e.message}`);
          setLoading(false);
        }
      }
    };
    
    fetchAnalytics();
    const intervalId = setInterval(fetchAnalytics, 15000);
    
    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  // Loading state with skeleton
  if (loading) {
    return (
      <motion.div 
        className="analytics-dashboard"
        initial={{ opacity: 0 }} 
        animate={{ opacity: 1 }} 
        exit={{ opacity: 0 }}
      >
        <div className="analytics-header">
          <div className="analytics-header-left">
            <button className="back-btn" onClick={onBack} title="Back to Chat">
              <ArrowLeft size={20} />
            </button>
            <h2>Analytics Dashboard</h2>
          </div>
          <p className="analytics-subtitle">Crunching your data...</p>
        </div>

        <div className="kpi-grid">
          {[1, 2, 3, 4].map(i => (
            <motion.div 
              key={i} 
              className="kpi-card skeleton-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, type: "spring", stiffness: 300, damping: 24 }}
            >
              <div className="skeleton-icon pulse-glow" />
              <div className="skeleton-text-group">
                <div className="skeleton-line skeleton-value pulse-glow" />
                <div className="skeleton-line skeleton-label pulse-glow" />
              </div>
            </motion.div>
          ))}
        </div>

        <div className="charts-grid">
          {[1, 2].map(i => (
            <motion.div 
              key={i} 
              className="chart-card"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.4 + i * 0.15, type: "spring", stiffness: 300, damping: 24 }}
            >
              <div className="skeleton-line skeleton-chart-title pulse-glow" style={{ width: '40%', marginBottom: '1.5rem' }} />
              <div className="skeleton-chart pulse-glow" />
            </motion.div>
          ))}
        </div>
      </motion.div>
    );
  }

  // Error state
  if (error) {
    return (
      <motion.div className="analytics-dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div className="analytics-header">
          <div className="analytics-header-left">
            <button className="back-btn" onClick={onBack} title="Back to Chat">
              <ArrowLeft size={20} />
            </button>
            <h2>Analytics Dashboard</h2>
          </div>
        </div>
        <div style={{ margin: '4rem auto', textAlign: 'center', maxWidth: '500px' }}>
          <div style={{ background: '#fef2f2', color: '#ef4444', padding: '1rem', borderRadius: '12px', marginBottom: '1.5rem' }}>
            <Activity size={32} style={{ marginBottom: '0.5rem' }} />
            <p style={{ fontWeight: 600, fontSize: '1.1rem' }}>Failed to load analytics</p>
            <p style={{ color: '#64748b', fontSize: '0.9rem', marginTop: '0.5rem' }}>{error}</p>
          </div>
          <button 
            onClick={onBack}
            className="auth-submit-btn" 
            style={{ width: 'auto', margin: '0 auto', padding: '0.75rem 2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <ArrowLeft size={18} /> Return to Chat
          </button>
        </div>
      </motion.div>
    );
  }

  // Empty data state
  if (!data || !data.summary || data.summary.total_documents === 0) {
    return (
      <motion.div className="analytics-dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div className="analytics-header">
          <div className="analytics-header-left">
            <button className="back-btn" onClick={onBack} title="Back to Chat">
              <ArrowLeft size={20} />
            </button>
            <h2>Analytics Dashboard</h2>
          </div>
        </div>
        <motion.div 
          style={{ maxWidth: '600px', margin: '4rem auto', textAlign: 'center', background: '#fff', padding: '3rem', borderRadius: '20px', border: '1px solid #e2e8f0', boxShadow: '0 10px 40px rgba(0,0,0,0.1)' }}
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
        >
          <div style={{ background: '#fef2f2', color: '#ef4444', width: '64px', height: '64px', borderRadius: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
            <Activity size={32} />
          </div>
          <h2 style={{ color: '#0f172a', marginBottom: '0.5rem' }}>Database Empty</h2>
          <p style={{ color: '#64748b', marginTop: '1rem', lineHeight: '1.6' }}>
            Your MongoDB Atlas collection is empty. Upload an Excel file to populate the database and generate analytics.
          </p>
          <button 
            onClick={onBack}
            className="auth-submit-btn" 
            style={{ width: 'auto', margin: '2rem auto 0', padding: '0.75rem 2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <ArrowLeft size={18} /> Return & Upload Data
          </button>
        </motion.div>
      </motion.div>
    );
  }

  const { summary, distributions } = data;
  const distKeys = Object.keys(distributions || {});

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  return (
    <motion.div 
      className="analytics-dashboard"
      initial="hidden"
      animate="show"
      variants={containerVariants}
    >
      <div className="analytics-header">
        <div className="analytics-header-left">
          <button className="back-btn" onClick={onBack} title="Back to Chat">
            <ArrowLeft size={20} />
          </button>
          <h2>Analytics Dashboard</h2>
        </div>
        <p className="analytics-subtitle">Real-time dynamic insights from your data • {summary?.total_documents?.toLocaleString()} records</p>
      </div>

      {/* Dynamic KPI Cards */}
      <div className="kpi-grid">
        <KpiCard icon={Users} label="Total Records" value={summary?.total_documents?.toLocaleString() || 0} color="#4f46e5" />
        
        {summary?.active_rate !== undefined && (
          <KpiCard icon={Activity} label="Active Rate" value={`${summary.active_rate}%`} color="#10b981" />
        )}
        
        {Object.keys(summary || {})
          .filter(k => k.startsWith('unique_'))
          .slice(0, 6)
          .map((k, idx) => {
            const fieldName = k.replace('unique_', '');
            const FieldIcon = getFieldIcon(fieldName);
            return (
              <KpiCard 
                key={k} 
                icon={FieldIcon} 
                label={`Unique ${fieldName}s`} 
                value={summary[k]} 
                color={COLORS[(idx + 2) % COLORS.length]} 
              />
            );
        })}
      </div>

      {/* Dynamic Charts Grid */}
      {distKeys.length > 0 ? (
        <div className="charts-grid">
          {distKeys.map((key, index) => {
              const distData = distributions[key];
              if (!distData || distData.length === 0) return null;
              
              const isManyItems = distData.length > 8; 
              
              return (
                <ChartCard key={key} title={`${key} Breakdown`}>
                   <ResponsiveContainer width="100%" height={isManyItems ? 500 : 380}>
                     {isManyItems ? (
                       <BarChart data={distData} layout="vertical" margin={{ top: 5, right: 30, left: 60, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                          <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} />
                          <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} width={100} />
                          <Tooltip content={<CustomTooltip />} />
                          <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                            {distData.map((_, i) => <Cell key={i} fill={COLORS[(i + index) % COLORS.length]} />)}
                          </Bar>
                        </BarChart>
                     ) : (
                       <PieChart>
                          <Pie 
                            data={distData} 
                            cx="50%" 
                            cy="50%" 
                            innerRadius={60} 
                            outerRadius={90} 
                            paddingAngle={5} 
                            dataKey="value" 
                            label={({ name, percent }) => percent > 0.02 ? `${name} (${(percent * 100).toFixed(0)}%)` : ''}
                          >
                            {distData.map((_, i) => <Cell key={i} fill={COLORS[(i + index) % COLORS.length]} />)}
                          </Pie>
                          <Tooltip content={<CustomTooltip />} />
                          <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px' }} />
                        </PieChart>
                     )}
                   </ResponsiveContainer>
                </ChartCard>
              );
          })}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
          <p>Data exists but no categorical distributions were detected.</p>
        </div>
      )}
    </motion.div>
  );
}
