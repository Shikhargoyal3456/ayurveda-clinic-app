import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { 
  Users, Calendar, Pill, FileText, Bot, Mic, UserPlus, Stethoscope, 
  BarChart2, Wrench, Zap, Clock, Upload, RefreshCw, Activity, 
  Search, ShieldAlert, Sparkles, CheckCircle2, LogOut, Filter, 
  ChevronRight, ShoppingCart, MessageSquare, ExternalLink, Info,
  ArrowLeft, User, Trash2, Square, Volume2, X
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import VoiceMicInput from '../components/VoiceMicInput';
import PrescriptionReaderModal from '../components/PrescriptionReaderModal';
import DosageTimingBadge from '../components/DosageTimingBadge';

export default function DoctorDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('overview');
  const [archiveViewMode, setArchiveViewMode] = useState('patients'); // 'patients' | 'cases'
  const [isPrescriptionModalOpen, setIsPrescriptionModalOpen] = useState(false);
  const [isAddPatientModalOpen, setIsAddPatientModalOpen] = useState(false);
  const [newPatientForm, setNewPatientForm] = useState({
    name: '',
    age: 35,
    gender: 'Male',
    phone: '',
    email: '',
    prakriti: 'Vata-Pitta',
    complaints: ''
  });
  const [isSubmittingPatient, setIsSubmittingPatient] = useState(false);
  const [patientModalError, setPatientModalError] = useState('');
  const [modalPatientId, setModalPatientId] = useState(null);
  const [dictatedNotes, setDictatedNotes] = useState('');
  const [isVoiceListening, setIsVoiceListening] = useState(false);
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
    setDictatedNotes(text);
  };

  const handleVoiceStart = () => {
    // When clicking mic again, delete previous notes as requested
    setDictatedNotes('');
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

  const handleCreatePatientSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!newPatientForm.name.trim()) {
      setPatientModalError('Patient name is required.');
      return;
    }
    setIsSubmittingPatient(true);
    setPatientModalError('');
    try {
      const res = await fetch('/api/patients/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newPatientForm.name.trim(),
          age: parseInt(newPatientForm.age, 10) || 35,
          gender: newPatientForm.gender,
          phone: newPatientForm.phone.trim(),
          email: newPatientForm.email.trim(),
          prakriti: newPatientForm.prakriti,
          medical_history: newPatientForm.complaints.trim()
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        await fetchPatients();
        await fetchDashboardData();
        setIsAddPatientModalOpen(false);
        setNewPatientForm({
          name: '',
          age: 35,
          gender: 'Male',
          phone: '',
          email: '',
          prakriti: 'Vata-Pitta',
          complaints: ''
        });
        if (data.patient) {
          setSelectedPatient(data.patient);
          setActiveTab('prescriptions');
        }
      } else {
        setPatientModalError(data.message || 'Failed to register patient.');
      }
    } catch (err) {
      console.error('Error registering patient:', err);
      setPatientModalError('Network error while registering patient.');
    } finally {
      setIsSubmittingPatient(false);
    }
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
    { 
      id: 'voice', 
      label: "Voice Consultation", 
      path: "/consultation/voice", 
      icon: Mic, 
      color: "#10B981" 
    },
    { 
      id: 'add_patient', 
      label: "Add Patient", 
      action: () => setIsAddPatientModalOpen(true), 
      path: "/new/patients/add", 
      icon: UserPlus, 
      color: "#06B6D4" 
    },
    { 
      id: 'prescriptions', 
      label: "Case Sheets Archive", 
      action: () => { setSelectedPatient(null); setArchiveViewMode('cases'); setActiveTab('prescriptions'); }, 
      icon: FileText, 
      color: "#F59E0B" 
    },
    { 
      id: 'ocr', 
      label: "AI Prescription OCR", 
      path: "/ocr-decoder", 
      icon: Upload, 
      color: "#E8B24A" 
    },
    { 
      id: 'order_meds', 
      label: "Pharmacy Store", 
      path: "/order-medicines", 
      icon: ShoppingCart, 
      color: "#38BDF8" 
    },
    { 
      id: 'device', 
      label: "Device Diagnostics", 
      path: "/device-check", 
      icon: Wrench, 
      color: "#A78BFA" 
    },
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
              <button onClick={() => { setModalPatientId(null); setIsPrescriptionModalOpen(true); }} className="btn-gold" style={{ padding: '7px 14px', fontSize: '0.84rem' }}>
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
              <section className="glass-card" style={{ padding: '22px', borderRadius: '18px', background: isVoiceListening ? 'rgba(239, 68, 68, 0.04)' : 'rgba(16, 185, 129, 0.05)', border: isVoiceListening ? '1px solid rgba(239, 68, 68, 0.35)' : '1px solid rgba(16, 185, 129, 0.2)', transition: 'all 0.3s ease' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <VoiceMicInput 
                      onTranscript={handleVoiceTranscript}
                      onStart={handleVoiceStart}
                      onListeningChange={setIsVoiceListening}
                    />
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <h4 style={{ margin: 0, fontSize: '0.98rem', color: isVoiceListening ? '#EF4444' : '#10B981', fontWeight: '700' }}>
                          Clinical Hands-Free Voice Dictation
                        </h4>
                        {isVoiceListening && (
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            background: 'rgba(239, 68, 68, 0.15)',
                            color: '#EF4444',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            fontSize: '0.72rem',
                            fontWeight: '700',
                            animation: 'pulse 1.5s infinite'
                          }}>
                            ● Recording... Speak now
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                        Click microphone to speak symptoms or clinical notes. Clicking mic starts a fresh note.
                      </span>
                    </div>
                  </div>
                  {dictatedNotes && (
                    <button 
                      onClick={() => setDictatedNotes('')} 
                      style={{ 
                        background: 'rgba(239, 68, 68, 0.1)', 
                        border: '1px solid rgba(239, 68, 68, 0.25)', 
                        color: '#EF4444', 
                        fontSize: '0.8rem', 
                        fontWeight: '700', 
                        padding: '5px 12px',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <Trash2 size={13} /> Clear Notes
                    </button>
                  )}
                </div>
                <textarea
                  rows={3}
                  value={dictatedNotes}
                  onChange={(e) => setDictatedNotes(e.target.value)}
                  placeholder="Spoken notes or clinical symptoms appear here in real-time..."
                  style={{
                    width: '100%',
                    padding: '14px',
                    borderRadius: '12px',
                    background: 'rgba(0, 0, 0, 0.28)',
                    border: isVoiceListening ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid rgba(255, 255, 255, 0.1)',
                    boxShadow: isVoiceListening ? '0 0 14px rgba(239, 68, 68, 0.2)' : 'none',
                    color: '#F8FAFC',
                    fontSize: '0.9rem',
                    outline: 'none',
                    resize: 'vertical',
                    transition: 'all 0.2s ease'
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
                    const accentColor = action.color || '#10B981';
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
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'translateY(-2px)';
                          e.currentTarget.style.borderColor = `${accentColor}70`;
                          e.currentTarget.style.background = `${accentColor}18`;
                          e.currentTarget.style.boxShadow = `0 6px 16px ${accentColor}25`;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
                          e.currentTarget.style.boxShadow = 'none';
                        }}
                        style={{
                          padding: '12px 16px',
                          justifyContent: 'flex-start',
                          borderRadius: '12px',
                          fontSize: '0.88rem',
                          fontWeight: '700',
                          cursor: 'pointer',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          background: 'rgba(255, 255, 255, 0.03)',
                          color: '#F8FAFC',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
                        }}
                      >
                        <div style={{
                          width: '28px',
                          height: '28px',
                          borderRadius: '8px',
                          background: `${accentColor}20`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0
                        }}>
                          <IconComp size={16} style={{ color: accentColor }} />
                        </div>
                        {action.label}
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
                              <button onClick={() => navigate('/consultation/voice')} className="btn-primary" style={{ padding: '6px 12px', fontSize: '0.78rem', cursor: 'pointer', border: 'none' }}>
                                Consultation
                              </button>
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
                          <button onClick={() => navigate('/consultation/voice')} className="btn-primary" style={{ padding: '6px 14px', fontSize: '0.8rem', cursor: 'pointer', border: 'none' }}>
                            Start EMR
                          </button>
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
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                          <button
                            onClick={() => setArchiveViewMode('patients')}
                            style={{
                              padding: '8px 16px',
                              borderRadius: '10px',
                              background: archiveViewMode === 'patients' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                              border: `1px solid ${archiveViewMode === 'patients' ? 'rgba(16, 185, 129, 0.45)' : 'rgba(255, 255, 255, 0.1)'}`,
                              color: archiveViewMode === 'patients' ? '#10B981' : '#94A3B8',
                              fontWeight: '700',
                              fontSize: '0.88rem',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}
                          >
                            <Users size={16} /> Patients Directory ({patients.length})
                          </button>
                          <button
                            onClick={() => setArchiveViewMode('cases')}
                            style={{
                              padding: '8px 16px',
                              borderRadius: '10px',
                              background: archiveViewMode === 'cases' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                              border: `1px solid ${archiveViewMode === 'cases' ? 'rgba(245, 158, 11, 0.45)' : 'rgba(255, 255, 255, 0.1)'}`,
                              color: archiveViewMode === 'cases' ? '#F59E0B' : '#94A3B8',
                              fontWeight: '700',
                              fontSize: '0.88rem',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}
                          >
                            <FileText size={16} /> All Case Sheets Archive ({prescriptions.length})
                          </button>
                        </div>
                        <span style={{ fontSize: '0.84rem', color: '#94A3B8' }}>
                          {archiveViewMode === 'patients'
                            ? "Select a patient below to view their individualized medical history, case sheets, and prescriptions."
                            : "Chronological archive of all doctor prescriptions, clinical diagnoses, and 1-0-1 Ayurvedic dosage schedules across the clinic."}
                        </span>
                      </div>

                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                        <button
                          onClick={() => setIsAddPatientModalOpen(true)}
                          className="btn-secondary"
                          style={{ padding: '9px 16px', fontSize: '0.86rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '6px' }}
                        >
                          <UserPlus size={15} color="#06B6D4" /> Add Patient
                        </button>
                        <button 
                          onClick={() => setIsPrescriptionModalOpen(true)}
                          className="btn-gold"
                          style={{ padding: '9px 18px', fontSize: '0.86rem', fontWeight: '700' }}
                        >
                          <Upload size={15} style={{ marginRight: '6px' }} /> Upload Prescription
                        </button>
                      </div>
                    </div>

                    {/* Search Bar */}
                    <div style={{ position: 'relative' }}>
                      <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
                      <input
                        type="text"
                        placeholder={archiveViewMode === 'patients' ? "Search patients by name, prakriti, or phone..." : "Search case sheets by patient, diagnosis, or medicine..."}
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

                  {/* VIEW MODE A: PATIENTS DIRECTORY */}
                  {archiveViewMode === 'patients' && (
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
                  )}

                  {/* VIEW MODE B: ALL CLINICAL CASE SHEETS & PRESCRIPTIONS ARCHIVE */}
                  {archiveViewMode === 'cases' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {filteredPrescriptions.length > 0 ? (
                        filteredPrescriptions.map((rx) => {
                          const matchingPatient = patients.find(p => 
                            String(p.id) === String(rx.patient_id) || 
                            (p.name && rx.patient_name && p.name.toLowerCase() === rx.patient_name.toLowerCase())
                          );

                          return (
                            <div 
                              key={rx.id}
                              className="glass-card"
                              style={{
                                padding: '22px 26px',
                                borderRadius: '18px',
                                border: '1px solid rgba(255, 255, 255, 0.08)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '14px'
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                                <div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                                    <h3 style={{ margin: 0, fontSize: '1.18rem', fontWeight: '800', color: '#F8FAFC' }}>
                                      {rx.diagnosis || 'Ayurvedic Clinical Consultation'}
                                    </h3>
                                    <span style={{
                                      padding: '2px 8px',
                                      borderRadius: '6px',
                                      background: 'rgba(16, 185, 129, 0.15)',
                                      color: '#10B981',
                                      fontSize: '0.74rem',
                                      fontWeight: '700'
                                    }}>
                                      Rx #{rx.id}
                                    </span>
                                  </div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', fontSize: '0.84rem', color: '#94A3B8' }}>
                                    <span style={{ color: '#06B6D4', fontWeight: '700' }}>
                                      👤 {rx.patient_name || 'Patient'}
                                    </span>
                                    {rx.patient_age && <span>• {rx.patient_age} yrs ({rx.patient_gender || 'Other'})</span>}
                                    {rx.created_at && <span>• 📅 {new Date(rx.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>}
                                  </div>
                                </div>

                                <button
                                  onClick={() => {
                                    if (matchingPatient) setSelectedPatient(matchingPatient);
                                    else setSelectedPatient({ id: rx.patient_id, name: rx.patient_name, age: rx.patient_age, gender: rx.patient_gender });
                                  }}
                                  style={{
                                    padding: '7px 16px',
                                    borderRadius: '8px',
                                    background: 'rgba(16, 185, 129, 0.12)',
                                    border: '1px solid rgba(16, 185, 129, 0.3)',
                                    color: '#10B981',
                                    fontSize: '0.82rem',
                                    fontWeight: '700',
                                    cursor: 'pointer'
                                  }}
                                >
                                  View Patient Dossier →
                                </button>
                              </div>

                              {/* Medicines Breakdown Table */}
                              {rx.medicines && rx.medicines.length > 0 && (
                                <div style={{ overflowX: 'auto', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                                    <thead>
                                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', color: '#94A3B8', textAlign: 'left' }}>
                                        <th style={{ padding: '8px 14px' }}>Medicine</th>
                                        <th style={{ padding: '8px 14px' }}>Dosage & Timing (1-0-1 Schedule)</th>
                                        <th style={{ padding: '8px 14px' }}>Duration</th>
                                        <th style={{ padding: '8px 14px' }}>Instructions</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {rx.medicines.map((m, mIdx) => (
                                        <tr key={mIdx} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                                          <td style={{ padding: '10px 14px', fontWeight: '700', color: '#F8FAFC' }}>
                                            {m.medicine_name || m.name}
                                          </td>
                                          <td style={{ padding: '10px 14px' }}>
                                            <DosageTimingBadge 
                                              frequency={m.frequency || '1-0-1'} 
                                              dosage={typeof m.dosage === 'object' ? `${m.dosage?.amount || ''} ${m.dosage?.unit || ''}` : m.dosage} 
                                            />
                                          </td>
                                          <td style={{ padding: '10px 14px', color: '#94A3B8' }}>{m.duration || '15 days'}</td>
                                          <td style={{ padding: '10px 14px', color: '#CBD5E1' }}>{m.instructions || 'After food'}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}

                              {rx.advice && (
                                <div style={{ fontSize: '0.82rem', color: '#94A3B8', background: 'rgba(255, 255, 255, 0.02)', padding: '8px 12px', borderRadius: '8px' }}>
                                  <strong style={{ color: '#E8B24A' }}>Advice:</strong> {rx.advice}
                                </div>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <div className="glass-card" style={{ padding: '40px', textAlign: 'center', borderRadius: '18px' }}>
                          <FileText size={38} style={{ color: '#94A3B8', marginBottom: '10px', opacity: 0.6 }} />
                          <h3 style={{ margin: '0 0 6px', color: '#F8FAFC' }}>No case sheets found</h3>
                          <p style={{ color: '#94A3B8', fontSize: '0.88rem' }}>Upload or dictate a prescription to record your first clinical case sheet.</p>
                        </div>
                      )}
                    </div>
                  )}

                  {archiveViewMode === 'patients' && patients.length === 0 && (
                    <div className="glass-card" style={{ padding: '40px', textAlign: 'center', borderRadius: '18px' }}>
                      <Users size={40} style={{ color: '#94A3B8', marginBottom: '12px' }} />
                      <h3 style={{ margin: '0 0 6px', color: '#F8FAFC' }}>No patients registered yet</h3>
                      <p style={{ color: '#94A3B8', fontSize: '0.9rem', margin: '0 0 16px' }}>
                        Click "Add Patient" above or upload a prescription to register your first patient.
                      </p>
                      <button onClick={() => setIsAddPatientModalOpen(true)} className="btn-primary" style={{ padding: '10px 20px', marginRight: '8px' }}>
                        <UserPlus size={16} style={{ marginRight: '6px' }} /> Add Patient
                      </button>
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
                          onClick={() => { setModalPatientId(selectedPatient?.id); setIsPrescriptionModalOpen(true); }}
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
                              <button
                                onClick={() => navigate('/consultation/voice')}
                                className="btn-primary"
                                style={{ padding: '8px 16px', fontSize: '0.82rem', cursor: 'pointer', border: 'none', display: 'flex', alignItems: 'center' }}
                              >
                                <Mic size={14} style={{ marginRight: '6px' }} /> Voice Consultation
                              </button>
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

      {/* ======================================================== */}
      {/* MODAL: REGISTER NEW CLINICAL PATIENT                     */}
      {/* ======================================================== */}
      {isAddPatientModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(10px)',
          zIndex: 1100,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: 'linear-gradient(145deg, #0d281e, #061510)',
            border: '1px solid rgba(16, 185, 129, 0.35)',
            borderRadius: '24px',
            width: '100%',
            maxWidth: '540px',
            padding: '28px',
            boxShadow: '0 20px 50px rgba(0,0,0,0.8)',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '10px',
                  background: 'rgba(16, 185, 129, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#10B981'
                }}>
                  <UserPlus size={20} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '800', color: '#F8FAFC' }}>
                    Add New Patient
                  </h3>
                  <div style={{ fontSize: '0.78rem', color: '#94A3B8' }}>
                    Quick registration for case sheets, prescriptions & AI copilot
                  </div>
                </div>
              </div>
              <button
                onClick={() => setIsAddPatientModalOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94A3B8',
                  fontSize: '1.2rem',
                  cursor: 'pointer',
                  padding: '4px'
                }}
              >
                ✕
              </button>
            </div>

            {patientModalError && (
              <div style={{
                marginBottom: '16px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#FCA5A5',
                fontSize: '0.84rem'
              }}>
                {patientModalError}
              </div>
            )}

            <form onSubmit={handleCreatePatientSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '4px' }}>
                  Patient Full Name <span style={{ color: '#EF4444' }}>*</span>
                </label>
                <input
                  type="text"
                  required
                  autoFocus
                  placeholder="e.g. Ramesh Chandra, Meera Bai"
                  value={newPatientForm.name}
                  onChange={(e) => setNewPatientForm({ ...newPatientForm, name: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.4)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.9rem',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '4px' }}>
                    Age (Years)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="120"
                    value={newPatientForm.age}
                    onChange={(e) => setNewPatientForm({ ...newPatientForm, age: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: 'rgba(0, 0, 0, 0.4)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#F8FAFC',
                      fontSize: '0.9rem',
                      boxSizing: 'border-box',
                      outline: 'none'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '4px' }}>
                    Gender
                  </label>
                  <select
                    value={newPatientForm.gender}
                    onChange={(e) => setNewPatientForm({ ...newPatientForm, gender: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: '#071510',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#F8FAFC',
                      fontSize: '0.9rem',
                      boxSizing: 'border-box',
                      outline: 'none'
                    }}
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '4px' }}>
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    placeholder="+91 98765 43210"
                    value={newPatientForm.phone}
                    onChange={(e) => setNewPatientForm({ ...newPatientForm, phone: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: 'rgba(0, 0, 0, 0.4)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#F8FAFC',
                      fontSize: '0.9rem',
                      boxSizing: 'border-box',
                      outline: 'none'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '4px' }}>
                    Ayurvedic Prakriti
                  </label>
                  <select
                    value={newPatientForm.prakriti}
                    onChange={(e) => setNewPatientForm({ ...newPatientForm, prakriti: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: '#071510',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#10B981',
                      fontWeight: '700',
                      fontSize: '0.9rem',
                      boxSizing: 'border-box',
                      outline: 'none'
                    }}
                  >
                    <option value="Vata-Pitta">Vata-Pitta</option>
                    <option value="Pitta-Kapha">Pitta-Kapha</option>
                    <option value="Kapha-Vata">Kapha-Vata</option>
                    <option value="Vata Dominant">Vata Dominant</option>
                    <option value="Pitta Dominant">Pitta Dominant</option>
                    <option value="Kapha Dominant">Kapha Dominant</option>
                    <option value="Tridoshic (Sama)">Tridoshic</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '4px' }}>
                  Chief Complaints / Symptoms
                </label>
                <input
                  type="text"
                  placeholder="e.g. Joint stiffness, acidity, fatigue"
                  value={newPatientForm.complaints}
                  onChange={(e) => setNewPatientForm({ ...newPatientForm, complaints: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.4)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.9rem',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
                <Link
                  to="/new/patients/add"
                  onClick={() => setIsAddPatientModalOpen(false)}
                  style={{ fontSize: '0.8rem', color: '#06B6D4', textDecoration: 'none', fontWeight: '600' }}
                >
                  Open Full Registration Page →
                </Link>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setIsAddPatientModalOpen(false)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      color: '#E2E8F0',
                      cursor: 'pointer',
                      fontSize: '0.84rem'
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingPatient}
                    style={{
                      padding: '8px 20px',
                      borderRadius: '8px',
                      background: 'linear-gradient(135deg, #10B981, #059669)',
                      border: 'none',
                      color: '#FFFFFF',
                      fontWeight: '700',
                      cursor: isSubmittingPatient ? 'wait' : 'pointer',
                      fontSize: '0.86rem'
                    }}
                  >
                    {isSubmittingPatient ? 'Saving...' : 'Register Patient'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Prescription Reader Modal with Save to Case Sheet Support */}
      <PrescriptionReaderModal
        isOpen={isPrescriptionModalOpen}
        onClose={() => setIsPrescriptionModalOpen(false)}
        onAddMedicinesToCart={handleVoiceTranscript}
        onPrescriptionSaved={handlePrescriptionSaved}
        initialPatientId={modalPatientId}
      />
    </div>
  );
}
