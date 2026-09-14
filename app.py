import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import copy
from datetime import datetime

# Import scoring engine functions
from core.scoring_engine import (
    load_data,
    evaluate_teaching,
    evaluate_research,
    evaluate_service,
    generate_feedback,
    evaluate_all
)

# Import Agent Bridge for Multi-Agent In/Out Orchestration
from core.agent_bridge import (
    STAGES,
    add_faculty_profile,
    delete_faculty_profile,
    ingest_upstream_event,
    dispatch_to_agent_60,
    dispatch_to_hr_payroll,
    save_faculty_records,
    load_contest_logs,
    save_contest_log_entry,
    update_contest_log_by_id,
    apply_course_metric_correction,
    apply_research_metric_correction,
    generate_mock_longitudinal_data
)

# Page Configuration
st.set_page_config(
    page_title="Agent 59 | Faculty Appraisal Engine",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Modern Institutional Theme & Steppers
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 22px 26px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .agent-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .pill-active { background-color: #dcfce7; color: #15803d; border: 1px solid #86efac; }
    .pill-info { background-color: #e0f2fe; color: #0369a1; border: 1px solid #7dd3fc; }
    .pill-warn { background-color: #fef08a; color: #854d0e; border: 1px solid #facc15; }
    .pill-sealed { background-color: #ede9fe; color: #6d28d9; border: 1px solid #c4b5fd; }
    
    .stepper-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .step-item {
        display: flex;
        align-items: center;
        font-size: 0.86rem;
        font-weight: 600;
        color: #64748b;
    }
    .step-active {
        color: #2563eb;
    }
    .step-completed {
        color: #16a34a;
    }
    .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        margin-right: 8px;
        font-size: 0.8rem;
    }
    
    .briefing-box {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 16px;
        border-radius: 0 8px 8px 0;
        margin: 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# Session State for Stages, Notifications, Seals, and Contests
if "faculty_stages" not in st.session_state:
    st.session_state.faculty_stages = {
        "F001": STAGES[2], # HoD review
        "F002": STAGES[1], # Faculty review
        "F003": STAGES[0]  # Raw ingestion
    }
if "recent_notification" not in st.session_state:
    st.session_state.recent_notification = None
if "contested_records" not in st.session_state:
    st.session_state.contested_records = {}
if "fairness_bonuses" not in st.session_state:
    st.session_state.fairness_bonuses = {}
if "dispatched_tickets" not in st.session_state:
    st.session_state.dispatched_tickets = []
if "hr_payloads" not in st.session_state:
    st.session_state.hr_payloads = {}
if "portal_view" not in st.session_state:
    st.session_state.portal_view = "👨‍🏫 Faculty Self-Service Portal"
if "active_role" not in st.session_state:
    st.session_state.active_role = "Faculty Member"

# Load Dynamic Data
rubric, faculty_list = load_data()
all_evaluations = evaluate_all()

# Apply any approved HoD fairness bonus credits
for e in all_evaluations:
    if e["faculty_id"] in st.session_state.fairness_bonuses:
        bonus = st.session_state.fairness_bonuses[e["faculty_id"]]
        e["total_score"] = round(min(100.0, e["total_score"] + bonus), 2)
        e["breakdown"]["teaching"] = round(min(40.0, e["breakdown"]["teaching"] + bonus), 2)

# Ensure all faculties have a stage assigned
for f in faculty_list:
    if f["faculty_id"] not in st.session_state.faculty_stages:
        st.session_state.faculty_stages[f["faculty_id"]] = STAGES[0]

# Compute Department Averages
dept_avg_teaching = sum(e["breakdown"]["teaching"] for e in all_evaluations) / len(all_evaluations) if all_evaluations else 0
dept_avg_research = sum(e["breakdown"]["research"] for e in all_evaluations) / len(all_evaluations) if all_evaluations else 0
dept_avg_service = sum(e["breakdown"]["service"] for e in all_evaluations) / len(all_evaluations) if all_evaluations else 0
dept_avg_total = sum(e["total_score"] for e in all_evaluations) / len(all_evaluations) if all_evaluations else 0

# Header Section
st.markdown("""
<div class="main-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin: 0; font-size: 1.85rem; font-weight: 700; color: white;">Agent 59: Autonomous Faculty Performance & Appraisal Engine</h1>
            <p style="margin: 4px 0 0 0; font-size: 1.02rem; opacity: 0.95;">Institutional AI Platform for Academics — Group 11: Faculty Management</p>
        </div>
        <div style="text-align: right;">
            <span class="agent-pill pill-active">🟢 Multi-Agent Fabric Online</span><br/>
            <span style="font-size: 0.82rem; opacity: 0.9;">Rubric: AY 2026–27 Standard (100 Pts)</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Controls
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/diploma.png", width=64)
    st.header("Appraisal Console")
    
    # Role Simulator
    simulated_roles = [
        "Faculty Member",
        "Head of Department (HoD)",
        "Dean",
        "Principal",
        "HR"
    ]
    st.selectbox("🔑 Log in as (Role Simulator)", simulated_roles, key="active_role")
    
    role = st.session_state.active_role
    
    # Portal View Selector with state binding
    if role == "Faculty Member":
        portal_options = ["👨‍🏫 Faculty Self-Service Portal"]
    elif role == "Head of Department (HoD)":
        portal_options = ["🏛️ Department Oversight (HoD)", "🌐 Multi-Agent In/Out Simulator"]
    elif role == "Dean":
        portal_options = ["🏛️ School Oversight (Dean)"]
    elif role == "Principal":
        portal_options = ["🏢 Institutional Executive Dashboard"]
    elif role == "HR":
        portal_options = ["👔 HR Institutional Dashboard"]
    else:
        portal_options = ["👨‍🏫 Faculty Self-Service Portal"]
        
    current_index = portal_options.index(st.session_state.portal_view) if st.session_state.portal_view in portal_options else 0
    selected_view = st.radio("Select Portal View", portal_options, index=current_index)
    st.session_state.portal_view = selected_view
    
    st.markdown("---")
    
    # Faculty Selection (Filtered by scope)
    # Principal, HR, Dean, Promotion Committee see all. HoD sees all (to simulate different depts). Faculty sees all (just for demo purposes).
    # To properly simulate RBAC, let's show all faculty in the dropdown, and pretend the active role BELONGS to the selected faculty's department/school.
    faculty_options = {f"{f['name']} ({f['faculty_id']})": f for f in faculty_list}
    selected_name = st.selectbox("Select Active Faculty Member", list(faculty_options.keys()))
    selected_faculty = faculty_options[selected_name]
    fac_id = selected_faculty["faculty_id"]
    
    # Matching evaluation
    selected_eval = next((e for e in all_evaluations if e["faculty_id"] == fac_id), None)
    if not selected_eval and all_evaluations:
        selected_eval = all_evaluations[0]
        
    st.markdown("---")
    
    # Stage Controller in Sidebar
    st.subheader("Lifecycle Stage Tracker")
    current_stage = st.session_state.faculty_stages.get(fac_id, STAGES[0])
    st.markdown(f"**Current Stage:**\n`{current_stage}`")
    
    new_stage = st.selectbox("Manually Advance Stage", STAGES, index=STAGES.index(current_stage))
    if new_stage != current_stage:
        st.session_state.faculty_stages[fac_id] = new_stage
        st.rerun()
        
    st.markdown("---")
    st.subheader("Connected Agent Mesh")
    st.markdown("""
    - <span class="agent-pill pill-active">Agent 6</span> Curriculum & Pacing
    - <span class="agent-pill pill-active">Agent 27</span> Faculty Development (FDP)
    - <span class="agent-pill pill-active">Agent 58</span> Governance & Workload
    - <span class="agent-pill pill-info">Agent 60</span> Pedagogical Upskilling (Out)
    - <span class="agent-pill pill-sealed">HR/Payroll</span> Sealed Merit Integration
    """, unsafe_allow_html=True)

# Top Lifecycle Stepper Display
current_fac_stage = st.session_state.faculty_stages.get(fac_id, STAGES[0])
stage_idx = STAGES.index(current_fac_stage)

s1_cls = "step-completed" if stage_idx > 0 else ("step-active" if stage_idx == 0 else "")
s2_cls = "step-completed" if stage_idx > 1 else ("step-active" if stage_idx == 1 else "")
s3_cls = "step-completed" if stage_idx > 2 else ("step-active" if stage_idx == 2 else "")
s4_cls = "step-completed" if stage_idx == 3 else ""

st.markdown(f"""
<div class="stepper-container">
    <div class="step-item {s1_cls}">
        <span class="step-badge" style="background:{'#dcfce7' if stage_idx>=0 else '#f1f5f9'}; color:{'#15803d' if stage_idx>=0 else '#64748b'};">1</span>
        <span>1. Upstream Ingestion</span>
    </div>
    <span style="color:#cbd5e1;">➔</span>
    <div class="step-item {s2_cls}">
        <span class="step-badge" style="background:{'#dcfce7' if stage_idx>=1 else '#f1f5f9'}; color:{'#15803d' if stage_idx>=1 else '#64748b'};">2</span>
        <span>2. Self-Review & Contest</span>
    </div>
    <span style="color:#cbd5e1;">➔</span>
    <div class="step-item {s3_cls}">
        <span class="step-badge" style="background:{'#dcfce7' if stage_idx>=2 else '#f1f5f9'}; color:{'#15803d' if stage_idx>=2 else '#64748b'};">3</span>
        <span>3. HoD Fairness Review</span>
    </div>
    <span style="color:#cbd5e1;">➔</span>
    <div class="step-item {s4_cls}">
        <span class="step-badge" style="background:{'#ede9fe' if stage_idx==3 else '#f1f5f9'}; color:{'#6d28d9' if stage_idx==3 else '#64748b'};">4</span>
        <span>4. Sealed & Dispatched</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Floating 3-second bubble notification
if st.session_state.recent_notification:
    notif = st.session_state.recent_notification
    st.toast(notif['text'], icon="🔔")
    st.session_state.recent_notification = None

# -------------------------------------------------------------
# TAB 1: FACULTY SELF-SERVICE PORTAL
# -------------------------------------------------------------
if st.session_state.portal_view == "👨‍🏫 Faculty Self-Service Portal":
    st.info(
        f"📋 **Stage Notice ({current_fac_stage}):** Academic metrics for **{selected_faculty['name']}** are loaded. "
        f"Scores are dynamically synthesized from Agent 6 (Curriculum), Agent 58 (Governance), and Scopus/WoS."
    )
    
    # Profile Info Card
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"**Faculty Member:**\n### {selected_faculty['name']}")
        st.caption(f"ID: {selected_faculty['faculty_id']} | {selected_faculty['designation']}")
    with c2:
        st.metric(
            label="Total Appraisal Score",
            value=f"{selected_eval['total_score']} / 100",
            delta=f"{round(selected_eval['total_score'] - dept_avg_total, 1)} vs Dept Avg"
        )
    with c3:
        st.metric(
            label="Teaching (Max 40)",
            value=f"{selected_eval['breakdown']['teaching']} pts",
            delta=f"{round(selected_eval['breakdown']['teaching'] - dept_avg_teaching, 1)}"
        )
    with c4:
        st.metric(
            label="Research (Max 35)",
            value=f"{selected_eval['breakdown']['research']} pts",
            delta=f"{round(selected_eval['breakdown']['research'] - dept_avg_research, 1)}"
        )
        
    st.markdown("---")
    
    # Visual Analytics & Radar
    col_chart, col_status = st.columns([1.2, 1])
    
    with col_chart:
        st.subheader("Performance Benchmark (vs Department Average)")
        
        categories = ['Teaching & Pedagogy', 'Research & IP', 'Service & Governance']
        fac_scores = [
            (selected_eval['breakdown']['teaching'] / 40) * 100,
            (selected_eval['breakdown']['research'] / 35) * 100,
            (selected_eval['breakdown']['service'] / 25) * 100
        ]
        dept_scores = [
            (dept_avg_teaching / 40) * 100,
            (dept_avg_research / 35) * 100,
            (dept_avg_service / 25) * 100
        ]
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=fac_scores + [fac_scores[0]],
            theta=categories + [categories[0]],
            fill='toself',
            name=selected_faculty['name'],
            line_color='#2563eb',
            fillcolor='rgba(37, 99, 235, 0.2)'
        ))
        fig.add_trace(go.Scatterpolar(
            r=dept_scores + [dept_scores[0]],
            theta=categories + [categories[0]],
            fill='toself',
            name='Dept Average',
            line_color='#94a3b8',
            fillcolor='rgba(148, 163, 184, 0.15)'
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")),
            showlegend=True,
            margin=dict(l=40, r=40, t=20, b=20),
            height=320
        )
        st.plotly_chart(fig, width='stretch')
        
    with col_status:
        st.subheader("Diagnostic Feedback")
        st.success(f"🌟 **Key Strength Identified:**\n{selected_eval['diagnostic_feedback']['key_strength']}")
        st.warning(f"🎯 **Targeted Developmental Gap:**\n{selected_eval['diagnostic_feedback']['developmental_gap']}")
        
        # Dossier Stage Status
        if stage_idx == 3:
            st.markdown(
                '<div style="padding: 10px; background-color: #ede9fe; border: 1px solid #c4b5fd; border-radius: 8px; color: #6d28d9; font-weight: 600;">'
                '🔒 Dossier Status: Officially Sealed & Transmitted to HR</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div style="padding: 10px; background-color: #fefce8; border: 1px solid #fde047; border-radius: 8px; color: #854d0e; font-weight: 600;">'
                f'⏳ Active Stage: {current_fac_stage}</div>',
                unsafe_allow_html=True
            )
            
    st.markdown("---")
    
    # Ingested Records Breakdown with XAI Drawers
    st.subheader("Pre-Populated Records & Explainability Trace (XAI)")
    
    p1, p2, p3 = st.tabs(["📚 Teaching & Pedagogy (40 Pts)", "🔬 Research & IP (35 Pts)", "🏛️ Service & Governance (25 Pts)"])
    
    with p1:
        courses_df = pd.DataFrame(selected_faculty["teaching"]["courses"])
        st.write("##### Ingested Course Delivery Data (from Agent 6 & ERP)")
        st.dataframe(
            courses_df.rename(columns={
                "course_name": "Course",
                "difficulty_rating": "Difficulty Weight",
                "class_size": "Enrolled Students",
                "syllabus_coverage_percentage": "Syllabus Coverage (%)",
                "pass_rate_percentage": "Pass Rate (%)",
                "student_feedback_score": "Student Feedback (/5.0)"
            }),
            width='stretch'
        )
        st.caption(f"Direct Classroom Teaching Load: **{selected_faculty['teaching']['direct_teaching_hours_per_week']} hours/week**")
        
        with st.expander("🔍 **Explainable AI (XAI): Mathematical Formula & Calculation Breakdown**", expanded=False):
            st.markdown(f"""
            - **Syllabus Coverage Score (Max 10):** `{selected_eval['xai_traceability']['teaching_trace']['syllabus']}`
            - **Pass Rate Normalization with Course Difficulty (Max 10):** 
              `{selected_eval['xai_traceability']['teaching_trace']['pass_rate_normalized']}`
              *(Note: Protects faculty instructing tough, foundational subjects from arbitrary penalties).*
            - **Student Feedback Score (Max 10):** `{selected_eval['xai_traceability']['teaching_trace']['student_feedback']}`
            - **Weekly Teaching Hours (Max 10):** `{selected_eval['xai_traceability']['teaching_trace']['teaching_hours']}`
            - **Total Category Score:** **{selected_eval['breakdown']['teaching']} / 40 pts**
            """)

    with p2:
        st.write("##### Ingested Scholarly Articles & IP (Scopus / WoS Ingest)")
        pubs = selected_faculty["research"]["publications"]
        if pubs:
            pubs_df = pd.DataFrame(pubs)
            st.dataframe(pubs_df.rename(columns={"title": "Paper Title", "doi": "DOI", "index": "Index Source", "quartile": "Tier"}), width='stretch')
        else:
            st.caption("No journal or conference papers logged for this appraisal cycle.")
            
        r_cols = st.columns(3)
        with r_cols[0]:
            st.markdown(f"**Patents Filed/Granted:** {len(selected_faculty['research']['patents'])}")
        with r_cols[1]:
            st.markdown(f"**Funded Research Grants:** {selected_faculty['research']['funded_grants']}")
        with r_cols[2]:
            st.markdown(f"**PhD Scholars Mentored:** {selected_faculty['research']['phd_students_guided']}")
            
        with st.expander("🔍 **Explainable AI (XAI): Research Tiering & Weighting Breakdown**", expanded=False):
            st.markdown(f"""
            - **Publications:** `{selected_eval['xai_traceability']['research_trace']['publications']}`
            - **Patents:** `{selected_eval['xai_traceability']['research_trace']['patents']}`
            - **Funded Grants:** `{selected_eval['xai_traceability']['research_trace']['grants']}`
            - **PhD Guidance:** `{selected_eval['xai_traceability']['research_trace']['phd']}`
            - **Formula & Cap:** `{selected_eval['xai_traceability']['research_trace']['calculation']}`
            """)

    with p3:
        st.write("##### Ingested Administrative Load & Governance (from Agent 58 & Agent 27)")
        s_c1, s_c2, s_c3 = st.columns(3)
        with s_c1:
            st.markdown("**Institutional Roles:**")
            if selected_faculty["service"]["administrative_roles"]:
                for r in selected_faculty["service"]["administrative_roles"]:
                    st.write(f"- {r}")
            else:
                st.write("None logged")
        with s_c2:
            st.markdown("**Assigned Committees:**")
            for c in selected_faculty["service"]["committees"]:
                st.write(f"- {c}")
        with s_c3:
            st.markdown(f"**FDPs & Pedagogical Workshops:** {selected_faculty['service']['fdps_attended']}")
            
        with st.expander("🔍 **Explainable AI (XAI): Governance Credit Calculation**", expanded=False):
            st.markdown(f"""
            - **Administrative Duties:** `{selected_eval['xai_traceability']['service_trace']['administrative_duties']}`
            - **Committees:** `{selected_eval['xai_traceability']['service_trace']['committees']}`
            - **Faculty Development Certifications:** `{selected_eval['xai_traceability']['service_trace']['fdps_attended']}`
            - **Total Category Score:** **{selected_eval['breakdown']['service']} / 25 pts**
            """)

    st.markdown("---")
    
    # Human-in-the-loop: Contest / Evidence Submission
    st.subheader("🛡️ Human-in-the-Loop: Contest or Submit Supplementary Evidence")
    
    # Initialize dynamic form counter for fresh inputs
    if "contest_form_counter" not in st.session_state:
        st.session_state.contest_form_counter = 0
        
    form_key = f"contest_form_{st.session_state.contest_form_counter}"
    
    with st.expander("Submit Additional Proof / Audit Request for Agent 59 Score", expanded=True):
        with st.form(form_key):
            metric_target = st.selectbox(
                "Select Dimension to Contest / Supplement",
                [
                    "Research: Missing Scopus/WoS Paper or Patent",
                    "Teaching: Syllabus / Passing Rate Re-audit",
                    "Service: Institutional Committee Credit"
                ]
            )
            explanation = st.text_area(
                "Justification / Discrepancy Description",
                placeholder="e.g. Patent application #20261109 was granted on Aug 28th and should be credited.",
                value=""
            )
            uploaded_file = st.file_uploader("Attach Certificate / Verification Document (PDF/PNG)", type=["pdf", "png", "jpg", "docx"])
            submitted = st.form_submit_button("Submit Evidence to Dean Review Queue", type="primary")
            
            if submitted:
                if not explanation.strip():
                    st.error("Please provide a justification or description for the audit request.")
                else:
                    file_name = uploaded_file.name if uploaded_file else "None attached"
                    file_bytes = uploaded_file.getvalue() if uploaded_file else None
                    
                    # 1. Save to separate persistent audit log file (data/contest_audit_log.json) and disk
                    new_entry = save_contest_log_entry(
                        fac_id,
                        selected_faculty["name"],
                        metric_target,
                        explanation.strip(),
                        file_name,
                        file_bytes
                    )
                    
                    # 2. Update session state for active review banner
                    st.session_state.contested_records[fac_id] = {
                        "metric": metric_target,
                        "explanation": explanation.strip(),
                        "timestamp": new_entry["timestamp"]
                    }
                    
                    # 3. Advance stage to Stage 3: HoD Oversight
                    st.session_state.faculty_stages[fac_id] = STAGES[2]
                    
                    # 4. Increment counter to reset form to completely blank
                    st.session_state.contest_form_counter += 1
                    
                    st.session_state.recent_notification = {
                        "text": f"Audit query filed for {selected_faculty['name']}. Dossier advanced to Stage 3 for HoD Review."
                    }
                    st.success("✅ Audit request logged! Form reset to blank and stage advanced to Stage 3.")
                    st.rerun()

        # Display Historical Persistent Contest & Audit Logs (Collapsible)
        faculty_audit_logs = [log for log in load_contest_logs() if log.get("faculty_id") == fac_id]
        if faculty_audit_logs:
            with st.expander(f"📜 Submitted Evidence & Audit History ({len(faculty_audit_logs)} submissions recorded)", expanded=False):
                for item in reversed(faculty_audit_logs):
                    status = item.get("status", "Pending Review")
                    status_color = "#b45309" if status == "Pending Review" else ("#15803d" if "Approved" in status else "#b91c1c")
                    status_bg = "#fef3c7" if status == "Pending Review" else ("#dcfce7" if "Approved" in status else "#fee2e2")
                    
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; background-color: #ffffff;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 700; color: #1e3a8a; font-size: 0.95rem;">{item.get('metric_contested')}</span>
                                    <span style="background-color: {status_bg}; color: {status_color}; font-weight: 600; padding: 3px 8px; border-radius: 4px; font-size: 0.78rem;">{status}</span>
                                </div>
                                <p style="margin: 6px 0; font-size: 0.9rem; color: #334155;"><strong>Faculty Justification:</strong> {item.get('justification')}</p>
                                <p style="margin: 0; font-size: 0.78rem; color: #64748b;">Ticket ID: <code>{item.get('log_id')}</code> | Submitted: {item.get('timestamp')}</p>
                            </div>
                            """, unsafe_allow_html=True
                        )
                        
                        # Document Download / Preview
                        ev_path = item.get("evidence_file_path")
                        if ev_path and os.path.exists(ev_path):
                            col_doc1, col_doc2 = st.columns([1.5, 3])
                            with col_doc1:
                                with open(ev_path, "rb") as f_ev:
                                    st.download_button(
                                        label=f"📄 Download Attached Evidence ({item.get('evidence_document')})",
                                        data=f_ev.read(),
                                        file_name=item.get('evidence_document'),
                                        key=f"dl_fac_{item['log_id']}"
                                    )
                            with col_doc2:
                                if item.get('evidence_document', '').lower().endswith(('.png', '.jpg', '.jpeg')):
                                    st.image(ev_path, caption=item.get('evidence_document'), width=200)
                                    
                        # If HoD resolved this query, display official decision and remark (if dismissed)
                        if status != "Pending Review":
                            remark_line = f"<strong>💬 HoD Remark:</strong> {item.get('hod_remark')}<br/>" if item.get('hod_remark') else ""
                            adj_line = f"<strong>⚖️ Adjustment Details:</strong> {item.get('adjustment_applied')}<br/>" if item.get('adjustment_applied') else ""
                            st.markdown(
                                f"""
                                <div style="background-color: #f8fafc; border-left: 3px solid #3b82f6; padding: 8px 12px; margin-bottom: 12px; border-radius: 0 4px 4px 0; font-size: 0.85rem;">
                                    <strong>🏛️ Official HoD Decision:</strong> {status}<br/>
                                    {remark_line}
                                    {adj_line}
                                    <span style="font-size: 0.75rem; color: #64748b;">Resolved at: {item.get('resolved_at', 'N/A')}</span>
                                </div>
                                """, unsafe_allow_html=True
                            )

    st.markdown("---")
    
    # Career Sandbox ("What-If" Simulator)
    st.subheader("🔮 Career Sandbox: 'What-If' Appraisal Simulator")
    st.caption("Model your career growth and simulate how upcoming achievements will elevate your institutional standing.")
    
    sim_col1, sim_col2 = st.columns([1.2, 1])
    with sim_col1:
        add_q1 = st.slider("Additional Q1 Journal Papers", 0, 4, 0)
        add_patent = st.slider("Additional Granted Patents", 0, 2, 0)
        add_grant = st.slider("Additional Research Grants Won", 0, 2, 0)
        add_phd = st.slider("Additional PhD Scholars Graduated", 0, 3, 0)
        add_fdp = st.slider("Additional FDPs Attended (Agent 27)", 0, 5, 0)
        base_feedback = float(selected_faculty["teaching"]["courses"][0]["student_feedback_score"]) if selected_faculty["teaching"]["courses"] else 3.5
        target_feedback = st.slider("Projected Student Feedback Rating (/5.0)", base_feedback, 5.0, base_feedback, step=0.1)

    # Compute What-If Simulation
    sim_faculty = copy.deepcopy(selected_faculty)
    for _ in range(add_q1):
        sim_faculty["research"]["publications"].append({"title": "Simulated Q1 Paper", "doi": "sim.doi", "index": "Scopus", "quartile": "Q1"})
    for _ in range(add_patent):
        sim_faculty["research"]["patents"].append({"title": "Simulated Patent", "status": "Granted", "year": 2026})
    sim_faculty["research"]["funded_grants"] += add_grant
    sim_faculty["research"]["phd_students_guided"] += add_phd
    sim_faculty["service"]["fdps_attended"] += add_fdp
    for c in sim_faculty["teaching"]["courses"]:
        c["student_feedback_score"] = target_feedback

    sim_t, _, _ = evaluate_teaching(sim_faculty)
    sim_r, _, _ = evaluate_research(sim_faculty)
    sim_s, _, _ = evaluate_service(sim_faculty)
    sim_total = round(sim_t + sim_r + sim_s, 2)
    score_delta = round(sim_total - selected_eval["total_score"], 2)

    with sim_col2:
        st.markdown("#### Projected Appraisal Outcome")
        st.metric(
            label="Simulated Total Score",
            value=f"{sim_total} / 100",
            delta=f"+{score_delta} pts increase" if score_delta > 0 else "No change"
        )
        st.write(f"- **Simulated Teaching:** {round(sim_t, 1)} / 40 pts")
        st.write(f"- **Simulated Research:** {round(sim_r, 1)} / 35 pts")
        st.write(f"- **Simulated Service:** {round(sim_s, 1)} / 25 pts")
        
        if score_delta > 10:
            st.balloons()
            st.success("🚀 Significant career milestone! This projection elevates you to the Tier-1 Performance Band.")
        elif score_delta > 0:
            st.info("📈 Positive growth trajectory logged. Keep pursuing indexed publications and pedagogy workshops.")


# -------------------------------------------------------------
# TAB 2: HOD OVERSIGHT DASHBOARD
# -------------------------------------------------------------
elif st.session_state.portal_view == "🏛️ Department Oversight (HoD)":
    st.subheader("🏛️ Department Oversight & Executive Appraisal Leaderboard")
    dept_name = selected_faculty.get("department", "Computer Science & Engineering")
    st.caption(f"Department of {dept_name} — AY 2026-27 Comprehensive Review")
    
    # Leaderboard Table with Stages & Audit Adjustments
    all_logs = load_contest_logs()
    summary_data = []
    
    # Filter by department
    dept_evals = [e for e in all_evaluations if next((f for f in faculty_list if f["faculty_id"] == e["faculty_id"]), {}).get("department") == dept_name]
    
    for e in dept_evals:
        fac = next((f for f in faculty_list if f["faculty_id"] == e["faculty_id"]), None)
        desig = fac["designation"] if fac else "Faculty"
        f_stage = st.session_state.faculty_stages.get(e["faculty_id"], STAGES[0])
        
        # Check audit logs for this faculty member
        fac_logs = [l for l in all_logs if l.get("faculty_id") == e["faculty_id"]]
        pending_cnt = sum(1 for l in fac_logs if l.get("status") == "Pending Review")
        approved_logs = [l for l in fac_logs if "Approved" in l.get("status", "")]
        
        if pending_cnt > 0:
            audit_badge = f"⚠️ {pending_cnt} Query Pending"
        elif approved_logs:
            latest_adj = approved_logs[-1].get("adjustment_applied", "Adjusted")
            audit_badge = f"✅ {latest_adj}"
        else:
            audit_badge = "Verified Baseline"

        summary_data.append({
            "Faculty ID": e["faculty_id"],
            "Faculty Name": e["name"],
            "Designation": desig,
            "Teaching (/40)": e["breakdown"]["teaching"],
            "Research (/35)": e["breakdown"]["research"],
            "Service (/25)": e["breakdown"]["service"],
            "Total Score (/100)": e["total_score"],
            "Audit & Adjustments": audit_badge,
            "Appraisal Stage": f_stage
        })
        
    summary_df = pd.DataFrame(summary_data).sort_values(by="Total Score (/100)", ascending=False).reset_index(drop=True)
    summary_df.index += 1
    st.dataframe(summary_df, width='stretch')
    
    # Department Comparative Bar Chart
    st.subheader("Comparative Category Distribution across Faculty")
    chart_df = pd.melt(
        summary_df,
        id_vars=["Faculty Name"],
        value_vars=["Teaching (/40)", "Research (/35)", "Service (/25)"],
        var_name="Category",
        value_name="Score"
    )
    bar_fig = px.bar(
        chart_df,
        x="Faculty Name",
        y="Score",
        color="Category",
        barmode="group",
        color_discrete_sequence=["#3b82f6", "#10b981", "#f59e0b"],
        height=320
    )
    bar_fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(bar_fig, width='stretch')
    
    st.markdown("---")
    
    # Automated HoD Discussion Brief
    st.subheader(f"🤖 Automated AI Executive Brief: {selected_faculty['name']}")
    
    # Retrieve all pending queries for selected faculty
    faculty_pending_queries = [q for q in load_contest_logs() if q.get("faculty_id") == fac_id and q.get("status") == "Pending Review"]

    if faculty_pending_queries:
        audit_note_items = [f"<li>⚠️ <strong>Pending Faculty Query ({q['timestamp']}):</strong> {q['metric_contested']} — <em>\"{q['justification']}\"</em></li>" for q in faculty_pending_queries]
        audit_note = f"<ul style='color: #b45309; margin-top: 8px;'>{''.join(audit_note_items)}</ul>"
    else:
        audit_note = ""

    difficulty_val = selected_faculty['teaching']['courses'][0]['difficulty_rating'] if selected_faculty['teaching']['courses'] else 1.0
    pass_val = selected_faculty['teaching']['courses'][0]['pass_rate_percentage'] if selected_faculty['teaching']['courses'] else 75
    c_name = selected_faculty['teaching']['courses'][0]['course_name'] if selected_faculty['teaching']['courses'] else 'General Courses'

    st.markdown(f"""
    <div class="briefing-box">
        <h4 style="margin-top:0; color:#1e3a8a;">Executive Synthesis for HoD Review</h4>
        <p><strong>Candidate:</strong> {selected_faculty['name']} ({selected_faculty['designation']}) | <strong>Total Score:</strong> {selected_eval['total_score']}/100 | <strong>Stage:</strong> {current_fac_stage}</p>
        <ul>
            <li><strong>Key Academic Strengths:</strong> {selected_eval['diagnostic_feedback']['key_strength']}</li>
            <li><strong>Algorithmic Fairness Adjustments Applied:</strong> Course difficulty weight ({difficulty_val}x) applied to student pass percentage ({pass_val}%) for <em>{c_name}</em> to balance rigorous grading.</li>
            <li><strong>Developmental Action Plan (Route to Agent 60):</strong> {selected_eval['diagnostic_feedback']['developmental_gap']}</li>
        </ul>
        {audit_note}
    </div>
    """, unsafe_allow_html=True)
    
    # Interactive HITL Multi-Query Review Queue
    if faculty_pending_queries:
        st.markdown(f"### 🛡️ Human-in-the-Loop Review Queue ({len(faculty_pending_queries)} Pending for {selected_faculty['name']})")
        st.caption("Review each submitted audit contest individually. Inspect attached evidence and choose to either adjust metrics or dismiss with remarks.")
        
        for idx, q in enumerate(faculty_pending_queries):
            with st.expander(f"📌 Query #{idx+1} [Ticket: {q.get('log_id')}] — {q.get('metric_contested')} ({q.get('timestamp')})", expanded=True):
                st.markdown(
                    f"""
                    <div style="background-color: #fffbeb; border: 1px solid #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; border-radius: 6px; margin-bottom: 10px;">
                        <strong style="color: #92400e;">Contested Dimension:</strong> {q.get('metric_contested')}<br/>
                        <strong>Faculty Justification:</strong> <em>"{q.get('justification')}"</em>
                    </div>
                    """, unsafe_allow_html=True
                )
                
                # Evidence Document Download & Preview for HoD
                ev_path = q.get("evidence_file_path")
                if ev_path and os.path.exists(ev_path):
                    st.write("##### 📎 Attached Evidence Document")
                    col_ev1, col_ev2 = st.columns([1.5, 3])
                    with col_ev1:
                        with open(ev_path, "rb") as f_ev:
                            st.download_button(
                                label=f"📥 Download & Inspect Document ({q.get('evidence_document')})",
                                data=f_ev.read(),
                                file_name=q.get('evidence_document'),
                                key=f"dl_hod_{q.get('log_id')}"
                            )
                    with col_ev2:
                        if q.get('evidence_document', '').lower().endswith(('.png', '.jpg', '.jpeg')):
                            st.image(ev_path, caption=q.get('evidence_document'), width=220)
                else:
                    st.caption("No supplementary file attached by faculty.")
                    
                st.markdown("---")
                
                # Resolution Decision Actions
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    st.write("##### Option A: Approve & Apply Adjustment")
                    adj_mode = st.selectbox(
                        "Select Institutional Adjustment to Apply",
                        [
                            "Direct Course Correction (Adjust Syllabus & Pass Rate Sliders)",
                            "Award +3.0 Discretionary Fairness Points",
                            "Add Verified Scopus Journal Paper (+10.0 pts)"
                        ],
                        key=f"adj_mode_{q.get('log_id')}"
                    )
                    
                    # Current baseline values for sliders
                    curr_s = selected_faculty['teaching']['courses'][0].get('syllabus_coverage_percentage', 85) if selected_faculty['teaching']['courses'] else 85
                    curr_p = selected_faculty['teaching']['courses'][0].get('pass_rate_percentage', 75) if selected_faculty['teaching']['courses'] else 75
                    
                    if "Direct Course Correction" in adj_mode:
                        adj_s = st.slider(
                            "Adjusted Syllabus Coverage (%)",
                            min_value=50,
                            max_value=100,
                            value=int(min(100, max(curr_s + 5, 95))),
                            step=1,
                            key=f"slider_s_{q.get('log_id')}"
                        )
                        adj_p = st.slider(
                            "Adjusted Student Pass Rate (%)",
                            min_value=40,
                            max_value=100,
                            value=int(min(100, max(curr_p + 5, 85))),
                            step=1,
                            key=f"slider_p_{q.get('log_id')}"
                        )
                        adj_bonus = st.slider(
                            "Additional Discretionary Fairness Credit (+pts)",
                            min_value=0.0,
                            max_value=5.0,
                            value=2.0,
                            step=0.5,
                            key=f"slider_b_{q.get('log_id')}"
                        )
                    else:
                        adj_s, adj_p, adj_bonus = 100, 90, 0.0

                    if st.button(f"✅ Approve Query {q.get('log_id')}", key=f"btn_app_{q.get('log_id')}", type="primary"):
                        # Apply corresponding adjustment to data layer
                        if "Direct Course Correction" in adj_mode:
                            apply_course_metric_correction(fac_id, new_syllabus=adj_s, new_pass_rate=adj_p)
                            if adj_bonus > 0:
                                st.session_state.fairness_bonuses[fac_id] = st.session_state.fairness_bonuses.get(fac_id, 0) + adj_bonus
                                adj_desc = f"Course Metric Corrected ({adj_s}% Syl, {adj_p}% Pass) +{adj_bonus} pts"
                            else:
                                adj_desc = f"Course Metric Corrected ({adj_s}% Syl, {adj_p}% Pass)"
                        elif "Scopus Journal" in adj_mode:
                            apply_research_metric_correction(fac_id, title=f"Verified Research Article ({q.get('justification')[:25]}...)")
                            adj_desc = "Added Verified Scopus Q1 Publication (+10 pts)"
                        else:
                            st.session_state.fairness_bonuses[fac_id] = st.session_state.fairness_bonuses.get(fac_id, 0) + 3.0
                            adj_desc = "Awarded +3.0 Discretionary Fairness Points"
                            
                        # Update persistent audit log without requiring remark
                        update_contest_log_by_id(q.get('log_id'), "Approved", hod_remark="", adjustment_applied=adj_desc)
                        
                        # Check remaining pending
                        remaining = [item for item in load_contest_logs() if item.get("faculty_id") == fac_id and item.get("status") == "Pending Review"]
                        if not remaining and fac_id in st.session_state.contested_records:
                            del st.session_state.contested_records[fac_id]
                            
                        st.session_state.recent_notification = {
                            "text": f"✅ Query {q.get('log_id')} APPROVED with {adj_desc}!"
                        }
                        st.rerun()

                with col_res2:
                    st.write("##### Option B: Dismiss Contest Query")
                    dsm_remark = st.text_input(
                        "Official Dismissal Remark (Mandatory)",
                        value="Central examination cell records confirm original score; evidence insufficient.",
                        key=f"dsm_rem_{q.get('log_id')}"
                    )
                    if st.button(f"❌ Dismiss Query {q.get('log_id')}", key=f"btn_dsm_{q.get('log_id')}"):
                        if not dsm_remark.strip():
                            st.error("A dismissal remark is required for institutional audit compliance.")
                        else:
                            # Update persistent audit log
                            update_contest_log_by_id(q.get('log_id'), "Dismissed", hod_remark=dsm_remark.strip(), adjustment_applied="None")
                            
                            remaining = [item for item in load_contest_logs() if item.get("faculty_id") == fac_id and item.get("status") == "Pending Review"]
                            if not remaining and fac_id in st.session_state.contested_records:
                                del st.session_state.contested_records[fac_id]
                                
                            st.session_state.recent_notification = {
                                "text": f"ℹ️ Query {q.get('log_id')} dismissed. Official remark logged for faculty review."
                            }
                            st.rerun()
                            
        st.markdown("---")
    
    # One-Click Approval Gate & Outbound HR Dispatch
    st.subheader("Official Certification & Seal")
    col_seal1, col_seal2 = st.columns([1.5, 1])
    
    with col_seal1:
        st.write("Seal and transmit this dossier to the Academic Senate and Registrar's office. Once sealed, the appraisal advances to **Stage 4 (Sealed & Dispatched)**, locking metrics and generating the outbound HR Merit payload.")
        
    with col_seal2:
        is_already_sealed = (st.session_state.faculty_stages.get(fac_id) == STAGES[3])
        if is_already_sealed:
            st.success(f"✅ Dossier for {selected_faculty['name']} is Officially Sealed (Stage 4).")
            if st.button("Unseal Dossier (Revert to Stage 3)"):
                st.session_state.faculty_stages[fac_id] = STAGES[2]
                st.session_state.recent_notification = {"text": f"Dossier for {selected_faculty['name']} unsealed and reverted to Stage 3."}
                st.rerun()
        else:
            if st.button("🔐 Approve & Seal Appraisal Dossier", type="primary"):
                # Advance stage to Stage 4
                st.session_state.faculty_stages[fac_id] = STAGES[3]
                
                # Outbound dispatch to HR/Payroll
                hr_packet = dispatch_to_hr_payroll(
                    fac_id,
                    selected_faculty["name"],
                    selected_eval["total_score"],
                    selected_eval["breakdown"],
                    approver="Prof. K. Sundaram (Dean of Academic Affairs)"
                )
                st.session_state.hr_payloads[fac_id] = hr_packet
                st.session_state.recent_notification = {
                    "text": f"Dossier for {selected_faculty['name']} sealed! Stage advanced to Stage 4 (Dispatched to HR)."
                }
                st.balloons()
                st.success(f"Dossier successfully sealed and advanced to Stage 4!")
                st.rerun()

    if fac_id in st.session_state.hr_payloads:
        with st.expander("📄 **View Generated Outbound HR/Payroll Payload (Agent 59 ➔ HR ERP)**", expanded=True):
            st.json(st.session_state.hr_payloads[fac_id])


# -------------------------------------------------------------
# TAB 3: DEAN OVERSIGHT DASHBOARD
# -------------------------------------------------------------
elif st.session_state.portal_view == "🏛️ School Oversight (Dean)":
    school_name = selected_faculty.get("school", "School of Engineering")
    st.subheader(f"🏛️ School Oversight: {school_name}")
    st.caption("Dean Level View — Aggregated metrics across all departments within the school.")
    
    school_evals = [e for e in all_evaluations if next((f for f in faculty_list if f["faculty_id"] == e["faculty_id"]), {}).get("school") == school_name]
    
    s_data = []
    for e in school_evals:
        fac = next((f for f in faculty_list if f["faculty_id"] == e["faculty_id"]), None)
        s_data.append({
            "Faculty Name": e["name"],
            "Department": fac.get("department", ""),
            "Total Score (/100)": e["total_score"]
        })
    s_df = pd.DataFrame(s_data).sort_values(by="Total Score (/100)", ascending=False)
    st.dataframe(s_df, width='stretch')
    
    st.markdown("---")
    st.subheader("📈 3-Year Longitudinal Trend Analysis")
    trend_data = []
    for e in school_evals:
        hist = generate_mock_longitudinal_data(e["faculty_id"], e["total_score"])
        for yr, sc in hist.items():
            trend_data.append({"Faculty Name": e["name"], "Academic Year": yr, "Score": sc})
    
    if trend_data:
        trend_df = pd.DataFrame(trend_data)
        line_fig = px.line(trend_df, x="Academic Year", y="Score", color="Faculty Name", markers=True)
        st.plotly_chart(line_fig, width='stretch')

# -------------------------------------------------------------
# TAB 4: INSTITUTIONAL EXECUTIVE DASHBOARD (Principal/HR)
# -------------------------------------------------------------
elif st.session_state.portal_view == "🏢 Institutional Executive Dashboard":
    st.subheader("🏢 Institutional Executive Dashboard")
    st.caption("Principal & HR View — NAAC/NIRF Readiness and complete institutional aggregates.")
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Faculty Tracked", len(all_evaluations))
    col_b.metric("Institution Avg Score", round(sum(e["total_score"] for e in all_evaluations)/len(all_evaluations), 1) if all_evaluations else 0)
    col_c.metric("NAAC Preparedness", "Tier 1 Eligible")
    
    st.markdown("---")
    st.subheader("📈 Institutional 3-Year Longitudinal Trend")
    trend_data = []
    for e in all_evaluations:
        hist = generate_mock_longitudinal_data(e["faculty_id"], e["total_score"])
        for yr, sc in hist.items():
            trend_data.append({"Faculty Name": e["name"], "Academic Year": yr, "Score": sc})
    
    if trend_data:
        trend_df = pd.DataFrame(trend_data)
        line_fig = px.line(trend_df, x="Academic Year", y="Score", color="Faculty Name", markers=True)
        st.plotly_chart(line_fig, width='stretch')

# -------------------------------------------------------------
# TAB 5: HR INSTITUTIONAL DASHBOARD
# -------------------------------------------------------------
elif st.session_state.portal_view == "👔 HR Institutional Dashboard":
    st.subheader("👔 HR Institutional Dashboard")
    st.caption("Human Resources View — Complete Staff Data, Appraisal Records & Quality Reports.")
    
    hr_data = []
    
    def get_salary(designation):
        if "Senior Professor" in designation: return "₹ 1,80,000 / mo"
        elif "Professor" in designation: return "₹ 1,50,000 / mo"
        elif "Associate" in designation: return "₹ 1,20,000 / mo"
        else: return "₹ 90,000 / mo"
        
    for e in all_evaluations:
        fac = next((f for f in faculty_list if f["faculty_id"] == e["faculty_id"]), {})
        desig = fac.get("designation", "Faculty")
        perf_band = "Tier 1: Exemplary" if e["total_score"] >= 80 else ("Tier 2: Commendable" if e["total_score"] >= 60 else "Tier 3: Developmental")
        
        hr_data.append({
            "Faculty Name": e["name"],
            "Designation": desig,
            "Present Salary": get_salary(desig),
            "Performance (Score)": f"{e['total_score']} ({perf_band})",
            "Appraisal Brief": e["diagnostic_feedback"]["key_strength"],
            "Outcome / Action": e["diagnostic_feedback"]["developmental_gap"]
        })
    
    st.dataframe(pd.DataFrame(hr_data), width='stretch')
    
    st.markdown("---")
    st.subheader("📊 Aggregate Faculty Quality Reports")
    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Performance Band Distribution")
        bands = {"Tier 1": 0, "Tier 2": 0, "Tier 3": 0}
        for e in all_evaluations:
            if e["total_score"] >= 80: bands["Tier 1"] += 1
            elif e["total_score"] >= 60: bands["Tier 2"] += 1
            else: bands["Tier 3"] += 1
        pie_fig = px.pie(names=list(bands.keys()), values=list(bands.values()), color_discrete_sequence=px.colors.sequential.Teal)
        st.plotly_chart(pie_fig, width='stretch', height=300)
        
    with col2:
        st.write("#### Departmental Quality Index")
        dept_scores = {}
        for e in all_evaluations:
            fac = next((f for f in faculty_list if f["faculty_id"] == e["faculty_id"]), {})
            d = fac.get("department", "Unknown")
            dept_scores.setdefault(d, []).append(e["total_score"])
        
        dept_avg = {d: sum(scores)/len(scores) for d, scores in dept_scores.items()}
        bar_fig = px.bar(x=list(dept_avg.keys()), y=list(dept_avg.values()), labels={"x": "Department", "y": "Avg Score"}, color_discrete_sequence=["#10b981"])
        st.plotly_chart(bar_fig, width='stretch', height=300)

    st.markdown("---")
    st.subheader("📈 Institutional 3-Year Longitudinal Trend")
    trend_data = []
    for e in all_evaluations:
        hist = generate_mock_longitudinal_data(e["faculty_id"], e["total_score"])
        for yr, sc in hist.items():
            trend_data.append({"Faculty Name": e["name"], "Academic Year": yr, "Score": sc})
    
    if trend_data:
        trend_df = pd.DataFrame(trend_data)
        line_fig = px.line(trend_df, x="Academic Year", y="Score", color="Faculty Name", markers=True)
        st.plotly_chart(line_fig, width='stretch')

# -------------------------------------------------------------
# TAB 6: MULTI-AGENT IN/OUT FABRIC SIMULATOR
# -------------------------------------------------------------
else:
    st.subheader("🌐 Multi-Agent Fabric: Inbound Feeders & Outbound Dispatch")
    st.caption("Test and observe how Agent 59 exchanges real-time data contracts with upstream and downstream agents.")

    tab_in, tab_out, tab_roster = st.tabs([
        "📥 Inbound Events (Agents 6, 27, 58 ➔ Agent 59)",
        "📤 Outbound Dispatch (Agent 59 ➔ Agent 60 & HR)",
        "👥 Faculty Roster Manager (Add / Remove)"
    ])

    # 1. INBOUND SIMULATOR
    with tab_in:
        st.write(f"#### Inject Live Event into **{selected_faculty['name']}**'s Record")
        st.info("Select an upstream agent to push new data into Agent 59. Watch the score and XAI formulas update instantly across the entire application!")
        
        # Display current baseline
        st.markdown(f"**Current Baseline Score:** `{selected_eval['total_score']} / 100` | **Current Stage:** `{current_fac_stage}`")
        
        source_agent = st.selectbox(
            "Select Originating Upstream Agent",
            [
                "Research Scopus/WoS Ingest (New Indexed Publication)",
                "Agent 6: Curriculum & Pacing (New Course / Pass Rate)",
                "Agent 58: Governance & Workload (New Committee / Admin Load)",
                "Agent 27: Faculty Development (New FDP Certificate)"
            ]
        )
        
        with st.form("inbound_event_form"):
            if "Research Scopus" in source_agent:
                paper_title = st.text_input("Paper Title", value="Scalable Multimodal Agents in Higher Education")
                paper_doi = st.text_input("DOI", value="10.1109/TAFFC.2026.112233")
                quartile = st.selectbox("Journal Tier", ["Q1 (+10 pts)", "Q2 (+7 pts)", "Q3 (+4 pts)", "Conference (+2 pts)"])
            elif "Agent 6" in source_agent:
                c_name = st.text_input("Course Name", value="Distributed Systems & Cloud Architecture")
                diff = st.slider("Course Difficulty Rating", 1.0, 1.5, 1.3, step=0.1)
                syllabus = st.slider("Syllabus Coverage (%)", 70, 100, 95)
                pass_rt = st.slider("Pass Rate (%)", 50, 100, 82)
                feedback = st.slider("Student Feedback Rating (/5.0)", 1.0, 5.0, 4.4, step=0.1)
            elif "Agent 58" in source_agent:
                admin_role = st.text_input("Administrative Role (e.g. HoD, Lab Head)", value="NBA Accreditation Coordinator")
                comm_name = st.text_input("Institutional Committee", value="Curriculum Revision Committee")
            else: # Agent 27
                fdp_name = st.text_input("FDP Title", value="AICTE 5-Day Workshop on High-Performance Computing")
                fdp_count = st.number_input("Certificates Earned", min_value=1, max_value=3, value=1)
                
            inbound_submitted = st.form_submit_button("⚡ Ingest Event & Update Stage", type="primary")
            
            if inbound_submitted:
                old_score = selected_eval['total_score']
                
                if "Research Scopus" in source_agent:
                    clean_tier = quartile.split()[0]
                    ingest_upstream_event(
                        fac_id,
                        "Research_Scopus_WoS",
                        "PUBLICATION_INDEXED",
                        {"title": paper_title, "doi": paper_doi, "index": "Scopus", "quartile": clean_tier}
                    )
                    evt_desc = f"New {clean_tier} paper indexed from Scopus"
                elif "Agent 6" in source_agent:
                    ingest_upstream_event(
                        fac_id,
                        "Agent_6_Curriculum",
                        "COURSE_COMPLETED",
                        {
                            "course_name": c_name,
                            "difficulty_rating": diff,
                            "class_size": 65,
                            "syllabus_coverage_percentage": syllabus,
                            "pass_rate_percentage": pass_rt,
                            "student_feedback_score": feedback
                        }
                    )
                    evt_desc = f"Course '{c_name}' ingested from Agent 6"
                elif "Agent 58" in source_agent:
                    ingest_upstream_event(
                        fac_id,
                        "Agent_58_Governance",
                        "GOVERNANCE_ROLE_ASSIGNED",
                        {"role": admin_role, "committee": comm_name}
                    )
                    evt_desc = f"Governance duties ingested from Agent 58"
                else: # Agent 27
                    ingest_upstream_event(
                        fac_id,
                        "Agent_27_FDP",
                        "FDP_COMPLETED",
                        {"fdp_name": fdp_name, "fdp_count": fdp_count}
                    )
                    evt_desc = f"FDP certificates ingested from Agent 27"
                
                # Advance stage to Stage 2: Faculty Self-Review
                st.session_state.faculty_stages[fac_id] = STAGES[1]
                
                # Re-evaluate
                updated_evals = evaluate_all()
                new_eval = next((e for e in updated_evals if e["faculty_id"] == fac_id), selected_eval)
                new_score = new_eval['total_score']
                score_diff = round(new_score - old_score, 2)
                diff_text = f"+{score_diff}" if score_diff >= 0 else f"{score_diff}"
                
                st.session_state.recent_notification = {
                    "text": f"✅ {evt_desc}! Score updated: {old_score} ➔ {new_score} ({diff_text} pts). Stage advanced to: {STAGES[1]}."
                }
                st.session_state.portal_view = "👨‍🏫 Faculty Self-Service Portal"
                st.rerun()

    # 2. OUTBOUND SIMULATOR
    with tab_out:
        st.write("#### Outbound Dispatch: Agent 59 ➔ Agent 60 (Pedagogical Upskilling)")
        st.markdown(
            "Agent 59 automatically identifies developmental deficits and triggers targeted remediation tickets "
            "to **Agent 60** so faculty receive training before the next academic cycle."
        )
        
        target_gap = selected_eval["diagnostic_feedback"]["developmental_gap"]
        st.markdown(f"**Identified Gap for {selected_faculty['name']}:**")
        st.warning(f"🎯 {target_gap}")
        
        priority = st.selectbox("Dispatch Priority", ["NORMAL", "HIGH", "URGENT"], index=1)
        
        if st.button("🚀 Dispatch Ticket to Agent 60", type="primary"):
            ticket = dispatch_to_agent_60(
                fac_id,
                selected_faculty["name"],
                target_gap,
                priority=priority
            )
            st.session_state.dispatched_tickets.append(ticket)
            # Advance stage
            st.session_state.faculty_stages[fac_id] = STAGES[3]
            st.session_state.recent_notification = {
                "text": f"Remediation ticket dispatched to Agent 60! Stage advanced to: {STAGES[3]}."
            }
            st.balloons()
            st.success("✅ Outbound Ticket Transmitted to Agent 60's Inbound Queue!")
            st.rerun()
            
        if st.session_state.dispatched_tickets:
            st.markdown("##### Recent Dispatched Payloads to Agent 60")
            for t in reversed(st.session_state.dispatched_tickets[-3:]):
                with st.expander(f"📦 Ticket {t['ticket_id']} — {t['target_faculty']['name']} ({t['timestamp']})", expanded=True):
                    st.json(t)

    # 3. ROSTER MANAGER
    with tab_roster:
        st.write("#### Faculty Roster Directory")
        st.caption("Add new faculty profiles or decommission departures. Updates save directly into the master data store.")
        
        col_add, col_del = st.columns(2)
        
        with col_add:
            st.markdown("##### ➕ Register New Faculty Member")
            with st.form("add_faculty_form"):
                new_id = st.text_input("Faculty ID", value=f"F00{len(faculty_list)+1}")
                new_name = st.text_input("Full Name", placeholder="e.g. Dr. Kavita Krishnan")
                new_desig = st.selectbox("Designation", ["Assistant Professor", "Associate Professor", "Professor", "Senior Professor"])
                add_sub = st.form_submit_button("Add to Roster")
                if add_sub:
                    if not new_name.strip():
                        st.error("Name cannot be blank.")
                    else:
                        try:
                            add_faculty_profile(new_id, new_name, new_desig)
                            st.session_state.faculty_stages[new_id] = STAGES[0]
                            st.session_state.recent_notification = {"text": f"New faculty member {new_name} ({new_id}) registered at Stage 1."}
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))
                            
        with col_del:
            st.markdown("##### 🗑️ Decommission / Remove Faculty Member")
            with st.form("del_faculty_form"):
                del_id = st.selectbox("Select Faculty to Remove", [f"{f['name']} ({f['faculty_id']})" for f in faculty_list])
                del_sub = st.form_submit_button("Remove from Ecosystem", type="secondary")
                if del_sub:
                    target_del_id = del_id.split("(")[-1].replace(")", "").strip()
                    if len(faculty_list) <= 1:
                        st.error("Cannot remove the last remaining faculty record.")
                    else:
                        delete_faculty_profile(target_del_id)
                        if target_del_id in st.session_state.faculty_stages:
                            del st.session_state.faculty_stages[target_del_id]
                        st.session_state.recent_notification = {"text": f"Faculty record {target_del_id} removed from the system."}
                        st.rerun()

st.markdown("---")
st.caption("Agent 59 • Autonomous Faculty Performance Agent • Academic Multi-Agent Ecosystem v2.4")
