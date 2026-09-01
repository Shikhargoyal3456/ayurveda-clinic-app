import React, { useState } from 'react';
import { HeartPulse, Bot, Pill, Activity, Calendar, Heart, FileText, Clock, ArrowRight, Wrench, ShoppingBag, Upload, Mic } from 'lucide-react';
import VoiceMicInput from '../components/VoiceMicInput';
import PrescriptionReaderModal from '../components/PrescriptionReaderModal';

export default function PatientDashboard() {
  const [isPrescriptionModalOpen, setIsPrescriptionModalOpen] = useState(false);
  const [voiceQuery, setVoiceQuery] = useState('');

  const handleVoiceTranscript = (text) => {
    setVoiceQuery(text);
    // Redirect or trigger search
    window.location.href = `/order-medicines?q=${encodeURIComponent(text)}`;
  };

  const handlePrescriptionExtracted = (medicines) => {
    alert(`Extracted ${medicines.length} medicines! Redirecting to cart...`);
    window.location.href = '/order-medicines';
  };

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '24px' }}>
      {/* Header Banner */}
      <section className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '24px 28px', borderRadius: '16px', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <p style={{ color: '#10B981', fontWeight: '700', fontSize: '0.85rem', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <HeartPulse size={16} /> Kash AI Patient Health Portal
          </p>
          <h1 style={{ fontSize: '2rem', fontWeight: '800', margin: '0 0 4px', color: '#F8FAFC' }}>Welcome Back, Health Portal User</h1>
          <p style={{ color: '#94A3B8', margin: 0, fontSize: '0.9rem' }}>Your personalized Ayurvedic health, AI diagnosis & prescription workspace</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={() => setIsPrescriptionModalOpen(true)} className="btn-gold">
            <Upload size={16} style={{ marginRight: '6px' }} /> Upload Prescription (AI Reader)
          </button>
          <a href="/new/ai-doctor" className="btn-primary">
            <Bot size={16} style={{ marginRight: '6px' }} /> AI Health Assistant
          </a>
        </div>
      </section>

      {/* Voice Assistant Bar */}
      <section className="glass-card" style={{ padding: '16px 20px', borderRadius: '14px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '16px', background: 'rgba(232, 178, 74, 0.06)', border: '1px solid rgba(232, 178, 74, 0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
          <VoiceMicInput onTranscript={handleVoiceTranscript} />
          <div>
            <span style={{ fontSize: '0.9rem', fontWeight: '700', color: '#E8B24A', display: 'block' }}>Voice Assistant Active</span>
            <span style={{ fontSize: '0.82rem', color: '#94A3B8' }}>Tap mic to speak your symptoms or search for remedies hands-free</span>
          </div>
        </div>
        {voiceQuery && (
          <span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', padding: '4px 12px', borderRadius: '12px', fontSize: '0.85rem' }}>
            Recorded: "{voiceQuery}"
          </span>
        )}
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '24px' }}>
        {/* Sidebar Navigation */}
        <aside className="glass-card" style={{ padding: '20px', height: 'fit-content', borderRadius: '16px' }}>
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

        {/* Main Health Dashboard Content */}
        <main style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Stat Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div className="glass-card" style={{ padding: '20px', borderRadius: '14px' }}>
              <div style={{ color: '#10B981', marginBottom: '8px' }}><Heart size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>94%</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Wellness Index</div>
            </div>

            <div className="glass-card" style={{ padding: '20px', borderRadius: '14px' }}>
              <div style={{ color: '#06B6D4', marginBottom: '8px' }}><Calendar size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>1</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Active Consultation</div>
            </div>

            <div className="glass-card" style={{ padding: '20px', borderRadius: '14px' }}>
              <div style={{ color: '#6366F1', marginBottom: '8px' }}><FileText size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>2</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Verified Prescriptions</div>
            </div>
          </div>

          {/* Quick Actions & AI Reader Card */}
          <section className="glass-card" style={{ padding: '24px', borderRadius: '16px', background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(232, 178, 74, 0.08))' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div>
                <h3 style={{ margin: '0 0 6px', fontSize: '1.2rem', color: '#F8FAFC' }}>Have a paper or doctor's prescription?</h3>
                <p style={{ margin: 0, color: '#94A3B8', fontSize: '0.9rem' }}>Scan it with AI to view medicine list, dosage instructions, and order directly online.</p>
              </div>
              <button onClick={() => setIsPrescriptionModalOpen(true)} className="btn-gold" style={{ padding: '12px 20px', fontSize: '0.9rem' }}>
                <Upload size={16} style={{ marginRight: '6px' }} /> Scan Prescription
              </button>
            </div>
          </section>

          {/* Prescriptions & Ordering Quick Action */}
          <section className="glass-card" style={{ padding: '24px', borderRadius: '16px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1.1rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Pill size={18} style={{ color: '#06B6D4' }} /> Online Pharmacy & Medicines
            </h3>
            <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginBottom: '16px' }}>
              Order authentic classical formulations, Rasayanas, and wellness supplements directly from verified suppliers.
            </p>
            <a href="/order-medicines" className="btn-primary" style={{ display: 'inline-flex', padding: '10px 20px', fontSize: '0.9rem' }}>
              <ShoppingBag size={16} style={{ marginRight: '6px' }} /> Open Medicine Store
            </a>
          </section>
        </main>
      </div>

      {/* Prescription Reader Modal */}
      <PrescriptionReaderModal
        isOpen={isPrescriptionModalOpen}
        onClose={() => setIsPrescriptionModalOpen(false)}
        onAddMedicinesToCart={handlePrescriptionExtracted}
      />
    </div>
  );
}
