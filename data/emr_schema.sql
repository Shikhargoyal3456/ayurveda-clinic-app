-- =========================================================
-- EMR SYSTEM DATABASE SCHEMA
-- Ayurveda + Modern Medicine
-- Target: MySQL / MariaDB style DDL
-- Note: the current FastAPI runtime in this repo uses a compact
-- JSON-backed EMR module for incremental rollout. This file is the
-- normalized target schema for a fuller PostgreSQL/MySQL migration.
-- =========================================================

CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'doctor_ayurveda', 'doctor_modern', 'patient', 'pharmacist', 'lab_tech') NOT NULL,
    doctor_type ENUM('ayurveda', 'modern', 'both') NULL,
    registration_id VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

CREATE TABLE patients (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT UNIQUE,
    ur_number VARCHAR(50) UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    date_of_birth DATE NOT NULL,
    gender ENUM('male', 'female', 'other') NOT NULL,
    blood_group VARCHAR(5),
    mobile VARCHAR(15) NOT NULL,
    alternate_mobile VARCHAR(15),
    email VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    pincode VARCHAR(10),
    emergency_contact_name VARCHAR(100),
    emergency_contact_number VARCHAR(15),
    occupation VARCHAR(100),
    marital_status ENUM('single', 'married', 'divorced', 'widowed'),
    profile_photo_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_patients_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE family_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    relation VARCHAR(50),
    condition_name VARCHAR(255),
    diagnosis_age INT,
    notes TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_family_history_patient FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE TABLE allergies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    allergen_type ENUM('drug', 'food', 'environmental', 'herb', 'other') NOT NULL,
    allergen_name VARCHAR(255) NOT NULL,
    reaction TEXT,
    severity ENUM('mild', 'moderate', 'severe') NOT NULL,
    recorded_by INT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_allergies_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_allergies_recorded_by FOREIGN KEY (recorded_by) REFERENCES users(id)
);

CREATE TABLE vital_signs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    recorded_by INT,
    bp_systolic INT,
    bp_diastolic INT,
    heart_rate INT,
    respiratory_rate INT,
    temperature DECIMAL(4,1),
    oxygen_saturation INT,
    blood_sugar_fasting DECIMAL(6,2),
    blood_sugar_random DECIMAL(6,2),
    height_cm DECIMAL(5,2),
    weight_kg DECIMAL(5,2),
    bmi DECIMAL(4,2),
    pain_score INT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CONSTRAINT fk_vitals_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_vitals_recorded_by FOREIGN KEY (recorded_by) REFERENCES users(id),
    CONSTRAINT chk_vital_pain CHECK (pain_score BETWEEN 0 AND 10)
);

CREATE TABLE appointments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration_minutes INT DEFAULT 30,
    type ENUM('new', 'followup', 'emergency', 'telemedicine') NOT NULL,
    system_type ENUM('ayurveda', 'modern', 'integrated') NOT NULL,
    reason TEXT,
    status ENUM('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show') DEFAULT 'scheduled',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_appointments_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_appointments_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
);

CREATE TABLE consultations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    appointment_id INT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    consultation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    system_type ENUM('ayurveda', 'modern', 'integrated') NOT NULL,
    chief_complaints TEXT,
    history_of_present_illness TEXT,
    past_medical_history TEXT,
    treatment_plan TEXT,
    followup_date DATE,
    status ENUM('draft', 'finalized', 'billed') DEFAULT 'draft',
    CONSTRAINT fk_consult_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id),
    CONSTRAINT fk_consult_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_consult_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
);

CREATE TABLE soap_notes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    visit_id INT,
    subjective TEXT,
    objective TEXT,
    assessment TEXT,
    plan TEXT,
    review_of_systems TEXT,
    physical_exam TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_soap_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_soap_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
);

CREATE TABLE icd11_codes (
    id INT PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    diagnosis VARCHAR(500) NOT NULL,
    category VARCHAR(255),
    chapter VARCHAR(255)
);

CREATE TABLE patient_diagnoses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    diagnosis_code VARCHAR(20),
    doctor_id INT NOT NULL,
    diagnosis_date DATE NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    status ENUM('active', 'resolved', 'chronic', 'rule_out') DEFAULT 'active',
    notes TEXT,
    CONSTRAINT fk_diag_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_diag_doctor FOREIGN KEY (doctor_id) REFERENCES users(id),
    CONSTRAINT fk_diag_code FOREIGN KEY (diagnosis_code) REFERENCES icd11_codes(code)
);

