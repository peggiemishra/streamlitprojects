# timezone_dashboard_fixed.py
import streamlit as st
from datetime import datetime, timedelta, timezone as _timezone
import pytz
import os
import pandas as pd  # <- for CSV export

st.set_page_config(page_title="Dynamic Timezone Converter", layout="wide")

# Prefer zoneinfo when available (Python 3.9+). Fall back to pytz where needed.
try:
    from zoneinfo import ZoneInfo
    USE_ZONEINFO = True
except Exception:
    ZoneInfo = None
    USE_ZONEINFO = False

@st.cache_data
def get_timezones():
    # Keep the exhaustive IANA list from pytz for selection consistency
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

@st.cache_data
def build_offset_map(timezones):
    # Build a map tz -> current offset seconds. Cached to avoid repeated work.
    m = {}
    now_utc = datetime.utcnow()
    for tz in timezones:
        try:
            if USE_ZONEINFO:
                tzobj = ZoneInfo(tz)
                aware = now_utc.replace(tzinfo=ZoneInfo('UTC')).astimezone(tzobj)
            else:
                tzobj = pytz.timezone(tz)
                aware = datetime.now(tzobj)
            off = aware.utcoffset()
            m[tz] = int(off.total_seconds()) if off is not None else None
        except Exception:
            m[tz] = None
    return m

# Detection heuristics for local timezone
def detect_local_timezone_candidate(timezones, offset_map):
    # 1) env override
    env_tz = os.environ.get("DEFAULT_SOURCE_TZ")
    if env_tz and env_tz in timezones:
        return env_tz, "env"

    # 2) tzlocal if available
    try:
        import tzlocal
        try:
            name = tzlocal.get_localzone_name()
            if name in timezones:
                return name, "tzlocal_name"
        except Exception:
            try:
                tzobj = tzlocal.get_localzone()
                if hasattr(tzobj, "zone") and tzobj.zone in timezones:
                    return tzobj.zone, "tzlocal_zone"
            except Exception:
                pass
    except Exception:
        pass

    # 3) try astimezone() attributes
    try:
        local_aware = datetime.now().astimezone()
        tzinfo = local_aware.tzinfo
        if tzinfo is not None:
            for attr in ("zone", "key"):
                if hasattr(tzinfo, attr):
                    try:
                        val = getattr(tzinfo, attr)
                        if isinstance(val, str) and val in timezones:
                            return val, "astimezone_attr"
                    except Exception:
                        pass
            tzname = local_aware.tzname()
            if tzname and tzname in timezones:
                return tzname, "astimezone_tzname_exact"
    except Exception:
        pass

    # 4) abbreviation mapping (expandable)
    abbrev_map = {
        "IST": "Asia/Kolkata",
        "CST": "America/Chicago",
        "EST": "America/New_York",
        "PST": "America/Los_Angeles",
    }
    try:
        local_abbr = datetime.now().astimezone().tzname()
        if local_abbr and local_abbr in abbrev_map:
            cand = abbrev_map[local_abbr]
            if cand in timezones:
                return cand, "abbrev_map"
    except Exception:
        pass

    # 5) match by current UTC offset using cached offset_map
    try:
        local_offset = datetime.now().astimezone().utcoffset()
        if local_offset is not None:
            local_seconds = int(local_offset.total_seconds())
            matches = [tz for tz, sec in offset_map.items() if sec == local_seconds]
            # prefer Asia/Kolkata for systems in that offset if present
            for prefer in ("Asia/Kolkata",):
                if prefer in matches:
                    return prefer, "offset_prefer"
            for m in matches:
                if "Kolkata" in m or "India" in m:
                    return m, "offset_name_match"
            if matches:
                return matches[0], "offset_first_match"
    except Exception:
        pass

    return "UTC", "fallback"

# helper: create aware datetime for a given zone name from naive dt
def make_aware_from_naive(naive_dt, tzname):
    if USE_ZONEINFO:
        tzobj = ZoneInfo(tzname)
        # create aware with fold control — caller may set fold
        aware = naive_dt.replace(tzinfo=tzobj)
        return aware
    else:
        tzobj = pytz.timezone(tzname)
        try:
            aware = tzobj.localize(naive_dt, is_dst=None)
        except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
            # let caller handle ambiguity by trying True/False
            raise
        return aware

# UI start
st.title("Dynamic Timezone Converter")

timezones = get_timezones()
offset_map = build_offset_map(timezones)

default_source_tz, detect_path = detect_local_timezone_candidate(timezones, offset_map)

