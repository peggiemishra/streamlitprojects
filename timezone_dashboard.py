# timezone_dashboard_fixed_v2.py
import streamlit as st
from datetime import datetime
import pytz
import os

st.set_page_config(page_title="Dynamic Timezone Converter", layout="wide")

@st.cache_data
def get_timezones():
    return list(pytz.all_timezones)

def format_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def tz_info_from_aware_dt(aware_dt):
    offset = aware_dt.utcoffset()
    if offset is None:
        return "UTC±00:00"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    abs_total = abs(total_seconds)
    hours = abs_total // 3600
    minutes = (abs_total % 3600) // 60
    return f"UTC{sign}{hours:02d}:{minutes:02d}"

# Improved detection function
def detect_local_timezone_candidate(timezones):
    # 1) env override
    env_tz = os.environ.get("DEFAULT_SOURCE_TZ")
    if env_tz and env_tz in timezones:
        return env_tz

    # 2) tzlocal if available (best option)
    try:
        import tzlocal
        try:
            name = tzlocal.get_localzone_name()
            if name in timezones:
                return name
        except Exception:
            try:
                tzobj = tzlocal.get_localzone()
                if hasattr(tzobj, "zone") and tzobj.zone in timezones:
                    return tzobj.zone
            except Exception:
                pass
    except Exception:
        pass

    # 3) try to read a zone name from astimezone() (ZoneInfo on modern systems)
    try:
        local_aware = datetime.now().astimezone()
        tzinfo = local_aware.tzinfo
        if tzinfo is not None:
            # try possible attributes that may contain the zone name
            for attr in ("zone", "key"):
                if hasattr(tzinfo, attr):
                    try:
                        val = getattr(tzinfo, attr)
                        if isinstance(val, str) and val in timezones:
                            return val
                    except Exception:
                        pass
            # some systems expose full name via tzname()
            tzname = local_aware.tzname()
            if tzname:
                # direct exact match (rare)
                if tzname in timezones:
                    return tzname
    except Exception:
        pass

    # 4) abbreviation mapping (common ambiguous cases -> preferred IANA)
    abbrev_map = {
        "IST": "Asia/Kolkata",  # India Standard Time (ambiguous: also Israel/Sri Lanka historically)
        "CST": "America/Chicago",
        "EST": "America/New_York",
        "PST": "America/Los_Angeles",
        # add more if you need them
    }
    try:
        local_abbr = datetime.now().astimezone().tzname()
        if local_abbr and local_abbr in abbrev_map:
            cand = abbrev_map[local_abbr]
            if cand in timezones:
                return cand
    except Exception:
        pass

    # 5) match by current UTC offset: prefer zones that include 'Kolkata' or 'India'
    try:
        local_offset = datetime.now().astimezone().utcoffset()
        if local_offset is not None:
            local_seconds = int(local_offset.total_seconds())
            # collect candidates with same offset right now
            matches = []
            for tz in timezones:
                try:
                    tz_offset = datetime.now(pytz.timezone(tz)).utcoffset()
                    if tz_offset is not None and int(tz_offset.total_seconds()) == local_seconds:
                        matches.append(tz)
                except Exception:
                    continue
            # prefer India/Kolkata if present
            for prefer in ("Asia/Kolkata",):
                if prefer in matches:
                    return prefer
            # prefer any with 'India' or 'Kolkata' in name
            for m in matches:
                if "Kolkata" in m or "India" in m:
                    return m
            # otherwise return the first reasonable match (same offset)
            if matches:
                return matches[0]
    except Exception:
        pass

    # final fallback
    return "UTC"

timezones = get_timezones()

default_source_tz = detect_local_timezone_candidate(timezones)

# Sidebar navigation
with st.sidebar:
    st.title("Time Conversion Mode Selector")
    mode = st.radio("Choose conversion mode:", ["Current Time Conversion", "Manual Time Conversion"])
    st.markdown("---")
    st.caption("Choose Home Clock and Other Clocks in the main panel.")
    # helpful debug line so you can see what the app thinks your zone is
    st.info(f"Detected local timezone (default): {default_source_tz}")

# Collapsible clock panel (renamed)
with st.expander("Clock Settings", expanded=True):
    col1, col2 = st.columns([1, 1])
    with col1:
        source_tz_name = st.selectbox(
            "Home Clock",
            timezones,
            index=timezones.index(default_source_tz) if default_source_tz in timezones else 0,
        )
    with col2:
        target_tz_names = st.multiselect("Other Clocks", [tz for tz in timezones if tz != source_tz_name])

source_tz = pytz.timezone(source_tz_name)

st.markdown("## Clock Conversion")

left_col, right_col = st.columns([1, 1.4])

def render_card(container, title, aware_dt, tzname):
    tz = pytz.timezone(tzname)
    dt_in_tz = aware_dt.astimezone(tz)
    abbrev = dt_in_tz.tzname() or ""
    offset = tz_info_from_aware_dt(dt_in_tz)
    weekday = dt_in_tz.strftime('%A')
    with container:
        st.markdown(f"**{title}**")
        st.write(f"**Timezone:** {tzname} ({abbrev})")
        st.write(f"**Local time:** {format_dt(dt_in_tz)}")
        st.write(f"**Weekday:** {weekday}")
        st.write(f"**Offset:** {offset}")
        st.write("---")

if mode == "Current Time Conversion":
    st.subheader("🕒 Current Time Conversion")
    source_now = datetime.now(source_tz)
    left_col.markdown("### Home Clock")
    render_card(left_col, f"Current time in {source_tz_name}", source_now, source_tz_name)
    right_col.markdown("### Other Clocks")
    if not target_tz_names:
        right_col.info("Select one or more Other Clocks in the 'Clock Settings' above.")
    else:
        for tgt_name in target_tz_names:
            tgt_time_source_view = source_now
            render_card(right_col, f"{tgt_name}", tgt_time_source_view, tgt_name)
else:
    st.subheader("🧭 Manual Time Conversion")
    now_in_source = datetime.now(source_tz)
    now_local_naive = now_in_source.replace(tzinfo=None)
    default_date = now_local_naive.date()
    default_time = now_local_naive.time().replace(microsecond=0)

    user_date = st.date_input("Select date (Home Clock):", default_date)
    user_time = st.time_input("Select time (Home Clock):", default_time)

    chosen_dt_naive = datetime.combine(user_date, user_time)

    try:
        localized_source_dt = source_tz.localize(chosen_dt_naive, is_dst=None)
    except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
        try:
            localized_source_dt = source_tz.localize(chosen_dt_naive, is_dst=True)
        except Exception:
            localized_source_dt = source_tz.localize(chosen_dt_naive, is_dst=False)

    left_col.markdown("### Home Clock (chosen time)")
    render_card(left_col, f"Chosen time in {source_tz_name}", localized_source_dt, source_tz_name)

    right_col.markdown("### Converted Other Clocks")
    if not target_tz_names:
        right_col.info("Select one or more Other Clocks in the 'Clock Settings' above.")
    else:
        for tgt_name in target_tz_names:
            render_card(right_col, f"{tgt_name} (converted)", localized_source_dt, tgt_name)

st.markdown("---")
st.caption("Tip: abbreviations (PST/IST/CST) are shown for the chosen date — DST-aware, so they'll switch (e.g. PST ↔ PDT) when applicable.")
