import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Loader2, Volume2 } from 'lucide-react';

export default function VoiceMicInput({ onTranscript, placeholder = "Speak now...", className = "", buttonStyle = {} }) {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');
  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    // Check if browser supports Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-IN'; // Default to English (India), supports Hindi terms

      recognition.onresult = (event) => {
        let transcriptStr = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcriptStr += event.results[i][0].transcript;
        }
        if (onTranscript && transcriptStr.trim()) {
          onTranscript(transcriptStr);
        }
      };

      recognition.onerror = (evt) => {
        console.warn('Speech recognition error:', evt.error);
        if (evt.error !== 'no-speech') {
          setError('Voice input error. Click to retry.');
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, [onTranscript]);

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
            onTranscript(data.transcript);
          } else {
            setError(data.error || 'Could not transcribe audio.');
          }
        } catch (err) {
          console.error('Audio transcription error:', err);
          setError('Failed to process voice recording.');
        } finally {
          setIsProcessing(false);
          // Stop media tracks
          stream.getTracks().forEach(track => track.stop());
        }
      };

      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setIsListening(true);
    } catch (err) {
      console.error('Microphone access denied or error:', err);
      setError('Microphone permission required.');
      setIsListening(false);
    }
  };

  const toggleListening = () => {
    setError('');
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        // Fallback to MediaRecorder audio upload if Web Speech API fails
        startFallbackAudioRecording();
      }
    } else {
      startFallbackAudioRecording();
    }
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', position: 'relative' }}>
      <button
        type="button"
        onClick={toggleListening}
        disabled={isProcessing}
        title={isListening ? "Listening... Click to stop" : "Click to speak via Microphone"}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '42px',
          height: '42px',
          borderRadius: '50%',
          border: isListening ? '2px solid #EF4444' : '1px solid rgba(255, 255, 255, 0.2)',
          background: isListening 
            ? 'rgba(239, 68, 68, 0.2)' 
            : isProcessing 
              ? 'rgba(16, 185, 129, 0.2)' 
              : 'rgba(255, 255, 255, 0.08)',
          color: isListening ? '#EF4444' : isProcessing ? '#10B981' : '#F8FAFC',
          cursor: isProcessing ? 'wait' : 'pointer',
          transition: 'all 0.2s ease',
          boxShadow: isListening ? '0 0 15px rgba(239, 68, 68, 0.5)' : 'none',
          ...buttonStyle
        }}
        className={className}
      >
        {isProcessing ? (
          <Loader2 size={18} className="animate-spin" />
        ) : isListening ? (
          <Volume2 size={18} style={{ animation: 'pulse 1s infinite' }} />
        ) : (
          <Mic size={18} />
        )}
      </button>

      {isListening && (
        <span style={{
          position: 'absolute',
          top: '-24px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: '#EF4444',
          color: 'white',
          fontSize: '0.7rem',
          fontWeight: '700',
          padding: '2px 8px',
          borderRadius: '10px',
          whiteSpace: 'nowrap',
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
        }}>
          Listening...
        </span>
      )}

      {error && (
        <span style={{
          position: 'absolute',
          bottom: '-22px',
          left: '50%',
          transform: 'translateX(-50%)',
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
