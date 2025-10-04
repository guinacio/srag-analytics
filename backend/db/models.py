"""SQLAlchemy models for SRAG analytics database."""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Date, Float, Boolean, Text,
    Index, ForeignKey, DateTime, ARRAY
)
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class SRAGCase(Base):
    """
    Main SRAG (Severe Acute Respiratory Syndrome) cases table.
    Curated from DATASUS INFLUD CSV files.
    """
    __tablename__ = "srag_cases"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    nu_notific = Column(String(50), index=True)  # Notification number

    # Temporal fields
    dt_notific = Column(Date, index=True)  # Notification date
    dt_sin_pri = Column(Date, index=True)  # First symptoms date
    sem_not = Column(Integer)  # Notification week
    sem_pri = Column(Integer)  # First symptoms week

    # Geographic fields
    sg_uf_not = Column(String(2), index=True)  # State (UF) of notification
    co_mun_not = Column(String(10))  # Municipality code of notification
    sg_uf = Column(String(2))  # State of residence
    co_mun_res = Column(String(10))  # Municipality of residence
    cs_zona = Column(String(1))  # Zone (urban/rural)

    # Demographics
    cs_sexo = Column(String(1))  # Sex
    dt_nasc = Column(Date)  # Birth date
    nu_idade_n = Column(Integer)  # Age number
    tp_idade = Column(String(1))  # Age type
    cs_raca = Column(String(1))  # Race/ethnicity
    cs_escol_n = Column(String(1))  # Education level

    # Clinical presentation
    febre = Column(Integer)  # Fever (1=yes, 2=no, 9=ignored)
    tosse = Column(Integer)  # Cough
    garganta = Column(Integer)  # Sore throat
    dispneia = Column(Integer)  # Dyspnea
    desc_resp = Column(Integer)  # Respiratory distress
    saturacao = Column(Integer)  # Oxygen saturation < 95%
    diarreia = Column(Integer)  # Diarrhea
    vomito = Column(Integer)  # Vomit

    # Risk factors
    puerpera = Column(Integer)  # Postpartum
    cardiopati = Column(Integer)  # Cardiopathy
    diabetes = Column(Integer)  # Diabetes
    obesidade = Column(Integer)  # Obesity
    imunodepre = Column(Integer)  # Immunosuppression
    asma = Column(Integer)  # Asthma
    pneumopati = Column(Integer)  # Pneumopathy
    renal = Column(Integer)  # Renal disease
    hepatica = Column(Integer)  # Hepatic disease

    # Hospitalization
    hospital = Column(Integer)  # Hospitalized
    dt_interna = Column(Date)  # Hospitalization date
    uti = Column(Integer, index=True)  # ICU admission (critical for metrics)
    dt_entuti = Column(Date)  # ICU entry date
    dt_saiduti = Column(Date)  # ICU exit date
    suport_ven = Column(Integer)  # Ventilation support

    # Vaccination (critical for metrics)
    vacina = Column(Integer, index=True)  # Flu vaccine
    dt_ut_dose = Column(Date)  # Last flu vaccine dose date
    vacina_cov = Column(Integer, index=True)  # COVID vaccine
    dose_1_cov = Column(Integer)  # COVID dose 1
    dose_2_cov = Column(Integer)  # COVID dose 2
    dose_ref = Column(Integer)  # COVID booster
    dose_2ref = Column(Integer)  # COVID 2nd booster

    # Laboratory
    pcr_resul = Column(Integer)  # PCR result
    dt_pcr = Column(Date)  # PCR date
    res_an = Column(Integer)  # Antigen result
    classi_fin = Column(Integer, index=True)  # Final classification (5=SRAG COVID)
    criterio = Column(Integer)  # Diagnostic criteria

    # Outcome (critical for mortality metrics)
    evolucao = Column(Integer, index=True)  # Evolution (1=cure, 2=death, 3=death from other)
    dt_evoluca = Column(Date, index=True)  # Outcome date
    dt_encerra = Column(Date)  # Case closure date

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_srag_date_uf', 'dt_sin_pri', 'sg_uf_not'),
        Index('idx_srag_outcome', 'evolucao', 'dt_evoluca'),
        Index('idx_srag_icu', 'uti', 'dt_entuti'),
        Index('idx_srag_classification', 'classi_fin'),
    )


class DataDictionary(Base):
    """
    Structured knowledge base from SIVEP-Gripe data dictionary PDF.
    Serves as authoritative schema reference for SQL agent.
    """
    __tablename__ = "data_dictionary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_name = Column(String(100), unique=True, index=True)  # Column name in DB
    display_name = Column(String(200))  # Human-readable name
    description = Column(Text)  # Field description
    field_type = Column(String(50))  # Data type (text, date, integer, etc.)
    categories = Column(Text)  # Valid categories/values (JSON or text)
    is_required = Column(Boolean, default=False)  # Required field flag
    constraints = Column(Text)  # Additional constraints
    source_page = Column(Integer)  # PDF page reference
    notes = Column(Text)  # Additional notes

    # Embeddings for RAG (semantic search)
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small dimension

    created_at = Column(DateTime, default=datetime.utcnow)


class DailyMetrics(Base):
    """
    Materialized daily metrics for fast chart rendering.
    Pre-computed from srag_cases for performance.
    """
    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_date = Column(Date, unique=True, index=True)
    total_cases = Column(Integer, default=0)
    new_cases = Column(Integer, default=0)
    total_deaths = Column(Integer, default=0)
    new_deaths = Column(Integer, default=0)
    icu_admissions = Column(Integer, default=0)
    vaccinated_cases = Column(Integer, default=0)

    # State-level aggregates (optional)
    uf_breakdown = Column(Text)  # JSON with per-state counts

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MonthlyMetrics(Base):
    """
    Materialized monthly metrics for 12-month trend charts.
    """
    __tablename__ = "monthly_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    total_cases = Column(Integer, default=0)
    total_deaths = Column(Integer, default=0)
    avg_icu_occupancy = Column(Float)  # Average ICU occupancy
    vaccination_rate = Column(Float)  # Percentage vaccinated

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_monthly_year_month', 'year', 'month', unique=True),
    )
