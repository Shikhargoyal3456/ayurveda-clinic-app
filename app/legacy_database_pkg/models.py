from sqlalchemy import Column, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    age = Column(Integer)
    gender = Column(String)
    phone = Column(String)

    cases = relationship("CaseSheet", back_populates="patient")


class CaseSheet(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    prakriti = Column(String)
    diagnosis = Column(String)
    symptoms = Column(String)
    notes = Column(String)
    ai_prescription = Column(Text)
    followup_date = Column(Date, nullable=True)
    followup_notes = Column(String, nullable=True)

    patient = relationship("Patient", back_populates="cases")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    date = Column(Date)
    time = Column(String)
    reason = Column(String)

    patient = relationship("Patient")
