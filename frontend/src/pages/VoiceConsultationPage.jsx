import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Mic, Square, Sparkles, User, Save, RefreshCw, ArrowLeft, 
  Bot, CheckCircle2, AlertCircle, Trash2, ExternalLink, Volume2, 
  FileText, Pill, Calendar, Clock, Activity, Check, Plus
} from 'lucide-react';
import DosageTimingBadge from '../components/DosageTimingBadge';

export default function VoiceConsultationPage() {
  const navigate = useNavigate();

  // Voice recording states
  const [isListening, setIsListening] = useState(false);
  const [language, setLanguage] = useState('en-IN');
  const [transcript, setTranscript] = useState('');
  const [interimText, setInterimText] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractError, setExtractError] = useState('');

  // Patient states
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('new');
  const [patientName, setPatientName] = useState('');
  const [patientAge, setPatientAge] = useState(35);
  const [patientGender, setPatientGender] = useState('Male');

  // Clinical SOAP states
  const [symptoms, setSymptoms] = useState([]);
  const [newSymptomInput, setNewSymptomInput] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [clinicalAdvice, setClinicalAdvice] = useState('');
  const [followUp, setFollowUp] = useState('7 days');
  const [medicines, setMedicines] = useState([]);

  // Save states
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');

  const recognitionRef = useRef(null);

  // Fetch patient list
  useEffect(() => {
    fetch('/api/patients/list')
      .then(res => res.json())
      .then(data => {
        if (data.success && data.patients) {
          setPatients(data.patients);
        }
      })
      .catch(err => console.error('Error loading patients:', err));
  }, []);

  // Web Speech API Setup
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = language;

      recognition.onresult = (event) => {
        let finalChunk = '';
        let interimChunk = '';
        for (let i = 0; i < event.results.length; i++) {
          const res = event.results[i];
          if (res && res[0]) {
            if (res.isFinal) {
              finalChunk += res[0].transcript + ' ';
            } else {
              interimChunk += res[0].transcript;
            }
          }
        }
        setTranscript(finalChunk.trim());
        setInterimText(interimChunk.trim());
      };

      recognition.onerror = (evt) => {
        console.warn('Speech error:', evt.error);
        if (evt.error !== 'no-speech') {
          setExtractError('Microphone error: ' + evt.error);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, [language]);

  const handleToggleListening = () => {
    setExtractError('');
    if (isListening) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      setIsListening(false);
      setInterimText('');
    } else {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.lang = language;
          recognitionRef.current.start();
          setIsListening(true);
        } catch (err) {
          console.error('Speech recognition start failed:', err);
          setExtractError('Could not start microphone. Please grant browser permissions.');
        }
      } else {
        setExtractError('Web Speech API is not supported in this browser. Please use Google Chrome or Edge.');
      }
    }
  };

  const handlePatientSelectChange = (e) => {
    const val = e.target.value;
    setSelectedPatientId(val);
    if (val !== 'new') {
      const p = patients.find(pat => String(pat.id) === String(val));
      if (p) {
        setPatientName(p.name);
        setPatientAge(p.age || 35);
        setPatientGender(p.gender || 'Other');
      }
    } else {
      setPatientName('');
    }
  };

  const handleExtractSOAP = async () => {
    const fullText = (transcript + ' ' + interimText).trim();
    if (!fullText) {
      setExtractError('Please dictate or type consultation notes first.');
      return;
    }

    setIsExtracting(true);
    setExtractError('');
    setSaveSuccess('');

    try {
      const res = await fetch('/api/voice/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: fullText,
          patient_name: patientName.trim() || 'Patient'
        })
      });

      const data = await res.json();
      if (res.ok && data.success) {
        if (data.diagnosis) setDiagnosis(data.diagnosis);
        if (data.symptoms && Array.isArray(data.symptoms)) {
          setSymptoms(data.symptoms);
        }
        if (data.follow_up) setFollowUp(data.follow_up);
        if (data.patient?.name && !patientName) {
          setPatientName(data.patient.name);
        }

        // Format medicines
        if (data.medicines && Array.isArray(data.medicines)) {
          const formatted = data.medicines.map((m, idx) => {
            if (typeof m === 'string') {
              return {
                medicine_name: m,
                dosage: '1 unit',
                frequency: '1-0-1',
                duration: '15 days',
                instructions: 'After meals with warm water'
              };
            }
            return {
              medicine_name: m.medicine_name || m.name || `Medicine ${idx + 1}`,
              dosage: m.dosage || '1 unit',
              frequency: m.frequency || '1-0-1',
              duration: m.duration || '15 days',
              instructions: m.instructions || 'After meals'
            };
          });
          setMedicines(formatted);
        }

        if (data.structured_data?.treatment_plan) {
          setClinicalAdvice(data.structured_data.treatment_plan);
        }
      } else {
        setExtractError(data.error || 'Failed to extract clinical SOAP note.');
      }
    } catch (err) {
      console.error('Extraction request error:', err);
      setExtractError('Network error while processing clinical transcription.');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleAddSymptom = () => {
    if (newSymptomInput.trim() && !symptoms.includes(newSymptomInput.trim())) {
      setSymptoms(prev => [...prev, newSymptomInput.trim()]);
      setNewSymptomInput('');
    }
  };

  const handleRemoveSymptom = (idx) => {
    setSymptoms(prev => prev.filter((_, i) => i !== idx));
  };

  const handleMedicineChange = (idx, field, val) => {
    setMedicines(prev => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [field]: val };
      return copy;
    });
  };

  const handleAddMedicineRow = () => {
    setMedicines(prev => [
      ...prev,
      { medicine_name: 'New Formulation', dosage: '1 unit', frequency: '1-0-1', duration: '15 days', instructions: 'After meals' }
    ]);
  };

  const handleRemoveMedicine = (idx) => {
    setMedicines(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSaveCaseSheet = async () => {
    if (!patientName.trim()) {
      setExtractError('Please enter or select a patient before saving.');
      return;
    }

    setIsSaving(true);
    setExtractError('');
    setSaveSuccess('');

    try {
      const res = await fetch('/api/prescriptions/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: selectedPatientId !== 'new' ? Number(selectedPatientId) : null,
          patient_name: patientName.trim(),
          patient_age: Number(patientAge) || 35,
          patient_gender: patientGender,
          diagnosis: diagnosis.trim() || 'Voice Consultation Assessment',
          advice: clinicalAdvice.trim() || `Follow-up in ${followUp}. Rest and adhere to prescribed medicines.`,
          medicines: medicines,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setSaveSuccess(`Case Sheet successfully recorded for ${data.patient?.name || patientName}!`);
      } else {
        setExtractError(data.error || 'Failed to save clinical case sheet.');
      }
    } catch (err) {
      console.error('Error saving case sheet:', err);
      setExtractError('Network error saving case sheet.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{
      maxWidth: '1280px',
      margin: '0 auto',
      padding: '30px 24px 80px',
      color: '#F8FAFC'
    }}>
      {/* Header Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <button
          onClick={() => navigate('/doctor')}
          className="btn-ghost"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', fontSize: '0.86rem' }}
        >
          <ArrowLeft size={16} /> Back to Doctor Dashboard
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <a
            href="http://localhost:8000/consultation/voice"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', padding: '8px 14px', textDecoration: 'none' }}
          >
            <ExternalLink size={14} /> Open OPD Full Console (Port 8000)
          </a>
        </div>
      </div>

      {/* Page Title Banner */}
      <div className="glass-card" style={{
        padding: '24px',
        borderRadius: '20px',
        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(6, 182, 212, 0.06))',
        border: '1px solid rgba(16, 185, 129, 0.25)',
        marginBottom: '24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '54px',
            height: '54px',
            borderRadius: '16px',
            background: 'rgba(16, 185, 129, 0.2)',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#10B981'
          }}>
            <Mic size={28} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: '800', color: '#F8FAFC' }}>
              AI Voice Clinical Consultation Suite
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: '0.88rem', color: '#94A3B8' }}>
              Hands-free bilingual consultation speech-to-text. Speaks symptoms & AI generates structured SOAP Case Sheets.
            </p>
          </div>
        </div>

        {/* Language Selection */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <label style={{ fontSize: '0.85rem', color: '#94A3B8', fontWeight: '600' }}>Language:</label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            disabled={isListening}
            style={{
              padding: '8px 12px',
              borderRadius: '10px',
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#F8FAFC',
              fontSize: '0.85rem',
              outline: 'none',
              cursor: isListening ? 'not-allowed' : 'pointer'
            }}
          >
            <option value="en-IN">English (India)</option>
            <option value="hi-IN">हिन्दी (Hindi)</option>
            <option value="en-US">English (US)</option>
          </select>
        </div>
      </div>

      {/* Alert Banners */}
      {saveSuccess && (
        <div style={{
          padding: '14px 18px',
          borderRadius: '12px',
          background: 'rgba(16, 185, 129, 0.15)',
          border: '1px solid rgba(16, 185, 129, 0.4)',
          color: '#10B981',
          fontSize: '0.9rem',
          fontWeight: '700',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <CheckCircle2 size={20} />
          <span>{saveSuccess}</span>
          <button 
            onClick={() => navigate('/doctor')} 
            style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#F8FAFC', textDecoration: 'underline', cursor: 'pointer', fontSize: '0.85rem' }}
          >
            View in Dashboard →
          </button>
        </div>
      )}

      {extractError && (
        <div style={{
          padding: '14px 18px',
          borderRadius: '12px',
          background: 'rgba(239, 68, 68, 0.12)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#EF4444',
          fontSize: '0.88rem',
          fontWeight: '600',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <AlertCircle size={20} />
          <span>{extractError}</span>
        </div>
      )}

      {/* Main Grid: Left = Voice Input, Right = Structured SOAP */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '24px' }}>
        
        {/* LEFT COLUMN: Voice Dictation & Patient Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Patient Card */}
          <div className="glass-card" style={{ padding: '22px', borderRadius: '18px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1.05rem', fontWeight: '700', color: '#10B981', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <User size={18} /> Patient Identification
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Select Existing Patient
                </label>
                <select
                  value={selectedPatientId}
                  onChange={handlePatientSelectChange}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.85rem',
                    outline: 'none'
                  }}
                >
                  <option value="new">+ Create / Enter Walk-In Patient</option>
                  {patients.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Patient Full Name
                </label>
                <input
                  type="text"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  placeholder="e.g. Aarav Sharma"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.85rem'
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Age
                </label>
                <input
                  type="number"
                  value={patientAge}
                  onChange={(e) => setPatientAge(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.85rem'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Gender
                </label>
                <select
                  value={patientGender}
                  onChange={(e) => setPatientGender(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.85rem'
                  }}
                >
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>
          </div>

          {/* Live Voice Recording Panel */}
          <div className="glass-card" style={{
            padding: '22px',
            borderRadius: '18px',
            border: isListening ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={18} color={isListening ? '#EF4444' : '#10B981'} />
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700', color: '#F8FAFC' }}>
                  Consultation Audio Stream
                </h3>
              </div>

              {isListening ? (
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'rgba(239, 68, 68, 0.18)',
                  color: '#EF4444',
                  padding: '3px 10px',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  fontWeight: '700',
                  animation: 'pulse 1.5s infinite'
                }}>
                  ● Recording ({language})... Speak naturally
                </span>
              ) : (
                <span style={{ fontSize: '0.8rem', color: '#94A3B8' }}>Microphone Idle</span>
              )}
            </div>

            {/* Controls Bar */}
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
              <button
                onClick={handleToggleListening}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  borderRadius: '12px',
                  background: isListening ? '#EF4444' : '#10B981',
                  border: 'none',
                  color: 'white',
                  fontWeight: '700',
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  boxShadow: isListening ? '0 0 16px rgba(239, 68, 68, 0.4)' : '0 4px 12px rgba(16, 185, 129, 0.3)'
                }}
              >
                {isListening ? (
                  <>
                    <Square size={16} style={{ fill: 'white' }} /> Stop Dictation
                  </>
                ) : (
                  <>
                    <Mic size={16} /> Start Voice Consultation
                  </>
                )}
              </button>

              <button
                onClick={() => { setTranscript(''); setInterimText(''); }}
                disabled={!transcript && !interimText}
                className="btn-ghost"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.84rem' }}
              >
                <Trash2 size={15} /> Clear Audio Text
              </button>
            </div>

            {/* Transcript Textbox */}
            <div style={{ position: 'relative' }}>
              <textarea
                rows={7}
                value={interimText ? `${transcript} ${interimText}` : transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Click 'Start Voice Consultation' and speak with the patient in Hindi or English. Spoken words will appear here in real time without repetition..."
                style={{
                  width: '100%',
                  padding: '14px',
                  borderRadius: '12px',
                  background: 'rgba(0, 0, 0, 0.35)',
                  border: isListening ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#F8FAFC',
                  fontSize: '0.9rem',
                  lineHeight: '1.6',
                  outline: 'none',
                  resize: 'vertical'
                }}
              />
            </div>

            {/* Extract SOAP Button */}
            <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={handleExtractSOAP}
                disabled={isExtracting || (!transcript && !interimText)}
                className="btn-gold"
                style={{
                  padding: '10px 20px',
                  fontSize: '0.88rem',
                  fontWeight: '700',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                {isExtracting ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" /> Structuring SOAP Note with AI...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} /> Generate AI Clinical SOAP Note
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Structured SOAP & Case Sheet Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          <div className="glass-card" style={{ padding: '24px', borderRadius: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: '800', color: '#E8B24A', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={18} /> Structured Clinical SOAP Note
              </h3>
              <span style={{ fontSize: '0.78rem', color: '#94A3B8' }}>Subjective • Objective • Assessment • Plan</span>
            </div>

            {/* S: Symptoms & Chief Complaints */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px', fontWeight: '700' }}>
                [S] Symptoms & Chief Complaints
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
                {symptoms.map((symp, idx) => (
                  <span
                    key={idx}
                    style={{
                      background: 'rgba(16, 185, 129, 0.15)',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      color: '#10B981',
                      padding: '4px 10px',
                      borderRadius: '16px',
                      fontSize: '0.8rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    {symp}
                    <button
                      onClick={() => handleRemoveSymptom(idx)}
                      style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer', padding: 0 }}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={newSymptomInput}
                  onChange={(e) => setNewSymptomInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddSymptom())}
                  placeholder="Add symptom (press Enter)..."
                  style={{
                    flex: 1,
                    padding: '7px 10px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.84rem'
                  }}
                />
                <button onClick={handleAddSymptom} className="btn-ghost" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                  + Add
                </button>
              </div>
            </div>

            {/* A: Diagnosis */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px', fontWeight: '700' }}>
                [A] Provisional Diagnosis & Dosha Imbalance
              </label>
              <input
                type="text"
                value={diagnosis}
                onChange={(e) => setDiagnosis(e.target.value)}
                placeholder="e.g. Amavata / Rheumatoid Arthritis (Vata-Kapha Imbalance)"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#F8FAFC',
                  fontSize: '0.86rem'
                }}
              />
            </div>

            {/* P: Medicines Table */}
            <div style={{ marginBottom: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <label style={{ fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', fontWeight: '700' }}>
                  [P] Prescribed Formulations ({medicines.length})
                </label>
                <button
                  onClick={handleAddMedicineRow}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#10B981',
                    fontSize: '0.8rem',
                    fontWeight: '700',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Plus size={14} /> Add Medicine
                </button>
              </div>

              {medicines.length === 0 ? (
                <div style={{ padding: '16px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', textAlign: 'center', color: '#64748B', fontSize: '0.85rem' }}>
                  No medicines extracted yet. Speak the Rx in the microphone or click '+ Add Medicine'.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8', textAlign: 'left' }}>
                        <th style={{ padding: '6px 8px' }}>Medicine</th>
                        <th style={{ padding: '6px 8px' }}>Dosage</th>
                        <th style={{ padding: '6px 8px' }}>Frequency (1-0-1)</th>
                        <th style={{ padding: '6px 8px' }}>Duration</th>
                        <th style={{ padding: '6px 8px' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {medicines.map((med, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                          <td style={{ padding: '6px 8px' }}>
                            <input
                              type="text"
                              value={med.medicine_name}
                              onChange={(e) => handleMedicineChange(idx, 'medicine_name', e.target.value)}
                              style={{ width: '100%', padding: '5px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC', fontWeight: '700' }}
                            />
                          </td>
                          <td style={{ padding: '6px 8px' }}>
                            <input
                              type="text"
                              value={med.dosage}
                              onChange={(e) => handleMedicineChange(idx, 'dosage', e.target.value)}
                              style={{ width: '70px', padding: '5px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC' }}
                            />
                          </td>
                          <td style={{ padding: '6px 8px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <input
                                type="text"
                                value={med.frequency}
                                onChange={(e) => handleMedicineChange(idx, 'frequency', e.target.value)}
                                style={{ width: '80px', padding: '5px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC' }}
                              />
                              <DosageTimingBadge frequency={med.frequency || '1-0-1'} compact={true} />
                            </div>
                          </td>
                          <td style={{ padding: '6px 8px' }}>
                            <input
                              type="text"
                              value={med.duration}
                              onChange={(e) => handleMedicineChange(idx, 'duration', e.target.value)}
                              style={{ width: '70px', padding: '5px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC' }}
                            />
                          </td>
                          <td style={{ padding: '6px 8px' }}>
                            <button
                              onClick={() => handleRemoveMedicine(idx)}
                              style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer' }}
                            >
                              ×
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Diet & Pathya/Apathya Clinical Advice */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px', fontWeight: '700' }}>
                Diet, Lifestyle & Clinical Advice (Pathya / Apathya)
              </label>
              <textarea
                rows={3}
                value={clinicalAdvice}
                onChange={(e) => setClinicalAdvice(e.target.value)}
                placeholder="e.g. Drink warm water, avoid sour/fermented foods, light yoga and pranayama."
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#F8FAFC',
                  fontSize: '0.85rem',
                  resize: 'vertical'
                }}
              />
            </div>

            {/* Save Button */}
            <button
              onClick={handleSaveCaseSheet}
              disabled={isSaving}
              className="btn-primary"
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '12px',
                fontSize: '0.95rem',
                fontWeight: '800',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                background: 'linear-gradient(135deg, #10B981, #059669)',
                boxShadow: '0 4px 16px rgba(16, 185, 129, 0.35)'
              }}
            >
              {isSaving ? (
                <>
                  <RefreshCw size={18} className="animate-spin" /> Saving Case Sheet...
                </>
              ) : (
                <>
                  <Save size={18} /> Save Case Sheet to Patient Record
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
