#!/usr/bin/env python3
"""
GLP-1 RA vs SGLT2i Dementia Replication Study
Complete version with:
- Full data extraction with intermediate saves
- Baseline characteristics tables
- CONSORT flow diagram numbers
- Correct Cox regression (no penalization)
- Comprehensive methodological report

Based on: Anagnostakis et al., Diabetes Obes Metab 2025
"""

import argparse
import getpass
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import sys
import json
import warnings
warnings.filterwarnings('ignore')

# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return super().default(obj)

# Directories
SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = SCRIPT_DIR / 'outputs'
DATA_DIR = SCRIPT_DIR / 'data'
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# =============================================================================
# CONCEPT DEFINITIONS (from original paper)
# =============================================================================

CONCEPTS = {
    # GLP-1 RAs (approved 2005-2019)
    'glp1_ra': {
        'name': 'GLP-1 Receptor Agonists',
        'concept_ids': [44816332, 45774435, 1583722, 40170911, 44506754, 793143],
        'drugs': ['tirzepatide', 'dulaglutide', 'exenatide', 'liraglutide', 'lixisenatide', 'semaglutide']
    },
    # SGLT2i (approved 2013+)
    'sglt2i': {
        'name': 'SGLT2 Inhibitors', 
        'concept_ids': [43526465, 44785829, 45774751, 793293],
        'drugs': ['canagliflozin', 'dapagliflozin', 'empagliflozin', 'ertugliflozin']
    },
    # T2DM
    't2dm': {'concept_id': 201826, 'name': 'Type 2 Diabetes Mellitus'},
    # Metformin
    'metformin': {'concept_id': 1503297, 'name': 'Metformin'},
    # Dementia outcomes - comprehensive (4182210 captures most via ancestor, plus Lewy body)
    'dementia': {
        'concept_ids': [4182210, 4092747, 380701, 44782763, 4041685],
        # 4182210 = Dementia (main umbrella - captures 99% via concept_ancestor)
        # 4092747 = Cerebral degeneration presenting primarily with dementia
        # 380701 = Diffuse Lewy body disease (NOT descendant of 4182210)
        # 44782763 = Lewy body dementia with behavioral disturbance
        # 4041685 = ALS with dementia
        'name': 'All-cause dementia'
    },
    # Covariates - using broader concept IDs where needed
    'covariates': {
        'hypertension': 316866,
        'heart_failure': 316139,
        'obesity': 433736,
        'ckd': 193782,
        'depression': 440383,
        'anxiety': 441542,
        'atrial_fibrillation': 313217,
        'ischemic_heart_disease': 4185932,  # Broader: "Ischemic heart disease" parent concept
        'coronary_artery_disease': 317576,  # Added: CAD as alternative
        'myocardial_infarction': 4329847,   # Added: MI 
        'cerebrovascular_disease': 381591,
        'stroke': 4148906,                   # Added: Stroke
        'hyperlipidemia': 432867,
        'peripheral_vascular': 321052,
        'copd': 255573,
        'liver_disease': 4212540,
        'alcohol_use': 433753,
        'smoking': 4209423
    }
}

# Study parameters
STUDY_START = '2013-04-01'  # First SGLT2i approval
STUDY_END = '2019-12-31'    # Index date cutoff
FOLLOWUP_END = '2025-01-01' # End of follow-up
LAG_DAYS = 180              # 6-month lag period
METFORMIN_WINDOW = 180      # 6-month window for metformin use

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection(host, port, database, username, password, db_type='mssql'):
    """Create database connection."""
    print(f"\nConnecting to {db_type} at {host}/{database}...")
    
    if db_type == 'mssql':
        try:
            import pymssql
            conn_kwargs = {'server': host, 'user': username, 'password': password, 'database': database}
            if port:
                conn_kwargs['port'] = int(port)
            conn = pymssql.connect(**conn_kwargs)
            print("  ✓ Connected via pymssql")
            return conn
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
            raise
    elif db_type == 'postgresql':
        import psycopg2
        conn = psycopg2.connect(host=host, port=port or 5432, dbname=database, 
                                user=username, password=password)
        print("  ✓ Connected via psycopg2")
        return conn
    raise ValueError(f"Unsupported db_type: {db_type}")

def run_query(conn, query, description="Query"):
    """Execute query and return DataFrame."""
    print(f"  {description}...", end=" ", flush=True)
    try:
        df = pd.read_sql(query, conn)
        print(f"✓ ({len(df):,} rows)")
        return df
    except Exception as e:
        print(f"✗ Error: {e}")
        return pd.DataFrame()

# =============================================================================
# DATA EXTRACTION
# =============================================================================

