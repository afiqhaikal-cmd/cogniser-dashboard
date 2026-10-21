import json
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Cogniser | Factory Hygiene Inspection", page_icon="🏭", layout="wide")

STEPS = {
    1: ["Temperature", "Ear Ring", "Necklace", "Bracelet", "Ring", "Nail", "Wound", "Plaster"],
    2: ["Hair Cover", "Face Mask", "Protective Clothing", "Shoes"],
    3: ["Hand Washing"],
    4: ["Gloves"],
    5: ["Mobile Phone / Metal Detection"],
}
ALL_CHECKS = [check for group in STEPS.values() for check in group]


def init_state():
    defaults = {"employee": None, "face": False, "checks": {}, "history": [], "scenario": "Ready"}
    for name, default in defaults.items():
        if name not in st.session_state:
            st.session_state[name] = default


def outcome(checks):
    if len(checks) < len(ALL_CHECKS):
        return "PENDING"
    return "FAIL" if "FAIL" in checks.values() else "PASS"


def save_demo():
    if st.session_state.employee:
        checks = st.session_state.checks
        st.session_state.history.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Employee ID": st.session_state.employee,
            "Status": outcome(checks),
            "PASS": sum(value == "PASS" for value in checks.values()),
            "FAIL": sum(value == "FAIL" for value in checks.values()),
            "PENDING": len(ALL_CHECKS) - len(checks),
            "Source": "SIMULATION",
        })


def demo_face():
    st.session_state.employee = "DEMO-001"
    st.session_state.face = True
    st.session_state.checks = {}
    st.session_state.scenario = "Face detected (simulation)"


def demo_ppe():
    if not st.session_state.face:
        return
    st.session_state.checks.update({"Gloves": "PASS", "Face Mask": "FAIL", "Hair Cover": "PASS"})
    st.session_state.scenario = "PPE sample 1-0-1 (simulation)"
    save_demo()


def demo_full(passed):
    if not st.session_state.face:
        demo_face()
    st.session_state.checks = {key: "PASS" for key in ALL_CHECKS}
    if not passed:
        st.session_state.checks["Face Mask"] = "FAIL"
    st.session_state.scenario = "Completed inspection (simulation)"
    save_demo()


def reset_demo():
    st.session_state.employee = None
    st.session_state.face = False
    st.session_state.checks = {}
    st.session_state.history = []
    st.session_state.scenario = "Ready"


