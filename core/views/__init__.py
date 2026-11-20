"""
Chart-ready data for the dashboard and API.

Each view function takes loader output (see core.queries) and returns the data
a chart needs, with no plotting library involved. The Streamlit dashboard
draws these with Altair; the API will serve them as JSON for the Flutter app.
"""