CREATE TABLE modern_prescriptions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    prescription_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    visit_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    CONSTRAINT fk_modern_rx_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_modern_rx_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
);

CREATE TABLE modern_prescription_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    prescription_id INT NOT NULL,
    drug_name VARCHAR(255) NOT NULL,
    brand_name VARCHAR(255),
    strength VARCHAR(100),
    dosage_form VARCHAR(100),
    frequency VARCHAR(100),
    duration_days INT,
    quantity INT,
    route VARCHAR(50),
    special_instructions TEXT,
    is_chronic BOOLEAN DEFAULT FALSE,
    refill_count INT DEFAULT 0,
    CONSTRAINT fk_modern_rx_item FOREIGN KEY (prescription_id) REFERENCES modern_prescriptions(id)
);

CREATE TABLE lab_orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lab_name VARCHAR(255),
    priority ENUM('routine', 'urgent', 'stat') DEFAULT 'routine',
    CONSTRAINT fk_lab_order_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_lab_order_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
);

CREATE TABLE lab_tests (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    test_name VARCHAR(255) NOT NULL,
    test_category VARCHAR(100),
    result_value TEXT,
    unit VARCHAR(50),
    normal_range VARCHAR(100),
    is_abnormal BOOLEAN DEFAULT FALSE,
    status ENUM('pending', 'in_progress', 'completed', 'cancelled') DEFAULT 'pending',
    result_date TIMESTAMP NULL,
    interpreted_by INT,
    notes TEXT,
    CONSTRAINT fk_lab_test_order FOREIGN KEY (order_id) REFERENCES lab_orders(id),
    CONSTRAINT fk_lab_test_interpreter FOREIGN KEY (interpreted_by) REFERENCES users(id)
);

CREATE TABLE immunizations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    vaccine_name VARCHAR(255) NOT NULL,
    administration_date DATE NOT NULL,
    next_due_date DATE,
    dose_number INT,
    administered_by INT,
    lot_number VARCHAR(100),
    facility_name VARCHAR(255),
    notes TEXT,
    CONSTRAINT fk_immunization_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_immunization_user FOREIGN KEY (administered_by) REFERENCES users(id)
);

CREATE TABLE prakriti_assessment (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    assessed_by INT NOT NULL,
    vata_score INT,
    pitta_score INT,
    kapha_score INT,
    prakriti_type VARCHAR(50),
    vata_percentage INT,
    pitta_percentage INT,
    kapha_percentage INT,
    assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CONSTRAINT fk_prakriti_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_prakriti_user FOREIGN KEY (assessed_by) REFERENCES users(id)
);

CREATE TABLE vikriti_assessment (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    assessed_by INT NOT NULL,
    current_vata INT,
    current_pitta INT,
    current_kapha INT,
    assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    triggering_factors TEXT,
    notes TEXT,
    CONSTRAINT fk_vikriti_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_vikriti_user FOREIGN KEY (assessed_by) REFERENCES users(id)
);

CREATE TABLE ashtavidha_pariksha (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    examined_by INT NOT NULL,
    nadi_vata BOOLEAN,
    nadi_pitta BOOLEAN,
    nadi_kapha BOOLEAN,
    nadi_rate INT,
    nadi_rhythm VARCHAR(50),
    mutra_color VARCHAR(50),
    mutra_quantity VARCHAR(50),
    mutra_characteristics TEXT,
    mala_consistency VARCHAR(50),
    mala_color VARCHAR(50),
    mala_frequency VARCHAR(50),
    jihva_coating VARCHAR(50),
    jihva_color VARCHAR(50),
    jihva_moisture VARCHAR(50),
    shabda_quality VARCHAR(50),
    shabda_strength VARCHAR(50),
    sparsha_temperature VARCHAR(50),
    sparsha_moisture VARCHAR(50),
    drik_appearance VARCHAR(50),
    drik_conjunctiva VARCHAR(50),
    akriti_build VARCHAR(50),
    akriti_nutrition VARCHAR(50),
    examined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ashta_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_ashta_user FOREIGN KEY (examined_by) REFERENCES users(id)
);

CREATE TABLE srotas_examination (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    examined_by INT NOT NULL,
    pranavaha_srotas TEXT,
    annavaha_srotas TEXT,
    udakavaha_srotas TEXT,
    rasavaha_srotas TEXT,
    raktavaha_srotas TEXT,
    mamsavaha_srotas TEXT,
    medovaha_srotas TEXT,
    asthivaha_srotas TEXT,
    majjavaha_srotas TEXT,
    shukravaha_srotas TEXT,
    mutravaha_srotas TEXT,
    purishavaha_srotas TEXT,
    svedavaha_srotas TEXT,
    examined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_srotas_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_srotas_user FOREIGN KEY (examined_by) REFERENCES users(id)
);

