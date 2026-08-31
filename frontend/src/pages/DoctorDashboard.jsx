import React from 'react';
import { Users, Calendar, IndianRupee, Star, Bot, TrendingUp, Mic, UserPlus, Stethoscope, BarChart2, Wrench, Pill, Zap, Clock } from 'lucide-react';

export default function DoctorDashboard() {
  const stats = [
    { label: "Total Patients", value: "1,248", change: "+12% this month", icon: Users, color: "#10B981" },
    { label: "Today's Appointments", value: "8 Scheduled", change: "3 upcoming", icon: Calendar, color: "#06B6D4" },
    { label: "Revenue This Month", value: "₹42,500", change: "+18% growth", icon: IndianRupee, color: "#6366F1" },
    { label: "Avg Satisfaction", value: "4.9 / 5", change: "From 180+ reviews", icon: Star, color: "#F59E0B" },
    { label: "AI-Assisted Cases", value: "312 Cases", change: "96% accuracy", icon: Bot, color: "#10B981" },
    { label: "Case Completion", value: "94%", change: "5 pending review", icon: TrendingUp, color: "#06B6D4" },
  ];

  const quickActions = [
    { label: "Voice Consultation", path: "/consultation/voice", icon: Mic },
    { label: "Add Patient", path: "/new/patients/add", icon: UserPlus },
    { label: "Schedule Appointment", path: "/appointments", icon: Calendar },
    { label: "AI Doctor Chat", path: "/new/ai-doctor", icon: Stethoscope },
    { label: "Feature Status", path: "/feature-status", icon: BarChart2 },
    { label: "Device Diagnostics", path: "/device-check", icon: Wrench },
    { label: "View Statistics", path: "/doctor/stats", icon: TrendingUp },
    { label: "New Prescription", path: "/new/prescriptions/new", icon: Pill },
  ];

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '24px' }}>
      {/* Header */}
      <section className="glass-card" style={{ padding: '28px', marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p style={{ color: '#10B981', fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>Clinic Command Center</p>
          <h1 style={{ fontSize: '2rem', fontWeight: '800' }}>Doctor Dashboard</h1>
          <p style={{ color: '#94A3B8', margin: '4px 0 0' }}>Welcome back, Dr. Ananya Sharma · Ayurvedic Physician</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn-primary">
            <Mic size={16} /> Start Voice Note
          </button>
        </div>
      </section>

      {/* Metric Cards Grid */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        {stats.map((stat, idx) => {
          const IconComponent = stat.icon;
          return (
            <div key={idx} className="glass-card" style={{ padding: '20px' }}>
              <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: `${stat.color}15`, color: stat.color, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                <IconComponent size={22} />
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: '800', color: '#F8FAFC' }}>{stat.value}</div>
              <div style={{ fontSize: '0.85rem', fontWeight: '600', color: '#94A3B8', marginTop: '4px' }}>{stat.label}</div>
              <div style={{ fontSize: '0.8rem', color: '#10B981', marginTop: '4px' }}>{stat.change}</div>
            </div>
          );
        })}
      </section>

      {/* Quick Actions Grid */}
      <section className="glass-card" style={{ padding: '28px', marginBottom: '32px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: '700', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Zap size={20} style={{ color: '#10B981' }} /> Quick Actions
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
          {quickActions.map((action, idx) => {
            const IconComp = action.icon;
            return (
              <a key={idx} href={action.path} className="btn-secondary" style={{ padding: '14px 18px', justifyContent: 'flex-start' }}>
                <IconComp size={18} style={{ color: '#10B981' }} /> {action.label}
              </a>
            );
          })}
        </div>
      </section>

      {/* Recent Consultation Activity */}
      <section className="glass-card" style={{ padding: '28px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: '700', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Clock size={20} style={{ color: '#06B6D4' }} /> Today's Consultation Queue
        </h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8' }}>
                <th style={{ padding: '12px' }}>Time</th>
                <th style={{ padding: '12px' }}>Patient Name</th>
                <th style={{ padding: '12px' }}>Prakriti / Diagnosis</th>
                <th style={{ padding: '12px' }}>Status</th>
                <th style={{ padding: '12px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '14px 12px' }}>10:00 AM</td>
                <td style={{ padding: '14px 12px', fontWeight: '600' }}>Anaya Mehta</td>
                <td style={{ padding: '14px 12px', color: '#94A3B8' }}>Vata-Pitta · Insomnia</td>
                <td style={{ padding: '14px 12px' }}><span className="badge badge-emerald">Active</span></td>
                <td style={{ padding: '14px 12px' }}><button className="btn-primary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>Start SOAP</button></td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '14px 12px' }}>11:30 AM</td>
                <td style={{ padding: '14px 12px', fontWeight: '600' }}>Rohan Iyer</td>
                <td style={{ padding: '14px 12px', color: '#94A3B8' }}>Kapha-Pitta · Digestive Imbalance</td>
                <td style={{ padding: '14px 12px' }}><span className="badge badge-cyan">Scheduled</span></td>
                <td style={{ padding: '14px 12px' }}><button className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>View Record</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
