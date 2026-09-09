import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Loader2, Volume2, Square } from 'lucide-react';

export default function VoiceMicInput({ 
  onTranscript, 
  onStart,
  onStop,
  onListeningChange,
  placeholder = "Speak now...", 
  className = "", 
  buttonStyle = {},
  showLabel = false,
}) {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');
  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    if (onListeningChange) {
      onListeningChange(isListening);
    }
  }, [isListening, onListeningChange]);

  useEffect(() => {
    // Check if browser supports Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-IN'; // Default to English (India), supports Hindi terms

      recognition.onresult = (event) => {
        let finalStr = '';
        let interimStr = '';
        for (let i = 0; i < event.results.length; i++) {
          const res = event.results[i];
          if (res && res[0]) {
            if (res.isFinal) {
              finalStr += res[0].transcript + ' ';
            } else {
              interimStr += res[0].transcript;
            }
          }
        }
        const fullTranscript = (finalStr + interimStr).trim();
        if (onTranscript && fullTranscript) {
          onTranscript(fullTranscript);
        }
      };

      recognition.onerror = (evt) => {
        console.warn('Speech recognition error:', evt.error);
        if (evt.error !== 'no-speech') {
          setError('Voice input error. Click to retry.');
        }
        setIsListening(false);
        if (onStop) onStop();
      };

      recognition.onend = () => {
        setIsListening(false);
        if (onStop) onStop();
      };

      recognitionRef.current = recognition;
    }
  }, [onTranscript, onStop]);

  const startFallbackAudioRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        setIsProcessing(true);
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio_file', audioBlob, 'recording.webm');

        try {
          const res = await fetch('/api/voice/transcribe', {
            method: 'POST',
            body: formData,
          });
          const data = await res.json();
          if (data.success && data.transcript) {
            if (onTranscript) {
              onTranscript(data.transcript);
            }
          } else {
            setError(data.error || 'Could not transcribe audio.');
          }
        } catch (err) {
          console.error('Audio transcription error:', err);
          setError('Failed to process voice recording.');
        } finally {
          setIsProcessing(false);
          stream.getTracks().forEach(track => track.stop());
        }
      };

      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setIsListening(true);
      if (onStart) onStart();
    } catch (err) {
      console.error('Microphone access denied or error:', err);
      setError('Microphone permission required.');
      setIsListening(false);
    }
  };

  const toggleListening = () => {
    setError('');
    if (isListening) {
      // STOP listening
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          console.warn('Error stopping recognition:', e);
        }
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsListening(false);
      if (onStop) onStop();
      return;
    }

    // START listening - notify parent to clear previous notes
    if (onStart) {
      onStart();
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        startFallbackAudioRecording();
      }
    } else {
      startFallbackAudioRecording();
    }
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', position: 'relative' }}>
      <button
        type="button"
        onClick={toggleListening}
        disabled={isProcessing}
        title={isListening ? "Listening... Click to Stop" : "Click to Speak via Microphone"}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          padding: showLabel ? '8px 16px' : '0',
          width: showLabel ? 'auto' : '42px',
          height: '42px',
          borderRadius: showLabel ? '24px' : '50%',
          border: isListening ? '2px solid #EF4444' : '1px solid rgba(255, 255, 255, 0.2)',
          background: isListening 
            ? 'rgba(239, 68, 68, 0.25)' 
            : isProcessing 
              ? 'rgba(16, 185, 129, 0.2)' 
              : 'rgba(255, 255, 255, 0.08)',
          color: isListening ? '#EF4444' : isProcessing ? '#10B981' : '#F8FAFC',
          cursor: isProcessing ? 'wait' : 'pointer',
          transition: 'all 0.2s ease',
          boxShadow: isListening ? '0 0 18px rgba(239, 68, 68, 0.55)' : 'none',
          fontWeight: '700',
          fontSize: '0.85rem',
          ...buttonStyle
        }}
        className={className}
      >
        {isProcessing ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            {showLabel && <span>Transcribing...</span>}
          </>
        ) : isListening ? (
          <>
            <Square size={16} style={{ fill: '#EF4444' }} />
            {showLabel ? <span>Stop Dictation</span> : null}
          </>
        ) : (
          <>
            <Mic size={18} />
            {showLabel ? <span>Start Dictation</span> : null}
          </>
        )}
      </button>

      {/* Explicit Stop Dictation Button visible while recording */}
      {isListening && !showLabel && (
        <button
          type="button"
          onClick={toggleListening}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 14px',
            borderRadius: '20px',
            background: '#EF4444',
            border: 'none',
            color: 'white',
            fontWeight: '700',
            fontSize: '0.8rem',
            cursor: 'pointer',
            boxShadow: '0 2px 10px rgba(239, 68, 68, 0.45)',
            animation: 'pulse 1.5s infinite'
          }}
        >
          <Square size={12} style={{ fill: 'white' }} /> Stop Dictation
        </button>
      )}

      {error && (
        <span style={{
          position: 'absolute',
          bottom: '-22px',
          left: '0',
          color: '#F87171',
          fontSize: '0.75rem',
          whiteSpace: 'nowrap'
        }}>
          {error}
        </span>
      )}
    </div>
  );
}