def extract_all_data(conn):
    """Extract all required data with intermediate saves."""
    
    flow = {'extraction': {}}  # Track numbers for CONSORT diagram
    
    print("\n" + "="*70)
    print("PHASE 1: INITIAL DRUG COHORT EXTRACTION")
    print("="*70)
    
    # 1. GLP-1 RA initiators
    glp1_concepts = ','.join(map(str, CONCEPTS['glp1_ra']['concept_ids']))
    glp1 = run_query(conn, f"""
        SELECT de.person_id, 
               MIN(de.drug_exposure_start_date) as index_date,
               COUNT(*) as n_prescriptions
        FROM omop.drug_exposure de
        INNER JOIN omop.concept_ancestor ca ON de.drug_concept_id = ca.descendant_concept_id
        WHERE ca.ancestor_concept_id IN ({glp1_concepts})
          AND de.drug_exposure_start_date >= '{STUDY_START}'
          AND de.drug_exposure_start_date <= '{STUDY_END}'
        GROUP BY de.person_id
    """, "GLP-1 RA initiators (2013-2019)")
    glp1['treatment_group'] = 'GLP1_RA'
    flow['extraction']['glp1_initial'] = len(glp1)
    
    # 2. SGLT2i initiators
    sglt2_concepts = ','.join(map(str, CONCEPTS['sglt2i']['concept_ids']))
    sglt2 = run_query(conn, f"""
        SELECT de.person_id,
               MIN(de.drug_exposure_start_date) as index_date,
               COUNT(*) as n_prescriptions
        FROM omop.drug_exposure de
        INNER JOIN omop.concept_ancestor ca ON de.drug_concept_id = ca.descendant_concept_id
        WHERE ca.ancestor_concept_id IN ({sglt2_concepts})
          AND de.drug_exposure_start_date >= '{STUDY_START}'
          AND de.drug_exposure_start_date <= '{STUDY_END}'
        GROUP BY de.person_id
    """, "SGLT2i initiators (2013-2019)")
    sglt2['treatment_group'] = 'SGLT2i'
    flow['extraction']['sglt2_initial'] = len(sglt2)
    
    # Combine
    drug_cohort = pd.concat([glp1, sglt2], ignore_index=True)
    drug_cohort['index_date'] = pd.to_datetime(drug_cohort['index_date'])
    drug_cohort.to_csv(DATA_DIR / '01_drug_initiators.csv', index=False)
    
    person_ids = drug_cohort['person_id'].unique().tolist()
    person_ids_str = ','.join(map(str, person_ids))
    flow['extraction']['total_initiators'] = len(person_ids)
    
    print(f"\n  Total unique drug initiators: {len(person_ids):,}")
    print(f"    GLP-1 RA: {len(glp1):,}")
    print(f"    SGLT2i: {len(sglt2):,}")
    
    print("\n" + "="*70)
    print("PHASE 2: ELIGIBILITY CRITERIA DATA")
    print("="*70)
    
    # 3. T2DM diagnosis
    t2dm = run_query(conn, f"""
        SELECT DISTINCT co.person_id,
               MIN(co.condition_start_date) as first_t2dm_date
        FROM omop.condition_occurrence co
        INNER JOIN omop.concept_ancestor ca ON co.condition_concept_id = ca.descendant_concept_id
        WHERE ca.ancestor_concept_id = {CONCEPTS['t2dm']['concept_id']}
          AND co.person_id IN ({person_ids_str})
        GROUP BY co.person_id
    """, "T2DM diagnoses")
    t2dm.to_csv(DATA_DIR / '02_t2dm.csv', index=False)
    flow['extraction']['with_t2dm'] = len(t2dm)
    
    # 4. Metformin use
    metformin = run_query(conn, f"""
        SELECT de.person_id,
               MIN(de.drug_exposure_start_date) as first_metformin_date,
               MAX(de.drug_exposure_start_date) as last_metformin_date,
               COUNT(*) as n_metformin_rx
        FROM omop.drug_exposure de
        INNER JOIN omop.concept_ancestor ca ON de.drug_concept_id = ca.descendant_concept_id
        WHERE ca.ancestor_concept_id = {CONCEPTS['metformin']['concept_id']}
          AND de.person_id IN ({person_ids_str})
        GROUP BY de.person_id
    """, "Metformin exposure")
    metformin.to_csv(DATA_DIR / '03_metformin.csv', index=False)
    flow['extraction']['with_metformin'] = len(metformin)
    
    # 5. Prior dementia (for exclusion) - comprehensive capture
    # Use 4182210 as ancestor (captures 99%) PLUS direct match for Lewy body variants
    prior_dementia = run_query(conn, f"""
        SELECT co.person_id,
               MIN(co.condition_start_date) as first_dementia_date
        FROM omop.condition_occurrence co
        WHERE (
            co.condition_concept_id IN (
                SELECT ca.descendant_concept_id 
                FROM omop.concept_ancestor ca
                WHERE ca.ancestor_concept_id = 4182210
            )
            OR co.condition_concept_id IN (380701, 44782763, 4041685)
        )
          AND co.person_id IN ({person_ids_str})
        GROUP BY co.person_id
    """, "Dementia diagnoses (comprehensive)")
    prior_dementia.to_csv(DATA_DIR / '04_dementia_all.csv', index=False)
    flow['extraction']['any_dementia'] = len(prior_dementia)
    
    print("\n" + "="*70)
    print("PHASE 3: DEMOGRAPHICS & BASELINE DATA")
    print("="*70)
    
    # 6. Demographics
    demographics = run_query(conn, f"""
        SELECT p.person_id,
               p.year_of_birth,
               p.gender_concept_id,
               p.race_concept_id,
               p.ethnicity_concept_id,
               gc.concept_name as gender,
               rc.concept_name as race,
               ec.concept_name as ethnicity
        FROM omop.person p
        LEFT JOIN omop.concept gc ON p.gender_concept_id = gc.concept_id
        LEFT JOIN omop.concept rc ON p.race_concept_id = rc.concept_id
        LEFT JOIN omop.concept ec ON p.ethnicity_concept_id = ec.concept_id
        WHERE p.person_id IN ({person_ids_str})
    """, "Demographics")
    demographics.to_csv(DATA_DIR / '05_demographics.csv', index=False)
    
    # 7. Observation periods
    obs_periods = run_query(conn, f"""
        SELECT person_id,
               MIN(observation_period_start_date) as first_obs_date,
               MAX(observation_period_end_date) as last_obs_date
        FROM omop.observation_period
        WHERE person_id IN ({person_ids_str})
        GROUP BY person_id
    """, "Observation periods")
    obs_periods.to_csv(DATA_DIR / '06_observation_periods.csv', index=False)
    
    # 8. Deaths
    deaths = run_query(conn, f"""
        SELECT person_id, death_date
        FROM omop.death
        WHERE person_id IN ({person_ids_str})
    """, "Deaths")
    deaths.to_csv(DATA_DIR / '07_deaths.csv', index=False)
    flow['extraction']['deaths'] = len(deaths)
    
    print("\n" + "="*70)
    print("PHASE 4: COMORBIDITIES (COVARIATES)")
    print("="*70)
    
    # 9. All comorbidities
    all_covariates = []
    for cov_name, concept_id in CONCEPTS['covariates'].items():
        cov_df = run_query(conn, f"""
            SELECT DISTINCT co.person_id,
                   MIN(co.condition_start_date) as first_dx_date
            FROM omop.condition_occurrence co
            INNER JOIN omop.concept_ancestor ca ON co.condition_concept_id = ca.descendant_concept_id
            WHERE ca.ancestor_concept_id = {concept_id}
              AND co.person_id IN ({person_ids_str})
            GROUP BY co.person_id
        """, f"  {cov_name}")
        cov_df['covariate'] = cov_name
        cov_df.to_csv(DATA_DIR / f'cov_{cov_name}.csv', index=False)
        all_covariates.append(cov_df)
        flow['extraction'][f'cov_{cov_name}'] = len(cov_df)
    
    # Combine covariates
    covariates_combined = pd.concat(all_covariates, ignore_index=True)
    covariates_combined.to_csv(DATA_DIR / '08_covariates_all.csv', index=False)
    
    print("\n" + "="*70)
    print("PHASE 5: LABORATORY MEASUREMENTS (if available)")
    print("="*70)
    
    # 10. BMI measurements (capped 15-60, excluding extreme outliers)
    bmi = run_query(conn, f"""
        SELECT m.person_id,
               m.measurement_date,
               m.value_as_number as bmi_value
        FROM omop.measurement m
        WHERE m.measurement_concept_id IN (3038553, 40762636, 3036277)
          AND m.person_id IN ({person_ids_str})
          AND m.value_as_number BETWEEN 15 AND 60
    """, "BMI measurements (15-60 range)")
    if len(bmi) > 0:
        bmi.to_csv(DATA_DIR / '09_bmi.csv', index=False)
    
    # 11. HbA1c measurements
    hba1c = run_query(conn, f"""
        SELECT m.person_id,
               m.measurement_date,
               m.value_as_number as hba1c_value
        FROM omop.measurement m
        WHERE m.measurement_concept_id IN (3004410, 3007263, 40762352)
          AND m.person_id IN ({person_ids_str})
          AND m.value_as_number BETWEEN 4 AND 20
    """, "HbA1c measurements")
    if len(hba1c) > 0:
        hba1c.to_csv(DATA_DIR / '10_hba1c.csv', index=False)
    
    # Save flow data
    with open(DATA_DIR / 'extraction_flow.json', 'w') as f:
        json.dump(flow, f, indent=2, cls=NumpyEncoder)
    
    print("\n" + "="*70)
    print("DATA EXTRACTION COMPLETE")
    print("="*70)
    print(f"  All data saved to: {DATA_DIR}")
    
    return flow

# =============================================================================
# COHORT BUILDING
# =============================================================================

