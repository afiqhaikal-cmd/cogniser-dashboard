"""Host original dashboard.py, with Supabase read-only evidence mirror."""
import runpy
import streamlit as st
from cloud_bridge import refresh_cloud
from streamlit_autorefresh import st_autorefresh

# dashboard.py sets page config; do not call st.set_page_config here.
st_autorefresh(interval=10000, limit=None, key="cogniser_auto_refresh")
try:
    refresh_cloud()
except KeyError as exc:
    st.error(f'Missing Streamlit secret: {exc}. Set SUPABASE_URL and SUPABASE_SECRET_KEY in Streamlit Cloud settings.')
    st.stop()
except Exception as exc:
    st.error(f'Unable to refresh cloud evidence: {exc}')
    st.stop()
runpy.run_path('dashboard.py', run_name='__main__')
