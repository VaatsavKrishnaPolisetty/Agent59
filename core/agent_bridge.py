import json
import os
import uuid
from datetime import datetime

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mock_faculty.json')
CONTEST_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'contest_audit_log.json')
EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'evidence')
os.makedirs(EVIDENCE_DIR, exist_ok=True)

STAGES = [
    "Stage 1: Raw Ingestion (Agents 6, 27, 58)",
    "Stage 2: Faculty Self-Review & Verification",
    "Stage 3: HoD Oversight & Fairness Audit",
    "Stage 4: Sealed & Dispatched (Agent 60 & HR)"
]

def load_faculty_records():
    """Loads current faculty records from disk."""
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, 'r') as f:
        return json.load(f)

def save_faculty_records(records):
    """Saves updated faculty records to disk."""
    with open(DATA_PATH, 'w') as f:
        json.dump(records, f, indent=2)

def add_faculty_profile(faculty_id, name, designation, department="Computer Science & Engineering", school="School of Engineering"):
    """Creates a new faculty record initialized with clean defaults."""
    records = load_faculty_records()
    if any(f["faculty_id"] == faculty_id for f in records):
        raise ValueError(f"Faculty with ID '{faculty_id}' already exists.")
        
    new_faculty = {
        "faculty_id": faculty_id,
        "name": name,
        "designation": designation,
        "department": department,
        "school": school,
        "teaching": {
            "courses": [
                {
                    "course_name": "Foundations of Computing",
                    "difficulty_rating": 1.1,
                    "class_size": 60,
                    "syllabus_coverage_percentage": 85,
                    "pass_rate_percentage": 75,
                    "student_feedback_score": 3.8
                }
            ],
            "direct_teaching_hours_per_week": 14
        },
        "research": {
            "publications": [],
            "patents": [],
            "funded_grants": 0,
            "phd_students_guided": 0
        },
        "service": {
            "administrative_roles": [],
            "committees": ["Department Academic Committee"],
            "fdps_attended": 1
        }
    }
    records.append(new_faculty)
    save_faculty_records(records)
    return new_faculty

def delete_faculty_profile(faculty_id):
    """Deletes a faculty profile by faculty_id."""
    records = load_faculty_records()
    filtered = [f for f in records if f["faculty_id"] != faculty_id]
    if len(filtered) == len(records):
        raise ValueError(f"Faculty ID '{faculty_id}' not found.")
    save_faculty_records(filtered)
    return True

def ingest_upstream_event(faculty_id, source_agent, event_type, payload):
    """
    Ingests live updates from upstream agents:
    - Agent 6: Course completion, syllabus coverage, pass rates
    - Agent 27: FDP & certification credits
    - Agent 58: Governance & committee appointments
    - Research APIs: Scopus/WoS publication indexing
    """
    records = load_faculty_records()
    faculty = next((f for f in records if f["faculty_id"] == faculty_id), None)
    if not faculty:
        raise ValueError(f"Faculty ID '{faculty_id}' not found.")
        
    log_entry = {
        "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_agent": source_agent,
        "event_type": event_type,
        "faculty_id": faculty_id,
        "details": payload
    }
    
    if source_agent == "Agent_6_Curriculum":
        # Add or update course record
        course_name = payload.get("course_name", "New Course")
        existing_course = next((c for c in faculty["teaching"]["courses"] if c["course_name"] == course_name), None)
        if existing_course:
            existing_course.update(payload)
        else:
            faculty["teaching"]["courses"].append(payload)
            
    elif source_agent == "Agent_27_FDP":
        # Increment FDP certifications
        faculty["service"]["fdps_attended"] += payload.get("fdp_count", 1)
        
    elif source_agent == "Agent_58_Governance":
        # Add administrative role or committee
        if "role" in payload and payload["role"]:
            if payload["role"] not in faculty["service"]["administrative_roles"]:
                faculty["service"]["administrative_roles"].append(payload["role"])
        if "committee" in payload and payload["committee"]:
            if payload["committee"] not in faculty["service"]["committees"]:
                faculty["service"]["committees"].append(payload["committee"])
                
    elif source_agent == "Research_Scopus_WoS":
        # Add publication
        faculty["research"]["publications"].append(payload)
        
    save_faculty_records(records)
    return log_entry

def dispatch_to_agent_60(faculty_id, faculty_name, gap_description, priority="HIGH"):
    """
    Generates an outbound JSON ticket dispatched to Agent 60 (Pedagogy & Upskilling).
    """
    ticket = {
        "ticket_id": f"UPGRADE-TKT-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sender_agent": "Agent_59_FacultyPerformance",
        "recipient_agent": "Agent_60_PedagogicalUpskilling",
        "target_faculty": {
            "faculty_id": faculty_id,
            "name": faculty_name
        },
        "diagnostic_context": {
            "identified_developmental_gap": gap_description,
            "prescribed_intervention": "Targeted Workshop on Active Learning & Student Engagement",
            "recommended_timeline": "Before next semester commencement",
            "priority": priority
        },
        "status": "DISPATCHED_TO_AGENT_60"
    }
    return ticket