CREATE TABLE agni_assessment (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    assessed_by INT NOT NULL,
    agni_type ENUM('sama', 'vishama', 'tikshna', 'manda') NOT NULL,
    digestive_strength INT,
    appetite VARCHAR(50),
    food_tolerance TEXT,
    bloating_frequency VARCHAR(50),
    gastric_issues TEXT,
    assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agni_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_agni_user FOREIGN KEY (assessed_by) REFERENCES users(id)
);

CREATE TABLE ama_assessment (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    assessed_by INT NOT NULL,
    ama_presence BOOLEAN,
    ama_severity INT,
    ama_location TEXT,
    symptoms_of_ama TEXT,
    assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ama_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_ama_user FOREIGN KEY (assessed_by) REFERENCES users(id)
);

CREATE TABLE ayurveda_diagnoses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    vyadhi_name VARCHAR(255) NOT NULL,
    vyadhi_sanskrit VARCHAR(255),
    dosha_involvement VARCHAR(100),
    dhatu_involvement VARCHAR(100),
    mala_involvement VARCHAR(100),
    srotas_involvement VARCHAR(100),
    sadhya_asadyata ENUM('sadhya', 'kashta_sadhya', 'asadhya'),
    stage VARCHAR(100),
    diagnosed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ayurdiag_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_ayurdiag_user FOREIGN KEY (doctor_id) REFERENCES users(id)
);

CREATE TABLE ayurveda_prescriptions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    prescription_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    diagnosis_reference INT,
    notes TEXT,
    CONSTRAINT fk_ayurrx_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_ayurrx_doctor FOREIGN KEY (doctor_id) REFERENCES users(id),
    CONSTRAINT fk_ayurrx_diag FOREIGN KEY (diagnosis_reference) REFERENCES ayurveda_diagnoses(id)
);

CREATE TABLE ayurveda_prescription_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    prescription_id INT NOT NULL,
    formulation_name VARCHAR(255) NOT NULL,
    sanskrit_name VARCHAR(255),
    form_type VARCHAR(100),
    dosage_seer VARCHAR(100),
    anupana VARCHAR(255),
    kala VARCHAR(100),
    duration_weeks INT,
    special_instructions TEXT,
    CONSTRAINT fk_ayurrx_item FOREIGN KEY (prescription_id) REFERENCES ayurveda_prescriptions(id)
);

CREATE TABLE panchakarma_treatments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    treatment_name VARCHAR(255) NOT NULL,
    treatment_type ENUM('vamana', 'virechana', 'basti', 'nasya', 'raktamokshana', 'other') NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    purvakarma_done BOOLEAN DEFAULT FALSE,
    pradhanakarma_done BOOLEAN DEFAULT FALSE,
    paschatkarma_done BOOLEAN DEFAULT FALSE,
    observations TEXT,
    outcome TEXT,
    status ENUM('scheduled', 'in_progress', 'completed', 'cancelled') DEFAULT 'scheduled',
    CONSTRAINT fk_panchakarma_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_panchakarma_user FOREIGN KEY (doctor_id) REFERENCES users(id)
);

CREATE TABLE documents (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    uploaded_by INT,
    document_type VARCHAR(100),
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INT,
    mime_type VARCHAR(100),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CONSTRAINT fk_documents_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_documents_user FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

CREATE TABLE clinical_notes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    consultation_id INT,
    note_type ENUM('progress', 'procedure', 'discharge', 'referral') NOT NULL,
    note_title VARCHAR(255),
    note_content TEXT,
    is_private BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_notes_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_notes_doctor FOREIGN KEY (doctor_id) REFERENCES users(id),
    CONSTRAINT fk_notes_consult FOREIGN KEY (consultation_id) REFERENCES consultations(id)
);

CREATE TABLE audit_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    action VARCHAR(255) NOT NULL,
    table_name VARCHAR(100),
    record_id INT,
    old_value TEXT,
    new_value TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE treatment_outcomes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    consultation_id INT,
    outcome_type ENUM('clinical', 'ayurvedic', 'patient_reported') NOT NULL,
    parameter_name VARCHAR(255),
    baseline_value VARCHAR(100),
    current_value VARCHAR(100),
    improvement_percentage DECIMAL(5,2),
    assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_outcome_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_outcome_consult FOREIGN KEY (consultation_id) REFERENCES consultations(id)
);
