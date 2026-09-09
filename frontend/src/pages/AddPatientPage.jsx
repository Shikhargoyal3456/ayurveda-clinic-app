import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { 
  UserPlus, 
  ArrowLeft, 
  CheckCircle2, 
  AlertCircle, 
  Users, 
  Activity, 
  Phone, 
  Mail, 
  FileText, 
  Sparkles, 
  Mic, 
  Calendar,
  Save,
  Pill
} from 'lucide-react';
import axios from 'axios';

export default function AddPatientPage() {
  const navigate = useNavigate();

  // Form fields
  const [name, setName] = useState('');
  const [age, setAge] = useState(35);
  const [gender, setGender] = useState('Male');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [prakriti, setPrakriti] = useState('Vata-Pitta');
  const [medicalHistory, setMedicalHistory] = useState('');
  const [chiefComplaints, setChiefComplaints] = useState('');

  // Submission states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [createdPatient, setCreatedPatient] = useState(null);

  // Recent patients list
  const [recentPatients, setRecentPatients] = useState([]);

  useEffect(() => {
    fetchRecentPatients();
  }, []);

  const fetchRecentPatients = async () => {
    try {
      const res = await axios.get('/api/patients/list');
      if (res.data && res.data.success && Array.isArray(res.data.patients)) {
        setRecentPatients(res.data.patients.slice(0, 6));
      }
    } catch (e) {
      console.warn('Could not load recent patients:', e);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Patient full name is required.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg('');

    try {
      const payload = {
        name: name.trim(),
        age: parseInt(age, 10) || 35,
        gender: gender,
        phone: phone.trim(),
        email: email.trim(),
        prakriti: prakriti,
        medical_history: [chiefComplaints, medicalHistory].filter(Boolean).join(' | '),
        address: [chiefComplaints, medicalHistory].filter(Boolean).join(' | ') || 'Ayurvedic Clinical Patient'
      };

      const res = await axios.post('/api/patients/create', payload);
      if (res.data && res.data.success) {
        setCreatedPatient(res.data.patient || { name, age, gender, prakriti });
        fetchRecentPatients();
        // Reset inputs
        setName('');
        setPhone('');
        setEmail('');
        setMedicalHistory('');
        setChiefComplaints('');
      } else {
        setErrorMsg(res.data?.message || 'Failed to register patient.');
      }
    } catch (err) {
      console.error('Error creating patient:', err);
      setErrorMsg(err.response?.data?.detail || err.message || 'Error saving patient to database.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      minHeight: 'calc(100vh - 68px)',
      background: 'radial-gradient(circle at 50% 0%, #0d281e 0%, #061510 100%)',
      color: '#F8FAFC',
      padding: '36px 24px 80px',
      boxSizing: 'border-box'
    }}>
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>

        {/* Top Breadcrumb */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={() => navigate('/doctor')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#E2E8F0',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '0.86rem'
              }}
            >
              <ArrowLeft size={16} /> Return to Doctor Portal
            </button>
            <span style={{ color: 'rgba(255, 255, 255, 0.3)' }}>/</span>
            <span style={{ color: '#10B981', fontWeight: '700', fontSize: '0.9rem' }}>Patient Registration</span>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() => navigate('/consultation/voice')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: '10px',
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: '#10B981',
                fontWeight: '700',
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              <Mic size={15} /> Voice Consultation
            </button>
          </div>
        </div>

        {/* Main Grid: Form + Recent Patients Sidebar */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '28px' }}>

          {/* Left Column: Form Card */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: '24px',
            padding: '32px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25), rgba(6, 182, 212, 0.2))',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10B981'
              }}>
                <UserPlus size={22} />
              </div>
              <div>
                <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: '800', color: '#F8FAFC' }}>
                  Register New Patient
                </h1>
                <p style={{ margin: 0, fontSize: '0.84rem', color: '#94A3B8' }}>
                  Add a patient profile to enable clinical case sheets, prescriptions, and AI grounding.
                </p>
              </div>
            </div>

            {/* Success Alert Banner */}
            {createdPatient && (
              <div style={{
                marginBottom: '24px',
                padding: '16px 20px',
                borderRadius: '14px',
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <CheckCircle2 size={22} color="#10B981" />
                  <div>
                    <div style={{ fontWeight: '700', color: '#10B981', fontSize: '0.94rem' }}>
                      Patient "{createdPatient.name}" Added Successfully!
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#CBD5E1' }}>
                      Prakriti: {createdPatient.prakriti} • Age: {createdPatient.age}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => navigate('/consultation/voice')}
                    style={{
                      padding: '7px 14px',
                      borderRadius: '8px',
                      background: '#10B981',
                      border: 'none',
                      color: 'white',
                      fontWeight: '700',
                      fontSize: '0.8rem',
                      cursor: 'pointer'
                    }}
                  >
                    Start Voice Rx →
                  </button>
                  <button
                    onClick={() => navigate('/doctor')}
                    style={{
                      padding: '7px 14px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.1)',
                      border: 'none',
                      color: '#E2E8F0',
                      fontWeight: '600',
                      fontSize: '0.8rem',
                      cursor: 'pointer'
                    }}
                  >
                    Go to Dossier
                  </button>
                </div>
              </div>
            )}

            {/* Error Alert Banner */}
            {errorMsg && (
              <div style={{
                marginBottom: '20px',
                padding: '12px 16px',
                borderRadius: '10px',
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#FCA5A5',
                fontSize: '0.86rem',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <AlertCircle size={18} /> {errorMsg}
              </div>
            )}

            {/* Registration Form */}
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>

              {/* Full Name */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                  Patient Full Name <span style={{ color: '#EF4444' }}>*</span>
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Aarav Sharma, Sunita Devi"
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'rgba(0, 0, 0, 0.35)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#F8FAFC',
                    fontSize: '0.92rem',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Age & Gender Row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                    Age (Years)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="120"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '12px 14px',
                      borderRadius: '10px',
                      background: 'rgba(0, 0, 0, 0.35)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      color: '#F8FAFC',
                      fontSize: '0.92rem',
                      boxSizing: 'border-box',
                      outline: 'none'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                    Gender
                  </label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '12px 14px',
                      borderRadius: '10px',
                      background: '#071510',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      color: '#F8FAFC',
                      fontSize: '0.92rem',
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

              {/* Phone & Email Row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                    Contact Phone
                  </label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="e.g. +91 98765 43210"
                    style={{
                      width: '100%',
                      padding: '12px 14px',
                      borderRadius: '10px',
                      background: 'rgba(0, 0, 0, 0.35)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      color: '#F8FAFC',
                      fontSize: '0.92rem',
                      boxSizing: 'border-box',
                      outline: 'none'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                    Email Address (Optional)
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="patient@example.com"
                    style={{
                      width: '100%',
                      padding: '12px 14px',
                      borderRadius: '10px',
                      background: 'rgba(0, 0, 0, 0.35)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      color: '#F8FAFC',
                      fontSize: '0.92rem',
                      boxSizing: 'border-box',
                      outline: 'none'
                    }}
                  />
                </div>
              </div>

              {/* Ayurvedic Prakriti / Dosha Imbalance */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                  Ayurvedic Prakriti / Dosha Dominance
                </label>
                <select
                  value={prakriti}
                  onChange={(e) => setPrakriti(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: '#071510',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#10B981',
                    fontWeight: '700',
                    fontSize: '0.92rem',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                >
                  <option value="Vata-Pitta">Vata-Pitta (Air & Fire)</option>
                  <option value="Pitta-Kapha">Pitta-Kapha (Fire & Earth)</option>
                  <option value="Kapha-Vata">Kapha-Vata (Earth & Air)</option>
                  <option value="Vata Dominant">Vata Dominant (Dryness, Joint stiffness, Nervous)</option>
                  <option value="Pitta Dominant">Pitta Dominant (Heat, Inflammation, Hyperacidity)</option>
                  <option value="Kapha Dominant">Kapha Dominant (Congestion, Heaviness, Sluggish)</option>
                  <option value="Tridoshic (Sama)">Tridoshic / Balanced (Sama Dosha)</option>
                </select>
              </div>

              {/* Chief Complaints */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                  Chief Complaints / Symptoms
                </label>
                <input
                  type="text"
                  value={chiefComplaints}
                  onChange={(e) => setChiefComplaints(e.target.value)}
                  placeholder="e.g. Joint pain in knee, acid reflux after meals, chronic insomnia"
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'rgba(0, 0, 0, 0.35)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#F8FAFC',
                    fontSize: '0.92rem',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Medical History */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: '700', color: '#CBD5E1', marginBottom: '6px' }}>
                  Medical History / Allergies / Notes
                </label>
                <textarea
                  rows="3"
                  value={medicalHistory}
                  onChange={(e) => setMedicalHistory(e.target.value)}
                  placeholder="e.g. Known diabetes for 4 years, allergic to dust, taking Triphala intermittently"
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'rgba(0, 0, 0, 0.35)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#F8FAFC',
                    fontSize: '0.9rem',
                    boxSizing: 'border-box',
                    outline: 'none',
                    resize: 'vertical'
                  }}
                />
              </div>

              {/* Submit Button */}
              <div style={{ marginTop: '10px' }}>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    width: '100%',
                    padding: '14px',
                    borderRadius: '12px',
                    background: 'linear-gradient(135deg, #10B981, #059669)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: '800',
                    fontSize: '0.98rem',
                    cursor: isSubmitting ? 'wait' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    boxShadow: '0 4px 16px rgba(16, 185, 129, 0.35)'
                  }}
                >
                  <Save size={18} /> {isSubmitting ? 'Registering Patient...' : 'Register Patient in Clinic'}
                </button>
              </div>

            </form>
          </div>

          {/* Right Column: Existing Patients & Quick Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Quick Actions Card */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '20px',
              padding: '24px'
            }}>
              <h3 style={{ margin: '0 0 14px', fontSize: '1.05rem', fontWeight: '700', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={18} color="#10B981" /> Consultation Quick Links
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <button
                  onClick={() => navigate('/consultation/voice')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    color: '#10B981',
                    fontWeight: '700',
                    fontSize: '0.86rem',
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                >
                  <Mic size={16} /> Open Voice Consultation Suite
                </button>

                <button
                  onClick={() => navigate('/ocr-decoder')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'rgba(232, 178, 74, 0.1)',
                    border: '1px solid rgba(232, 178, 74, 0.25)',
                    color: '#E8B24A',
                    fontWeight: '700',
                    fontSize: '0.86rem',
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                >
                  <FileText size={16} /> AI Prescription Vision OCR
                </button>

                <button
                  onClick={() => navigate('/order-medicines')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'rgba(6, 182, 212, 0.1)',
                    border: '1px solid rgba(6, 182, 212, 0.25)',
                    color: '#06B6D4',
                    fontWeight: '700',
                    fontSize: '0.86rem',
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                >
                  <Pill size={16} /> Pharmacy Medicine Store
                </button>
              </div>
            </div>

            {/* Existing Clinic Patients */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '20px',
              padding: '24px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Users size={18} color="#06B6D4" /> Existing Clinic Patients ({recentPatients.length})
                </h3>
              </div>

              {recentPatients.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px', color: '#94A3B8', fontSize: '0.84rem' }}>
                  No patients found in clinic database.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {recentPatients.map((p) => (
                    <div
                      key={p.id}
                      onClick={() => navigate('/doctor')}
                      style={{
                        padding: '12px 14px',
                        borderRadius: '10px',
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid rgba(255, 255, 255, 0.06)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                        e.currentTarget.style.background = 'rgba(16, 185, 129, 0.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.06)';
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: '700', fontSize: '0.88rem', color: '#F8FAFC' }}>
                          {p.name}
                        </div>
                        <div style={{ fontSize: '0.74rem', color: '#94A3B8' }}>
                          {p.gender}, {p.age} yrs • {p.prakriti || 'Vata-Pitta'}
                        </div>
                      </div>

                      <span style={{
                        padding: '3px 8px',
                        borderRadius: '12px',
                        background: 'rgba(16, 185, 129, 0.15)',
                        color: '#10B981',
                        fontSize: '0.72rem',
                        fontWeight: '700'
                      }}>
                        {p.prescriptions_count || 0} Rx
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>

        </div>

      </div>
    </div>
  );
}
