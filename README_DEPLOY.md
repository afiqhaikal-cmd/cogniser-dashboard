# Cogniser P'Aun Online Reviewer Demo

Standalone synthetic-data reviewer demo. This is a simplified adaptation of Cogniser Original Factory v49, not the full production application. It intentionally has no FastAPI, SQLite, physical CCTV or live worker data.

## Publish using Streamlit Community Cloud
1. Create a new PRIVATE GitHub repository and upload app.py, requirements.txt and .streamlit/config.toml, keeping the directory structure.
2. Visit https://share.streamlit.io/ and sign in with GitHub.
3. Select Create app, choose the repository/branch and set main file path to app.py.
4. Deploy, wait for successful build and copy the app URL to P'Aun.
5. Note: A publicly accessible Streamlit app URL may be accessible to anyone with the link; do not put personal data or credentials into the repo. For restricted access use a supported authentication solution.

## Demo flow
Face Recognition -> PPE Sample (Gloves PASS, Mask FAIL, Hair Cover PASS) -> see PENDING/BLUE -> All PASS (GREEN) or Completed FAIL (RED). Audit entries remain within the browser session only.

## Limits
No real Cogniser events, no database persistence, no production authentication, no physical lamp/audio/gate. Demo audit CSV is not the official factory report. Cloud deployment requires the owner's GitHub/Streamlit login and cannot be completed by simply sharing this ZIP.
