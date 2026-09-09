import React, { useState, useEffect } from 'react';
import { 
  Sparkles, Upload, FileText, CheckCircle, AlertTriangle, 
  RefreshCw, ShoppingCart, ArrowRight, Save, User, Pill, CheckCircle2 
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import DosageTimingBadge from '../components/DosageTimingBadge';

export default function OCRDecoderPage() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [medicines, setMedicines] = useState([]);
  const navigate = useNavigate();

  // Patient linking & saving
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('new');
  const [patientName, setPatientName] = useState('');
  const [diagnosis, setDiagnosis] = useState('Ayurvedic Clinical Consultation');
  const [advice, setAdvice] = useState('Follow prescribed dosage with warm water.');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');
  const [recentPrescriptions, setRecentPrescriptions] = useState([]);

  // Fetch patients and recent prescriptions
  const loadData = async () => {
    try {
      const [patRes, rxRes] = await Promise.all([
        fetch('/api/patients/list'),
        fetch('/api/prescriptions?limit=5')
      ]);
      if (patRes.ok) {
        const patData = await patRes.json();
        if (patData.success && patData.patients) setPatients(patData.patients);
      }
      if (rxRes.ok) {
        const rxData = await rxRes.json();
        if (rxData.success && rxData.prescriptions) setRecentPrescriptions(rxData.prescriptions);
      }
    } catch (err) {
      console.error('Error loading data for OCR decoder page:', err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileSelect = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      if (selected.size > 5 * 1024 * 1024) {
        setError('File must be 5MB or smaller.');
        return;
      }
      setFile(selected);
      setPreviewUrl(URL.createObjectURL(selected));
      setError('');
      setResult(null);
      setSaveSuccess('');
    }
  };

  const handleDecode = async () => {
    if (!file) {
      setError('Please upload a prescription image or lab report PDF.');
      return;
    }

    setIsLoading(true);
    setError('');
    setSaveSuccess('');

    const formData = new FormData();
    formData.append('prescription_image', file);

    try {
      const res = await fetch('/api/prescription/decode-handwriting', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.success && data.data) {
        setResult(data.data);
        setMedicines(data.data.medicines || []);
        if (data.data.patient_name && !patientName) {
          setPatientName(data.data.patient_name);
        }
        if (data.data.diagnosis) {
          setDiagnosis(data.data.diagnosis);
        }
      } else {
        setError(data.error || data.detail || 'Could not analyze prescription image.');
      }
    } catch (err) {
      console.error('OCR Request Error:', err);
      setError('Failed to process prescription file.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveToCaseSheet = async () => {
    if (!patientName.trim()) {
      setError('Please enter a patient name to save this prescription.');
      return;
    }

    setIsSaving(true);
    setError('');
    setSaveSuccess('');

    try {
      const res = await fetch('/api/prescriptions/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: selectedPatientId !== 'new' ? Number(selectedPatientId) : null,
          patient_name: patientName.trim(),
          diagnosis: diagnosis.trim() || 'Ayurvedic Clinical Consultation',
          advice: advice.trim(),
          medicines: medicines,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setSaveSuccess(`Prescription & Case Sheet successfully saved for ${data.patient?.name || patientName}!`);
        loadData(); // reload recent prescriptions
      } else {
        setError(data.error || data.detail || 'Failed to save prescription.');
      }
    } catch (err) {
      console.error('Error saving prescription:', err);
      setError('Network error saving prescription.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: '1150px', margin: '0 auto', padding: '32px 20px' }}>
      
      {/* Header Banner */}
      <div className="glass-card" style={{ padding: '32px', borderRadius: '24px', marginBottom: '32px', background: 'linear-gradient(135deg, rgba(232, 178, 74, 0.1), rgba(16, 185, 129, 0.1))', border: '1px solid rgba(232, 178, 74, 0.3)' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 14px', borderRadius: '20px', background: 'rgba(232, 178, 74, 0.15)', color: '#E8B24A', fontSize: '0.85rem', fontWeight: '700', marginBottom: '12px' }}>
          <Sparkles size={16} /> Neural-Grade Vision OCR & Case Sheet Recorder
        </div>
        <h1 style={{ fontSize: '2.4rem', fontWeight: '800', margin: '0 0 8px', color: '#F8FAFC' }}>
          AI Prescription Handwriting Reader
        </h1>
        <p style={{ color: '#94A3B8', fontSize: '1rem', margin: 0, maxWidth: '750px' }}>
          Upload any paper prescription, doctor's handwritten notes, or diagnostic report. Our vision AI decodes medicines, dosages, frequencies, and automatically saves them into the patient's Case Sheet.
        </p>
      </div>

      {/* Notifications */}
      {error && (
        <div style={{ padding: '14px 18px', borderRadius: '14px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#F87171', fontSize: '0.9rem', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={18} /> {error}
        </div>
      )}

      {saveSuccess && (
        <div style={{ padding: '14px 18px', borderRadius: '14px', background: 'rgba(16, 185, 129, 0.18)', border: '1px solid rgba(16, 185, 129, 0.4)', color: '#10B981', fontSize: '0.92rem', marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', fontWeight: '700' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={20} /> {saveSuccess}
          </div>
          <button
            onClick={() => navigate('/doctor')}
            className="btn-primary"
            style={{ padding: '6px 14px', fontSize: '0.82rem' }}
          >
            View in Doctor Case Sheets →
          </button>
        </div>
      )}

      {/* Upload Box */}
      {!result ? (
        <div className="glass-card" style={{ padding: '40px', borderRadius: '24px', textAlign: 'center', position: 'relative', border: '2px dashed rgba(16, 185, 129, 0.3)', marginBottom: '40px' }}>
          <input
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileSelect}
            style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
          />

          {previewUrl ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <img src={previewUrl} alt="Prescription preview" style={{ maxHeight: '280px', borderRadius: '14px', border: '1px solid rgba(255, 255, 255, 0.2)' }} />
              <span style={{ color: '#10B981', fontWeight: '700', fontSize: '0.95rem' }}>
                <CheckCircle size={18} style={{ display: 'inline', marginRight: '6px' }} />
                {file?.name} ({(file.size / 1024).toFixed(1)} KB)
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
              <div style={{ width: '68px', height: '68px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'grid', placeItems: 'center' }}>
                <Upload size={32} />
              </div>
              <h3 style={{ margin: 0, fontSize: '1.3rem', fontWeight: '700', color: '#F8FAFC' }}>Drop Handwritten Prescription Image Here</h3>
              <p style={{ color: '#94A3B8', fontSize: '0.9rem', margin: 0 }}>Supports JPG, PNG, WEBP & PDF files up to 5MB</p>
            </div>
          )}

          <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={handleDecode}
              disabled={isLoading || !file}
              className="btn-gold"
              style={{ padding: '14px 36px', fontSize: '1rem', fontWeight: '700', opacity: isLoading || !file ? 0.6 : 1 }}
            >
              {isLoading ? (
                <>
                  <RefreshCw size={18} className="animate-spin" style={{ marginRight: '8px' }} />
                  Processing Handwriting with Vision AI...
                </>
              ) : (
                <>
                  <Sparkles size={18} style={{ marginRight: '8px' }} /> Decode Prescription Now
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* Results Section */
        <div className="glass-card" style={{ padding: '32px', borderRadius: '24px', marginBottom: '40px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <div>
              <span style={{ color: '#10B981', fontWeight: '700', fontSize: '0.85rem' }}>DECODING COMPLETE</span>
              <h2 style={{ fontSize: '1.6rem', fontWeight: '800', margin: '2px 0 0', color: '#F8FAFC' }}>Prescription Details Extracted</h2>
            </div>
            <button
              onClick={() => { setResult(null); setFile(null); setPreviewUrl(''); setSaveSuccess(''); }}
              className="btn-ghost"
              style={{ padding: '10px 18px', fontSize: '0.88rem' }}
            >
              Decode Another File
            </button>
          </div>

          {/* Patient Linking & Case Sheet Form */}
          <div style={{
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: '16px',
            padding: '20px',
            marginBottom: '24px'
          }}>
            <h4 style={{ margin: '0 0 14px', fontSize: '1rem', fontWeight: '800', color: '#10B981', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <User size={18} /> Assign & Save to Patient Case Sheet
            </h4>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', marginBottom: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Select Existing Patient
                </label>
                <select
                  value={selectedPatientId}
                  onChange={(e) => {
                    setSelectedPatientId(e.target.value);
                    if (e.target.value !== 'new') {
                      const p = patients.find(pat => String(pat.id) === String(e.target.value));
                      if (p) setPatientName(p.name);
                    }
                  }}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    background: '#0B1512',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.88rem'
                  }}
                >
                  <option value="new">+ Create / Enter New Patient</option>
                  {patients.map(p => (
                    <option key={p.id} value={p.id}>{p.name} ({p.age}y / {p.gender})</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Patient Full Name
                </label>
                <input
                  type="text"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  placeholder="e.g. Aarav Sharma"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.88rem'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Clinical Diagnosis
                </label>
                <input
                  type="text"
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  placeholder="e.g. Amavata / Rheumatoid Arthritis"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.88rem'
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px' }}>
                Doctor Advice / Intake Instructions
              </label>
              <input
                type="text"
                value={advice}
                onChange={(e) => setAdvice(e.target.value)}
                placeholder="e.g. Take with warm water after meals"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '10px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#F8FAFC',
                  fontSize: '0.88rem'
                }}
              />
            </div>
          </div>

          {/* Medicines Catalog */}
          <h3 style={{ fontSize: '1.2rem', fontWeight: '700', marginBottom: '16px' }}>
            Decoded Medicines Catalog ({medicines.length})
          </h3>
          <div style={{ overflowX: 'auto', marginBottom: '28px', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '14px', padding: '12px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8', textAlign: 'left' }}>
                  <th style={{ padding: '10px 14px' }}>Medicine</th>
                  <th style={{ padding: '10px 14px' }}>Dosage</th>
                  <th style={{ padding: '10px 14px' }}>Frequency</th>
                  <th style={{ padding: '10px 14px' }}>Duration</th>
                  <th style={{ padding: '10px 14px' }}>Instructions</th>
                </tr>
              </thead>
              <tbody>
                {medicines.map((m, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '12px 14px', fontWeight: '700', color: '#F8FAFC' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Pill size={15} color="#10B981" />
                        {m.medicine_name}
                      </div>
                    </td>
                    <td style={{ padding: '12px 14px', color: '#CBD5E1' }}>{m.dosage || '1 unit'}</td>
                    <td style={{ padding: '12px 14px' }}>
                      <DosageTimingBadge frequency={m.frequency || '1-0-1'} />
                    </td>
                    <td style={{ padding: '12px 14px', color: '#CBD5E1' }}>{m.duration || '5 days'}</td>
                    <td style={{ padding: '12px 14px', color: '#94A3B8' }}>{m.instructions || 'After meals'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '14px', flexWrap: 'wrap' }}>
            <button
              onClick={handleSaveToCaseSheet}
              disabled={isSaving || medicines.length === 0}
              className="btn-primary"
              style={{ padding: '12px 28px', fontSize: '0.95rem', fontWeight: '700' }}
            >
              <Save size={18} style={{ marginRight: '8px' }} />
              {isSaving ? 'Saving to Case Sheet...' : 'Save to Patient Case Sheet'}
            </button>

            <button
              onClick={() => navigate('/order-medicines')}
              className="btn-gold"
              style={{ padding: '12px 28px', fontSize: '0.95rem', fontWeight: '700' }}
            >
              <ShoppingCart size={18} style={{ marginRight: '8px' }} /> Order Medicines from Pharmacy Store
            </button>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* RECENT SAVED PRESCRIPTIONS & CASE SHEETS ARCHIVE */}
      {/* ======================================================== */}
      <div className="glass-card" style={{ padding: '28px', borderRadius: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: '800', margin: 0, color: '#F8FAFC' }}>
              Recently Saved Prescriptions & Cases
            </h3>
            <span style={{ fontSize: '0.82rem', color: '#94A3B8' }}>
              Verified clinical records persisted into the EMR database
            </span>
          </div>
          <button
            onClick={() => navigate('/doctor')}
            className="btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.82rem' }}
          >
            Open Full Doctor Case Sheet Portal →
          </button>
        </div>

        {recentPrescriptions.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {recentPrescriptions.map((rx) => (
              <div 
                key={rx.id} 
                style={{ 
                  padding: '16px 20px', 
                  borderRadius: '14px', 
                  background: 'rgba(255, 255, 255, 0.03)', 
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <strong style={{ color: '#F8FAFC', fontSize: '1rem' }}>{rx.patient_name}</strong>
                    <span style={{ padding: '2px 8px', borderRadius: '12px', background: 'rgba(232, 178, 74, 0.12)', color: '#E8B24A', fontSize: '0.75rem', fontWeight: '700' }}>
                      {rx.diagnosis}
                    </span>
                  </div>
                  <span style={{ color: '#94A3B8', fontSize: '0.8rem', display: 'block', marginTop: '4px' }}>
                    {rx.medicine_count} medicines • {rx.date_str || 'Recent'}
                  </span>
                </div>

                <button
                  onClick={() => navigate('/doctor')}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '8px',
                    background: 'rgba(16, 185, 129, 0.12)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    color: '#10B981',
                    fontSize: '0.8rem',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                >
                  View Case Sheet
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: '#94A3B8', margin: 0, fontSize: '0.9rem' }}>
            No saved prescriptions yet. Upload and decode a prescription above to save your first case sheet.
          </p>
        )}
      </div>

    </div>
  );
}
