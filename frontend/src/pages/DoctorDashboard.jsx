import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Users, Calendar, Pill, FileText, Bot, Mic, UserPlus, Stethoscope, 
  BarChart2, Wrench, Zap, Clock, Upload, RefreshCw, Activity, 
  Search, ShieldAlert, Sparkles, CheckCircle2, LogOut, Filter, 
  ChevronRight, ShoppingCart, MessageSquare, ExternalLink, Info,
  ArrowLeft, User
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import VoiceMicInput from '../components/VoiceMicInput';
import PrescriptionReaderModal from '../components/PrescriptionReaderModal';
import DosageTimingBadge from '../components/DosageTimingBadge';

export default function DoctorDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('overview');
  const [isPrescriptionModalOpen, setIsPrescriptionModalOpen] = useState(false);
  const [dictatedNotes, setDictatedNotes] = useState('');
  const [loading, setLoading] = useState(true);

  // Clinical data states
  const [prescriptions, setPrescriptions] = useState([]);
  const [caseSheets, setCaseSheets] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [selectedPatientFilter, setSelectedPatientFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRxId, setExpandedRxId] = useState(null);

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
      }
    } catch (err) {
      console.error('Error fetching doctor dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPrescriptions = async () => {
    try {
      const res = await fetch('/api/prescriptions');
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.prescriptions) {
          setPrescriptions(data.prescriptions);
        }
      }
    } catch (err) {
      console.error('Error fetching prescriptions:', err);
    }
  };

  const fetchCaseSheets = async () => {
    try {
      const res = await fetch('/api/case-sheets');
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.case_sheets) {
          setCaseSheets(data.case_sheets);
        }
      }
    } catch (err) {
      console.error('Error fetching case sheets:', err);
    }
  };

  const fetchPatients = async () => {
    try {
      const res = await fetch('/api/patients/list');
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.patients) {
          setPatients(data.patients);
        }
      }
    } catch (err) {
      console.error('Error fetching patients:', err);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    fetchPrescriptions();
    fetchCaseSheets();
    fetchPatients();
  }, []);

  const handleVoiceTranscript = (text) => {
    setDictatedNotes(prev => (prev ? `${prev} ${text}` : text));
  };

  const handlePrescriptionSaved = () => {
    fetchPrescriptions();
    fetchCaseSheets();
    fetchDashboardData();
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const sidebarMenuItems = [
    { id: 'overview', label: 'Clinical Overview', icon: Activity },
    { id: 'queue', label: 'Patient Queue', icon: Clock, badge: dashboardData.appointment_queue.length || 0 },
    { id: 'prescriptions', label: 'Prescriptions & Cases', icon: Pill, badge: prescriptions.length || dashboardData.stats.total_prescriptions || 0 },
    { id: 'scribe', label: 'AI Voice Scribe', icon: Mic },
    { id: 'ocr', label: 'Prescription OCR', icon: Upload },
  ];

  const stats = [
    { label: "Total Patients", value: patients.length || dashboardData.stats.total_patients || "12", icon: Users, color: "#10B981" },
    { label: "Today's Appointments", value: dashboardData.stats.today_appointments || "5", icon: Calendar, color: "#06B6D4" },
    { label: "Active Prescriptions", value: prescriptions.length || dashboardData.stats.total_prescriptions || "18", icon: Pill, color: "#6366F1" },
    { label: "Clinical Case Sheets", value: caseSheets.length || dashboardData.stats.total_cases || "14", icon: FileText, color: "#F59E0B" },
  ];

  const quickActions = [
    { id: 'voice', label: "Voice Consultation", path: "/consultation/voice", icon: Mic },
    { id: 'add_patient', label: "Add Patient", path: "/new/patients/add", icon: UserPlus },
    { id: 'prescriptions', label: "Case Sheets Archive", action: () => setActiveTab('prescriptions'), icon: FileText },
    { id: 'ocr', label: "AI Prescription OCR", action: () => setIsPrescriptionModalOpen(true), path: "/ocr-decoder", icon: Upload },
    { id: 'order_meds', label: "Pharmacy Store", path: "/order-medicines", icon: ShoppingCart },
    { id: 'device', label: "Device Diagnostics", path: "/device-check", icon: Wrench },
  ];

  // Filtered prescriptions list
  const filteredPrescriptions = prescriptions.filter(rx => {
    const matchesPatient = selectedPatientFilter === 'all' || String(rx.patient_id) === String(selectedPatientFilter);
    const matchesSearch = !searchQuery.trim() || 
      rx.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rx.diagnosis.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (rx.medicines && rx.medicines.some(m => (m.medicine_name || m.name || '').toLowerCase().includes(searchQuery.toLowerCase())));
    return matchesPatient && matchesSearch;
  });

  return (
    <div style={{ minHeight: 'calc(100vh - 68px)', display: 'flex', width: '100%', position: 'relative' }}>
      
      {/* ======================================================== */}
      {/* LEFT FULL-HEIGHT STATIC SIDEBAR (Flush on screen left)   */}
      {/* ======================================================== */}
      <aside 
        style={{ 
          width: '270px', 
          position: 'fixed', 
          top: '68px', 
          left: 0, 
          bottom: 0, 
          height: 'calc(100vh - 68px)', 
          display: 'flex', 
          flexDirection: 'column', 
          justifyContent: 'space-between',
          borderRight: '1px solid rgba(16, 185, 129, 0.22)',
          boxShadow: '4px 0 24px rgba(0, 0, 0, 0.45)',
          background: 'rgba(9, 18, 14, 0.98)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          padding: '24px 16px',
          boxSizing: 'border-box',
          zIndex: 100,
          overflowY: 'auto'
        }}
      >
        {/* Top: Menu Items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ color: '#94A3B8', fontSize: '0.74rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.12em', padding: '0 12px 12px' }}>
            Doctor Clinical Portal
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
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between',
                    padding: '12px 14px', 
                    borderRadius: '12px', 
                    border: 'none',
                    background: isSelected ? 'rgba(16, 185, 129, 0.16)' : 'transparent',
                    color: isSelected ? '#10B981' : '#94A3B8',
                    borderLeft: isSelected ? '3px solid #10B981' : '3px solid transparent',
                    fontWeight: isSelected ? '700' : '600', 
                    fontSize: '0.9rem', 
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    textAlign: 'left'
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <IconComp size={18} style={{ color: isSelected ? '#10B981' : '#94A3B8' }} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span style={{ 
                      fontSize: '0.72rem', 
                      padding: '2px 8px', 
                      borderRadius: '999px', 
                      background: isSelected ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255, 255, 255, 0.08)', 
                      color: isSelected ? '#10B981' : '#F8FAFC',
                      fontWeight: '700'
                    }}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Bottom: User Profile Card & Sign Out Button */}
          <div style={{
            marginTop: 'auto',
            paddingTop: '18px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            {/* Doctor Profile Info */}
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '12px', 
              padding: '10px 12px',
              borderRadius: '14px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.06)'
            }}>
              <div style={{
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #10B981, #059669)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFFFFF',
                fontWeight: '800',
                fontSize: '0.95rem',
                position: 'relative',
                flexShrink: 0
              }}>
                {(user?.name || 'Dr. Ananya').split(' ').map(n => n[0]).slice(0, 2).join('')}
                <span style={{
                  position: 'absolute',
                  bottom: '1px',
                  right: '1px',
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background: '#10B981',
                  border: '2px solid #0B1512'
                }} title="Online" />
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ 
                  fontSize: '0.88rem', 
                  fontWeight: '700', 
                  color: '#F8FAFC', 
                  whiteSpace: 'nowrap', 
                  overflow: 'hidden', 
                  textOverflow: 'ellipsis' 
                }}>
                  {user?.name || 'Dr. Ananya Sharma'}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#10B981', fontWeight: '600' }}>
                  Ayurvedic Physician
                </div>
              </div>
            </div>

            {/* Logout Button */}
            <button
              onClick={handleLogout}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                padding: '11px',
                borderRadius: '12px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                color: '#F87171',
                fontSize: '0.85rem',
                fontWeight: '700',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.4)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.25)';
              }}
            >
              <LogOut size={16} /> Sign Out
            </button>
          </div>
        </aside>

        {/* ======================================================== */}
        {/* MAIN WORKSPACE AREA (Scrolls smoothly beside fixed bar)  */}
        {/* ======================================================== */}
        <div style={{ 
          marginLeft: '270px', 
          width: 'calc(100% - 270px)', 
          minHeight: 'calc(100vh - 68px)',
          padding: '24px 32px 64px',
          boxSizing: 'border-box'
        }}>
          {/* Top Banner */}
          <div style={{ 
            marginBottom: '24px', 
            padding: '14px 24px', 
            borderRadius: '16px', 
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(6, 182, 212, 0.12))', 
            border: '1px solid rgba(16, 185, 129, 0.3)', 
            color: '#10B981', 
            fontWeight: '700', 
            fontSize: '0.9rem', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            flexWrap: 'wrap', 
            gap: '12px' 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={18} /> Doctor Clinical Suite — Real-Time EMR, Vision OCR & AI Copilot Grounding
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button onClick={() => { fetchDashboardData(); fetchPrescriptions(); fetchCaseSheets(); }} style={{ background: 'none', border: 'none', color: '#10B981', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <RefreshCw size={14} className={loading ? 'spin' : ''} /> {loading ? 'Syncing...' : 'Live Refresh'}
              </button>
              <button onClick={() => setIsPrescriptionModalOpen(true)} className="btn-gold" style={{ padding: '7px 14px', fontSize: '0.84rem' }}>
                <Upload size={14} style={{ marginRight: '6px' }} /> Quick Prescription OCR
              </button>
            </div>
          </div>

          <main style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

          {/* TAB 1: OVERVIEW */}
          {(activeTab === 'overview' || activeTab === 'scribe') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              
              {/* Metric Cards Grid */}
              <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                {stats.map((stat, idx) => {
                  const IconComponent = stat.icon;
                  return (
                    <div key={idx} className="glass-card" style={{ padding: '20px', borderRadius: '16px' }}>
                      <div style={{ width: '42px', height: '42px', borderRadius: '12px', background: `${stat.color}18`, color: stat.color, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
                        <IconComponent size={22} />
                      </div>
                      <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#F8FAFC' }}>{stat.value}</div>
                      <div style={{ fontSize: '0.84rem', fontWeight: '600', color: '#94A3B8', marginTop: '4px' }}>{stat.label}</div>
                    </div>
                  );
                })}
              </section>

              {/* Voice Dictation Workspace */}
              <section className="glass-card" style={{ padding: '22px', borderRadius: '18px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <VoiceMicInput onTranscript={handleVoiceTranscript} />
                    <div>
                      <h4 style={{ margin: 0, fontSize: '0.98rem', color: '#10B981', fontWeight: '700' }}>Clinical Hands-Free Voice Dictation</h4>
                      <span style={{ fontSize: '0.8rem', color: '#94A3B8' }}>Click microphone to dictate symptoms or clinical notes using Groq Speech AI</span>
                    </div>
                  </div>
                  {dictatedNotes && (
                    <button onClick={() => setDictatedNotes('')} style={{ background: 'none', border: 'none', color: '#EF4444', fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer' }}>
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
                    padding: '14px',
                    borderRadius: '12px',
                    background: 'rgba(0, 0, 0, 0.28)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#F8FAFC',
                    fontSize: '0.9rem',
                    outline: 'none',
                    resize: 'vertical'
                  }}
                />
              </section>

              {/* Quick Actions Grid */}
              <section className="glass-card" style={{ padding: '24px', borderRadius: '18px' }}>
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
                            navigate(action.path);
                          }
                        }}
                        className="btn-secondary"
                        style={{
                          padding: '12px 16px',
                          justifyContent: 'flex-start',
                          borderRadius: '12px',
                          fontSize: '0.88rem',
                          cursor: 'pointer',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          background: 'rgba(255, 255, 255, 0.03)',
                          color: '#F8FAFC',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        <IconComp size={16} style={{ color: '#10B981' }} /> {action.label}
                      </button>
                    );
                  })}
                </div>
              </section>

              {/* Today's Queue Preview */}
              <section className="glass-card" style={{ padding: '24px', borderRadius: '18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Clock size={18} style={{ color: '#06B6D4' }} /> Today's Patient Queue
                  </h3>
                  <button onClick={() => setActiveTab('queue')} style={{ background: 'none', border: 'none', color: '#06B6D4', fontSize: '0.82rem', fontWeight: '700', cursor: 'pointer' }}>
                    View Detailed Queue →
                  </button>
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

          {/* TAB 2: DETAILED PATIENT QUEUE */}
          {activeTab === 'queue' && (
            <div className="glass-card" style={{ padding: '28px', borderRadius: '20px' }}>
              <h2 style={{ fontSize: '1.3rem', fontWeight: '800', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Clock size={22} color="#06B6D4" /> Detailed Patient Appointment Queue
              </h2>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8' }}>
                      <th style={{ padding: '12px' }}>Appt ID</th>
                      <th style={{ padding: '12px' }}>Time</th>
                      <th style={{ padding: '12px' }}>Patient Name</th>
                      <th style={{ padding: '12px' }}>Assessment / Prakriti</th>
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

          {/* ======================================================== */}
          {/* ======================================================== */}
          {/* TAB 3: PRESCRIPTIONS & CLINICAL CASE SHEETS ARCHIVE */}
          {/* ======================================================== */}
          {activeTab === 'prescriptions' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {!selectedPatient ? (
                /* ======================================================== */
                /* VIEW 1: PATIENTS LIST DIRECTORY (Default Starting View)  */
                /* ======================================================== */
                <>
                  <div className="glass-card" style={{ padding: '24px', borderRadius: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
                      <div>
                        <h2 style={{ fontSize: '1.4rem', fontWeight: '800', margin: '0 0 4px', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <Users size={24} color="#10B981" /> Patients Directory
                        </h2>
                        <span style={{ fontSize: '0.86rem', color: '#94A3B8' }}>
                          Select a patient below to open their clinical prescriptions, case sheets, and medication history.
                        </span>
                      </div>
                      <button 
                        onClick={() => setIsPrescriptionModalOpen(true)}
                        className="btn-gold"
                        style={{ padding: '10px 20px', fontSize: '0.9rem', fontWeight: '700' }}
                      >
                        <Upload size={16} style={{ marginRight: '6px' }} /> Upload New Prescription
                      </button>
                    </div>

                    {/* Search Bar for Patients */}
                    <div style={{ position: 'relative' }}>
                      <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
                      <input
                        type="text"
                        placeholder="Search patients by name, prakriti, or phone..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '12px 14px 12px 42px',
                          borderRadius: '12px',
                          background: 'rgba(0, 0, 0, 0.25)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          color: '#F8FAFC',
                          fontSize: '0.9rem',
                          outline: 'none'
                        }}
                      />
                    </div>
                  </div>

                  {/* Grid of Patient Cards */}
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', 
                    gap: '18px' 
                  }}>
                    {patients
                      .filter(p => {
                        if (!searchQuery.trim()) return true;
                        const q = searchQuery.toLowerCase();
                        return (
                          (p.name && p.name.toLowerCase().includes(q)) ||
                          (p.prakriti && p.prakriti.toLowerCase().includes(q)) ||
                          (p.phone && p.phone.includes(q))
                        );
                      })
                      .map((p) => {
                        const pRxCount = prescriptions.filter(rx => 
                          String(rx.patient_id) === String(p.id) || 
                          (rx.patient_name && rx.patient_name.toLowerCase() === p.name.toLowerCase())
                        ).length || p.prescriptions_count || 0;

                        return (
                          <div 
                            key={p.id}
                            onClick={() => setSelectedPatient(p)}
                            className="glass-card"
                            style={{
                              padding: '22px',
                              borderRadius: '18px',
                              border: '1px solid rgba(16, 185, 129, 0.22)',
                              background: 'rgba(15, 29, 23, 0.85)',
                              cursor: 'pointer',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              gap: '16px',
                              transition: 'all 0.2s ease',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.transform = 'translateY(-2px)';
                              e.currentTarget.style.borderColor = 'rgba(16, 185, 129, 0.55)';
                              e.currentTarget.style.boxShadow = '0 8px 24px rgba(16, 185, 129, 0.15)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.transform = 'translateY(0)';
                              e.currentTarget.style.borderColor = 'rgba(16, 185, 129, 0.22)';
                              e.currentTarget.style.boxShadow = 'none';
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
                              <div style={{
                                width: '46px',
                                height: '46px',
                                borderRadius: '14px',
                                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25), rgba(6, 182, 212, 0.2))',
                                border: '1px solid rgba(16, 185, 129, 0.35)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0
                              }}>
                                <User size={22} color="#10B981" />
                              </div>

                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ 
                                  fontSize: '1.15rem', 
                                  fontWeight: '800', 
                                  color: '#F8FAFC', 
                                  whiteSpace: 'nowrap', 
                                  overflow: 'hidden', 
                                  textOverflow: 'ellipsis' 
                                }}>
                                  {p.name}
                                </div>
                                <div style={{ fontSize: '0.82rem', color: '#94A3B8', marginTop: '2px' }}>
                                  {p.age ? `${p.age}y` : 'Adult'} • {p.gender || 'Patient'}
                                </div>
                              </div>

                              <span style={{ 
                                padding: '2px 9px', 
                                borderRadius: '16px', 
                                background: 'rgba(232, 178, 74, 0.15)', 
                                color: '#E8B24A', 
                                fontSize: '0.74rem', 
                                fontWeight: '700',
                                whiteSpace: 'nowrap'
                              }}>
                                {p.prakriti || 'Vata-Pitta'}
                              </span>
                            </div>

                            {/* Patient Stats & Click Prompt */}
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              paddingTop: '12px',
                              borderTop: '1px solid rgba(255, 255, 255, 0.06)'
                            }}>
                              <span style={{
                                padding: '3px 9px',
                                borderRadius: '8px',
                                background: pRxCount > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                                color: pRxCount > 0 ? '#10B981' : '#94A3B8',
                                fontSize: '0.78rem',
                                fontWeight: '700'
                              }}>
                                📋 {pRxCount} {pRxCount === 1 ? 'Prescription' : 'Prescriptions'}
                              </span>

                              <span style={{ 
                                fontSize: '0.82rem', 
                                color: '#10B981', 
                                fontWeight: '700',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px'
                              }}>
                                View Details →
                              </span>
                            </div>
                          </div>
                        );
                      })}
                  </div>

                  {patients.length === 0 && (
                    <div className="glass-card" style={{ padding: '40px', textAlign: 'center', borderRadius: '18px' }}>
                      <Users size={40} style={{ color: '#94A3B8', marginBottom: '12px' }} />
                      <h3 style={{ margin: '0 0 6px', color: '#F8FAFC' }}>No patients registered yet</h3>
                      <p style={{ color: '#94A3B8', fontSize: '0.9rem', margin: '0 0 16px' }}>
                        Upload a prescription to automatically register your first patient.
                      </p>
                      <button onClick={() => setIsPrescriptionModalOpen(true)} className="btn-gold" style={{ padding: '10px 20px' }}>
                        <Upload size={16} style={{ marginRight: '6px' }} /> Upload Prescription Now
                      </button>
                    </div>
                  )}
                </>
              ) : (
                /* ======================================================== */
                /* VIEW 2: PATIENT DETAILS VIEW (Shown on Click)            */
                /* ======================================================== */
                <>
                  {/* Top Navigation & Patient Dossier Header */}
                  <div className="glass-card" style={{ padding: '20px 24px', borderRadius: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px', marginBottom: '16px' }}>
                      <button 
                        onClick={() => setSelectedPatient(null)}
                        className="btn-secondary"
                        style={{ padding: '8px 16px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}
                      >
                        <ArrowLeft size={16} /> Back to Patients List
                      </button>

                      {/* Quick Switch Patient Dropdown */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '0.82rem', color: '#94A3B8' }}>Switch Patient:</span>
                        <select
                          value={selectedPatient.id}
                          onChange={(e) => {
                            const found = patients.find(p => String(p.id) === String(e.target.value));
                            if (found) setSelectedPatient(found);
                          }}
                          style={{
                            padding: '8px 12px',
                            borderRadius: '10px',
                            background: '#0B1512',
                            border: '1px solid rgba(16, 185, 129, 0.3)',
                            color: '#F8FAFC',
                            fontSize: '0.85rem',
                            outline: 'none',
                            cursor: 'pointer'
                          }}
                        >
                          {patients.map(p => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </select>

                        <button 
                          onClick={() => setIsPrescriptionModalOpen(true)}
                          className="btn-gold"
                          style={{ padding: '8px 16px', fontSize: '0.84rem', fontWeight: '700' }}
                        >
                          <Upload size={14} style={{ marginRight: '6px' }} /> Upload Rx for Patient
                        </button>
                      </div>
                    </div>

                    {/* Patient Overview Details Banner */}
                    <div style={{
                      padding: '16px 20px',
                      borderRadius: '14px',
                      background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(6, 182, 212, 0.08))',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '14px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                        <div style={{
                          width: '50px',
                          height: '50px',
                          borderRadius: '16px',
                          background: 'rgba(16, 185, 129, 0.25)',
                          border: '1px solid rgba(16, 185, 129, 0.4)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <User size={26} color="#10B981" />
                        </div>
                        <div>
                          <div style={{ fontSize: '1.35rem', fontWeight: '800', color: '#F8FAFC' }}>
                            {selectedPatient.name}
                          </div>
                          <div style={{ fontSize: '0.85rem', color: '#94A3B8', marginTop: '2px' }}>
                            {selectedPatient.age ? `${selectedPatient.age} years` : 'Adult'} • {selectedPatient.gender || 'Patient'} • Phone: {selectedPatient.phone || 'On file'}
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                        <span style={{ 
                          padding: '5px 12px', 
                          borderRadius: '20px', 
                          background: 'rgba(232, 178, 74, 0.18)', 
                          color: '#E8B24A', 
                          fontSize: '0.82rem', 
                          fontWeight: '700' 
                        }}>
                          Prakriti: {selectedPatient.prakriti || 'Vata-Pitta'}
                        </span>
                        <span style={{ 
                          padding: '5px 12px', 
                          borderRadius: '20px', 
                          background: 'rgba(16, 185, 129, 0.18)', 
                          color: '#10B981', 
                          fontSize: '0.82rem', 
                          fontWeight: '700' 
                        }}>
                          {prescriptions.filter(rx => 
                            String(rx.patient_id) === String(selectedPatient.id) || 
                            (rx.patient_name && rx.patient_name.toLowerCase() === selectedPatient.name.toLowerCase())
                          ).length} Prescriptions Recorded
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Prescriptions for this Patient */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {(() => {
                      const patientRxs = prescriptions.filter(rx => 
                        String(rx.patient_id) === String(selectedPatient.id) || 
                        (rx.patient_name && rx.patient_name.toLowerCase() === selectedPatient.name.toLowerCase())
                      );

                      if (patientRxs.length === 0) {
                        return (
                          <div className="glass-card" style={{ padding: '40px', textAlign: 'center', borderRadius: '18px' }}>
                            <Pill size={40} style={{ color: '#94A3B8', marginBottom: '12px' }} />
                            <h3 style={{ margin: '0 0 6px', color: '#F8FAFC' }}>No prescriptions recorded for {selectedPatient.name}</h3>
                            <p style={{ color: '#94A3B8', fontSize: '0.9rem', margin: '0 0 16px' }}>
                              Upload a handwritten prescription via OCR to save medications and generate a case sheet for this patient.
                            </p>
                            <button onClick={() => setIsPrescriptionModalOpen(true)} className="btn-gold" style={{ padding: '10px 20px' }}>
                              <Upload size={16} style={{ marginRight: '6px' }} /> Upload Prescription Now
                            </button>
                          </div>
                        );
                      }

                      return patientRxs.map((rx) => {
                        const meds = rx.medicines || [];

                        return (
                          <div 
                            key={rx.id} 
                            className="glass-card" 
                            style={{ 
                              padding: '24px', 
                              borderRadius: '18px', 
                              border: '1px solid rgba(16, 185, 129, 0.2)',
                              background: 'rgba(15, 29, 23, 0.85)'
                            }}
                          >
                            {/* Prescription Header */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
                              <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                  <span style={{ fontSize: '1.2rem', fontWeight: '800', color: '#F8FAFC' }}>
                                    Prescription #{rx.id}
                                  </span>
                                  <span style={{ fontSize: '0.82rem', color: '#94A3B8' }}>
                                    Recorded on {rx.date_str || 'Recent'}
                                  </span>
                                </div>
                                <p style={{ margin: '6px 0 0', color: '#10B981', fontWeight: '700', fontSize: '0.95rem' }}>
                                  Diagnosis: {rx.diagnosis}
                                </p>
                              </div>

                              <div>
                                <span style={{ 
                                  padding: '4px 12px', 
                                  borderRadius: '12px', 
                                  background: 'rgba(16, 185, 129, 0.15)', 
                                  color: '#10B981', 
                                  fontSize: '0.8rem', 
                                  fontWeight: '700' 
                                }}>
                                  {rx.medicine_count} Medicines Prescribed
                                </span>
                              </div>
                            </div>

                            {/* Medicines Breakdown Table with 1-0-1 badges */}
                            <div style={{ overflowX: 'auto', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '12px', padding: '12px', marginBottom: '16px' }}>
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', color: '#94A3B8', textAlign: 'left' }}>
                                    <th style={{ padding: '8px 12px' }}>Medicine Name</th>
                                    <th style={{ padding: '8px 12px' }}>Dosage</th>
                                    <th style={{ padding: '8px 12px' }}>Frequency & Daily Timing</th>
                                    <th style={{ padding: '8px 12px' }}>Duration</th>
                                    <th style={{ padding: '8px 12px' }}>Instructions</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {meds.map((m, mIdx) => (
                                    <tr key={mIdx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                      <td style={{ padding: '10px 12px', fontWeight: '700', color: '#F8FAFC' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <Pill size={14} color="#10B981" />
                                          {m.medicine_name || m.name || 'Ayurvedic Formulation'}
                                        </div>
                                      </td>
                                      <td style={{ padding: '10px 12px', color: '#CBD5E1' }}>{m.dosage || '1 unit'}</td>
                                      <td style={{ padding: '10px 12px' }}>
                                        <DosageTimingBadge frequency={m.frequency || '1-0-1'} />
                                      </td>
                                      <td style={{ padding: '10px 12px', color: '#CBD5E1' }}>
                                        {m.duration ? (/^\d+$/.test(String(m.duration).trim()) ? `${m.duration} days` : m.duration) : '7 days'}
                                      </td>
                                      <td style={{ padding: '10px 12px', color: '#94A3B8' }}>{m.instructions || 'With warm water'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>

                            {/* Clinical Advice */}
                            {rx.advice && (
                              <div style={{ fontSize: '0.85rem', color: '#94A3B8', marginBottom: '16px', background: 'rgba(255, 255, 255, 0.02)', padding: '10px 14px', borderRadius: '10px' }}>
                                <strong style={{ color: '#E8B24A' }}>Clinical Advice: </strong> {rx.advice}
                              </div>
                            )}

                            {/* Bottom Actions */}
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                              <button
                                onClick={() => navigate('/order-medicines')}
                                className="btn-gold"
                                style={{ padding: '8px 16px', fontSize: '0.82rem' }}
                              >
                                <ShoppingCart size={14} style={{ marginRight: '6px' }} /> Order for Patient
                              </button>
                              <a
                                href="/consultation/voice"
                                className="btn-primary"
                                style={{ padding: '8px 16px', fontSize: '0.82rem', textDecoration: 'none' }}
                              >
                                <Mic size={14} style={{ marginRight: '6px' }} /> Voice Consultation
                              </a>
                            </div>
                          </div>
                        );
                      });
                    })()}
                  </div>
                </>
              )}
            </div>
          )}

        </main>
      </div>

      {/* Prescription Reader Modal with Save to Case Sheet Support */}
      <PrescriptionReaderModal
        isOpen={isPrescriptionModalOpen}
        onClose={() => setIsPrescriptionModalOpen(false)}
        onAddMedicinesToCart={handleVoiceTranscript}
        onPrescriptionSaved={handlePrescriptionSaved}
      />
    </div>
  );
}
