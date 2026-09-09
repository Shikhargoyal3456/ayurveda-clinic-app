import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, Sparkles, X, Send, User, ChevronDown, 
  RotateCcw, ShieldCheck, Pill, FileText, CheckCircle2,
  Stethoscope, AlertCircle, RefreshCw, MessageSquare
} from 'lucide-react';

// Rich markdown formatter to clean up asterisks, hashtags, dashes, and dividers
function FormattedMarkdownText({ text }) {
  if (!text) return null;

  // Helper to format inline elements: **bold**, *italic*, `code`
  const formatInline = (inlineText) => {
    if (!inlineText) return null;
    const parts = [];
    const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(inlineText)) !== null) {
      if (match.index > lastIndex) {
        parts.push(inlineText.substring(lastIndex, match.index));
      }
      const token = match[0];
      if (token.startsWith('**') && token.endsWith('**')) {
        parts.push(
          <strong key={match.index} style={{ color: '#F8FAFC', fontWeight: '700' }}>
            {token.slice(2, -2)}
          </strong>
        );
      } else if (token.startsWith('*') && token.endsWith('*')) {
        parts.push(
          <em key={match.index} style={{ color: '#CBD5E1', fontStyle: 'italic' }}>
            {token.slice(1, -1)}
          </em>
        );
      } else if (token.startsWith('`') && token.endsWith('`')) {
        parts.push(
          <code key={match.index} style={{ padding: '2px 6px', borderRadius: '4px', background: 'rgba(255,255,255,0.1)', color: '#10B981', fontSize: '0.82rem' }}>
            {token.slice(1, -1)}
          </code>
        );
      }
      lastIndex = regex.lastIndex;
    }

    if (lastIndex < inlineText.length) {
      parts.push(inlineText.substring(lastIndex));
    }

    return parts.length > 0 ? parts : inlineText;
  };

  const lines = text.split('\n');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      {lines.map((line, i) => {
        const trimmed = line.trim();

        // 1. Empty lines
        if (!trimmed) {
          return <div key={i} style={{ height: '4px' }} />;
        }

        // 2. Horizontal dividers: --- or ***
        if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
          return <hr key={i} style={{ border: 'none', borderTop: '1px solid rgba(255, 255, 255, 0.12)', margin: '8px 0' }} />;
        }

        // 3. Headings: ###, ##, #
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={i} style={{ fontSize: '0.94rem', fontWeight: '800', color: '#10B981', margin: '8px 0 2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '4px', height: '14px', background: '#10B981', borderRadius: '2px', display: 'inline-block' }} />
              {formatInline(trimmed.slice(4))}
            </h4>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={i} style={{ fontSize: '1.02rem', fontWeight: '800', color: '#F8FAFC', margin: '10px 0 4px' }}>
              {formatInline(trimmed.slice(3))}
            </h3>
          );
        }
        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={i} style={{ fontSize: '1.1rem', fontWeight: '800', color: '#E8B24A', margin: '12px 0 6px' }}>
              {formatInline(trimmed.slice(2))}
            </h2>
          );
        }

        // 4. Bullet lists: - or *
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const content = trimmed.slice(2);
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '2px 0', paddingLeft: '2px' }}>
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#10B981', flexShrink: 0, marginTop: '7px' }} />
              <div style={{ flex: 1, fontSize: '0.88rem', lineHeight: '1.45' }}>
                {formatInline(content)}
              </div>
            </div>
          );
        }

        // 5. Numbered lists: 1. , 2. 
        const numberedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
        if (numberedMatch) {
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '2px 0', paddingLeft: '2px' }}>
              <span style={{ color: '#E8B24A', fontWeight: '700', fontSize: '0.82rem', minWidth: '16px' }}>
                {numberedMatch[1]}.
              </span>
              <div style={{ flex: 1, fontSize: '0.88rem', lineHeight: '1.45' }}>
                {formatInline(numberedMatch[2])}
              </div>
            </div>
          );
        }

        // 6. Regular paragraph line
        return (
          <p key={i} style={{ margin: '2px 0', fontSize: '0.88rem', lineHeight: '1.45', color: '#F8FAFC' }}>
            {formatInline(trimmed)}
          </p>
        );
      })}
    </div>
  );
}

