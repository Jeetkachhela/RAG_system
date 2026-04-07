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

  const { summary, by_zone, by_rank, by_city, by_category, active_status, by_team } = data;

  return (
    <div className="analytics-dashboard">
      <div className="analytics-header">
        <div className="analytics-header-left">
          <button className="back-btn" onClick={onBack}>
            <ArrowLeft size={16} /> Back to Chat
          </button>
          <h2>Analytics Dashboard</h2>
        </div>
        <p className="analytics-subtitle">Real-time insights from your agent network</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <KpiCard icon={Users} label="Total Agents" value={summary.total_agents} color="#4f46e5" />
        <KpiCard icon={Activity} label="Active Rate" value={`${summary.active_rate}%`} color="#10b981" />
        <KpiCard icon={Globe} label="Zones" value={summary.zones} color="#06b6d4" />
        <KpiCard icon={MapPin} label="Cities" value={summary.cities} color="#f59e0b" />
        <KpiCard icon={TrendingUp} label="Rank Tiers" value={summary.ranks} color="#8b5cf6" />
        <KpiCard icon={Users} label="Active Agents" value={summary.active_agents} color="#059669" />
      </div>

      {/* Charts Grid */}
      <div className="charts-grid">
        {/* Agents by Zone - Bar Chart */}
        <ChartCard title="Agents by Zone">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={by_zone} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 12, fill: '#64748b' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {by_zone.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Rank Distribution - Donut Chart */}
        <ChartCard title="Rank Distribution">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={by_rank} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3} dataKey="value" label={renderCustomLabel} labelLine={false}>
                {by_rank.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Active vs Inactive - Donut Chart */}
        <ChartCard title="Active vs Inactive">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={active_status} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value" label={renderCustomLabel} labelLine={false}>
                {active_status.map((_, i) => <Cell key={i} fill={i === 0 ? '#10b981' : '#ef4444'} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Top Cities - Horizontal Bar */}
        <ChartCard title="Top 15 Cities">
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={by_city} layout="vertical" margin={{ top: 5, right: 20, left: 60, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} width={80} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                {by_city.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Category Breakdown - Pie Chart */}
        <ChartCard title="Category Breakdown">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={by_category} cx="50%" cy="50%" outerRadius={100} paddingAngle={2} dataKey="value" label={renderCustomLabel} labelLine={false}>
                {by_category.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Team Distribution - Bar Chart */}
        <ChartCard title="Top Teams">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={by_team} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} angle={-30} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 12, fill: '#64748b' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {by_team.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
