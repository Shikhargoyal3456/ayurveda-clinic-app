import React, { useState, useEffect } from 'react';
import { 
  X, Upload, Sparkles, AlertTriangle, CheckCircle, FileText, 
  Plus, ShoppingCart, RefreshCw, Save, User, CheckCircle2 
} from 'lucide-react';
import DosageTimingBadge from './DosageTimingBadge';

export default function PrescriptionReaderModal({ 
  isOpen, 
  onClose, 
  onAddMedicinesToCart, 
  onPrescriptionSaved,
  initialPatientId = null 
}) {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [editableMedicines, setEditableMedicines] = useState([]);

  // Patient assignment & saving states
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('new');
  const [patientName, setPatientName] = useState('');
  const [patientAge, setPatientAge] = useState(35);
  const [patientGender, setPatientGender] = useState('Male');
  const [diagnosis, setDiagnosis] = useState('Ayurvedic Clinical Consultation');
  const [clinicalAdvice, setClinicalAdvice] = useState('Take medicines after meals with warm water.');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');

  // Fetch active patients list
  useEffect(() => {
    if (isOpen) {
      fetch('/api/patients/list')
        .then(res => res.json())
        .then(data => {
          if (data.success && data.patients) {
            setPatients(data.patients);
            if (initialPatientId) {
              const matched = data.patients.find(p => String(p.id) === String(initialPatientId));
              if (matched) {
                setSelectedPatientId(String(matched.id));
                setPatientName(matched.name);
                setPatientAge(matched.age || 35);
                setPatientGender(matched.gender || 'Other');
                return;
              }
            }
            setSelectedPatientId('new');
            setPatientName('');
          }
        })
        .catch(err => console.error('Error fetching patients:', err));
    }
  }, [isOpen, initialPatientId]);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (selectedFile.size > 5 * 1024 * 1024) {
        setError('File size must be 5MB or smaller.');
        return;
      }
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setError('');
      setResult(null);
      setSaveSuccess('');
    }
  };

  const handleAnalyzePrescription = async () => {
    if (!file) {
      setError('Please select or drag a prescription file first.');
      return;
    }

    setIsLoading(true);
    setError('');
    setSaveSuccess('');

    const formData = new FormData();
    formData.append('prescription_image', file);

    try {
      const response = await fetch('/api/prescription/decode-handwriting', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': document.cookie.split('; ').find(row => row.startsWith('csrf_access_token='))?.split('=')[1] || ''
        },
        body: formData,
      });

      const data = await response.json();
      if (response.ok && data.success && data.data) {
        setResult(data.data);
        setEditableMedicines(data.data.medicines || []);
        if (data.data.patient_name && !patientName) {
          setPatientName(data.data.patient_name);
        }
        if (data.data.diagnosis) {
          setDiagnosis(data.data.diagnosis);
        }
        if (data.data.clinical_advice) {
          setClinicalAdvice(data.data.clinical_advice);
        }
      } else {
        if (data.detail && typeof data.detail === 'string' && data.detail.includes('login')) {
          setError('Please log in to use the AI prescription reader.');
        } else {
          setError(data.error || data.detail || 'Could not analyze prescription. Please try a clearer image.');
        }
      }
    } catch (err) {
      console.error('Prescription OCR request error:', err);
      setError('Network error while analyzing prescription.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMedicineChange = (index, field, value) => {
    const updated = [...editableMedicines];
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      updated[index][parent] = { ...updated[index][parent], [child]: value };
    } else {
      updated[index][field] = value;
    }
    setEditableMedicines(updated);
  };

  const handleRemoveMedicine = (index) => {
    setEditableMedicines(prev => prev.filter((_, i) => i !== index));
  };

  const handleAddMedicineRow = () => {
    setEditableMedicines(prev => [
      ...prev,
      { medicine_name: 'New Medicine', dosage: '1 unit', frequency: '1-0-1', duration: '7 days', instructions: 'After meals' }
    ]);
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

  const handleSaveToCaseSheet = async () => {
    if (!patientName.trim()) {
      setError('Please provide a patient name to save this prescription to their case sheet.');
      return;
    }

    if (editableMedicines.length === 0) {
      setError('Please include at least one medicine in the prescription.');
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
          patient_age: Number(patientAge) || 35,
          patient_gender: patientGender,
          diagnosis: diagnosis.trim() || 'Ayurvedic Clinical Consultation',
          advice: clinicalAdvice.trim(),
          medicines: editableMedicines,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setSaveSuccess(`Prescription & Case Sheet successfully saved for ${data.patient?.name || patientName}!`);
        if (onPrescriptionSaved) {
          onPrescriptionSaved();
        }
      } else {
        setError(data.error || data.detail || 'Failed to save prescription and case sheet.');
      }
    } catch (err) {
      console.error('Error saving prescription:', err);
      setError('Network error saving prescription.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddToCart = () => {
    if (onAddMedicinesToCart && editableMedicines.length > 0) {
      onAddMedicinesToCart(editableMedicines);
      onClose();
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 1000,
      background: 'rgba(11, 21, 18, 0.88)',
      backdropFilter: 'blur(12px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div className="glass-card" style={{
        width: '100%',
        maxWidth: '900px',
        maxHeight: '92vh',
        overflowY: 'auto',
        borderRadius: '24px',
        padding: '30px',
        position: 'relative',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.75)',
        border: '1px solid rgba(16, 185, 129, 0.25)',
        background: 'rgba(11, 21, 18, 0.95)'
      }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            background: 'rgba(255, 255, 255, 0.08)',
            border: 'none',
            color: '#94A3B8',
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <X size={20} />
        </button>

        {/* Title Header */}
        <div style={{ marginBottom: '24px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 12px',
            borderRadius: '20px',
            background: 'rgba(232, 178, 74, 0.15)',
            color: '#E8B24A',
            fontSize: '0.8rem',
            fontWeight: '700',
            marginBottom: '8px'
          }}>
            <Sparkles size={14} /> AI Vision OCR & Case Sheet Recorder
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: '800', margin: 0, color: '#F8FAFC' }}>
            Prescription Handwriting Reader & Case Sheet
          </h2>
          <p style={{ margin: '4px 0 0', color: '#94A3B8', fontSize: '0.88rem' }}>
            Decode handwritten doctor prescriptions with Gemini Vision, verify medicines, and persist directly into the patient's Case Sheet.
          </p>
        </div>

        {/* Status Messages */}
        {error && (
          <div style={{ padding: '12px 16px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#F87171', fontSize: '0.88rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {saveSuccess && (
          <div style={{ padding: '12px 16px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.18)', border: '1px solid rgba(16, 185, 129, 0.4)', color: '#10B981', fontSize: '0.88rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '700' }}>
            <CheckCircle2 size={18} /> {saveSuccess}
          </div>
        )}

        {/* State 1: Upload Form */}
        {!result ? (
          <div>
            <div style={{
              border: '2px dashed rgba(16, 185, 129, 0.3)',
              borderRadius: '16px',
              padding: '36px',
              textAlign: 'center',
              background: 'rgba(0, 0, 0, 0.25)',
              position: 'relative',
              cursor: 'pointer'
            }}>
              <input
                type="file"
                accept="image/*,.pdf"
                onChange={handleFileChange}
                style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
              />
              {previewUrl ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                  <img src={previewUrl} alt="Prescription" style={{ maxHeight: '220px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.1)' }} />
                  <span style={{ color: '#10B981', fontWeight: '700', fontSize: '0.88rem' }}>
                    <CheckCircle size={16} style={{ display: 'inline', marginRight: '6px' }} />
                    {file?.name} ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '54px', height: '54px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Upload size={24} />
                  </div>
                  <div>
                    <strong style={{ color: '#F8FAFC', fontSize: '1.05rem', display: 'block' }}>Choose prescription image or take photo</strong>
                    <span style={{ color: '#94A3B8', fontSize: '0.82rem' }}>Supports JPG, PNG, WEBP, PDF up to 5MB</span>
                  </div>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px', gap: '12px' }}>
              <button onClick={onClose} className="btn-ghost" style={{ padding: '10px 18px' }}>
                Cancel
              </button>
              <button
                onClick={handleAnalyzePrescription}
                disabled={isLoading || !file}
                className="btn-gold"
                style={{ padding: '12px 24px', opacity: isLoading || !file ? 0.6 : 1 }}
              >
                {isLoading ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" style={{ marginRight: '8px' }} />
                    Decoding Prescription Handwriting with Vision AI...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} style={{ marginRight: '8px' }} />
                    Decode Prescription
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          /* State 2: Extracted Results & Save to Case Sheet */
          <div>
            {/* Patient Linking & Case Sheet Form */}
            <div style={{
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              borderRadius: '16px',
              padding: '18px',
              marginBottom: '20px'
            }}>
              <h4 style={{ margin: '0 0 12px', fontSize: '0.95rem', fontWeight: '800', color: '#10B981', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <User size={16} /> Link to Patient Case Sheet
              </h4>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Select Patient
                  </label>
                  <select
                    value={selectedPatientId}
                    onChange={handlePatientSelectChange}
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      background: '#0B1512',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#F8FAFC',
                      fontSize: '0.85rem'
                    }}
                  >
                    <option value="new">+ Create New Patient</option>
                    {patients.map(p => (
                      <option key={p.id} value={p.id}>{p.name} ({p.age}y / {p.gender})</option>
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
                      padding: '8px 10px',
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
                    Diagnosis
                  </label>
                  <input
                    type="text"
                    value={diagnosis}
                    onChange={(e) => setDiagnosis(e.target.value)}
                    placeholder="e.g. Amavata / Rheumatoid Arthritis"
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      background: 'rgba(0, 0, 0, 0.3)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#F8FAFC',
                      fontSize: '0.85rem'
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Doctor Clinical Advice / Instructions
                </label>
                <input
                  type="text"
                  value={clinicalAdvice}
                  onChange={(e) => setClinicalAdvice(e.target.value)}
                  placeholder="e.g. Take with warm water after meals, avoid cold food"
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#F8FAFC',
                    fontSize: '0.85rem'
                  }}
                />
              </div>
            </div>

            {/* Extracted Medicines Catalog */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: '800', color: '#F8FAFC' }}>
                Extracted Medicines ({editableMedicines.length})
              </h4>
              <button
                onClick={handleAddMedicineRow}
                style={{
                  background: 'rgba(16, 185, 129, 0.12)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  color: '#10B981',
                  padding: '4px 10px',
                  borderRadius: '8px',
                  fontSize: '0.78rem',
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

            <div style={{ overflowX: 'auto', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '12px', padding: '10px', marginBottom: '20px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8', textAlign: 'left' }}>
                    <th style={{ padding: '8px 10px' }}>Medicine</th>
                    <th style={{ padding: '8px 10px' }}>Dosage</th>
                    <th style={{ padding: '8px 10px' }}>Frequency</th>
                    <th style={{ padding: '8px 10px' }}>Duration</th>
                    <th style={{ padding: '8px 10px' }}>Instructions</th>
                    <th style={{ padding: '8px 10px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {editableMedicines.map((med, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '6px 10px' }}>
                        <input
                          type="text"
                          value={med.medicine_name}
                          onChange={(e) => handleMedicineChange(idx, 'medicine_name', e.target.value)}
                          style={{ width: '100%', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC', fontWeight: '700' }}
                        />
                      </td>
                      <td style={{ padding: '6px 10px' }}>
                        <input
                          type="text"
                          value={typeof med.dosage === 'string' ? med.dosage : (med.dosage_text || (med.dosage?.amount ? `${med.dosage.amount} ${med.dosage?.unit || ''}`.trim() : ''))}
                          onChange={(e) => handleMedicineChange(idx, 'dosage', e.target.value)}
                          style={{ width: '80px', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC' }}
                        />
                      </td>
                      <td style={{ padding: '6px 10px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <input
                            type="text"
                            value={med.frequency || ''}
                            onChange={(e) => handleMedicineChange(idx, 'frequency', e.target.value)}
                            placeholder="e.g. 1-0-1"
                            style={{ width: '90px', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC' }}
                          />
                          <DosageTimingBadge frequency={med.frequency || '1-0-1'} compact={true} />
                        </div>
                      </td>
                      <td style={{ padding: '6px 10px' }}>
                        <input
                          type="text"
                          value={med.duration || ''}
                          onChange={(e) => handleMedicineChange(idx, 'duration', e.target.value)}
                          style={{ width: '80px', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC' }}
                        />
                      </td>
                      <td style={{ padding: '6px 10px' }}>
                        <input
                          type="text"
                          value={med.instructions || med.special_instructions || ''}
                          onChange={(e) => handleMedicineChange(idx, 'instructions', e.target.value)}
                          style={{ width: '100%', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#F8FAFC' }}
                        />
                      </td>
                      <td style={{ padding: '6px 10px' }}>
                        <button
                          onClick={() => handleRemoveMedicine(idx)}
                          style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer' }}
                          title="Remove medicine"
                        >
                          <X size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Bottom Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <button
                onClick={() => { setResult(null); setFile(null); setPreviewUrl(''); setSaveSuccess(''); }}
                className="btn-ghost"
                style={{ padding: '10px 18px', fontSize: '0.85rem' }}
              >
                Upload Different File
              </button>

              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  onClick={handleSaveToCaseSheet}
                  disabled={isSaving || editableMedicines.length === 0}
                  className="btn-primary"
                  style={{ padding: '12px 24px', fontSize: '0.9rem', fontWeight: '700' }}
                >
                  <Save size={16} style={{ marginRight: '6px' }} />
                  {isSaving ? 'Saving to Case Sheet...' : 'Save to Patient Case Sheet'}
                </button>

                <button
                  onClick={handleAddToCart}
                  disabled={editableMedicines.length === 0}
                  className="btn-gold"
                  style={{ padding: '12px 20px', fontSize: '0.9rem', fontWeight: '700' }}
                >
                  <ShoppingCart size={16} style={{ marginRight: '6px' }} />
                  Add to Cart ({editableMedicines.length})
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
