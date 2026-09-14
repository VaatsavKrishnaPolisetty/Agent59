import json
import os

def load_data():
    """Loads the mock data and rubric from the data directory."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, 'data', 'rubric.json'), 'r') as f:
        rubric = json.load(f)
    with open(os.path.join(base_dir, 'data', 'mock_faculty.json'), 'r') as f:
        faculty_data = json.load(f)
    return rubric, faculty_data

def evaluate_teaching(faculty):
    """Evaluates teaching based on syllabus, pass rate (normalized), feedback, and hours."""
    # Max points: 40 (Syllabus 10, Pass rate 10, Feedback 10, Hours 10)
    teaching = faculty.get('teaching', {})
    courses = teaching.get('courses', [])
    hours = teaching.get('direct_teaching_hours_per_week', 0)
    
    if not courses:
        return 0, {}, {"syllabus": 0, "pass": 0, "feedback": 0, "hours": 0}
    
    # Averages across all courses taught by the faculty
    avg_difficulty = sum(c.get('difficulty_rating', 1.0) for c in courses) / len(courses)
    avg_syllabus = sum(c.get('syllabus_coverage_percentage', 0) for c in courses) / len(courses)
    avg_pass_rate = sum(c.get('pass_rate_percentage', 0) for c in courses) / len(courses)
    avg_feedback = sum(c.get('student_feedback_score', 0) for c in courses) / len(courses)
    
    # 1. Syllabus (Max 10 pts)
    syllabus_score = (avg_syllabus / 100.0) * 10.0
    
    # 2. Pass Rate (Max 10 pts) - normalized with difficulty rating
    normalized_pass_rate = min(100.0, avg_pass_rate * avg_difficulty)
    pass_rate_score = (normalized_pass_rate / 100.0) * 10.0
    
    # 3. Feedback (Max 10 pts, out of 5)
    feedback_score = (avg_feedback / 5.0) * 10.0
    
    # 4. Hours (Max 10 pts, assuming 16 hours is 100% capacity)
    hours_score = min(10.0, (hours / 16.0) * 10.0)
    
    total_teaching = syllabus_score + pass_rate_score + feedback_score + hours_score
    
    traceability = {
        "syllabus": f"({avg_syllabus:.1f}% / 100) * 10 = {syllabus_score:.1f} pts",
        "pass_rate_normalized": f"min(100, {avg_pass_rate:.1f}% * {avg_difficulty:.1f} difficulty) / 100 * 10 = {pass_rate_score:.1f} pts",
        "student_feedback": f"({avg_feedback:.1f} / 5.0) * 10 = {feedback_score:.1f} pts",
        "teaching_hours": f"min(10, ({hours} / 16 capacity) * 10) = {hours_score:.1f} pts"
    }
    
    return min(40.0, total_teaching), traceability, {"syllabus": syllabus_score, "pass": pass_rate_score, "feedback": feedback_score, "hours": hours_score}

def evaluate_research(faculty):
    """Evaluates research output based on publication tier, patents, grants, and PhD guidance."""
    # Max points: 35
    research = faculty.get('research', {})
    pubs = research.get('publications', [])
    patents = research.get('patents', [])
    grants = research.get('funded_grants', 0)
    phd = research.get('phd_students_guided', 0)
    
    pub_score = 0
    pub_trace = []
    for p in pubs:
        q = p.get('quartile', '')
        if q == 'Q1': 
            pub_score += 10
            pub_trace.append("Q1 Paper (+10)")
        elif q == 'Q2': 
            pub_score += 7
            pub_trace.append("Q2 Paper (+7)")
        elif q == 'Q3': 
            pub_score += 4
            pub_trace.append("Q3 Paper (+4)")
        elif q == 'Q4' or q == 'Conference': 
            pub_score += 2
            pub_trace.append(f"{q} Paper (+2)")
            
    patent_score = len(patents) * 8
    patent_trace = f"{len(patents)} Patents (+{patent_score})"
    
    grant_score = grants * 10
    grant_trace = f"{grants} Grants (+{grant_score})"
    
    phd_score = phd * 5
    phd_trace = f"{phd} PhD students (+{phd_score})"
    
    raw_total = pub_score + patent_score + grant_score + phd_score
    capped_total = min(35.0, raw_total)
    
    traceability = {
        "publications": " | ".join(pub_trace) if pub_trace else "No publications (0)",
        "patents": patent_trace,
        "grants": grant_trace,
        "phd": phd_trace,
        "calculation": f"min(35, {pub_score} + {patent_score} + {grant_score} + {phd_score} = {raw_total}) = {capped_total} pts"
    }
    
    return capped_total, traceability, raw_total

def evaluate_service(faculty):
    """Evaluates institutional service and administrative load."""
    # Max points: 25 (Admin 10, Committees 10, FDPs 5)
    service = faculty.get('service', {})
    admin = service.get('administrative_roles', [])
    committees = service.get('committees', [])
    fdps = service.get('fdps_attended', 0)
    
    admin_score = min(10.0, len(admin) * 5.0) # 5 points per role
    committee_score = min(10.0, len(committees) * 3.0) # 3 points per committee
    fdp_score = min(5.0, fdps * 2.0) # 2 points per FDP
    
    total = admin_score + committee_score + fdp_score
    
    traceability = {
        "administrative_duties": f"{len(admin)} roles * 5 = {admin_score} (max 10)",
        "committees": f"{len(committees)} committees * 3 = {committee_score} (max 10)",
        "fdps_attended": f"{fdps} FDPs * 2 = {fdp_score} (max 5)"
    }
    
    return min(25.0, total), traceability, total

def generate_feedback(faculty, teaching_parts, research_raw, service_raw):
    """Generates diagnostic feedback with 1 key strength and 1 developmental gap."""
    strengths = []
    gaps = []
    
    # Teaching Diagnostics
    if teaching_parts.get('feedback', 0) >= 8:
        strengths.append("Excellent student feedback indicating strong pedagogical delivery.")
    elif teaching_parts.get('feedback', 0) < 6.5:
        gaps.append("Consider attending Agent 60's Workshop on Pedagogy to improve student engagement.")
        
    if teaching_parts.get('syllabus', 0) < 9:
        gaps.append("Syllabus coverage is below target. Review course pacing with Agent 6 (Curriculum Agent).")
        
    # Research Diagnostics
    if research_raw >= 20:
        strengths.append("Outstanding research output and IP generation.")
    elif research_raw < 10:
        gaps.append("Research output is low. Seek collaborative grant opportunities or seed funding.")
        
    # Service Diagnostics
    if service_raw >= 15:
        strengths.append("Strong institutional service and administrative leadership (Agent 58 commended).")
    elif service_raw < 5:
        gaps.append("Increase participation in institutional committees or acquire more FDP certifications (Agent 27).")
        
    # Fallbacks to ensure exactly 1 strength and 1 gap
    if not strengths: strengths.append("Consistent performance across baseline academic duties.")
    if not gaps: gaps.append("Continue maintaining current high standards across all domains.")
    
    return strengths[0], gaps[0]

def evaluate_all():
    """Runs the scoring engine for all mock faculty members."""
    rubric, faculty_list = load_data()
    results = []
    
    for faculty in faculty_list:
        t_score, t_trace, t_parts = evaluate_teaching(faculty)
        r_score, r_trace, r_raw = evaluate_research(faculty)
        s_score, s_trace, s_raw = evaluate_service(faculty)
        
        total_score = t_score + r_score + s_score
        
        strength, gap = generate_feedback(faculty, t_parts, r_raw, s_raw)
        
        results.append({
            "faculty_id": faculty["faculty_id"],
            "name": faculty["name"],
            "total_score": round(total_score, 2),
            "breakdown": {
                "teaching": round(t_score, 2),
                "research": round(r_score, 2),
                "service": round(s_score, 2)
            },
            "diagnostic_feedback": {
                "key_strength": strength,
                "developmental_gap": gap
            },
            "xai_traceability": {
                "teaching_trace": t_trace,
                "research_trace": r_trace,
                "service_trace": s_trace
            }
        })
        
    return results

if __name__ == "__main__":
    results = evaluate_all()
    print(json.dumps(results, indent=2))
