import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Loader2, Users, Activity, ArrowLeft, MessageSquare, TrendingUp } from 'lucide-react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return <div style={{padding: '2rem', color: '#ef4444', background: '#fef2f2', borderRadius: '8px'}}>Chart crashed: {this.state.error?.toString()}</div>;
    }
    return this.props.children;
  }
}

// Audited Fix: Dynamic routing ensures Vercel cloud deployments never attempt to contact Localhost.
const API_BASE = (import.meta?.env?.VITE_API_BASE || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:8001/api' : null))?.replace(/\/$/, '');

if (!import.meta?.env?.VITE_API_BASE && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
  throw new Error("VITE_API_BASE not configured");
}

const COLORS = ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16', '#e11d48'];

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

const renderCustomLabel = ({ name, percent }) => {
  if (percent < 0.05) return null;
  return `${name} (${(percent * 100).toFixed(0)}%)`;
};

export default function AnalyticsDashboardWrapper(props) {
  return (
    <ErrorBoundary>
      <AnalyticsDashboard {...props} />
    </ErrorBoundary>
  );
}

function AnalyticsDashboard({ onBack }) {

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchAnalytics = async () => {
      try {
        const res = await axios.get(`${API_BASE}/analytics`);
        if (isMounted) {
          setData(res.data);
          setLoading(false);
        }
      } catch (e) {
        if (isMounted) {
            console.error("Analytics API failed:", e);
            toast.error("Analytics API failed");
            setLoading(false);
        }
      }
    };
    
    // Initial fetch
    fetchAnalytics();
    
    // Set up auto-refresh polling every 15 seconds for completely dynamic data views
    const intervalId = setInterval(fetchAnalytics, 15000);
    
    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

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

        {/* Skeleton KPI Cards */}
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

        {/* Skeleton Charts */}
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

  if (!data || !data.distributions || Object.keys(data.distributions).length === 0) {
    return (
      <div className="analytics-loading" style={{ margin: '4rem auto', textAlign: 'center' }}>
        <p style={{ marginBottom: '2rem', fontSize: '1.2rem', color: '#64748b' }}>No analytics data available</p>
        <button className="auth-btn highlight" onClick={onBack} style={{ margin: '0 auto', display: 'flex', alignItems: 'center', gap: '0.5rem', width: 'fit-content', padding: '0.75rem 2rem' }}>
          <ArrowLeft size={18} /> Back to Chat
        </button>
      </div>
    );
  }

  const { summary, distributions, usage } = data;
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
        <p className="analytics-subtitle">Real-time dynamic insights from your data</p>
      </div>

      {(!summary?.total_documents || summary.total_documents === 0) ? (
        <motion.div 
          className="auth-card" 
          style={{ maxWidth: '600px', margin: '4rem auto', textAlign: 'center', boxShadow: '0 10px 40px rgba(0,0,0,0.1)' }}
          variants={containerVariants}
        >
           <div className="auth-logo-box" style={{ background: '#fef2f2', color: '#ef4444' }}>
              <Activity size={32} />
           </div>
           <h2>Database Offline/Empty</h2>
           <p style={{ color: '#64748b', marginTop: '1rem', lineHeight: '1.6' }}>
             Your Kanan MongoDB Atlas cluster is currently completely empty or unreachable. The RAG AI engine and Analytics Dashboard cannot generate visual vectors until you seed the databank.
           </p>
           <button 
              onClick={onBack}
              className="auth-btn highlight" 
              style={{ width: 'auto', margin: '2rem auto 0', padding: '0.75rem 2rem' }}
            >
             <ArrowLeft size={18} /> Return to Engine & Upload Excel
           </button>
        </motion.div>
      ) : (
      <>
        {/* Dynamic KPI Cards */}
        <div className="kpi-grid">
        <KpiCard icon={Users} label="Total Records" value={summary?.total_documents || 0} color="#4f46e5" />
        
        {usage && usage.total_queries !== undefined && (
          <KpiCard icon={MessageSquare} label="Total Queries" value={usage.total_queries} color="#ec4899" />
        )}

        {summary?.active_rate !== undefined && (
          <KpiCard icon={Activity} label="Active Rate" value={`${summary.active_rate}%`} color="#10b981" />
        )}
        
        {Object.keys(summary || {})
          .filter(k => k.startsWith('unique_'))
          .map((k, idx) => {
            const label = k.replace('unique_', '');
            return (
              <KpiCard 
                key={k} 
                icon={Activity} 
                label={`Unique ${label}s`} 
                value={summary[k]} 
                color={COLORS[idx % COLORS.length]} 
              />
            );
        })}
      </div>

      {/* Dynamic Charts Grid */}
      <div className="charts-grid">
        {usage && usage.top_queries && usage.top_queries.length > 0 && (
          <ChartCard title="Top User Queries">
            <ResponsiveContainer width="100%" height={380}>
              <BarChart data={usage.top_queries} layout="vertical" margin={{ top: 5, right: 30, left: 60, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} width={120} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                  {usage.top_queries.map((_, i) => <Cell key={i} fill={COLORS[(i + 4) % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {distKeys.map((key, index) => {
            const distData = distributions[key];
            if (!distData || distData.length === 0) return null;
            
            // Render BarChart if too many categories, else PieChart
            const isManyItems = distData.length > 8; 
            
            return (
              <ChartCard key={key} title={`${key} Breakdown`}>
                 <ErrorBoundary>
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
                 </ErrorBoundary>
              </ChartCard>
            );
        })}
      </div>
      </>
      )}
    </motion.div>
  );
}
