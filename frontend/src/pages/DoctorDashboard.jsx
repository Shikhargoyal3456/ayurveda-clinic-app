import React, { useState, useEffect } from 'react';
import { 
  Users, Calendar, Pill, FileText, Bot, Mic, UserPlus, Stethoscope, 
  BarChart2, Wrench, Zap, Clock, Upload, RefreshCw, Activity, 
  Search, ShieldAlert, Sparkles, CheckCircle2
} from 'lucide-react';
import VoiceMicInput from '../components/VoiceMicInput';
import PrescriptionReaderModal from '../components/PrescriptionReaderModal';

export default function DoctorDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isPrescriptionModalOpen, setIsPrescriptionModalOpen] = useState(false);
  const [dictatedNotes, setDictatedNotes] = useState('');
  const [loading, setLoading] = useState(true);
  const defaultInitialData = {
    stats: { total_patients: 12, today_appointments: 5, total_prescriptions: 18, total_cases: 14, available_medicines: 24 },
    appointment_queue: [
      { id: 1, time: '09:30 AM', patient_name: 'Aarav Sharma', prakriti: 'Vata-Pitta Imbalance', status: 'Active' },
      { id: 2, time: '10:15 AM', patient_name: 'Priya Patel', prakriti: 'Kapha Prakriti (Asthma)', status: 'Scheduled' },
      { id: 3, time: '11:00 AM', patient_name: 'Rajesh Verma', prakriti: 'Pitta-Vata (Joint Pain)', status: 'Scheduled' },
    ],
    recent_cases: [
      { id: 101, patient_name: 'Aarav Sharma', diagnosis: 'Amavata (Rheumatoid Arthritis)', symptoms: 'Joint stiffness, morning fatigue', date: '2026-09-08' },
      { id: 102, patient_name: 'Priya Patel', diagnosis: 'Svasa Roga (Chronic Bronchitis)', symptoms: 'Wheezing, breathlessness', date: '2026-09-07' }
    ]
  };

  const [dashboardData, setDashboardData] = useState(defaultInitialData);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/dashboard/doctor');
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.stats) {
          setDashboardData(data);
        }
      } else {
        console.warn('Endpoint /api/dashboard/doctor responded with status:', res.status);
      }
    } catch (err) {
      console.error('Error fetching doctor dashboard:', err);
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleVoiceTranscript = (text) => {
    setDictatedNotes(prev => (prev ? `${prev} ${text}` : text));
  };

  const handlePrescriptionRead = (medicines) => {
    const names = medicines.map(m => m.medicine_name).join(', ');
    setDictatedNotes(prev => (prev ? `${prev} [Parsed RX: ${names}]` : `Parsed Prescription Medicines: ${names}`));
  };

  const sidebarMenuItems = [
    { id: 'overview', label: 'Clinical Overview', icon: Activity },
    { id: 'queue', label: 'Patient Queue', icon: Clock, badge: dashboardData.appointment_queue.length || 0 },
    { id: 'cases', label: 'Case Sheets', icon: FileText, badge: dashboardData.recent_cases.length || 0 },
    { id: 'scribe', label: 'AI Voice Scribe', icon: Mic },
    { id: 'ocr', label: 'Prescription OCR', icon: Upload },
  ];

  const stats = [
    { label: "Total Patients", value: dashboardData.stats.total_patients || "0", icon: Users, color: "#10B981" },
    { label: "Today's Appointments", value: dashboardData.stats.today_appointments || "0", icon: Calendar, color: "#06B6D4" },
    { label: "Active Prescriptions", value: dashboardData.stats.total_prescriptions || "0", icon: Pill, color: "#6366F1" },
    { label: "Clinical Case Sheets", value: dashboardData.stats.total_cases || "0", icon: FileText, color: "#F59E0B" },
  ];

  const quickActions = [
    { id: 'voice', label: "Voice Consultation", path: "/consultation/voice", icon: Mic },
    { id: 'add_patient', label: "Add Patient", path: "/new/patients/add", icon: UserPlus },
    { id: 'appt', label: "Schedule Appointment", path: "/appointments", icon: Calendar },
    { id: 'ai_doctor', label: "AI Doctor Chat", path: "/new/ai-doctor", icon: Stethoscope },
    { id: 'ocr', label: "AI Prescription OCR", action: () => setIsPrescriptionModalOpen(true), path: "/ocr-decoder", icon: Upload },
    { id: 'device', label: "Device Diagnostics", path: "/device-check", icon: Wrench },
  ];


  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px 16px', minHeight: '85vh' }}>
      
      {/* Top Banner */}
      <div style={{ marginBottom: '20px', padding: '12px 24px', borderRadius: '14px', background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(6, 182, 212, 0.2))', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#10B981', fontWeight: '700', fontSize: '0.9rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={18} /> Doctor Portal — Real-Time Clinical Queue & Groq Speech Dictation
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button onClick={fetchDashboardData} style={{ background: 'none', border: 'none', color: '#10B981', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> {loading ? 'Syncing...' : 'Live Refresh'}
          </button>
          <button onClick={() => setIsPrescriptionModalOpen(true)} className="btn-gold" style={{ padding: '6px 12px', fontSize: '0.82rem' }}>
            <Upload size={14} style={{ marginRight: '4px' }} /> Quick OCR
          </button>
        </div>
      </div>

      {/* Main Grid: Left Sidebar Navigation + Workspace */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '24px' }}>
        
        {/* LEFT SIDEBAR NAVIGATION */}
        <aside className="glass-card" style={{ padding: '20px 14px', height: 'fit-content', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ color: '#94A3B8', fontSize: '0.78rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.1em', padding: '0 10px 8px' }}>
            Doctor Console
          </div>

          {sidebarMenuItems.map((item) => {
            const IconComp = item.icon;
            const isSelected = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.id === 'ocr') {
                    setIsPrescriptionModalOpen(true);
                  } else {
                    setActiveTab(item.id);
                  }
                }}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 14px', borderRadius: '12px', border: 'none',
                  background: isSelected ? 'rgba(16, 185, 129, 0.16)' : 'transparent',
                  color: isSelected ? '#10B981' : '#94A3B8',
                  borderLeft: isSelected ? '3px solid #10B981' : '3px solid transparent',
                  fontWeight: isSelected ? '700' : '600', fontSize: '0.92rem', cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <IconComp size={18} /> {item.label}
                </div>
                {item.badge !== undefined && (
                  <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '999px', background: 'rgba(255, 255, 255, 0.08)', color: '#F8FAFC' }}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </aside>

        {/* MAIN WORKSPACE AREA */}
        <main style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

          {/* TAB 1: OVERVIEW */}
          {(activeTab === 'overview' || activeTab === 'scribe') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              
              {/* Metric Cards Grid */}
              <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                {stats.map((stat, idx) => {
                  const IconComponent = stat.icon;
                  return (
                    <div key={idx} className="glass-card" style={{ padding: '20px', borderRadius: '14px' }}>
                      <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: `${stat.color}15`, color: stat.color, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                        <IconComponent size={22} />
                      </div>
                      <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>{stat.value}</div>
                      <div style={{ fontSize: '0.85rem', fontWeight: '600', color: '#94A3B8', marginTop: '4px' }}>{stat.label}</div>
                    </div>
                  );
                })}
              </section>

              {/* Voice Dictation Workspace */}
              <section className="glass-card" style={{ padding: '20px', borderRadius: '16px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <VoiceMicInput onTranscript={handleVoiceTranscript} />
                    <div>
                      <h4 style={{ margin: 0, fontSize: '0.98rem', color: '#10B981', fontWeight: '700' }}>Clinical Hands-Free Voice Dictation</h4>
                      <span style={{ fontSize: '0.8rem', color: '#94A3B8' }}>Click microphone to dictate symptoms or clinical notes using Groq Speech AI</span>
                    </div>
                  </div>
                  {dictatedNotes && (
                    <button onClick={() => setDictatedNotes('')} style={{ background: 'none', border: 'none', color: '#EF4444', fontSize: '0.8rem', cursor: 'pointer' }}>
                      Clear Notes
                    </button>
                  )}
                </div>
                <textarea
                  rows={3}
                  value={dictatedNotes}
                  onChange={(e) => setDictatedNotes(e.target.value)}
                  placeholder="Spoken notes or AI prescription OCR extractions appear here in real-time..."
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '10px',
                    background: 'rgba(0, 0, 0, 0.25)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#F8FAFC',
                    fontSize: '0.9rem',
                    outline: 'none',
                    resize: 'vertical'
                  }}
                />
              </section>

              {/* Quick Actions Grid */}
              <section className="glass-card" style={{ padding: '24px', borderRadius: '16px' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#F8FAFC' }}>
                  <Zap size={18} style={{ color: '#10B981' }} /> Clinical Quick Actions
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '12px' }}>
                  {quickActions.map((action, idx) => {
                    const IconComp = action.icon;
                    return (
                      <button
                        key={idx}
                        onClick={() => {
                          if (action.action) {
                            action.action();
                          } else if (action.path) {
                            window.location.href = action.path;
                          }
                        }}
                        className="btn-secondary"
                        style={{
                          padding: '12px 16px',
                          justify: 'flex-start',
                          borderRadius: '10px',
                          fontSize: '0.88rem',
                          cursor: 'pointer',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          background: 'rgba(255, 255, 255, 0.04)',
                          color: '#F8FAFC',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        <IconComp size={16} style={{ color: '#10B981' }} /> {action.label}
                      </button>
                    );
                  })}

                </div>
              </section>

              {/* Today's Queue */}
              <section className="glass-card" style={{ padding: '24px', borderRadius: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Clock size={18} style={{ color: '#06B6D4' }} /> Today's Patient Queue
                  </h3>
                  <span style={{ fontSize: '0.8rem', color: '#94A3B8' }}>{dashboardData.appointment_queue.length} Scheduled</span>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8' }}>
                        <th style={{ padding: '10px 12px' }}>Time</th>
                        <th style={{ padding: '10px 12px' }}>Patient Name</th>
                        <th style={{ padding: '10px 12px' }}>Prakriti / Assessment</th>
                        <th style={{ padding: '10px 12px' }}>Status</th>
                        <th style={{ padding: '10px 12px' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.appointment_queue.length > 0 ? (
                        dashboardData.appointment_queue.map((item, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                            <td style={{ padding: '12px' }}>{item.time}</td>
                            <td style={{ padding: '12px', fontWeight: '600', color: '#F8FAFC' }}>{item.patient_name}</td>
                            <td style={{ padding: '12px', color: '#94A3B8' }}>{item.prakriti}</td>
                            <td style={{ padding: '12px' }}>
                              <span style={{ padding: '4px 10px', borderRadius: '20px', background: item.status === 'Active' ? 'rgba(16,185,129,0.15)' : 'rgba(6,182,212,0.15)', color: item.status === 'Active' ? '#10B981' : '#06B6D4', fontWeight: '600', fontSize: '0.8rem' }}>
                                {item.status}
                              </span>
                            </td>
                            <td style={{ padding: '12px' }}>
                              <a href="/consultation/voice" className="btn-primary" style={{ padding: '6px 12px', fontSize: '0.78rem', textDecoration: 'none' }}>
                                Consultation
                              </a>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} style={{ padding: '20px', textAlign: 'center', color: '#94A3B8' }}>
                            No active appointments in queue.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}

          {/* TAB 2: PATIENT QUEUE */}
          {activeTab === 'queue' && (
            <div className="glass-card" style={{ padding: '24px' }}>
              <h2 style={{ fontSize: '1.2rem', fontWeight: '700', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Clock size={20} color="#06B6D4" /> Detailed Patient Appointment Queue
              </h2>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8' }}>
                      <th style={{ padding: '12px' }}>Appt ID</th>
                      <th style={{ padding: '12px' }}>Scheduled Time</th>
                      <th style={{ padding: '12px' }}>Patient Name</th>
                      <th style={{ padding: '12px' }}>Clinical Assessment</th>
                      <th style={{ padding: '12px' }}>Status</th>
                      <th style={{ padding: '12px' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboardData.appointment_queue.map((item, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '14px 12px' }}>#{item.id}</td>
                        <td style={{ padding: '14px 12px' }}>{item.time}</td>
                        <td style={{ padding: '14px 12px', fontWeight: '700', color: '#F8FAFC' }}>{item.patient_name}</td>
                        <td style={{ padding: '14px 12px', color: '#94A3B8' }}>{item.prakriti}</td>
                        <td style={{ padding: '14px 12px' }}>
                          <span style={{ padding: '4px 10px', borderRadius: '20px', background: 'rgba(16,185,129,0.15)', color: '#10B981', fontWeight: '600', fontSize: '0.8rem' }}>
                            {item.status}
                          </span>
                        </td>
                        <td style={{ padding: '14px 12px' }}>
                          <a href="/consultation/voice" className="btn-primary" style={{ padding: '6px 14px', fontSize: '0.8rem', textDecoration: 'none' }}>
                            Start EMR
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: CASE SHEETS */}
          {activeTab === 'cases' && (
            <div className="glass-card" style={{ padding: '24px' }}>
              <h2 style={{ fontSize: '1.2rem', fontWeight: '700', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={20} color="#F59E0B" /> Clinical Case Sheets History
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {dashboardData.recent_cases.length > 0 ? (
                  dashboardData.recent_cases.map((c, idx) => (
                    <div key={idx} style={{ padding: '16px', borderRadius: '12px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <strong style={{ color: '#F8FAFC', fontSize: '1rem' }}>{c.patient_name}</strong>
                        <span style={{ fontSize: '0.8rem', color: '#64748B' }}>{c.date}</span>
                      </div>
                      <p style={{ color: '#10B981', fontWeight: '600', margin: '4px 0', fontSize: '0.9rem' }}>Diagnosis: {c.diagnosis}</p>
                      {c.symptoms && <p style={{ color: '#94A3B8', margin: 0, fontSize: '0.85rem' }}>Symptoms: {c.symptoms}</p>}
                    </div>
                  ))
                ) : (
                  <p style={{ color: '#94A3B8', margin: 0 }}>No recent case sheets found in database.</p>
                )}
              </div>
            </div>
          )}

        </main>
      </div>

      {/* Prescription Reader Modal */}
      <PrescriptionReaderModal
        isOpen={isPrescriptionModalOpen}
        onClose={() => setIsPrescriptionModalOpen(false)}
        onAddMedicinesToCart={handlePrescriptionRead}
      />
    </div>
  );
}