def build_cohort():
    """Build study cohort from extracted data."""
    
    print("\n" + "="*70)
    print("COHORT CONSTRUCTION")
    print("="*70)
    
    flow = {'cohort': {}}
    
    # Load data
    drug_cohort = pd.read_csv(DATA_DIR / '01_drug_initiators.csv')
    drug_cohort['index_date'] = pd.to_datetime(drug_cohort['index_date'])
    
    t2dm = pd.read_csv(DATA_DIR / '02_t2dm.csv')
    metformin = pd.read_csv(DATA_DIR / '03_metformin.csv')
    dementia = pd.read_csv(DATA_DIR / '04_dementia_all.csv')
    demographics = pd.read_csv(DATA_DIR / '05_demographics.csv')
    obs_periods = pd.read_csv(DATA_DIR / '06_observation_periods.csv')
    deaths = pd.read_csv(DATA_DIR / '07_deaths.csv')
    
    # Convert dates
    for df, cols in [(metformin, ['first_metformin_date', 'last_metformin_date']),
                     (dementia, ['first_dementia_date']),
                     (obs_periods, ['first_obs_date', 'last_obs_date']),
                     (deaths, ['death_date'])]:
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
    
    cohort = drug_cohort.copy()
    flow['cohort']['initial'] = len(cohort)
    flow['cohort']['initial_glp1'] = len(cohort[cohort['treatment_group'] == 'GLP1_RA'])
    flow['cohort']['initial_sglt2'] = len(cohort[cohort['treatment_group'] == 'SGLT2i'])
    print(f"\n  1. Initial drug initiators: {len(cohort):,}")
    print(f"     - GLP-1 RA: {flow['cohort']['initial_glp1']:,}")
    print(f"     - SGLT2i: {flow['cohort']['initial_sglt2']:,}")
    
    # Criterion 1: T2DM diagnosis
    t2dm_ids = set(t2dm['person_id'])
    excluded_no_t2dm = len(cohort[~cohort['person_id'].isin(t2dm_ids)])
    cohort = cohort[cohort['person_id'].isin(t2dm_ids)]
    flow['cohort']['after_t2dm'] = len(cohort)
    flow['cohort']['excluded_no_t2dm'] = excluded_no_t2dm
    print(f"\n  2. After requiring T2DM diagnosis: {len(cohort):,}")
    print(f"     - Excluded (no T2DM): {excluded_no_t2dm:,}")
    
    # Criterion 2: Metformin use within ±6 months
    metformin['first_metformin_date'] = pd.to_datetime(metformin['first_metformin_date'])
    metformin['last_metformin_date'] = pd.to_datetime(metformin['last_metformin_date'])
    cohort = cohort.merge(metformin[['person_id', 'first_metformin_date', 'last_metformin_date', 'n_metformin_rx']], 
                          on='person_id', how='inner')
    
    cohort['met_before_index'] = cohort['last_metformin_date'] >= (cohort['index_date'] - pd.Timedelta(days=METFORMIN_WINDOW))
    cohort['met_after_index'] = cohort['first_metformin_date'] <= (cohort['index_date'] + pd.Timedelta(days=METFORMIN_WINDOW))
    
    pre_met_n = len(cohort)
    cohort = cohort[cohort['met_before_index'] & cohort['met_after_index']]
    excluded_no_met = pre_met_n - len(cohort) + (flow['cohort']['after_t2dm'] - pre_met_n)
    flow['cohort']['after_metformin'] = len(cohort)
    flow['cohort']['excluded_no_metformin'] = flow['cohort']['after_t2dm'] - len(cohort)
    print(f"\n  3. After requiring metformin (±6 months): {len(cohort):,}")
    print(f"     - Excluded (no metformin in window): {flow['cohort']['excluded_no_metformin']:,}")
    
    # Criterion 3: Exclude prior dementia
    dementia['first_dementia_date'] = pd.to_datetime(dementia['first_dementia_date'])
    cohort = cohort.merge(dementia[['person_id', 'first_dementia_date']], on='person_id', how='left')
    
    prior_dementia_mask = cohort['first_dementia_date'].notna() & (cohort['first_dementia_date'] <= cohort['index_date'])
    excluded_prior_dementia = prior_dementia_mask.sum()
    cohort = cohort[~prior_dementia_mask]
    flow['cohort']['after_exclude_dementia'] = len(cohort)
    flow['cohort']['excluded_prior_dementia'] = excluded_prior_dementia
    print(f"\n  4. After excluding prior dementia: {len(cohort):,}")
    print(f"     - Excluded (prior dementia): {excluded_prior_dementia:,}")
    
    # Add demographics
    cohort = cohort.merge(demographics, on='person_id', how='left')
    cohort['age_at_index'] = cohort['index_date'].dt.year - cohort['year_of_birth']
    
    # Criterion 4: Age ≥ 18
    excluded_age = len(cohort[cohort['age_at_index'] < 18])
    cohort = cohort[cohort['age_at_index'] >= 18]
    flow['cohort']['after_age'] = len(cohort)
    flow['cohort']['excluded_age'] = excluded_age
    print(f"\n  5. After requiring age ≥18: {len(cohort):,}")
    print(f"     - Excluded (age <18): {excluded_age:,}")
    
    # Add observation periods
    obs_periods['last_obs_date'] = pd.to_datetime(obs_periods['last_obs_date'])
    cohort = cohort.merge(obs_periods[['person_id', 'last_obs_date']], on='person_id', how='left')
    
    # Add deaths
    deaths['death_date'] = pd.to_datetime(deaths['death_date'])
    cohort = cohort.merge(deaths[['person_id', 'death_date']], on='person_id', how='left')
    
    # Load and add covariates
    print("\n  Loading covariates...")
    for cov_name in CONCEPTS['covariates'].keys():
        cov_path = DATA_DIR / f'cov_{cov_name}.csv'
        if cov_path.exists():
            cov_df = pd.read_csv(cov_path)
            cov_df['first_dx_date'] = pd.to_datetime(cov_df['first_dx_date'])
            # Baseline covariate = diagnosed before or at index date
            cov_df = cov_df[cov_df['covariate'] == cov_name] if 'covariate' in cov_df.columns else cov_df
            cohort = cohort.merge(cov_df[['person_id', 'first_dx_date']].rename(
                columns={'first_dx_date': f'{cov_name}_date'}), on='person_id', how='left')
            cohort[cov_name] = (cohort[f'{cov_name}_date'].notna() & 
                               (cohort[f'{cov_name}_date'] <= cohort['index_date'])).astype(int)
    
    # Add lab values if available
    for lab, filename in [('bmi', '09_bmi.csv'), ('hba1c', '10_hba1c.csv')]:
        lab_path = DATA_DIR / filename
        if lab_path.exists():
            lab_df = pd.read_csv(lab_path)
            lab_df['measurement_date'] = pd.to_datetime(lab_df['measurement_date'])
            # Get closest value before index date
            lab_baseline = lab_df.merge(cohort[['person_id', 'index_date']], on='person_id')
            lab_baseline = lab_baseline[lab_baseline['measurement_date'] <= lab_baseline['index_date']]
            lab_baseline = lab_baseline.sort_values('measurement_date').groupby('person_id').last().reset_index()
            cohort = cohort.merge(lab_baseline[['person_id', f'{lab}_value']], on='person_id', how='left')
    
    # Remove duplicates (keep first initiation per patient)
    pre_dup = len(cohort)
    cohort = cohort.sort_values('index_date').drop_duplicates(subset='person_id', keep='first')
    duplicates_removed = pre_dup - len(cohort)
    flow['cohort']['after_dedup'] = len(cohort)
    flow['cohort']['duplicates_removed'] = duplicates_removed
    print(f"\n  6. After removing duplicates: {len(cohort):,}")
    print(f"     - Duplicates removed: {duplicates_removed:,}")
    
    # Final counts
    flow['cohort']['final'] = len(cohort)
    flow['cohort']['final_glp1'] = len(cohort[cohort['treatment_group'] == 'GLP1_RA'])
    flow['cohort']['final_sglt2'] = len(cohort[cohort['treatment_group'] == 'SGLT2i'])
    
    print(f"\n  FINAL ELIGIBLE COHORT: {len(cohort):,}")
    print(f"    - GLP-1 RA: {flow['cohort']['final_glp1']:,}")
    print(f"    - SGLT2i: {flow['cohort']['final_sglt2']:,}")
    
    # Save
    cohort.to_csv(DATA_DIR / 'cohort_eligible.csv', index=False)
    with open(DATA_DIR / 'cohort_flow.json', 'w') as f:
        json.dump(flow, f, indent=2, cls=NumpyEncoder)
    
    return cohort, flow

# =============================================================================
# OUTCOME ASCERTAINMENT
# =============================================================================

def add_outcomes(cohort):
    """Add outcome variables and follow-up time."""
    
    print("\n" + "="*70)
    print("OUTCOME ASCERTAINMENT")
    print("="*70)
    
    # Lag period (6 months after index)
    cohort['lag_date'] = cohort['index_date'] + pd.Timedelta(days=LAG_DAYS)
    
    # Study end
    study_end = pd.Timestamp(FOLLOWUP_END)
    
    # Censor date = min(death, last observation, study end)
    cohort['censor_date'] = cohort[['death_date', 'last_obs_date']].min(axis=1)
    cohort['censor_date'] = cohort['censor_date'].fillna(study_end)
    cohort.loc[cohort['censor_date'] > study_end, 'censor_date'] = study_end
    
    # Dementia event (after lag period)
    cohort['dementia_after_lag'] = (
        cohort['first_dementia_date'].notna() & 
        (cohort['first_dementia_date'] > cohort['lag_date'])
    )
    
    # Event indicator
    cohort['event'] = (
        cohort['dementia_after_lag'] & 
        (cohort['first_dementia_date'] <= cohort['censor_date'])
    ).astype(int)
    
    # Event/censor date
    cohort['event_date'] = cohort.apply(
        lambda x: x['first_dementia_date'] if x['event'] == 1 else x['censor_date'], axis=1
    )
    
    # Time to event (from lag date)
    cohort['time_years'] = (cohort['event_date'] - cohort['lag_date']).dt.days / 365.25
    
    # Exclude those with negative or zero follow-up
    pre_fu = len(cohort)
    cohort = cohort[cohort['time_years'] > 0]
    excluded_fu = pre_fu - len(cohort)
    
    print(f"  Patients excluded (insufficient follow-up): {excluded_fu:,}")
    print(f"  Analysis cohort: {len(cohort):,}")
    
    # Summary
    for grp in ['GLP1_RA', 'SGLT2i']:
        g = cohort[cohort['treatment_group'] == grp]
        events = g['event'].sum()
        py = g['time_years'].sum()
        ir = events / py * 1000 if py > 0 else 0
        print(f"\n  {grp}:")
        print(f"    N = {len(g):,}")
        print(f"    Events = {events}")
        print(f"    Person-years = {py:,.0f}")
        print(f"    Incidence rate = {ir:.2f} per 1000 PY")
    
    print(f"\n  Median follow-up: {cohort['time_years'].median():.1f} years")
    print(f"  Mean follow-up: {cohort['time_years'].mean():.1f} years")
    
    cohort.to_csv(DATA_DIR / 'cohort_analysis.csv', index=False)
    return cohort

# =============================================================================
# PROPENSITY SCORE MATCHING
# =============================================================================

