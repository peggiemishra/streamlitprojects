# timezone_dashboard.py
import streamlit as st
from datetime import datetime
import pytz

st.set_page_config(page_title="Dynamic Timezone Converter", layout="wide")

@st.cache_data
def get_timezones():
    # return a plain list so Streamlit can serialize/cache it
    return list(pytz.all_timezones)

def format_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def tz_info_from_aware_dt(aware_dt):
    """
    Return human friendly offset string like 'UTC+05:30' given an AWARE datetime.
    """
    offset = aware_dt.utcoffset()
    if offset is None:
        return "UTC±00:00"
    total_seconds = int(offset.total_seconds())
    hours = total_seconds // 3600
    minutes = (abs(total_seconds) % 3600) // 60
    sign = "+" if hours >= 0 else "-"
    return f"UTC{sign}{abs(hours):02d}:{minutes:02d}"

timezones = get_timezones()

# Sidebar navigation
with st.sidebar:
    st.title("Time Conversion Mode Selector")
    mode = st.radio("Choose conversion mode:", ["Current Time Conversion", "Manual Time Conversion"])
    st.markdown("---")
    st.caption("Choose source and target timezones in the main panel.")

# Collapsible choose country panel
with st.expander("Choose Country Panel", expanded=True):
    col1, col2 = st.columns([1, 1])
    with col1:
        source_tz_name = st.selectbox(
            "Source Country / Timezone",
            timezones,
            index=timezones.index("UTC") if "UTC" in timezones else 0,
        )
    with col2:
        target_tz_names = st.multiselect(
            "Target Countries / Timezones", [tz for tz in timezones if tz != source_tz_name]
        )

source_tz = pytz.timezone(source_tz_name)

st.markdown("## Conversion Panel")

left_col, right_col = st.columns([1, 1.4])

def render_card(container, title, aware_dt, tzname):
    """
    container: a Streamlit DeltaGenerator (a column or st.* element)
    title: title text for the card
    aware_dt: AN AWARE datetime (has tzinfo) representing time in some timezone
    tzname: IANA timezone string for which we want to display time/abbr/offset
    """
    tz = pytz.timezone(tzname)
    # Convert the provided aware datetime into the target timezone (results in an aware datetime)
    dt_in_tz = aware_dt.astimezone(tz)
    # abbreviation and offset come from the aware datetime in that tz
    abbrev = dt_in_tz.tzname() or ""
    offset = tz_info_from_aware_dt(dt_in_tz)
    with container:
        st.markdown(f"**{title}**")
        st.write(f"**Timezone:** {tzname} ({abbrev})")
        st.write(f"**Local time:** {format_dt(dt_in_tz)}")
        st.write(f"**Offset:** {offset}")
        st.write("---")

if mode == "Current Time Conversion":
    st.subheader("🕒 Current Time Conversion")
    # aware datetime in source timezone
    source_now = datetime.now(source_tz)

    left_col.markdown("### Source")
    render_card(left_col, f"Current time in {source_tz_name}", source_now, source_tz_name)

    right_col.markdown("### Targets")
    if not target_tz_names:
        right_col.info("Select one or more target timezones in the 'Choose Country Panel' above.")
    else:
        for tgt_name in target_tz_names:
            tgt_time_source_view = source_now  # still aware in source_tz
            render_card(right_col, f"{tgt_name}", tgt_time_source_view, tgt_name)

else:
    st.subheader("🧭 Manual Time Conversion")
    # default date/time based on current time in source tz (naive values for widgets)
    now_local_naive = datetime.now().astimezone(source_tz).replace(tzinfo=None)
    default_date = now_local_naive.date()
    default_time = now_local_naive.time().replace(microsecond=0)

    user_date = st.date_input("Select date (source timezone):", default_date)
    user_time = st.time_input("Select time (source timezone):", default_time)

    chosen_dt_naive = datetime.combine(user_date, user_time)

    # Localize to source timezone while handling DST ambiguous/nonexistent times
    try:
        localized_source_dt = source_tz.localize(chosen_dt_naive, is_dst=None)
    except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
        # fallback tries
        try:
            localized_source_dt = source_tz.localize(chosen_dt_naive, is_dst=True)
        except Exception:
            localized_source_dt = source_tz.localize(chosen_dt_naive, is_dst=False)

    left_col.markdown("### Source (chosen time)")
    render_card(left_col, f"Chosen time in {source_tz_name}", localized_source_dt, source_tz_name)

    right_col.markdown("### Converted targets")
    if not target_tz_names:
        right_col.info("Select one or more target timezones in the 'Choose Country Panel' above.")
    else:
        for tgt_name in target_tz_names:
            render_card(right_col, f"{tgt_name} (converted)", localized_source_dt, tgt_name)

st.markdown("---")
st.caption("Tip: abbreviations (PST/IST/CST) are shown for the chosen date — DST-aware, so they'll switch (e.g. PST ↔ PDT) when applicable.")