with st.sidebar:
    st.title("Time Conversion Mode Selector")
    mode = st.radio("Choose conversion mode:", ["Current Time Conversion", "Manual Time Conversion"])
    st.markdown("---")
    st.caption("Choose Home Clock and Other Clocks in the main panel.")
    st.info(f"Detected local timezone (default): {default_source_tz} — via {detect_path}")

with st.expander("Clock Settings", expanded=True):
    col1, col2 = st.columns([1, 1])
    with col1:
        source_tz_name = st.selectbox(
            "Home Clock",
            timezones,
            index=timezones.index(default_source_tz) if default_source_tz in timezones else 0,
        )
    with col2:
        # show simple labels including current offset for better discoverability
        def label_for(tz):
            sec = offset_map.get(tz)
            if sec is None:
                return tz
            h = sec // 3600
            m = abs((sec % 3600) // 60)
            sign = "+" if sec >= 0 else "-"
            return f"{tz} (UTC{sign}{abs(h):02d}:{m:02d})"

        available_targets = [tz for tz in timezones if tz != source_tz_name]
        target_tz_names = st.multiselect("Other Clocks", available_targets, format_func=lambda x: label_for(x))

# choose source tzobj
if USE_ZONEINFO:
    source_tz = ZoneInfo(source_tz_name)
else:
    source_tz = pytz.timezone(source_tz_name)

st.markdown("## Clock Conversion")
left_col, right_col = st.columns([1, 1.4])

def render_card(container, title, aware_dt, tzname):
    # aware_dt is timezone-aware datetime
    if USE_ZONEINFO:
        tzobj = ZoneInfo(tzname)
        dt_in_tz = aware_dt.astimezone(tzobj)
    else:
        tzobj = pytz.timezone(tzname)
        dt_in_tz = aware_dt.astimezone(tzobj)

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
    if USE_ZONEINFO:
        source_now = datetime.now(ZoneInfo('UTC')).astimezone(source_tz)
    else:
        source_now = datetime.now(source_tz)

    left_col.markdown("### Home Clock")
    render_card(left_col, f"Current time in {source_tz_name}", source_now, source_tz_name)

    right_col.markdown("### Other Clocks")
    if not target_tz_names:
        right_col.info("Select one or more Other Clocks in the 'Clock Settings' above.")
    else:
        # build CSV-able data while rendering (include home clock as first row)
        rows = []

        # home clock row
        rows.append({
            "Label": "Home Clock",
            "Timezone": source_tz_name,
            "Abbrev": source_now.tzname(),
            "Local Time": format_dt(source_now),
            "Weekday": source_now.strftime('%A'),
            "ISO": source_now.isoformat(),
            "Epoch": int(source_now.timestamp()),
            "Offset": tz_info_from_aware_dt(source_now),
        })

        for tgt_name in target_tz_names:
            # render card
            render_card(right_col, f"{tgt_name}", source_now, tgt_name)
            # collect row
            if USE_ZONEINFO:
                dt_in_tgt = source_now.astimezone(ZoneInfo(tgt_name))
            else:
                dt_in_tgt = source_now.astimezone(pytz.timezone(tgt_name))
            rows.append({
                "Label": "Target Clock",
                "Timezone": tgt_name,
                "Abbrev": dt_in_tgt.tzname(),
                "Local Time": format_dt(dt_in_tgt),
                "Weekday": dt_in_tgt.strftime('%A'),
                "ISO": dt_in_tgt.isoformat(),
                "Epoch": int(dt_in_tgt.timestamp()),
                "Offset": tz_info_from_aware_dt(dt_in_tgt),
            })

        if rows:
            df = pd.DataFrame(rows)
            csv_data = df.to_csv(index=False)
            right_col.download_button(
                label="⬇️ Download CSV (All Clocks)",
                data=csv_data,
                file_name="all_clocks_current_conversion.csv",
                mime="text/csv",
            )

else:
    st.subheader("🧭 Manual Time Conversion")
    # present defaults in local source timezone
    if USE_ZONEINFO:
        now_in_source = datetime.now(ZoneInfo('UTC')).astimezone(source_tz)
    else:
        now_in_source = datetime.now(source_tz)

    now_local_naive = now_in_source.replace(tzinfo=None)
    default_date = now_local_naive.date()
    default_time = now_local_naive.time().replace(microsecond=0)

    user_date = st.date_input("Select date (Home Clock):", default_date)
    user_time = st.time_input("Select time (Home Clock):", default_time)

    chosen_dt_naive = datetime.combine(user_date, user_time)

    ambiguous = False
    ambiguity_note = None
    localized_source_dt = None

    # attempt to create an aware datetime; detect ambiguity and offer choice when possible
    if USE_ZONEINFO:
        try:
            # create two variants with fold=0 and fold=1 and compare offsets
            aware0 = chosen_dt_naive.replace(tzinfo=ZoneInfo(source_tz_name), fold=0)
            aware1 = chosen_dt_naive.replace(tzinfo=ZoneInfo(source_tz_name), fold=1)
            off0 = aware0.utcoffset()
            off1 = aware1.utcoffset()
            if off0 != off1:
                ambiguous = True
                ambiguity_note = "Ambiguous local time (DST transition). Choose interpretation:"
                choice = st.radio(ambiguity_note, ["Earlier (fold=0)", "Later (fold=1)"], index=0)
                localized_source_dt = aware0 if choice.startswith("Earlier") else aware1
            else:
                # not ambiguous — use default
                localized_source_dt = aware0
        except Exception:
            # fallback: naive attach
            localized_source_dt = chosen_dt_naive.replace(tzinfo=ZoneInfo(source_tz_name))
    else:
        tzobj = pytz.timezone(source_tz_name)
        try:
            localized_source_dt = tzobj.localize(chosen_dt_naive, is_dst=None)
        except pytz.AmbiguousTimeError:
            ambiguous = True
            ambiguity_note = "Ambiguous local time (DST). Choose interpretation:"
            choice = st.radio(ambiguity_note, ["Earlier (is_dst=False)", "Later (is_dst=True)"], index=0)
            try:
                localized_source_dt = tzobj.localize(chosen_dt_naive, is_dst=(True if choice.endswith("True)") else False))
            except Exception:
                # final fallback: pick is_dst=False
                localized_source_dt = tzobj.localize(chosen_dt_naive, is_dst=False)
        except pytz.NonExistentTimeError:
            ambiguous = True
            ambiguity_note = "Non-existent local time (clock jumped). Choose a fallback:"
            choice = st.radio(ambiguity_note, ["Shift forward 1 hour", "Shift backward 1 hour"], index=0)
            if choice.startswith("Shift forward"):
                fallback = chosen_dt_naive + timedelta(hours=1)
            else:
                fallback = chosen_dt_naive - timedelta(hours=1)
            localized_source_dt = tzobj.localize(fallback, is_dst=False)

    left_col.markdown("### Home Clock (chosen time)")
    render_card(left_col, f"Chosen time in {source_tz_name}", localized_source_dt, source_tz_name)

    right_col.markdown("### Converted Other Clocks")
    if not target_tz_names:
        right_col.info("Select one or more Other Clocks in the 'Clock Settings' above.")
    else:
        # collect rows for CSV while rendering (include home clock first)
        rows = []

        # home clock row
        rows.append({
            "Label": "Home Clock",
            "Timezone": source_tz_name,
            "Abbrev": localized_source_dt.tzname(),
            "Local Time": format_dt(localized_source_dt),
            "Weekday": localized_source_dt.strftime('%A'),
            "ISO": localized_source_dt.isoformat(),
            "Epoch": int(localized_source_dt.timestamp()),
            "Offset": tz_info_from_aware_dt(localized_source_dt),
        })

        for tgt_name in target_tz_names:
            render_card(right_col, f"{tgt_name} (converted)", localized_source_dt, tgt_name)
            if USE_ZONEINFO:
                dt_in_tgt = localized_source_dt.astimezone(ZoneInfo(tgt_name))
            else:
                dt_in_tgt = localized_source_dt.astimezone(pytz.timezone(tgt_name))
            rows.append({
                "Label": "Target Clock",
                "Timezone": tgt_name,
                "Abbrev": dt_in_tgt.tzname(),
                "Local Time": format_dt(dt_in_tgt),
                "Weekday": dt_in_tgt.strftime('%A'),
                "ISO": dt_in_tgt.isoformat(),
                "Epoch": int(dt_in_tgt.timestamp()),
                "Offset": tz_info_from_aware_dt(dt_in_tgt),
            })

        if rows:
            df = pd.DataFrame(rows)
            csv_data = df.to_csv(index=False)
            right_col.download_button(
                label="⬇️ Download CSV (All Clocks)",
                data=csv_data,
                file_name="all_clocks_manual_conversion.csv",
                mime="text/csv",
            )

st.markdown("---")
st.caption("Tip: CSV includes Home Clock + Target Clocks, with ISO & epoch columns for easy import.")