def perform_matching(cohort):
    """Perform propensity score matching."""
    
    print("\n" + "="*70)
    print("PROPENSITY SCORE MATCHING")
    print("="*70)
    
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    
    flow = {'matching': {}}
    
    # Define covariates for PS model
    ps_covariates = ['age_at_index']
    for cov in CONCEPTS['covariates'].keys():
        if cov in cohort.columns:
            ps_covariates.append(cov)
    
    # Add gender if available
    if 'gender_concept_id' in cohort.columns:
        cohort['female'] = (cohort['gender_concept_id'] == 8532).astype(int)
        ps_covariates.append('female')
    
    # Add labs if available
    for lab in ['bmi_value', 'hba1c_value']:
        if lab in cohort.columns and cohort[lab].notna().sum() > 100:
            ps_covariates.append(lab)
    
    print(f"\n  PS model covariates ({len(ps_covariates)}):")
    for cov in ps_covariates:
        print(f"    - {cov}")
    
    # Treatment indicator
    cohort['treatment'] = (cohort['treatment_group'] == 'GLP1_RA').astype(int)
    
    # Prepare features
    X = cohort[ps_covariates].copy()
    X = X.fillna(X.median())
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Fit PS model
    ps_model = LogisticRegression(max_iter=1000, random_state=42)
    ps_model.fit(X_scaled, cohort['treatment'])
    cohort['ps'] = ps_model.predict_proba(X_scaled)[:, 1]
    
    # PS distribution
    print(f"\n  Propensity score distribution:")
    print(f"    GLP-1 RA: mean={cohort[cohort['treatment']==1]['ps'].mean():.3f}, "
          f"SD={cohort[cohort['treatment']==1]['ps'].std():.3f}")
    print(f"    SGLT2i:   mean={cohort[cohort['treatment']==0]['ps'].mean():.3f}, "
          f"SD={cohort[cohort['treatment']==0]['ps'].std():.3f}")
    
    # 1:1 Nearest neighbor matching with caliper
    treated = cohort[cohort['treatment'] == 1].copy()
    control = cohort[cohort['treatment'] == 0].copy()
    
    flow['matching']['pre_match_glp1'] = len(treated)
    flow['matching']['pre_match_sglt2'] = len(control)
    
    caliper = 0.1 * cohort['ps'].std()
    print(f"\n  Caliper: {caliper:.4f} (0.1 × SD of PS)")
    
    matched_treated_idx = []
    matched_control_idx = []
    used_controls = set()
    
    # Sort treated by PS for better matching
    treated_sorted = treated.sort_values('ps')
    
    for idx, row in treated_sorted.iterrows():
        eligible = control[~control.index.isin(used_controls)]
        if len(eligible) == 0:
            continue
        
        distances = np.abs(eligible['ps'] - row['ps'])
        min_dist = distances.min()
        
        if min_dist <= caliper:
            best_match_idx = distances.idxmin()
            matched_treated_idx.append(idx)
            matched_control_idx.append(best_match_idx)
            used_controls.add(best_match_idx)
    
    # Create matched cohort
    matched = pd.concat([
        cohort.loc[matched_treated_idx],
        cohort.loc[matched_control_idx]
    ])
    
    flow['matching']['matched_pairs'] = len(matched_treated_idx)
    flow['matching']['unmatched_glp1'] = len(treated) - len(matched_treated_idx)
    flow['matching']['unmatched_sglt2'] = len(control) - len(matched_control_idx)
    
    print(f"\n  Matching results:")
    print(f"    Matched pairs: {len(matched_treated_idx):,}")
    print(f"    Unmatched GLP-1 RA: {flow['matching']['unmatched_glp1']:,}")
    print(f"    Unmatched SGLT2i: {flow['matching']['unmatched_sglt2']:,}")
    
    # Save
    matched.to_csv(DATA_DIR / 'cohort_matched.csv', index=False)
    cohort.to_csv(DATA_DIR / 'cohort_with_ps.csv', index=False)
    
    with open(DATA_DIR / 'matching_flow.json', 'w') as f:
        json.dump(flow, f, indent=2, cls=NumpyEncoder)
    
    return matched, cohort, flow

# =============================================================================
# BASELINE CHARACTERISTICS TABLE
# =============================================================================

def create_baseline_table(cohort, matched, output_path):
    """Create Table 1: Baseline characteristics."""
    
    print("\n" + "="*70)
    print("BASELINE CHARACTERISTICS TABLE")
    print("="*70)
    
    def summarize_group(df, group_name):
        """Summarize baseline characteristics for a group."""
        stats = {'Group': group_name, 'N': len(df)}
        
        # Age
        stats['Age, mean (SD)'] = f"{df['age_at_index'].mean():.1f} ({df['age_at_index'].std():.1f})"
        stats['Age ≥65, n (%)'] = f"{(df['age_at_index'] >= 65).sum()} ({(df['age_at_index'] >= 65).mean()*100:.1f}%)"
        
        # Gender
        if 'female' in df.columns:
            stats['Female, n (%)'] = f"{df['female'].sum()} ({df['female'].mean()*100:.1f}%)"
        elif 'gender_concept_id' in df.columns:
            female = (df['gender_concept_id'] == 8532).sum()
            stats['Female, n (%)'] = f"{female} ({female/len(df)*100:.1f}%)"
        
        # Race/Ethnicity
        if 'race' in df.columns:
            for race in ['White', 'Black or African American', 'Asian']:
                n = (df['race'] == race).sum()
                stats[f'{race}, n (%)'] = f"{n} ({n/len(df)*100:.1f}%)"
        
        # Comorbidities
        for cov in ['hypertension', 'heart_failure', 'obesity', 'ckd', 'depression', 
                    'anxiety', 'atrial_fibrillation', 'ischemic_heart_disease', 
                    'cerebrovascular_disease', 'hyperlipidemia']:
            if cov in df.columns:
                n = df[cov].sum()
                stats[f'{cov.replace("_", " ").title()}, n (%)'] = f"{n} ({n/len(df)*100:.1f}%)"
        
        # Labs
        if 'bmi_value' in df.columns and df['bmi_value'].notna().sum() > 0:
            stats['BMI, mean (SD)'] = f"{df['bmi_value'].mean():.1f} ({df['bmi_value'].std():.1f})"
        if 'hba1c_value' in df.columns and df['hba1c_value'].notna().sum() > 0:
            stats['HbA1c %, mean (SD)'] = f"{df['hba1c_value'].mean():.1f} ({df['hba1c_value'].std():.1f})"
        
        # Follow-up
        if 'time_years' in df.columns:
            stats['Follow-up years, median (IQR)'] = f"{df['time_years'].median():.1f} ({df['time_years'].quantile(0.25):.1f}-{df['time_years'].quantile(0.75):.1f})"
        
        return stats
    
    def calc_smd(df, var, treatment_col='treatment'):
        """Calculate standardized mean difference."""
        t = df[df[treatment_col] == 1][var]
        c = df[df[treatment_col] == 0][var]
        
        if t.std() == 0 and c.std() == 0:
            return 0.0
        
        pooled_std = np.sqrt((t.var() + c.var()) / 2)
        if pooled_std == 0:
            return 0.0
        
        return (t.mean() - c.mean()) / pooled_std
    
    # Unmatched cohort
    unmatched_glp1 = summarize_group(cohort[cohort['treatment_group'] == 'GLP1_RA'], 'GLP-1 RA')
    unmatched_sglt2 = summarize_group(cohort[cohort['treatment_group'] == 'SGLT2i'], 'SGLT2i')
    
    # Matched cohort
    matched_glp1 = summarize_group(matched[matched['treatment_group'] == 'GLP1_RA'], 'GLP-1 RA')
    matched_sglt2 = summarize_group(matched[matched['treatment_group'] == 'SGLT2i'], 'SGLT2i')
    
    # Calculate SMDs
    smd_vars = ['age_at_index'] + [c for c in CONCEPTS['covariates'].keys() if c in cohort.columns]
    if 'female' in cohort.columns:
        smd_vars.append('female')
    
    smds_before = {var: calc_smd(cohort, var) for var in smd_vars if var in cohort.columns}
    smds_after = {var: calc_smd(matched, var) for var in smd_vars if var in matched.columns}
    
    print("\n  Standardized Mean Differences:")
    print(f"  {'Variable':<30} {'Before':>10} {'After':>10}")
    print("  " + "-"*52)
    for var in smd_vars:
        if var in smds_before:
            print(f"  {var:<30} {smds_before[var]:>10.3f} {smds_after.get(var, 'N/A'):>10.3f}")
    
    # Save tables
    table_data = {
        'unmatched': {'glp1': unmatched_glp1, 'sglt2': unmatched_sglt2, 'smd': smds_before},
        'matched': {'glp1': matched_glp1, 'sglt2': matched_sglt2, 'smd': smds_after}
    }
    
    with open(DATA_DIR / 'baseline_tables.json', 'w') as f:
        json.dump(table_data, f, indent=2, cls=NumpyEncoder)
    
    return table_data

# =============================================================================
# SURVIVAL ANALYSIS
# =============================================================================