export default function DoctorAICopilot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patientSearch, setPatientSearch] = useState('');
  const [suggestedPrompts, setSuggestedPrompts] = useState([]);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // Load patients list for doctor selection
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
      console.error('Error loading patients for copilot:', err);
    }
  };

  useEffect(() => {
    fetchPatients();
  }, []);

  // Initial welcome message
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          sender: 'ai',
          text: 'Namaste Doctor! I am your AI Clinical Copilot. Which patient would you like to review or consult on today?',
          type: 'welcome'
        }
      ]);
    }
  }, []);

  // Handle selecting a patient
  const handleSelectPatient = async (patient) => {
    setSelectedPatient(patient);
    setIsLoading(true);

    const userMsg = {
      sender: 'user',
      text: `Let's review patient: ${patient.name}`
    };

    setMessages(prev => [...prev, userMsg]);

    try {
      const res = await fetch('/api/doctor/copilot-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patient.id,
          patient_name: patient.name,
          message: `Please summarize ${patient.name}'s clinical history, recorded case sheets, and current medications.`,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setMessages(prev => [
          ...prev,
          {
            sender: 'ai',
            text: data.reply,
            patientContext: data.patient,
          }
        ]);
        if (data.suggested_followups) {
          setSuggestedPrompts(data.suggested_followups);
        }
      } else {
        setMessages(prev => [
          ...prev,
          {
            sender: 'ai',
            text: `Loaded records for ${patient.name}. How can I assist with their treatment plan?`
          }
        ]);
      }
    } catch (err) {
      console.error('Copilot patient init error:', err);
      setMessages(prev => [
        ...prev,
        {
          sender: 'ai',
          text: `Loaded patient profile for ${patient.name} (${patient.age}y/${patient.gender}, ${patient.prakriti || 'Vata-Pitta'}). What would you like to know?`
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle sending question to Copilot
  const handleSendMessage = async (textToSend = inputValue) => {
    const question = textToSend.trim();
    if (!question || isLoading) return;

    const userMsg = { sender: 'user', text: question };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/doctor/copilot-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: selectedPatient?.id || null,
          patient_name: selectedPatient?.name || null,
          message: question,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        if (!selectedPatient && data.patient) {
          setSelectedPatient(data.patient);
        }
        setMessages(prev => [
          ...prev,
          {
            sender: 'ai',
            text: data.reply,
            patientContext: data.patient || selectedPatient,
          }
        ]);
        if (data.suggested_followups) {
          setSuggestedPrompts(data.suggested_followups);
        }
      } else {
        setMessages(prev => [
          ...prev,
          {
            sender: 'ai',
            text: data.reply || 'Could not process query. Please ensure Gemini API is configured.'
          }
        ]);
      }
    } catch (err) {
      console.error('Copilot send error:', err);
      setMessages(prev => [
        ...prev,
        {
          sender: 'ai',
          text: 'Network error communicating with Clinical AI. Please try again.'
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Reset conversation
  const handleReset = () => {
    setSelectedPatient(null);
    setSuggestedPrompts([]);
    setMessages([
      {
        sender: 'ai',
        text: 'Session refreshed. Which patient would you like to review now?',
        type: 'welcome'
      }
    ]);
    fetchPatients();
  };

  const filteredPatients = patients.filter(p => 
    p.name.toLowerCase().includes(patientSearch.toLowerCase())
  );

  return (
    <>
      {/* Floating Launcher Trigger (Bottom-Right) */}
      <div style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 9999,
      }}>
        {!isOpen ? (
          <button
            onClick={() => setIsOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '12px 20px',
              borderRadius: '999px',
              background: 'linear-gradient(135deg, #10B981 0%, #059669 50%, #047857 100%)',
              color: '#FFFFFF',
              border: '1px solid rgba(255, 255, 255, 0.25)',
              boxShadow: '0 10px 25px -5px rgba(16, 185, 129, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)',
              cursor: 'pointer',
              fontWeight: '700',
              fontSize: '0.92rem',
              transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-3px) scale(1.02)'}
            onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0) scale(1)'}
          >
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              background: 'rgba(255, 255, 255, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative'
            }}>
              <Sparkles size={16} color="#F4EEE1" />
              <span style={{
                position: 'absolute',
                top: '-2px',
                right: '-2px',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: '#FACC15',
                border: '1.5px solid #059669'
              }} />
            </div>
            <span>AI Doctor Copilot</span>
          </button>
        ) : null}
      </div>

      {/* Floating Chat Window */}
      {isOpen && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          width: '420px',
          maxWidth: 'calc(100vw - 32px)',
          height: '620px',
          maxHeight: 'calc(100vh - 48px)',
          background: 'rgba(9, 18, 15, 0.95)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          borderRadius: '24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.75), 0 0 30px rgba(16, 185, 129, 0.15)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 10000,
          overflow: 'hidden',
          animation: 'fadeIn 0.2s ease-out'
        }}>
          {/* Header */}
          <div style={{
            padding: '16px 20px',
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.18), rgba(6, 182, 212, 0.1))',
            borderBottom: '1px solid rgba(16, 185, 129, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '38px',
                height: '38px',
                borderRadius: '12px',
                background: 'rgba(16, 185, 129, 0.2)',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10B981'
              }}>
                <Stethoscope size={20} />
              </div>
              <div>
                <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: '800', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  Dr. Kash Copilot
                  <span style={{ fontSize: '0.68rem', padding: '2px 6px', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.25)', color: '#10B981', fontWeight: '700' }}>
                    Gemini 3.6
                  </span>
                </h4>
                <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>
                  {selectedPatient ? `Active: ${selectedPatient.name}` : 'Select a patient to begin'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                onClick={handleReset}
                title="Reset conversation"
                style={{
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: 'none',
                  color: '#94A3B8',
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <RotateCcw size={15} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                title="Close chat"
                style={{
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: 'none',
                  color: '#94A3B8',
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Active Patient Dossier Banner */}
          {selectedPatient && (
            <div style={{
              padding: '8px 16px',
              background: 'rgba(16, 185, 129, 0.1)',
              borderBottom: '1px solid rgba(16, 185, 129, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.78rem',
              color: '#F8FAFC'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <User size={13} color="#10B981" />
                <strong>{selectedPatient.name}</strong> ({selectedPatient.age}y/{selectedPatient.gender})
                <span style={{ color: '#E8B24A' }}>• {selectedPatient.prakriti || 'Vata-Pitta'}</span>
              </div>
              <button
                onClick={() => setSelectedPatient(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#10B981',
                  fontSize: '0.72rem',
                  fontWeight: '700',
                  cursor: 'pointer',
                  textDecoration: 'underline'
                }}
              >
                Switch Patient
              </button>
            </div>
          )}

          {/* Chat Messages Area */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}>
            {messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '88%',
                    padding: '12px 16px',
                    borderRadius: msg.sender === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                    background: msg.sender === 'user' 
                      ? 'linear-gradient(135deg, #10B981, #059669)' 
                      : 'rgba(255, 255, 255, 0.05)',
                    border: msg.sender === 'user'
                      ? 'none'
                      : '1px solid rgba(255, 255, 255, 0.08)',
                    color: '#F8FAFC',
                    fontSize: '0.88rem',
                    lineHeight: '1.45',
                    wordBreak: 'break-word',
                  }}
                >
                  {msg.sender === 'user' ? (
                    <span style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</span>
                  ) : (
                    <FormattedMarkdownText text={msg.text} />
                  )}
                </div>

                {/* If initial message and no patient selected yet: Show Patient Chips */}
                {msg.type === 'welcome' && !selectedPatient && (
                  <div style={{ marginTop: '12px', width: '100%' }}>
                    <div style={{ marginBottom: '8px', position: 'relative' }}>
                      <input
                        type="text"
                        placeholder="Search patient name..."
                        value={patientSearch}
                        onChange={(e) => setPatientSearch(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          borderRadius: '10px',
                          background: 'rgba(0,0,0,0.3)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          color: '#F8FAFC',
                          fontSize: '0.8rem',
                          outline: 'none'
                        }}
                      />
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {filteredPatients.slice(0, 6).map((p) => (
                        <button
                          key={p.id}
                          onClick={() => handleSelectPatient(p)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 12px',
                            borderRadius: '20px',
                            background: 'rgba(16, 185, 129, 0.12)',
                            border: '1px solid rgba(16, 185, 129, 0.3)',
                            color: '#10B981',
                            fontSize: '0.78rem',
                            fontWeight: '600',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(16, 185, 129, 0.25)'}
                          onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(16, 185, 129, 0.12)'}
                        >
                          <User size={12} /> {p.name} ({p.age}y)
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Thinking / Loading Animation */}
            {isLoading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10B981', fontSize: '0.82rem', padding: '6px 10px' }}>
                <RefreshCw size={14} className="animate-spin" />
                <span>Consulting patient case history & Gemini AI...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Prompt Chips */}
          {suggestedPrompts.length > 0 && (
            <div style={{
              padding: '6px 16px',
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              display: 'flex',
              gap: '6px',
              overflowX: 'auto',
              background: 'rgba(0, 0, 0, 0.2)'
            }}>
              {suggestedPrompts.slice(0, 3).map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(prompt)}
                  style={{
                    whiteSpace: 'nowrap',
                    padding: '4px 10px',
                    borderRadius: '12px',
                    background: 'rgba(232, 178, 74, 0.1)',
                    border: '1px solid rgba(232, 178, 74, 0.25)',
                    color: '#E8B24A',
                    fontSize: '0.74rem',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}

          {/* Bottom Chat Input Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            style={{
              padding: '12px 16px',
              background: 'rgba(11, 21, 18, 0.9)',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              gap: '10px',
              alignItems: 'center'
            }}
          >
            <input
              type="text"
              placeholder={selectedPatient ? `Ask about ${selectedPatient.name}'s diagnosis, meds...` : "Select or type a patient's name..."}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={isLoading}
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: '12px',
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                color: '#F8FAFC',
                fontSize: '0.88rem',
                outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '12px',
                background: inputValue.trim() ? 'linear-gradient(135deg, #10B981, #059669)' : 'rgba(255, 255, 255, 0.08)',
                color: inputValue.trim() ? '#FFFFFF' : '#64748B',
                border: 'none',
                cursor: inputValue.trim() ? 'pointer' : 'default',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease'
              }}
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
