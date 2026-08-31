import React from 'react';
import { HeartPulse, Bot, Pill, Activity, Calendar, Heart, FileText, Clock, ArrowRight, Wrench, ShoppingBag } from 'lucide-react';

export default function PatientDashboard() {
  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '24px' }}>
      {/* Header Banner */}
      <section className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '24px 28px', borderRadius: '16px', marginBottom: '24px' }}>
        <div>
          <p style={{ color: '#10B981', fontWeight: '700', fontSize: '0.85rem', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <HeartPulse size={16} /> Kash AI Health Hub
          </p>
          <h1 style={{ fontSize: '2rem', fontWeight: '800', margin: '0 0 4px' }}>Welcome Back, Anaya Mehta</h1>
          <p style={{ color: '#94A3B8', margin: 0, fontSize: '0.9rem' }}>Your personalized Ayurvedic health & wellness portal</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <a href="/new/ai-doctor" className="btn-primary">
            <Bot size={16} /> AI Health Assistant
          </a>
          <a href="/order_medicines" className="btn-secondary">
            <Pill size={16} /> Order Medicines
          </a>
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '24px' }}>
        {/* Sidebar */}
        <aside className="glass-card" style={{ padding: '20px', height: 'fit-content' }}>
          <p style={{ color: '#94A3B8', fontSize: '0.8rem', fontWeight: '700', textTransform: 'uppercase', margin: '0 0 12px' }}>Health Services</p>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <a href="/patient" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', fontWeight: '600', textDecoration: 'none' }}>
              <Activity size={18} /> My Health Overview
            </a>
            <a href="/appointments" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Calendar size={18} /> Appointments
            </a>
            <a href="/order-medicines" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Pill size={18} /> Prescriptions & Orders
            </a>
            <a href="/new/ai-doctor" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Bot size={18} /> AI Symptom Checker
            </a>
            <a href="/device-check" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Wrench size={18} /> Device Diagnostics
            </a>
          </nav>
        </aside>

        {/* Main Section */}
        <main style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Stat Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div className="glass-card" style={{ padding: '20px' }}>
              <div style={{ color: '#10B981', marginBottom: '8px' }}><Heart size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>92%</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Overall Wellness Score</div>
            </div>

            <div className="glass-card" style={{ padding: '20px' }}>
              <div style={{ color: '#06B6D4', marginBottom: '8px' }}><Calendar size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>2</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Upcoming Consultations</div>
            </div>

            <div className="glass-card" style={{ padding: '20px' }}>
              <div style={{ color: '#6366F1', marginBottom: '8px' }}><FileText size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>3</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Active Prescriptions</div>
            </div>
          </div>

          {/* Upcoming Appointments Table */}
          <section className="glass-card" style={{ padding: '24px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1.1rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={18} style={{ color: '#10B981' }} /> Upcoming Appointments
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8' }}>
                    <th style={{ padding: '10px' }}>Date</th>
                    <th style={{ padding: '10px' }}>Care Provider</th>
                    <th style={{ padding: '10px' }}>Time</th>
                    <th style={{ padding: '10px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '12px 10px' }}>Tomorrow</td>
                    <td style={{ padding: '12px 10px', fontWeight: '600' }}>Dr. Ananya Sharma</td>
                    <td style={{ padding: '12px 10px' }}>10:00 AM</td>
                    <td style={{ padding: '12px 10px' }}>
                      <a href="/appointments" style={{ color: '#10B981', textDecoration: 'none', fontWeight: '600', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        View Details <ArrowRight size={14} />
                      </a>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* Active Prescriptions Table */}
          <section className="glass-card" style={{ padding: '24px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1.1rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Pill size={18} style={{ color: '#06B6D4' }} /> Active Prescriptions & Medications
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8' }}>
                    <th style={{ padding: '10px' }}>Formulation / Diagnosis</th>
                    <th style={{ padding: '10px' }}>Issued Date</th>
                    <th style={{ padding: '10px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '12px 10px', fontWeight: '600' }}>Ashwagandha Churna & Brahmi Ghrita</td>
                    <td style={{ padding: '12px 10px' }}>28 Aug 2026</td>
                    <td style={{ padding: '12px 10px' }}>
                      <a href="/order-medicines" style={{ color: '#06B6D4', textDecoration: 'none', fontWeight: '600', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <ShoppingBag size={14} /> Reorder Medicines
                      </a>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