@st.cache_data(ttl=15, show_spinner=False)
def fetch_events():
    """Read-only REST query. Credentials remain in Streamlit server-side secrets."""
    try:
        url = str(st.secrets["SUPABASE_URL"]).rstrip("/")
        key = str(st.secrets["SUPABASE_SECRET_KEY"])
        if not url.startswith("https://"):
            return [], "SUPABASE_URL must start with https://"
        response = requests.get(
            f"{url}/rest/v1/cogniser_events",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "*", "limit": "100"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return [], "Unexpected response format"
        return data, None
    except KeyError:
        return [], "Missing SUPABASE_URL or SUPABASE_SECRET_KEY in Streamlit secrets"
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        return [], f"Supabase HTTP {code}. Check table access and credentials."
    except requests.RequestException:
        return [], "Cannot reach Supabase. Check connection and project availability."
    except Exception:
        return [], "Unable to load Supabase events. Check Streamlit app logs."


def visible_events(events):
    """Avoid rendering arbitrary raw payloads or personal/sensitive fields."""
    allowed = ["event_type", "employee_id", "camera_id", "event_id", "created_at", "received_at"]
    df = pd.DataFrame(events)
    cols = [column for column in allowed if column in df.columns]
    return df[cols] if cols else pd.DataFrame({"Record": list(range(1, len(events) + 1))})


init_state()
st.markdown("""<style>
.block-container {max-width:1450px;padding-top:1.4rem}
.hero {background:linear-gradient(100deg,#092f50,#086b83);color:white;border-radius:18px;padding:26px}
.hero h1 {color:white;margin:0;font-size:2.25rem}
.hero p {color:#d5edf4;margin:8px 0 0}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>COGNISER · FACTORY HYGIENE INSPECTION</h1><p>Face Recognition → Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Gate Eligibility</p></div>', unsafe_allow_html=True)
st.warning("REVIEWER PROTOTYPE · Demo controls use synthetic data. Supabase events are read-only and do not automatically approve inspections. No physical CCTV, sensors, speaker, indicator or gate is controlled by this web app.")

st.subheader("Try the demonstration")
a, b, c, d, e = st.columns(5)
a.button("1 · Face Recognition", on_click=demo_face, use_container_width=True)
b.button("2 · PPE Sample (1-0-1)", on_click=demo_ppe, disabled=not st.session_state.face, use_container_width=True)
c.button("3 · All PASS", on_click=demo_full, args=(True,), use_container_width=True)
d.button("4 · Completed FAIL", on_click=demo_full, args=(False,), use_container_width=True)
e.button("Reset Demo", on_click=reset_demo, use_container_width=True)

checks = st.session_state.checks
status = outcome(checks) if st.session_state.face else "READY"
colour = {"READY": "WHITE", "PENDING": "BLUE", "PASS": "GREEN", "FAIL": "RED"}[status]
hexes = {"WHITE": "#ffffff", "BLUE": "#2563eb", "GREEN": "#16a34a", "RED": "#dc2626"}

tabs = st.tabs([
    "LIVE OVERVIEW", "FACE RECOGNITION", "STEP 1 · HYGIENE", "STEP 2 · PPE",
    "STEP 3 · HAND WASHING", "STEP 4 · GLOVES", "STEP 5 · METAL DETECTION",
    "AUDIT & REPORT", "COGNISER CONNECTION", "4-COLOUR INDICATOR",
])
with tabs[0]:
    x, y, z = st.columns(3)
    x.metric("Employee ID", st.session_state.employee or "Not detected")
    y.metric("Inspection Status · Demo", status)
    z.metric("Checks completed · Demo", f"{len(checks)} / {len(ALL_CHECKS)}")
    st.info("Demo PPE updates individual checks. Overall status remains PENDING until all 15 mandatory checks are recorded.")
    st.dataframe(pd.DataFrame([
        {"Step": f"Step {step}", "Checkpoint": key, "Result": checks.get(key, "PENDING")}
        for step, keys in STEPS.items() for key in keys
    ]), hide_index=True, use_container_width=True)
with tabs[1]:
    st.header("Face Recognition · Simulation")
    st.write("Click **1 · Face Recognition** to simulate an identified employee.")
    st.metric("Current demo employee", st.session_state.employee or "No identity")
    st.caption("DEMO-001 is synthetic. Supabase face events are displayed separately under Cogniser Connection.")
for step, idx in [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]:
    with tabs[idx]:
        st.header(f"Step {step} · Inspection (Demo)")
        st.dataframe(pd.DataFrame([
            {"Checkpoint": key, "Result": checks.get(key, "PENDING"),
             "Source": "SIMULATION" if key in checks else "Awaiting evidence"}
            for key in STEPS[step]
        ]), hide_index=True, use_container_width=True)
with tabs[7]:
    st.header("Monthly Audit · Demo Session")
    if st.session_state.history:
        audit = pd.DataFrame(st.session_state.history)
        st.dataframe(audit, use_container_width=True, hide_index=True)
        st.download_button("Download Demo Audit CSV", audit.to_csv(index=False).encode("utf-8-sig"),
                           "cogniser_demo_audit.csv", "text/csv")
    else:
        st.info("Run a demo PPE or completed inspection to create a session-only audit entry.")
    st.caption("Demo history is not an official factory record and is not stored in Supabase.")
with tabs[8]:
    st.header("Cogniser Connection · Supabase")
    st.info("Supabase event retrieval is live when credentials are configured. Events are read-only; they do not yet update the inspection decision. The Cogniser hardware/CCTV connection has not been verified.")
    st.write("Prototype architecture: Dahua CCTV / Cogniser V1 → local FastAPI → local SQLite → local Streamlit. A separate local sync script can send events to Supabase, which this hosted app reads.")
    st.caption("Server Room: BMAX B1 Plus Mini PC and Cogniser V1. LAB: two Dahua IPC-HFW2441S-S cameras. Edge device and speaker models not yet selected.")
    if st.button("Refresh Supabase Data", key="refresh_supabase"):
        fetch_events.clear()
    events, error = fetch_events()
    if error:
        st.error(error)
    else:
        st.success(f"Connected to Supabase — {len(events)} events retrieved")
        if events:
            df_events = visible_events(events)
            st.dataframe(df_events, hide_index=True, use_container_width=True)
            if "event_type" in df_events.columns:
                st.write("Events by type (read-only):")
                st.dataframe(df_events["event_type"].fillna("unknown").value_counts().rename_axis("Event type").reset_index(name="Count"), hide_index=True)
            st.caption("These records may include synthetic tests or sample JSON sent by the local sync script. They are not proof of a live physical detection.")
        else:
            st.info("No events found in the cogniser_events table.")
with tabs[9]:
    st.header("Four-colour Indicator · SIMULATION ONLY")
    columns = st.columns(4)
    for col, name in zip(columns, hexes):
        with col:
            selected = name == colour
            border = "3px solid #0284c7" if selected else "1px solid #cbd5e1"
            st.markdown(
                f'<div style="border:{border};background:#f8fafc;padding:20px;border-radius:14px;text-align:center">'
                f'<div style="height:65px;width:65px;border-radius:50%;margin:auto;background:{hexes[name]};border:2px solid #64748b"></div>'
                f'<b style="color:#0f172a">{name}</b></div>', unsafe_allow_html=True,
            )
    st.metric("Virtual signal", colour)
    st.info({"WHITE": "Ready / Standby", "BLUE": "Processing / Awaiting checks",
             "GREEN": "Passed / Authorized (simulation)", "RED": "Failed / Unauthorized (simulation)"}[colour])
    st.warning("No physical indicator, speaker, or gate is controlled by this demo.")
