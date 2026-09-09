import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { HeartPulse, Bot, Pill, Activity, Calendar, Heart, FileText, Wrench, ShoppingBag, Upload, RefreshCw } from 'lucide-react';
import VoiceMicInput from '../components/VoiceMicInput';
import PrescriptionReaderModal from '../components/PrescriptionReaderModal';

export default function PatientDashboard() {
  const [isPrescriptionModalOpen, setIsPrescriptionModalOpen] = useState(false);
  const [voiceQuery, setVoiceQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [patientData, setPatientData] = useState({
    patient_name: 'Patient User',
    stats: { wellness_score: 90, active_consultations: 0, verified_prescriptions: 0, medicine_orders_count: 0 },
    prescriptions: [],
    appointments: [],
    orders: []
  });

  const fetchPatientData = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/dashboard/patient');
      const data = await res.json();
      if (res.ok && data.success) {
        setPatientData(data);
      }
    } catch (err) {
      console.error('Error fetching patient dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPatientData();
  }, []);

  const handleVoiceTranscript = (text) => {
    setVoiceQuery(text);
    window.location.href = `/order-medicines?q=${encodeURIComponent(text)}`;
  };

  const handlePrescriptionExtracted = (medicines) => {
    window.location.href = '/order-medicines';
  };

  return (
    <div style={{ maxWidth: '1250px', margin: '0 auto', padding: '24px' }}>
      {/* Top Banner */}
      <section className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '24px 28px', borderRadius: '16px', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <p style={{ color: '#10B981', fontWeight: '700', fontSize: '0.85rem', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <HeartPulse size={16} /> Kash AI Patient Health Portal
          </p>
          <h1 style={{ fontSize: '2rem', fontWeight: '800', margin: '0 0 4px', color: '#F8FAFC' }}>
            Welcome, {patientData.patient_name}
          </h1>
          <p style={{ color: '#94A3B8', margin: 0, fontSize: '0.9rem' }}>Personalized Ayurvedic Health Records & Voice AI Assistant</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={fetchPatientData} className="btn-ghost" style={{ padding: '10px 14px' }}>
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
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

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '24px' }}>
        {/* Sidebar Navigation */}
        <aside className="glass-card" style={{ padding: '20px', height: 'fit-content', borderRadius: '16px' }}>
          <p style={{ color: '#94A3B8', fontSize: '0.78rem', fontWeight: '700', textTransform: 'uppercase', margin: '0 0 12px' }}>Patient Portal</p>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Link to="/patient" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', fontWeight: '600', textDecoration: 'none' }}>
              <Activity size={18} /> My Health Overview
            </Link>
            <Link to="/ocr-decoder" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Upload size={18} /> AI Prescription OCR
            </Link>
            <a href="/appointments" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Calendar size={18} /> Appointments
            </a>
            <Link to="/order-medicines" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Pill size={18} /> Order Medicines
            </Link>
            <Link to="/device-check" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 14px', borderRadius: '10px', color: '#E2E8F0', textDecoration: 'none' }}>
              <Wrench size={18} /> Diagnostics Check
            </Link>
          </nav>
        </aside>

        {/* Main Content */}
        <main style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Stat Cards Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div className="glass-card" style={{ padding: '20px', borderRadius: '14px' }}>
              <div style={{ color: '#10B981', marginBottom: '8px' }}><Heart size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>{patientData.stats.wellness_score}%</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Ayurvedic Wellness Score</div>
            </div>

            <div className="glass-card" style={{ padding: '20px', borderRadius: '14px' }}>
              <div style={{ color: '#06B6D4', marginBottom: '8px' }}><Calendar size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>{patientData.stats.active_consultations}</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Active Consultations</div>
            </div>

            <div className="glass-card" style={{ padding: '20px', borderRadius: '14px' }}>
              <div style={{ color: '#6366F1', marginBottom: '8px' }}><FileText size={24} /></div>
              <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>{patientData.stats.verified_prescriptions}</div>
              <div style={{ color: '#94A3B8', fontSize: '0.85rem', fontWeight: '600' }}>Verified Prescriptions</div>
            </div>
          </div>

          {/* Quick Actions & AI Reader Card */}
          <section className="glass-card" style={{ padding: '24px', borderRadius: '16px', background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(232, 178, 74, 0.08))' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div>
                <h3 style={{ margin: '0 0 6px', fontSize: '1.15rem', color: '#F8FAFC' }}>Have a paper prescription?</h3>
                <p style={{ margin: 0, color: '#94A3B8', fontSize: '0.88rem' }}>Decode doctor's handwriting using AI and order medicines directly online.</p>
              </div>
              <button onClick={() => setIsPrescriptionModalOpen(true)} className="btn-gold" style={{ padding: '10px 20px', fontSize: '0.88rem' }}>
                <Upload size={16} style={{ marginRight: '6px' }} /> Scan Prescription
              </button>
            </div>
          </section>

          {/* Real Prescriptions List */}
          <section className="glass-card" style={{ padding: '24px', borderRadius: '16px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1.1rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px', color: '#F8FAFC' }}>
              <FileText size={18} style={{ color: '#10B981' }} /> My Prescriptions & EMR Notes
            </h3>
            {patientData.prescriptions.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {patientData.prescriptions.map((rx, idx) => (
                  <div key={idx} style={{ padding: '14px', borderRadius: '12px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <strong style={{ color: '#F8FAFC' }}>{rx.diagnosis}</strong>
                      <span style={{ fontSize: '0.8rem', color: '#94A3B8' }}>{rx.date}</span>
                    </div>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#CBD5E1' }}>{rx.advice}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: '#94A3B8', fontSize: '0.88rem', margin: 0 }}>
                No active prescription records found. Upload a prescription or consult a doctor.
              </p>
            )}
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