def dispatch_to_hr_payroll(faculty_id, faculty_name, total_score, category_breakdown, approver="Dean / HoD"):
    """
    Generates the sealed appraisal payload for Institutional HR & Payroll.
    """
    performance_band = "Tier 1: Exemplary" if total_score >= 80 else ("Tier 2: Commendable" if total_score >= 60 else "Tier 3: Developmental")
    payload = {
        "appraisal_id": f"APR-{datetime.now().year}-{faculty_id}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "faculty_id": faculty_id,
        "name": faculty_name,
        "score_summary": {
            "total_score": total_score,
            "breakdown": category_breakdown,
            "performance_band": performance_band
        },
        "actions_authorized": [
            "Merit-based annual increment calculation",
            "Eligible for research seed grant consideration" if category_breakdown.get("research", 0) >= 20 else "Standard annual increment",
            "Accreditation documentation sync (NAAC / NIRF)"
        ],
        "digital_seal": {
            "sealed_by": approver,
            "signature_hash": f"SHA256:{uuid.uuid5(uuid.NAMESPACE_DNS, f'{faculty_id}-{total_score}').hex}"
        },
        "status": "SEALED_AND_FILED"
    }
    return payload

def load_contest_logs():
    """Loads all historical contest and audit logs."""
    if not os.path.exists(CONTEST_LOG_PATH):
        return []
    try:
        with open(CONTEST_LOG_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_contest_log_entry(faculty_id, faculty_name, metric, explanation, document_name="None attached", file_bytes=None):
    """Appends a new contest log entry to the persistent log file and saves any uploaded evidence."""
    logs = load_contest_logs()
    log_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
    saved_rel_path = None
    
    if file_bytes and document_name and document_name != "None attached":
        safe_name = "".join(c for c in document_name if c.isalnum() or c in "._- ")
        saved_file_name = f"{log_id}_{safe_name}"
        saved_full_path = os.path.join(EVIDENCE_DIR, saved_file_name)
        try:
            with open(saved_full_path, "wb") as ef:
                ef.write(file_bytes)
            saved_rel_path = os.path.join("data", "evidence", saved_file_name)
        except Exception:
            saved_rel_path = None
            
    entry = {
        "log_id": log_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "faculty_id": faculty_id,
        "faculty_name": faculty_name,
        "metric_contested": metric,
        "justification": explanation,
        "evidence_document": document_name,
        "evidence_file_path": saved_rel_path,
        "status": "Pending Review",
        "hod_remark": "",
        "adjustment_applied": "",
        "resolved_at": ""
    }
    logs.append(entry)
    with open(CONTEST_LOG_PATH, 'w') as f:
        json.dump(logs, f, indent=2)
    return entry

def update_contest_log_by_id(log_id, new_status, hod_remark="", adjustment_applied=""):
    """Updates a specific contest log entry by its unique log_id."""
    logs = load_contest_logs()
    updated = False
    for item in logs:
        if item.get("log_id") == log_id:
            item["status"] = new_status
            item["hod_remark"] = hod_remark
            item["adjustment_applied"] = adjustment_applied
            item["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated = True
            break
    if updated:
        with open(CONTEST_LOG_PATH, 'w') as f:
            json.dump(logs, f, indent=2)
    return updated

def apply_course_metric_correction(faculty_id, new_syllabus=100, new_pass_rate=None):
    """
    Directly updates the underlying course data in mock_faculty.json so changes
    propagate dynamically across the course delivery table, XAI math, and scores.
    """
    records = load_faculty_records()
    faculty = next((f for f in records if f["faculty_id"] == faculty_id), None)
    if not faculty or not faculty.get("teaching", {}).get("courses"):
        return False
        
    primary_course = faculty["teaching"]["courses"][0]
    if new_syllabus is not None:
        primary_course["syllabus_coverage_percentage"] = new_syllabus
    if new_pass_rate is not None:
        primary_course["pass_rate_percentage"] = new_pass_rate
        
    save_faculty_records(records)
    return True

def apply_research_metric_correction(faculty_id, title="Verified Scopus Publication (HoD Approved)", quartile="Q1"):
    """Adds a verified publication directly to the faculty's research record in mock_faculty.json."""
    records = load_faculty_records()
    faculty = next((f for f in records if f["faculty_id"] == faculty_id), None)
    if not faculty:
        return False
    faculty["research"]["publications"].append({
        "title": title,
        "doi": f"10.1016/j.verified.{datetime.now().strftime('%Y%m%d%H%M')}",
        "index": "Scopus",
        "quartile": quartile
    })
    save_faculty_records(records)
    return True

def generate_mock_longitudinal_data(faculty_id, current_score):
    """Generates mock 3-year historical total scores for trend analysis based on current score."""
    import random
    random.seed(faculty_id) # deterministic mock
    return {
        "AY 2024-25": round(current_score - random.uniform(2, 8), 1),
        "AY 2025-26": round(current_score - random.uniform(-1, 5), 1),
        "AY 2026-27 (Current)": round(current_score, 1)
    }

