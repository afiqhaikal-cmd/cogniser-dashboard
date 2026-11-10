"""Hosted read-only Cogniser dashboard entrypoint."""
import os
os.environ['COGNISER_ONLINE']='1'
import runpy
import streamlit as st
from cloud_bridge import refresh_cloud
from streamlit_autorefresh import st_autorefresh

st_autorefresh(interval=10000, limit=None, key='cogniser_auto_refresh')
try:
    refresh_cloud()
except KeyError as exc:
    st.error(f'Missing Streamlit secret: {exc}. Configure SUPABASE_URL and SUPABASE_SECRET_KEY.')
    st.stop()
except Exception as exc:
    st.error(f'Cloud evidence refresh failed: {exc}')
    st.stop()
runpy.run_path('dashboard.py',run_name='__main__')