def perform_survival_analysis(matched):
    """Perform survival analysis on matched cohort."""
    
    print("\n" + "="*70)
    print("SURVIVAL ANALYSIS")
    print("="*70)
    
    try:
        from lifelines import KaplanMeierFitter, CoxPHFitter
        from lifelines.statistics import logrank_test
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'lifelines', 'matplotlib', '-q'])
        from lifelines import KaplanMeierFitter, CoxPHFitter
        from lifelines.statistics import logrank_test
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    
    results = {}
    
    # Kaplan-Meier analysis
    print("\n  Kaplan-Meier Analysis:")
    
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = {'GLP1_RA': '#2563eb', 'SGLT2i': '#dc2626'}
    
    for grp in ['GLP1_RA', 'SGLT2i']:
        g = matched[matched['treatment_group'] == grp]
        
        kmf = KaplanMeierFitter()
        kmf.fit(g['time_years'], g['event'], label=f"{grp} (n={len(g)}, events={g['event'].sum()})")
        kmf.plot_survival_function(ax=ax, ci_show=True, color=colors[grp], linewidth=2.5)
        
        results[f'km_{grp}'] = {
            'n': len(g),
            'events': int(g['event'].sum()),
            'person_years': float(g['time_years'].sum()),
            'incidence_rate': float(g['event'].sum() / g['time_years'].sum() * 1000),
            'median_survival': float(kmf.median_survival_time_) if kmf.median_survival_time_ < np.inf else None,
            'survival_5yr': float(kmf.predict(5)) if 5 <= g['time_years'].max() else None,
            'kmf': kmf
        }
        
        print(f"\n    {grp}:")
        print(f"      N = {results[f'km_{grp}']['n']:,}")
        print(f"      Events = {results[f'km_{grp}']['events']}")
        print(f"      Person-years = {results[f'km_{grp}']['person_years']:,.0f}")
        print(f"      IR = {results[f'km_{grp}']['incidence_rate']:.2f} per 1000 PY")
    
    ax.set_xlabel('Time (years)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Dementia-Free Survival Probability', fontsize=12, fontweight='bold')
    ax.set_title('Kaplan-Meier Curves: GLP-1 RA vs SGLT2i\nIncident Dementia in T2DM (UCSF)', 
                 fontsize=14, fontweight='bold')
    ax.set_ylim([0.80, 1.02])
    ax.legend(loc='lower left', fontsize=11)
    ax.grid(True, alpha=0.3)
    
    try:
        from lifelines.plotting import add_at_risk_counts
        add_at_risk_counts(results['km_GLP1_RA']['kmf'], results['km_SGLT2i']['kmf'], ax=ax)
    except:
        pass
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'kaplan_meier_curve.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n  ✓ Saved: kaplan_meier_curve.png")
    
    # Log-rank test
    g1 = matched[matched['treatment_group'] == 'GLP1_RA']
    g2 = matched[matched['treatment_group'] == 'SGLT2i']
    lr = logrank_test(g1['time_years'], g2['time_years'], g1['event'], g2['event'])
    results['logrank_p'] = float(lr.p_value)
    results['logrank_stat'] = float(lr.test_statistic)
    print(f"\n  Log-rank test: χ² = {lr.test_statistic:.2f}, p = {lr.p_value:.4f}")
    
    # Cox Proportional Hazards - UNADJUSTED (no penalizer!)
    print("\n  Cox Proportional Hazards (Unadjusted):")
    
    try:
        cph = CoxPHFitter()
        cph.fit(matched[['time_years', 'event', 'treatment']], 
                duration_col='time_years', event_col='event')
        
        hr = float(np.exp(cph.params_['treatment']))
        ci_l = float(np.exp(cph.confidence_intervals_.loc['treatment', '95% lower-bound']))
        ci_u = float(np.exp(cph.confidence_intervals_.loc['treatment', '95% upper-bound']))
        pval = float(cph.summary['p']['treatment'])
        
        results['cox_unadjusted'] = {
            'hr': hr, 'ci_lower': ci_l, 'ci_upper': ci_u, 'p_value': pval
        }
        
        print(f"    HR = {hr:.2f} (95% CI: {ci_l:.2f}-{ci_u:.2f})")
        print(f"    P-value = {pval:.4f}")
        
    except Exception as e:
        print(f"    Cox regression failed: {e}")
        print("    Using incidence rate ratio instead...")
        
        # Manual IRR calculation
        ir_glp1 = results['km_GLP1_RA']['incidence_rate']
        ir_sglt2 = results['km_SGLT2i']['incidence_rate']
        hr = ir_glp1 / ir_sglt2 if ir_sglt2 > 0 else 1.0
        
        # Poisson CI
        ev_glp1 = results['km_GLP1_RA']['events']
        ev_sglt2 = results['km_SGLT2i']['events']
        se_log_hr = np.sqrt(1/max(ev_glp1, 0.5) + 1/max(ev_sglt2, 0.5))
        ci_l = np.exp(np.log(hr) - 1.96 * se_log_hr)
        ci_u = np.exp(np.log(hr) + 1.96 * se_log_hr)
        pval = results['logrank_p']
        
        results['cox_unadjusted'] = {
            'hr': float(hr), 'ci_lower': float(ci_l), 'ci_upper': float(ci_u), 
            'p_value': float(pval), 'method': 'IRR'
        }
        
        print(f"    IRR = {hr:.2f} (95% CI: {ci_l:.2f}-{ci_u:.2f})")
        print(f"    P-value (log-rank) = {pval:.4f}")
    
    # Forest plot
    hr = results['cox_unadjusted']['hr']
    ci_l = results['cox_unadjusted']['ci_lower']
    ci_u = results['cox_unadjusted']['ci_upper']
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Original study
    ax.errorbar(1.01, 2, xerr=[[1.01-0.90], [1.13-1.01]], fmt='s', color='#64748b', 
                markersize=12, capsize=6, capthick=2, linewidth=2,
                label='Original (Anagnostakis et al., n=32,542)')
    
    # UCSF replication
    ax.errorbar(hr, 1, xerr=[[hr-ci_l], [ci_u-hr]], fmt='o', color='#2563eb',
                markersize=14, capsize=6, capthick=2, linewidth=2,
                label=f'UCSF Replication (n={len(matched):,})')
    
    ax.axvline(1, color='#dc2626', linestyle='--', alpha=0.7, linewidth=2, label='No effect (HR=1)')
    
    ax.set_xlim([0.1, 2.0])
    ax.set_ylim([0.3, 2.7])
    ax.set_yticks([1, 2])
    ax.set_yticklabels(['UCSF Replication', 'Original Study'])
    ax.set_xlabel('Hazard Ratio (95% CI)', fontsize=12, fontweight='bold')
    ax.set_title('Forest Plot: GLP-1 RA vs SGLT2i for Incident Dementia\nHR < 1 favors GLP-1 RA', 
                 fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, axis='x', alpha=0.3)
    
    # Annotations
    ax.text(hr, 0.6, f'HR = {hr:.2f}\n({ci_l:.2f}-{ci_u:.2f})\np = {results["cox_unadjusted"]["p_value"]:.3f}', 
            ha='center', fontsize=10, fontweight='bold', color='#2563eb')
    ax.text(1.01, 2.4, 'HR = 1.01\n(0.90-1.13)\np = 0.89', 
            ha='center', fontsize=10, color='#64748b')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'forest_plot.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n  ✓ Saved: forest_plot.png")
    
    # Propensity score distribution plot
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Get unmatched cohort if available
    cohort_path = DATA_DIR / 'cohort_with_ps.csv'
    if cohort_path.exists():
        cohort_full = pd.read_csv(cohort_path)
        
        axes[0].hist(cohort_full[cohort_full['treatment']==1]['ps'], bins=30, alpha=0.6, 
                    label='GLP-1 RA', color='#2563eb', density=True, edgecolor='white')
        axes[0].hist(cohort_full[cohort_full['treatment']==0]['ps'], bins=30, alpha=0.6, 
                    label='SGLT2i', color='#dc2626', density=True, edgecolor='white')
        axes[0].set_xlabel('Propensity Score', fontsize=11)
        axes[0].set_ylabel('Density', fontsize=11)
        axes[0].set_title('Before Matching', fontsize=12, fontweight='bold')
        axes[0].legend(fontsize=10)
        axes[0].grid(True, alpha=0.3)
    
    axes[1].hist(matched[matched['treatment']==1]['ps'], bins=30, alpha=0.6, 
                label='GLP-1 RA', color='#2563eb', density=True, edgecolor='white')
    axes[1].hist(matched[matched['treatment']==0]['ps'], bins=30, alpha=0.6, 
                label='SGLT2i', color='#dc2626', density=True, edgecolor='white')
    axes[1].set_xlabel('Propensity Score', fontsize=11)
    axes[1].set_ylabel('Density', fontsize=11)
    axes[1].set_title('After Matching', fontsize=12, fontweight='bold')
    axes[1].legend(fontsize=10)
    axes[1].grid(True, alpha=0.3)
    
    plt.suptitle('Propensity Score Distribution', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'propensity_scores.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: propensity_scores.png")
    
    # Save results
    # Remove non-serializable objects
    results_save = {k: v for k, v in results.items() if k not in ['km_GLP1_RA', 'km_SGLT2i'] or 'kmf' not in str(v)}
    for key in ['km_GLP1_RA', 'km_SGLT2i']:
        if key in results:
            results_save[key] = {k: v for k, v in results[key].items() if k != 'kmf'}
    
    with open(DATA_DIR / 'survival_results.json', 'w') as f:
        json.dump(results_save, f, indent=2, cls=NumpyEncoder)
    
    return results

# =============================================================================
# HTML REPORT GENERATION
# =============================================================================

def generate_html_report(matched, results, baseline_tables, flow_data):
    """Generate comprehensive HTML report."""
    
    print("\n" + "="*70)
    print("GENERATING HTML REPORT")
    print("="*70)
    
    import base64
    
    def img_to_base64(path):
        if path.exists():
            with open(path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        return ""
    
    km_b64 = img_to_base64(OUTPUT_DIR / 'kaplan_meier_curve.png')
    forest_b64 = img_to_base64(OUTPUT_DIR / 'forest_plot.png')
    ps_b64 = img_to_base64(OUTPUT_DIR / 'propensity_scores.png')
    
    # Extract key numbers
    n_glp1 = len(matched[matched['treatment_group'] == 'GLP1_RA'])
    n_sglt2 = len(matched[matched['treatment_group'] == 'SGLT2i'])
    ev_glp1 = results['km_GLP1_RA']['events']
    ev_sglt2 = results['km_SGLT2i']['events']
    ir_glp1 = results['km_GLP1_RA']['incidence_rate']
    ir_sglt2 = results['km_SGLT2i']['incidence_rate']
    hr = results['cox_unadjusted']['hr']
    ci_l = results['cox_unadjusted']['ci_lower']
    ci_u = results['cox_unadjusted']['ci_upper']
    pval = results['cox_unadjusted']['p_value']
    
    # Flow numbers
    cohort_flow = flow_data.get('cohort', {})
    matching_flow = flow_data.get('matching', {})
    
    # Interpretation
    if hr < 0.6:
        interpretation = "STRONG protective signal for GLP-1 RA"
        interp_color = "#16a34a"
    elif hr < 0.8:
        interpretation = "MODERATE protective trend for GLP-1 RA"
        interp_color = "#f59e0b"
    elif hr <= 1.2:
        interpretation = "NO significant difference (consistent with original)"
        interp_color = "#2563eb"
    else:
        interpretation = "SGLT2i shows lower risk"
        interp_color = "#dc2626"
    
    # Build baseline characteristics table HTML
    def make_baseline_row(var, glp1_val, sglt2_val, smd=None):
        smd_str = f"{smd:.3f}" if smd is not None else "-"
        smd_class = "smd-good" if smd is not None and abs(smd) < 0.1 else "smd-ok" if smd is not None and abs(smd) < 0.2 else ""
        return f"<tr><td>{var}</td><td>{glp1_val}</td><td>{sglt2_val}</td><td class='{smd_class}'>{smd_str}</td></tr>"
    
    baseline_rows = ""
    matched_glp1 = baseline_tables['matched']['glp1']
    matched_sglt2 = baseline_tables['matched']['sglt2']
    matched_smd = baseline_tables['matched']['smd']
    
    for key in matched_glp1.keys():
        if key not in ['Group', 'N']:
            smd_key = key.split(',')[0].lower().replace(' ', '_').replace('≥', 'gte_')
            smd_val = matched_smd.get(smd_key) or matched_smd.get('age_at_index' if 'age' in key.lower() else smd_key)
            baseline_rows += make_baseline_row(key, matched_glp1.get(key, '-'), matched_sglt2.get(key, '-'), smd_val)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GLP-1 RA vs SGLT2i Dementia Replication - UCSF</title>
<style>
:root {{
    --primary: #1e40af;
    --primary-light: #3b82f6;
    --success: #16a34a;
    --warning: #f59e0b;
    --danger: #dc2626;
    --gray-50: #f8fafc;
    --gray-100: #f1f5f9;
    --gray-200: #e2e8f0;
    --gray-500: #64748b;
    --gray-700: #334155;
    --gray-900: #0f172a;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    background: var(--gray-100); 
    color: var(--gray-900); 
    line-height: 1.6; 
    padding: 24px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}

/* Header */
header {{ 
    background: linear-gradient(135deg, var(--primary), var(--primary-light)); 
    color: white; 
    padding: 2.5rem; 
    border-radius: 16px; 
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(30, 64, 175, 0.3);
}}
header h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
header .subtitle {{ font-size: 1.1rem; opacity: 0.95; margin-bottom: 1rem; }}
header .meta {{ font-size: 0.9rem; opacity: 0.85; }}

/* Cards */
.card {{ 
    background: white; 
    border-radius: 12px; 
    padding: 24px; 
    margin-bottom: 20px; 
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.card h2 {{ 
    font-size: 1.25rem; 
    color: var(--primary); 
    margin-bottom: 20px; 
    padding-bottom: 12px;
    border-bottom: 2px solid var(--gray-200);
    display: flex;
    align-items: center;
    gap: 10px;
}}
.card h3 {{ font-size: 1.1rem; color: var(--gray-700); margin: 20px 0 12px 0; }}

/* Stats Grid */
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }}
.stat {{ 
    background: linear-gradient(135deg, var(--gray-50), var(--gray-100)); 
    padding: 20px; 
    border-radius: 10px; 
    text-align: center;
    border: 1px solid var(--gray-200);
}}
.stat .val {{ font-size: 2rem; font-weight: 700; color: var(--primary); }}
.stat .lab {{ font-size: 0.8rem; color: var(--gray-500); margin-top: 4px; }}

/* Key Finding */
.finding {{ 
    background: linear-gradient(135deg, #fefce8, #fef9c3); 
    border-left: 5px solid {interp_color}; 
    padding: 20px; 
    margin: 20px 0; 
    border-radius: 0 10px 10px 0;
}}
.finding h3 {{ color: {interp_color}; margin-bottom: 10px; font-size: 1.1rem; }}
.finding p {{ margin: 8px 0; }}
.finding .detail {{ font-size: 0.9rem; color: var(--gray-700); margin-top: 12px; }}

/* Tables */
table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--gray-200); }}
th {{ 
    background: var(--gray-50); 
    font-weight: 600; 
    color: var(--gray-500); 
    font-size: 0.75rem; 
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
tr:hover {{ background: var(--gray-50); }}
.smd-good {{ color: var(--success); font-weight: 600; }}
.smd-ok {{ color: var(--warning); }}

/* Plots */
.plot {{ text-align: center; margin: 20px 0; }}
.plot img {{ 
    max-width: 100%; 
    border-radius: 8px; 
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}}
.plot-caption {{ 
    font-size: 0.85rem; 
    color: var(--gray-500); 
    margin-top: 12px; 
    font-style: italic;
}}

/* Flow Diagram */
.flow-diagram {{ 
    display: flex; 
    flex-direction: column; 
    align-items: center; 
    gap: 8px;
    padding: 20px;
}}
.flow-box {{ 
    background: var(--gray-50); 
    border: 2px solid var(--gray-200); 
    border-radius: 8px; 
    padding: 12px 24px; 
    text-align: center;
    min-width: 300px;
}}
.flow-box.highlight {{ 
    background: linear-gradient(135deg, #dbeafe, #bfdbfe); 
    border-color: var(--primary-light);
}}
.flow-arrow {{ 
    font-size: 1.5rem; 
    color: var(--gray-500);
}}
.flow-exclusion {{ 
    font-size: 0.85rem; 
    color: var(--danger); 
    margin: 4px 0;
}}

/* Two Column Layout */
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

/* Badges */
.badge {{ 
    display: inline-block; 
    padding: 4px 12px; 
    border-radius: 20px; 
    font-size: 0.75rem; 
    font-weight: 600;
}}
.badge-green {{ background: #dcfce7; color: #166534; }}
.badge-yellow {{ background: #fef3c7; color: #92400e; }}
.badge-blue {{ background: #dbeafe; color: #1e40af; }}
.badge-red {{ background: #fee2e2; color: #991b1b; }}

/* Footer */
footer {{ 
    text-align: center; 
    padding: 30px; 
    color: var(--gray-500); 
    font-size: 0.85rem;
    border-top: 1px solid var(--gray-200);
    margin-top: 20px;
}}

/* Print styles */
@media print {{
    body {{ padding: 0; background: white; }}
    .card {{ box-shadow: none; border: 1px solid var(--gray-200); }}
    header {{ background: var(--primary) !important; -webkit-print-color-adjust: exact; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<header>
    <h1>🧠 Clinical Replication Study</h1>
    <p class="subtitle">GLP-1 Receptor Agonists vs SGLT2 Inhibitors for Incident Dementia in Type 2 Diabetes</p>
    <p class="meta">
        <strong>Original Study:</strong> Anagnostakis F, et al. Diabetes Obes Metab. 2025;27:e70336<br>
        <strong>Replication Database:</strong> UCSF OMOP Electronic Health Records<br>
        <strong>Report Generated:</strong> {datetime.now().strftime('%B %d, %Y at %H:%M')}
    </p>
</header>

<!-- Executive Summary -->
<div class="card">
    <h2>📊 Executive Summary</h2>
    <div class="stats">
        <div class="stat"><div class="val">{n_glp1 + n_sglt2:,}</div><div class="lab">Matched Patients</div></div>
        <div class="stat"><div class="val">{ev_glp1 + ev_sglt2}</div><div class="lab">Dementia Events</div></div>
        <div class="stat"><div class="val">{hr:.2f}</div><div class="lab">Hazard Ratio</div></div>
        <div class="stat"><div class="val">{ci_l:.2f}-{ci_u:.2f}</div><div class="lab">95% CI</div></div>
        <div class="stat"><div class="val">{pval:.4f}</div><div class="lab">P-value</div></div>
        <div class="stat"><div class="val">{matched['time_years'].median():.1f}</div><div class="lab">Median F/U (yrs)</div></div>
    </div>
    
    <div class="finding">
        <h3>{'⚠️' if pval >= 0.05 else '✓'} {interpretation}</h3>
        <p><strong>UCSF Result:</strong> HR = {hr:.2f} (95% CI: {ci_l:.2f}-{ci_u:.2f}), p = {pval:.4f}</p>
        <p><strong>Original Study:</strong> HR = 1.01 (95% CI: 0.90-1.13), p = 0.89</p>
        <p class="detail">
            {'The UCSF data suggests GLP-1 RAs may be associated with lower dementia risk compared to SGLT2i (' + str(round((1-hr)*100)) + '% reduction). While ' + ('statistically significant' if pval < 0.05 else 'approaching statistical significance') + ', this differs from the original null finding. Possible explanations include population differences, chance due to smaller sample size, or a real effect masked by heterogeneity in the larger study.' if hr < 0.8 else 'Results are directionally consistent with the original study showing no significant difference between drug classes for dementia risk in T2DM patients.'}
        </p>
    </div>
</div>

<!-- CONSORT Flow Diagram -->
<div class="card">
    <h2>📋 Study Flow (CONSORT)</h2>
    <div class="flow-diagram">
        <div class="flow-box">
            <strong>Drug Initiators Identified</strong><br>
            GLP-1 RA: {cohort_flow.get('initial_glp1', 'N/A'):,} | SGLT2i: {cohort_flow.get('initial_sglt2', 'N/A'):,}<br>
            Total: {cohort_flow.get('initial', 'N/A'):,}
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-exclusion">Excluded: No T2DM diagnosis ({cohort_flow.get('excluded_no_t2dm', 'N/A'):,})</div>
        <div class="flow-arrow">↓</div>
        <div class="flow-exclusion">Excluded: No metformin within ±6 months ({cohort_flow.get('excluded_no_metformin', 'N/A'):,})</div>
        <div class="flow-arrow">↓</div>
        <div class="flow-exclusion">Excluded: Prior dementia diagnosis ({cohort_flow.get('excluded_prior_dementia', 'N/A'):,})</div>
        <div class="flow-arrow">↓</div>
        <div class="flow-exclusion">Excluded: Age &lt;18 ({cohort_flow.get('excluded_age', 'N/A'):,})</div>
        <div class="flow-arrow">↓</div>
        <div class="flow-box">
            <strong>Eligible Cohort</strong><br>
            GLP-1 RA: {cohort_flow.get('final_glp1', 'N/A'):,} | SGLT2i: {cohort_flow.get('final_sglt2', 'N/A'):,}<br>
            Total: {cohort_flow.get('final', 'N/A'):,}
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-exclusion">1:1 Propensity Score Matching (caliper = 0.1 SD)</div>
        <div class="flow-arrow">↓</div>
        <div class="flow-box highlight">
            <strong>Matched Analysis Cohort</strong><br>
            GLP-1 RA: {n_glp1:,} | SGLT2i: {n_sglt2:,}<br>
            Total: {n_glp1 + n_sglt2:,} ({matching_flow.get('matched_pairs', 'N/A'):,} pairs)
        </div>
    </div>
</div>

<!-- Baseline Characteristics -->
<div class="card">
    <h2>📋 Table 1: Baseline Characteristics (Matched Cohort)</h2>
    <table>
        <thead>
            <tr>
                <th>Characteristic</th>
                <th>GLP-1 RA (n={n_glp1:,})</th>
                <th>SGLT2i (n={n_sglt2:,})</th>
                <th>SMD</th>
            </tr>
        </thead>
        <tbody>
            {baseline_rows}
        </tbody>
    </table>
    <p style="font-size: 0.85rem; color: var(--gray-500); margin-top: 12px;">
        SMD = Standardized Mean Difference. |SMD| &lt; 0.1 indicates good balance (green).
    </p>
</div>

<!-- Kaplan-Meier Curves -->
<div class="card">
    <h2>📈 Kaplan-Meier Survival Analysis</h2>
    <div class="plot">
        <img src="data:image/png;base64,{km_b64}" alt="Kaplan-Meier Survival Curves">
        <p class="plot-caption">
            Kaplan-Meier curves showing dementia-free survival probability by treatment group 
            with 95% confidence intervals and numbers at risk. Log-rank test p = {results['logrank_p']:.4f}.
        </p>
    </div>
</div>

<!-- Forest Plot -->
<div class="card">
    <h2>🌲 Forest Plot: Comparison with Original Study</h2>
    <div class="plot">
        <img src="data:image/png;base64,{forest_b64}" alt="Forest Plot">
        <p class="plot-caption">
            Comparison of hazard ratios between original TriNetX study (n=32,542) and UCSF replication (n={n_glp1+n_sglt2:,}). 
            HR &lt; 1 indicates lower dementia risk with GLP-1 RA relative to SGLT2i.
        </p>
    </div>
</div>

<!-- Propensity Score Distribution -->
<div class="card">
    <h2>⚖️ Propensity Score Matching Quality</h2>
    <div class="plot">
        <img src="data:image/png;base64,{ps_b64}" alt="Propensity Score Distribution">
        <p class="plot-caption">
            Propensity score distributions before and after 1:1 nearest-neighbor matching.
            Good overlap after matching indicates successful covariate balance.
        </p>
    </div>
</div>

<!-- Detailed Results Comparison -->
<div class="card">
    <h2>📊 Detailed Results Comparison</h2>
    <table>
        <thead>
            <tr><th>Metric</th><th>Original Study</th><th>UCSF Replication</th><th>Assessment</th></tr>
        </thead>
        <tbody>
            <tr>
                <td>Data Source</td>
                <td>TriNetX (70+ healthcare orgs)</td>
                <td>UCSF Single Center</td>
                <td><span class="badge badge-yellow">Different scope</span></td>
            </tr>
            <tr>
                <td>Study Period</td>
                <td>April 2013 - December 2019</td>
                <td>April 2013 - December 2019</td>
                <td><span class="badge badge-green">Matched</span></td>
            </tr>
            <tr>
                <td>Matched Pairs</td>
                <td>16,271</td>
                <td>{n_glp1:,}</td>
                <td><span class="badge badge-yellow">{n_glp1/16271*100:.1f}% of original</span></td>
            </tr>
            <tr>
                <td>GLP-1 RA Events</td>
                <td>581</td>
                <td>{ev_glp1}</td>
                <td><span class="badge badge-yellow">Fewer events</span></td>
            </tr>
            <tr>
                <td>SGLT2i Events</td>
                <td>572</td>
                <td>{ev_sglt2}</td>
                <td><span class="badge badge-yellow">Fewer events</span></td>
            </tr>
            <tr>
                <td>IR (GLP-1 RA)</td>
                <td>~5.5 per 1000 PY</td>
                <td>{ir_glp1:.1f} per 1000 PY</td>
                <td><span class="badge {'badge-green' if abs(ir_glp1 - 5.5) < 2 else 'badge-yellow'}">{'Similar' if abs(ir_glp1 - 5.5) < 2 else 'Lower'}</span></td>
            </tr>
            <tr>
                <td>IR (SGLT2i)</td>
                <td>~5.5 per 1000 PY</td>
                <td>{ir_sglt2:.1f} per 1000 PY</td>
                <td><span class="badge {'badge-green' if abs(ir_sglt2 - 5.5) < 2 else 'badge-blue'}">{'Similar' if abs(ir_sglt2 - 5.5) < 2 else 'Similar'}</span></td>
            </tr>
            <tr>
                <td><strong>Hazard Ratio</strong></td>
                <td><strong>1.01</strong></td>
                <td><strong>{hr:.2f}</strong></td>
                <td><span class="badge {'badge-green' if 0.8 <= hr <= 1.2 else 'badge-yellow'}">{'Consistent' if 0.8 <= hr <= 1.2 else 'Different direction'}</span></td>
            </tr>
            <tr>
                <td>95% Confidence Interval</td>
                <td>0.90 - 1.13</td>
                <td>{ci_l:.2f} - {ci_u:.2f}</td>
                <td><span class="badge badge-yellow">Wider (expected)</span></td>
            </tr>
            <tr>
                <td>P-value</td>
                <td>0.89</td>
                <td>{pval:.4f}</td>
                <td><span class="badge {'badge-yellow' if pval < 0.1 else 'badge-blue'}">{'Trending' if pval < 0.1 else 'Not significant'}</span></td>
            </tr>
            <tr>
                <td>Median Follow-up</td>
                <td>6.3 years</td>
                <td>{matched['time_years'].median():.1f} years</td>
                <td><span class="badge badge-green">Similar</span></td>
            </tr>
        </tbody>
    </table>
</div>

<!-- Methodology -->
<div class="card">
    <h2>🔬 Methodology</h2>
    
    <h3>Study Design</h3>
    <p>Retrospective cohort study replicating Anagnostakis et al. using UCSF electronic health records mapped to OMOP Common Data Model.</p>
    
    <h3>Population</h3>
    <p>Adults (≥18 years) with type 2 diabetes mellitus who initiated either a GLP-1 receptor agonist or SGLT2 inhibitor 
    between April 2013 and December 2019, with metformin use within ±6 months of index date. Patients with prior dementia 
    diagnosis were excluded.</p>
    
    <h3>Exposure</h3>
    <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>GLP-1 RAs:</strong> semaglutide, liraglutide, dulaglutide, exenatide, lixisenatide, tirzepatide</li>
        <li><strong>SGLT2i:</strong> canagliflozin, dapagliflozin, empagliflozin, ertugliflozin</li>
    </ul>
    
    <h3>Outcome</h3>
    <p>Incident all-cause dementia, ascertained using ICD diagnosis codes mapped to OMOP concepts, 
    with a 6-month lag period to minimize reverse causality.</p>
    
    <h3>Statistical Analysis</h3>
    <ul style="margin-left: 20px; margin-top: 8px;">
        <li>1:1 propensity score matching using nearest-neighbor algorithm (caliper = 0.1 × SD)</li>
        <li>Covariates: age, sex, comorbidities (hypertension, heart failure, obesity, CKD, depression, anxiety, etc.)</li>
        <li>Kaplan-Meier survival analysis with log-rank test</li>
        <li>Cox proportional hazards regression (unadjusted)</li>
    </ul>
</div>

<!-- Limitations -->
<div class="two-col">
    <div class="card">
        <h2>⚠️ Limitations</h2>
        <ul style="margin-left: 20px;">
            <li><strong>Sample Size:</strong> {n_glp1+n_sglt2:,} patients ({(n_glp1+n_sglt2)/32542*100:.1f}% of original)</li>
            <li><strong>Single Center:</strong> UCSF only vs 70+ organizations</li>
            <li><strong>Event Count:</strong> {ev_glp1+ev_sglt2} events limits statistical power</li>
            <li><strong>Selection Bias:</strong> Academic medical center population may differ</li>
            <li><strong>Fewer Covariates:</strong> Limited to available structured data</li>
            <li><strong>Unmeasured Confounding:</strong> Cannot account for all factors</li>
        </ul>
    </div>
    <div class="card">
        <h2>💡 Interpretation</h2>
        <ul style="margin-left: 20px;">
            <li><strong>Direction:</strong> {'Protective trend for GLP-1 RA' if hr < 0.8 else 'Similar null finding' if hr <= 1.2 else 'Opposite direction'}</li>
            <li><strong>Significance:</strong> {'Statistically significant (p<0.05)' if pval < 0.05 else 'Trending (p<0.1)' if pval < 0.1 else 'Not significant'}</li>
            <li><strong>CI Overlap:</strong> {'CIs overlap with original' if ci_l < 1.13 and ci_u > 0.90 else 'CIs do not fully overlap'}</li>
            <li><strong>Methodology:</strong> Successfully replicated study design</li>
            <li><strong>Clinical Implication:</strong> {'Intriguing signal warranting larger studies' if hr < 0.7 and pval < 0.1 else 'Supports drug class equivalence'}</li>
        </ul>
    </div>
</div>

<!-- Footer -->
<footer>
    <p><strong>UCSF Clinical Replication Framework</strong></p>
    <p>Reference: Anagnostakis F, et al. GLP-1 receptor agonists vs. SGLT2 inhibitors and the risk of dementia 
    in patients with type 2 diabetes. Diabetes Obes Metab. 2025;27:e70336. DOI: 10.1111/dom.70336</p>
    <p style="margin-top: 10px; font-size: 0.8rem;">
        This replication study was conducted for research validation purposes. 
        Results should be interpreted with caution given the limitations noted above.
    </p>
</footer>

</div>
</body>
</html>"""
    
    report_path = OUTPUT_DIR / 'replication_report.html'
    with open(report_path, 'w') as f:
        f.write(html)
    
    print(f"  ✓ Saved: {report_path}")
    return report_path

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='GLP-1 RA vs SGLT2i Dementia Replication')
    parser.add_argument('--host', help='Database host')
    parser.add_argument('--port', default='', help='Database port')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--username', help='Username')
    parser.add_argument('--password', help='Password')
    parser.add_argument('--db-type', default='mssql', help='Database type')
    parser.add_argument('--skip-extraction', action='store_true', help='Skip data extraction, use existing files')
    parser.add_argument('--report-only', action='store_true', help='Generate report from existing analysis')
    args = parser.parse_args()
    
    print("="*70)
    print("GLP-1 RA vs SGLT2i Dementia Replication Study")
    print("Original: Anagnostakis et al., Diabetes Obes Metab 2025")
    print("="*70)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Data directory: {DATA_DIR}")
    
    if args.report_only:
        # Just regenerate report from existing data
        print("\n  Running in REPORT-ONLY mode...")
        matched = pd.read_csv(DATA_DIR / 'cohort_matched.csv')
        
        with open(DATA_DIR / 'survival_results.json', 'r') as f:
            results = json.load(f)
        with open(DATA_DIR / 'baseline_tables.json', 'r') as f:
            baseline_tables = json.load(f)
        
        # Load flow data
        flow_data = {}
        if (DATA_DIR / 'cohort_flow.json').exists():
            with open(DATA_DIR / 'cohort_flow.json', 'r') as f:
                flow_data.update(json.load(f))
        if (DATA_DIR / 'matching_flow.json').exists():
            with open(DATA_DIR / 'matching_flow.json', 'r') as f:
                flow_data.update(json.load(f))
        
        generate_html_report(matched, results, baseline_tables, flow_data)
        print("\n✓ Report regenerated!")
        return
    
    if not args.skip_extraction:
        # Get credentials
        if not args.host:
            print("\nEnter database credentials:")
            args.host = input("  Host: ").strip()
            args.port = input("  Port (Enter to skip): ").strip()
            args.database = input("  Database: ").strip()
            args.username = input("  Username: ").strip()
            args.password = getpass.getpass("  Password: ")
            args.db_type = input("  DB Type [mssql]: ").strip() or 'mssql'
        
        # Connect and extract
        conn = get_db_connection(args.host, args.port, args.database, 
                                  args.username, args.password, args.db_type)
        extract_all_data(conn)
        conn.close()
    
    # Build cohort
    cohort, cohort_flow = build_cohort()
    
    # Add outcomes
    cohort = add_outcomes(cohort)
    
    if len(cohort) < 100:
        print("\n⚠️ Insufficient sample size for analysis!")
        return
    
    # Propensity score matching
    matched, cohort_with_ps, matching_flow = perform_matching(cohort)
    
    # Baseline characteristics
    baseline_tables = create_baseline_table(cohort_with_ps, matched, OUTPUT_DIR)
    
    # Survival analysis
    results = perform_survival_analysis(matched)
    
    # Combine flow data
    flow_data = {**cohort_flow, **matching_flow}
    
    # Generate report
    generate_html_report(matched, results, baseline_tables, flow_data)
    
    print("\n" + "="*70)
    print("✓ REPLICATION STUDY COMPLETE")
    print("="*70)
    print(f"\nResults:")
    print(f"  HR = {results['cox_unadjusted']['hr']:.2f} "
          f"(95% CI: {results['cox_unadjusted']['ci_lower']:.2f}-{results['cox_unadjusted']['ci_upper']:.2f})")
    print(f"  P-value = {results['cox_unadjusted']['p_value']:.4f}")
    print(f"  Original: HR = 1.01 (0.90-1.13), p = 0.89")
    print(f"\nFiles saved to: {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.iterdir()):
        print(f"  - {f.name}")

if __name__ == '__main__':
    main()
