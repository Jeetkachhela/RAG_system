import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Loader2, Users, Activity, MapPin, Globe, ArrowLeft, TrendingUp } from 'lucide-react';
import toast from 'react-hot-toast';

const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://127.0.0.1:8001/api').replace(/\/$/, '');

const COLORS = ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16', '#e11d48'];

const KpiCard = ({ icon: Icon, label, value, color }) => (
  <div className="kpi-card">
    <div className="kpi-icon" style={{ background: `${color}15`, color }}>
      <Icon size={22} />
    </div>
    <div className="kpi-info">
      <span className="kpi-value">{value}</span>
      <span className="kpi-label">{label}</span>
    </div>
  </div>
);

const ChartCard = ({ title, children }) => (
  <div className="chart-card">
    <h3 className="chart-title">{title}</h3>
    <div className="chart-body">{children}</div>
  </div>
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

export default function AnalyticsDashboard({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const res = await axios.get(`${API_BASE}/analytics`);
        setData(res.data);
      } catch (e) {
        toast.error("Failed to load analytics");
      } finally {
        setLoading(false);
      }
    };
    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <div className="analytics-loading">
        <Loader2 size={40} className="animate-spin" style={{ color: '#4f46e5' }} />
        <p>Loading Analytics Dashboard...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="analytics-loading">
        <p>No analytics data available. Please sync your database first.</p>
        <button className="back-btn" onClick={onBack}><ArrowLeft size={16} /> Back to Chat</button>
      </div>
    );
  }

  const { summary, distributions } = data;
  const distKeys = Object.keys(distributions || {});

  return (
    <div className="analytics-dashboard">
      <div className="analytics-header">
        <div className="analytics-header-left">
          <button className="back-btn" onClick={onBack}>
            <ArrowLeft size={16} /> Back to Chat
          </button>
          <h2>Analytics Dashboard</h2>
        </div>
        <p className="analytics-subtitle">Real-time dynamic insights from your data</p>
      </div>

      {/* Dynamic KPI Cards */}
      <div className="kpi-grid">
        <KpiCard icon={Users} label="Total Records" value={summary?.total_documents || 0} color="#4f46e5" />
        
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
                icon={TrendingUp} 
                label={`Unique ${label}s`} 
                value={summary[k]} 
                color={COLORS[idx % COLORS.length]} 
              />
            );
        })}
      </div>

      {/* Dynamic Charts Grid */}
      <div className="charts-grid">
        {distKeys.map((key, index) => {
            const distData = distributions[key];
            if (!distData || distData.length === 0) return null;
            
            // Render BarChart if too many categories, else PieChart
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
    </div>
  );
}
