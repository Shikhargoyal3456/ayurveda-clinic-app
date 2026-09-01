import React, { useState } from 'react';
import { X, Upload, Sparkles, AlertTriangle, CheckCircle, FileText, Plus, ShoppingCart, RefreshCw } from 'lucide-react';

export default function PrescriptionReaderModal({ isOpen, onClose, onAddMedicinesToCart }) {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [editableMedicines, setEditableMedicines] = useState([]);

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
    }
  };

  const handleAnalyzePrescription = async () => {
    if (!file) {
      setError('Please select or drag a prescription file first.');
      return;
    }

    setIsLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('prescription_image', file);

    try {
      const response = await fetch('/api/prescription/decode-handwriting', {
        method: 'POST',
        headers: {
          // CSRF token if cookie present
          'X-CSRF-Token': document.cookie.split('; ').find(row => row.startsWith('csrf_access_token='))?.split('=')[1] || ''
        },
        body: formData,
      });

      const data = await response.json();
      if (response.ok && data.success && data.data) {
        setResult(data.data);
        setEditableMedicines(data.data.medicines || []);
      } else {
        // Fallback / error response handling
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
      background: 'rgba(11, 21, 18, 0.85)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div className="glass-card" style={{
        width: '100%',
        maxWidth: '850px',
        maxHeight: '90vh',
        overflowY: 'auto',
        borderRadius: '20px',
        padding: '28px',
        position: 'relative',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
        border: '1px solid rgba(255, 255, 255, 0.15)'
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
            border: '1px solid rgba(232, 178, 74, 0.3)',
            color: '#E8B24A',
            fontSize: '0.8rem',
            fontWeight: '600',
            marginBottom: '10px'
          }}>
            <Sparkles size={14} /> AI Prescription OCR & Handwriting Reader
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: '800', margin: '0 0 6px', color: '#F8FAFC' }}>
            Upload Prescription
          </h2>
          <p style={{ color: '#94A3B8', fontSize: '0.9rem', margin: 0 }}>
            Upload an image or PDF of doctor's handwritten/printed prescription to automatically extract medicines & dosage.
          </p>
        </div>

        {/* Upload Zone */}
        {!result && (
          <div style={{
            border: '2px dashed rgba(255, 255, 255, 0.2)',
            borderRadius: '16px',
            padding: '32px 20px',
            textAlign: 'center',
            background: 'rgba(255, 255, 255, 0.02)',
            marginBottom: '20px',
            position: 'relative'
          }}>
            <input
              type="file"
              accept="image/*,.pdf"
              onChange={handleFileChange}
              style={{
                position: 'absolute',
                inset: 0,
                opacity: 0,
                cursor: 'pointer',
                width: '100%',
                height: '100%'
              }}
            />
            {previewUrl ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                <img
                  src={previewUrl}
                  alt="Prescription preview"
                  style={{ maxHeight: '200px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.15)' }}
                />
                <span style={{ fontSize: '0.85rem', color: '#10B981', fontWeight: '600' }}>
                  <CheckCircle size={16} style={{ display: 'inline', marginRight: '6px' }} />
                  {file?.name} Selected ({(file.size / 1024).toFixed(1)} KB)
                </span>
                <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Click or drop another file to replace</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'grid', placeItems: 'center' }}>
                  <Upload size={24} />
                </div>
                <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700', color: '#F8FAFC' }}>
                  Drag & Drop Prescription Image / PDF
                </h4>
                <p style={{ margin: 0, color: '#94A3B8', fontSize: '0.85rem' }}>
                  Supports JPG, PNG, WEBP & PDF (Max 5MB)
                </p>
              </div>
            )}
          </div>
        )}

        {/* Error message */}
        {error && (
          <div style={{
            padding: '12px 16px',
            borderRadius: '10px',
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#F87171',
            fontSize: '0.88rem',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle size={18} /> {error}
          </div>
        )}

        {/* Submit Button */}
        {!result && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <button
              onClick={onClose}
              className="btn-ghost"
              style={{ padding: '10px 20px', fontSize: '0.9rem' }}
            >
              Cancel
            </button>
            <button
              onClick={handleAnalyzePrescription}
              disabled={isLoading || !file}
              className="btn-gold"
              style={{ padding: '10px 24px', fontSize: '0.9rem', opacity: isLoading || !file ? 0.6 : 1 }}
            >
              {isLoading ? (
                <>
                  <RefreshCw size={16} className="animate-spin" style={{ marginRight: '6px' }} />
                  Analyzing Prescription with AI...
                </>
              ) : (
                <>
                  <Sparkles size={16} style={{ marginRight: '6px' }} /> Read Prescription
                </>
              )}
            </button>
          </div>
        )}

        {/* Decoded Results Display */}
        {result && (
          <div>
            {/* Metadata Info */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '12px',
              marginBottom: '20px',
              padding: '16px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase' }}>Doctor</span>
                <p style={{ margin: '2px 0 0', fontWeight: '700', color: '#F8FAFC' }}>{result.doctor_name || "Doctor Not Specified"}</p>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase' }}>Patient</span>
                <p style={{ margin: '2px 0 0', fontWeight: '700', color: '#F8FAFC' }}>{result.patient_name || "Self"}</p>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase' }}>Prescription Date</span>
                <p style={{ margin: '2px 0 0', fontWeight: '700', color: '#F8FAFC' }}>{result.date || "Recent"}</p>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#94A3B8', textTransform: 'uppercase' }}>AI Confidence</span>
                <p style={{ margin: '2px 0 0', fontWeight: '700', color: result.confidence_overall > 70 ? '#10B981' : '#E8B24A' }}>
                  {result.confidence_overall || 85}% Match
                </p>
              </div>
            </div>

            {/* Warning if unreadable parts */}
            {result.unreadable_parts && result.unreadable_parts.length > 0 && (
              <div style={{
                padding: '12px 16px',
                borderRadius: '10px',
                background: 'rgba(234, 179, 8, 0.12)',
                border: '1px solid rgba(234, 179, 8, 0.3)',
                color: '#FACC15',
                fontSize: '0.85rem',
                marginBottom: '16px'
              }}>
                <strong>Verification Note:</strong> {result.unreadable_parts.join(', ')}
              </div>
            )}

            {/* Extracted Medicines List Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: '700' }}>
                Extracted Medicines ({editableMedicines.length})
              </h3>
              <button
                onClick={() => setEditableMedicines(prev => [...prev, { medicine_name: '', dosage: { amount: '1', unit: 'tablet', frequency: 'Twice daily' }, confidence: 100 }])}
                style={{ background: 'none', border: 'none', color: '#10B981', fontSize: '0.85rem', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                <Plus size={14} /> Add Item Manually
              </button>
            </div>

            {/* Table of Medicines */}
            <div style={{ overflowX: 'auto', marginBottom: '24px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94A3B8', textAlign: 'left' }}>
                    <th style={{ padding: '8px 12px' }}>Medicine Name</th>
                    <th style={{ padding: '8px 12px' }}>Dosage & Unit</th>
                    <th style={{ padding: '8px 12px' }}>Frequency</th>
                    <th style={{ padding: '8px 12px' }}>Confidence</th>
                    <th style={{ padding: '8px 12px', width: '50px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {editableMedicines.map((med, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '8px 12px' }}>
                        <input
                          type="text"
                          value={med.medicine_name || ''}
                          onChange={(e) => handleMedicineChange(idx, 'medicine_name', e.target.value)}
                          placeholder="Medicine name..."
                          style={{
                            width: '100%',
                            padding: '6px 10px',
                            borderRadius: '8px',
                            background: 'rgba(255,255,255,0.05)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            color: '#F8FAFC'
                          }}
                        />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input
                          type="text"
                          value={typeof med.dosage === 'object' ? `${med.dosage?.amount || ''} ${med.dosage?.unit || ''}`.trim() : (med.dosage || '')}
                          onChange={(e) => handleMedicineChange(idx, 'dosage_text', e.target.value)}
                          placeholder="e.g. 1 tablet / 1 tsp"
                          style={{
                            width: '100%',
                            padding: '6px 10px',
                            borderRadius: '8px',
                            background: 'rgba(255,255,255,0.05)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            color: '#F8FAFC'
                          }}
                        />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <input
                          type="text"
                          value={med.frequency || (med.dosage?.frequency) || 'Twice daily'}
                          onChange={(e) => handleMedicineChange(idx, 'frequency', e.target.value)}
                          placeholder="e.g. Twice daily"
                          style={{
                            width: '100%',
                            padding: '6px 10px',
                            borderRadius: '8px',
                            background: 'rgba(255,255,255,0.05)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            color: '#F8FAFC'
                          }}
                        />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontSize: '0.75rem',
                          fontWeight: '700',
                          background: (med.confidence || 80) >= 75 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(234, 179, 8, 0.15)',
                          color: (med.confidence || 80) >= 75 ? '#10B981' : '#FACC15'
                        }}>
                          {med.confidence || 80}%
                        </span>
                      </td>
                      <td style={{ padding: '8px 12px' }}>
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                onClick={() => { setResult(null); setFile(null); setPreviewUrl(''); }}
                className="btn-ghost"
                style={{ padding: '10px 18px', fontSize: '0.85rem' }}
              >
                Upload Different File
              </button>
              <button
                onClick={handleAddToCart}
                disabled={editableMedicines.length === 0}
                className="btn-gold"
                style={{ padding: '12px 24px', fontSize: '0.92rem', fontWeight: '700' }}
              >
                <ShoppingCart size={18} style={{ marginRight: '8px' }} />
                Add Extracted Medicines to Cart ({editableMedicines.length})
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
