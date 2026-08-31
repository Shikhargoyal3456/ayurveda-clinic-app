import React, { useState } from 'react';
import { Search, Pill, Bot, ShoppingCart, Sparkles, Check } from 'lucide-react';

export default function OrderMedicines() {
  const [query, setQuery] = useState('');
  const [addedItems, setAddedItems] = useState({});

  const medicines = [
    { id: 1, name: "Ashwagandha Churna", category: "Rejuvenative / Rasayana", price: 240, description: "Supports stress relief, vitality, and calm sleep patterns." },
    { id: 2, name: "Avipattikar Churna", category: "Digestive / Agni", price: 180, description: "Relieves acidity, heartburn, and promotes healthy digestion." },
    { id: 3, name: "Brahmi Ghrita", category: "Nootropic / Medhya", price: 320, description: "Promotes memory, mental clarity, and nerve nourishment." },
    { id: 4, name: "Triphala Tablet", category: "Digestive / Shodhana", price: 150, description: "Gentle daily bowel regularity and antioxidant colon care." },
  ];

  const filteredMedicines = medicines.filter(m => 
    m.name.toLowerCase().includes(query.toLowerCase()) || 
    m.category.toLowerCase().includes(query.toLowerCase())
  );

  const toggleCart = (id) => {
    setAddedItems(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      {/* Header */}
      <section className="glass-card" style={{ padding: '28px', marginBottom: '24px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 12px', borderRadius: '20px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#10B981', fontSize: '0.8rem', fontWeight: '600', marginBottom: '12px' }}>
          <Sparkles size={14} /> Verified Ayurvedic Catalog
        </div>
        <h1 style={{ fontSize: '2rem', fontWeight: '800', margin: '0 0 8px' }}>Ayurvedic Medicine Store</h1>
        <p style={{ color: '#94A3B8', margin: 0 }}>Order authentic classical formulations & wellness supplements</p>

        {/* Search Bar */}
        <div style={{ marginTop: '20px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
            <input 
              type="text" 
              placeholder="Search formulations (e.g. Ashwagandha, Triphala, Digestion)..." 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ width: '100%', padding: '12px 16px 12px 48px', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: 'white', fontSize: '0.95rem', outline: 'none' }}
            />
          </div>
          <button className="btn-primary" style={{ padding: '12px 20px' }}>
            <Bot size={16} /> Ask AI Remedy Finder
          </button>
        </div>
      </section>

      {/* Catalog Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}>
        {filteredMedicines.map((item) => (
          <div key={item.id} className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Pill size={20} />
                </div>
                <span className="badge badge-emerald">{item.category}</span>
              </div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: '700', marginBottom: '6px' }}>{item.name}</h3>
              <p style={{ color: '#94A3B8', fontSize: '0.85rem', lineHeight: '1.5', marginBottom: '20px' }}>{item.description}</p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
              <span style={{ fontSize: '1.25rem', fontWeight: '800', color: '#F8FAFC' }}>₹{item.price}</span>
              <button 
                className={addedItems[item.id] ? "btn-secondary" : "btn-primary"} 
                onClick={() => toggleCart(item.id)}
                style={{ padding: '8px 14px', fontSize: '0.85rem' }}
              >
                {addedItems[item.id] ? (
                  <><Check size={14} style={{ color: '#10B981' }} /> Added</>
                ) : (
                  <><ShoppingCart size={14} /> Add to Cart</>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
