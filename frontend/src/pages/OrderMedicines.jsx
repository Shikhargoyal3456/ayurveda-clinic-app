import React, { useState, useEffect } from 'react';
import { Search, Pill, Bot, ShoppingCart, Sparkles, Check, Upload, Trash2, ArrowRight, Loader2, Info } from 'lucide-react';
import VoiceMicInput from '../components/VoiceMicInput';
import PrescriptionReaderModal from '../components/PrescriptionReaderModal';

export default function OrderMedicines() {
  const [query, setQuery] = useState('');
  const [medicines, setMedicines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cart, setCart] = useState({});
  const [isPrescriptionModalOpen, setIsPrescriptionModalOpen] = useState(false);
  const [aiSuggesting, setAiSuggesting] = useState(false);
  const [aiNotes, setAiNotes] = useState(null);
  const [orderSuccess, setOrderSuccess] = useState(false);

  // Fetch real medicine database
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    fetch(`/prescription/medicine-db?q=${encodeURIComponent(query)}&limit=30`)
      .then(res => res.json())
      .then(data => {
        if (!isMounted) return;
        if (data.success && Array.isArray(data.data) && data.data.length > 0) {
          const formatted = data.data.map((item, idx) => ({
            id: item.id || idx + 1,
            name: item.name,
            category: item.category || item.classification || "Ayurvedic Formulation",
            price: item.price || (120 + (idx * 25) % 300),
            description: item.generic_name 
              ? `Generic: ${item.generic_name}. Typical dosage: ${item.typical_dosages?.join(', ') || 'As directed by physician'}.`
              : `Classical formulation supporting holistic wellness and vitality.`,
            dosages: item.typical_dosages || [],
            frequencies: item.common_frequencies || []
          }));
          setMedicines(formatted);
        } else {
          setMedicines([]);
        }
      })
      .catch(err => {
        console.error("Error fetching medicine database:", err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => { isMounted = false; };
  }, [query]);

  const handleVoiceTranscript = (transcriptText) => {
    setQuery(transcriptText);
  };

  const handleAddMedicinesFromPrescription = (extractedMedicines) => {
    const updatedCart = { ...cart };
    extractedMedicines.forEach(med => {
      const name = med.medicine_name || "Prescribed Medicine";
      const key = name.toLowerCase();
      const dosageStr = typeof med.dosage === 'object' 
        ? `${med.dosage?.amount || ''} ${med.dosage?.unit || ''}`.trim() 
        : (med.dosage || '');
      
      updatedCart[key] = {
        name,
        dosage: dosageStr || 'As prescribed',
        frequency: med.frequency || 'Daily',
        price: 250,
        qty: (updatedCart[key]?.qty || 0) + 1
      };
    });
    setCart(updatedCart);
  };

  const addToCart = (med) => {
    const key = med.name.toLowerCase();
    setCart(prev => ({
      ...prev,
      [key]: {
        name: med.name,
        dosage: med.dosages[0] || '1 tablet',
        frequency: 'Twice daily',
        price: med.price,
        qty: (prev[key]?.qty || 0) + 1
      }
    }));
  };

  const removeFromCart = (key) => {
    setCart(prev => {
      const copy = { ...prev };
      delete copy[key];
      return copy;
    });
  };

  const updateQuantity = (key, delta) => {
    setCart(prev => {
      if (!prev[key]) return prev;
      const newQty = prev[key].qty + delta;
      if (newQty <= 0) {
        const copy = { ...prev };
        delete copy[key];
        return copy;
      }
      return { ...prev, [key]: { ...prev[key], qty: newQty } };
    });
  };

  const handleAiRemedyFinder = async () => {
    if (!query.trim()) {
      alert("Please type or speak your symptoms into the search bar first!");
      return;
    }

    setAiSuggesting(true);
    setAiNotes(null);

    try {
      const formData = new FormData();
      formData.append('symptoms', query);

      const res = await fetch('/order-medicines/ai-suggest', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': document.cookie.split('; ').find(row => row.startsWith('csrf_access_token='))?.split('=')[1] || ''
        },
        body: formData
      });
      const data = await res.json();
      if (data.suggested_medicines && data.suggested_medicines.length > 0) {
        setAiNotes(data);
      }
    } catch (err) {
      console.error("AI Remedy search failed:", err);
    } finally {
      setAiSuggesting(false);
    }
  };

  const cartItems = Object.entries(cart);
  const cartTotal = cartItems.reduce((acc, [_, item]) => acc + (item.price * item.qty), 0);

  const handlePlaceOrder = () => {
    setOrderSuccess(true);
    setTimeout(() => {
      setCart({});
      setOrderSuccess(false);
    }, 4000);
  };

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px' }}>
      {/* Header Banner */}
      <section className="glass-card" style={{ padding: '28px', marginBottom: '24px', borderRadius: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 12px', borderRadius: '20px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#10B981', fontSize: '0.8rem', fontWeight: '600', marginBottom: '12px' }}>
              <Sparkles size={14} /> AI-Powered Medicine & Pharmacy Store
            </div>
            <h1 style={{ fontSize: '2.2rem', fontWeight: '800', margin: '0 0 8px', color: '#F8FAFC' }}>Ayurvedic Medicine Store</h1>
            <p style={{ color: '#94A3B8', margin: 0, fontSize: '0.95rem' }}>
              Search classical formulations, speak symptoms via Mic, or upload prescription to auto-extract medicines.
            </p>
          </div>

          <button
            onClick={() => setIsPrescriptionModalOpen(true)}
            className="btn-gold"
            style={{ padding: '12px 22px', fontSize: '0.92rem' }}
          >
            <Upload size={18} style={{ marginRight: '8px' }} /> Upload Prescription (AI Reader)
          </button>
        </div>

        {/* Search & Voice Mic Input */}
        <div style={{ marginTop: '24px', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, position: 'relative', minWidth: '280px' }}>
            <Search size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
            <input 
              type="text" 
              placeholder="Search formulation or speak symptoms (e.g. Ashwagandha, Triphala, Digestion)..." 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ width: '100%', padding: '12px 52px 12px 48px', borderRadius: '14px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', color: 'white', fontSize: '0.95rem', outline: 'none' }}
            />
            {/* Voice Mic Button embedded inside search input */}
            <div style={{ position: 'absolute', right: '6px', top: '50%', transform: 'translateY(-50%)' }}>
              <VoiceMicInput onTranscript={handleVoiceTranscript} />
            </div>
          </div>

          <button 
            onClick={handleAiRemedyFinder}
            disabled={aiSuggesting}
            className="btn-ghost" 
            style={{ padding: '12px 20px', minHeight: '48px' }}
          >
            {aiSuggesting ? <Loader2 size={16} className="animate-spin" /> : <Bot size={18} />}
            <span style={{ marginLeft: '6px' }}>Ask AI Remedy Finder</span>
          </button>
        </div>

        {/* AI Recommendations Panel */}
        {aiNotes && (
          <div style={{
            marginTop: '20px',
            padding: '18px',
            borderRadius: '14px',
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            color: '#F8FAFC'
          }}>
            <h4 style={{ margin: '0 0 10px', fontSize: '1rem', color: '#10B981', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={16} /> AI Suggested Medicines for "{query}"
            </h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
              {aiNotes.suggested_medicines.map((item, i) => (
                <span key={i} onClick={() => setQuery(item)} style={{ cursor: 'pointer', background: 'rgba(16, 185, 129, 0.2)', color: '#10B981', padding: '4px 12px', borderRadius: '16px', fontSize: '0.85rem', fontWeight: '600' }}>
                  + {item}
                </span>
              ))}
            </div>
            {aiNotes.precautions && aiNotes.precautions.length > 0 && (
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#94A3B8' }}>
                <Info size={14} style={{ display: 'inline', marginRight: '4px' }} />
                {aiNotes.precautions.join(' ')}
              </p>
            )}
          </div>
        )}
      </section>

      {/* Main Content Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: cartItems.length > 0 ? '1fr 340px' : '1fr', gap: '24px' }}>
        
        {/* Medicine Catalog Grid */}
        <div>
          {loading ? (
            <div style={{ padding: '60px', textAlign: 'center', color: '#94A3B8' }}>
              <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto 12px', color: '#10B981' }} />
              <p>Loading real medicine database...</p>
            </div>
          ) : medicines.length === 0 ? (
            <div className="glass-card" style={{ padding: '40px', textAlign: 'center', color: '#94A3B8' }}>
              <Pill size={40} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
              <h3>No matching medicines found</h3>
              <p>Try searching for another formulation or speak into the microphone.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}>
              {medicines.map((item) => {
                const key = item.name.toLowerCase();
                const inCart = !!cart[key];

                return (
                  <div key={item.id} className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', borderRadius: '16px' }}>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                        <div style={{ width: '42px', height: '42px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Pill size={22} />
                        </div>
                        <span className="badge badge-emerald" style={{ fontSize: '0.75rem' }}>{item.category}</span>
                      </div>
                      <h3 style={{ fontSize: '1.15rem', fontWeight: '700', margin: '0 0 6px', color: '#F8FAFC' }}>{item.name}</h3>
                      <p style={{ color: '#94A3B8', fontSize: '0.85rem', lineHeight: '1.5', marginBottom: '20px' }}>{item.description}</p>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                      <span style={{ fontSize: '1.3rem', fontWeight: '800', color: '#F8FAFC' }}>₹{item.price}</span>
                      <button 
                        className={inCart ? "btn-secondary" : "btn-primary"} 
                        onClick={() => addToCart(item)}
                        style={{ padding: '8px 16px', fontSize: '0.85rem', borderRadius: '20px' }}
                      >
                        {inCart ? (
                          <><Check size={14} style={{ color: '#10B981', marginRight: '4px' }} /> Added ({cart[key].qty})</>
                        ) : (
                          <><ShoppingCart size={14} style={{ marginRight: '4px' }} /> Add to Cart</>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cart Sidebar */}
        {cartItems.length > 0 && (
          <aside className="glass-card" style={{ padding: '24px', height: 'fit-content', borderRadius: '20px', position: 'sticky', top: '20px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1.15rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShoppingCart size={20} style={{ color: '#10B981' }} /> My Medicine Order ({cartItems.length})
            </h3>

            {orderSuccess ? (
              <div style={{ padding: '20px', background: 'rgba(16, 185, 129, 0.15)', borderRadius: '12px', textStyle: 'center', color: '#10B981', textAlign: 'center' }}>
                <Check size={32} style={{ margin: '0 auto 8px' }} />
                <h4 style={{ margin: '0 0 4px', color: 'white' }}>Order Placed Successfully!</h4>
                <p style={{ margin: 0, fontSize: '0.85rem' }}>Your Ayurvedic medicines are being prepared for dispatch.</p>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px', maxHeight: '350px', overflowY: 'auto' }}>
                  {cartItems.map(([key, item]) => (
                    <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                      <div>
                        <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: '700', color: '#F8FAFC' }}>{item.name}</h4>
                        <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>{item.dosage} • ₹{item.price}</span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <button onClick={() => updateQuantity(key, -1)} style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', border: 'none', color: 'white', cursor: 'pointer' }}>-</button>
                        <span style={{ fontSize: '0.85rem', fontWeight: '700' }}>{item.qty}</span>
                        <button onClick={() => updateQuantity(key, 1)} style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', border: 'none', color: 'white', cursor: 'pointer' }}>+</button>
                        <button onClick={() => removeFromCart(key)} style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer', marginLeft: '4px' }}><Trash2 size={14} /></button>
                      </div>
                    </div>
                  ))}
                </div>

                <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '16px', marginBottom: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '1.1rem', fontWeight: '800', color: '#F8FAFC' }}>
                    <span>Total Amount:</span>
                    <span>₹{cartTotal}</span>
                  </div>
                </div>

                <button 
                  onClick={handlePlaceOrder}
                  className="btn-gold" 
                  style={{ width: '100%', padding: '14px', justifyContent: 'center', borderRadius: '12px' }}
                >
                  Checkout & Confirm Order <ArrowRight size={16} style={{ marginLeft: '6px' }} />
                </button>
              </>
            )}
          </aside>
        )}
      </div>

      {/* Prescription Reader OCR Modal */}
      <PrescriptionReaderModal
        isOpen={isPrescriptionModalOpen}
        onClose={() => setIsPrescriptionModalOpen(false)}
        onAddMedicinesToCart={handleAddMedicinesFromPrescription}
      />
    </div>
  );
}
