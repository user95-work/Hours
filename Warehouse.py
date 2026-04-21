import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from Bank_holidays import get_all_bank_holidays
from Scottish_Bank_Holidays import get_scotland_bank_holidays


DAY_START = 4
DAY_END = 18
OVERTIME_LIMIT = 40
Min_hours = 0

#How to RUn  it 
# & "C:\Users\thurdiss\Downloads\Python Rates\.venv\Scripts\streamlit.exe" run "C:\Users\thurdiss\Downloads\Python Rates\warehouse.py"


# ----------------------------
# DAY TYPE
# ----------------------------
def get_day_type(dt):
    wd = dt.weekday()
    if wd == 5:
        return "saturday"
    elif wd == 6:
        return "sunday"
    return "weekday"


# ----------------------------
# SAFE TIME PARSE
# ----------------------------
def parse_time(date, t):
    if pd.isna(t) or pd.isna(date):
        return None

    try:
        date = pd.to_datetime(date, dayfirst=True).date()
        time_obj = datetime.strptime(str(t), "%H:%M:%S").time()
        dt = datetime.combine(date, time_obj)
        return dt.replace(tzinfo=ZoneInfo("Europe/London"))
    except:
        return None


# ----------------------------
# PROCESS
# ----------------------------
def process(df):

    # ----------------------------
    # CLEAN + VALIDATION
    # ----------------------------
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"])

    # remove blank IDs properly
    df = df[df["ID Number"].notna()]
    df = df[df["ID Number"].astype(str).str.strip() != ""]

    df = df.sort_values(by=["ID Number", "Date"]).reset_index(drop=True)

    df["Start_dt"] = df.apply(lambda r: parse_time(r["Date"], r["Start"]), axis=1)
    df["End_dt"] = df.apply(lambda r: parse_time(r["Date"], r["Finish"]), axis=1)

    df = df.dropna(subset=["Start_dt", "End_dt"])

    # fix overnight shifts
    df.loc[df["End_dt"] <= df["Start_dt"], "End_dt"] += pd.Timedelta(days=1)

    output = []

    # ----------------------------
    # BANK HOLIDAYS (SAFE)
    # ----------------------------
    bank_holidays = (
        get_scotland_bank_holidays()
        if scotland_mode
        else get_all_bank_holidays()
    )
    bank_holidays = set(bank_holidays)

    # ----------------------------
    # PROCESS PER EMPLOYEE
    # ----------------------------
    for emp_id, group in df.groupby("ID Number"):

        running = 0  # weekly OT tracker

        for _, row in group.iterrows():

            start_dt = row["Start_dt"]
            end_dt = row["End_dt"]

            # ----------------------------
            # SAFETY CHECK (PREVENT HANGS)
            # ----------------------------
            if pd.isna(start_dt) or pd.isna(end_dt):
                continue

            shift_hours = (end_dt - start_dt).total_seconds() / 3600
            if shift_hours > 72:   # hard safety cap
                continue

            if shift_hours < Min_hours:
                end_dt = start_dt + pd.Timedelta(hours=Min_hours)

            shift_has_bh_hours = False

            # shift-level flag
            shift_started_on_bh = start_dt.date() in bank_holidays

            # ----------------------------
            # RATE BUCKETS
            # ----------------------------
            rates = {
                "weekday_day": 0,
                "weekday_night": 0,
                "weekday_ot_day": 0,
                "weekday_ot_night": 0,

                "saturday_day": 0,
                "saturday_night": 0,
                "saturday_ot_day": 0,
                "saturday_ot_night": 0,

                "sunday_day": 0,
                "sunday_night": 0,

                "bh_day": 0,
                "bh_night": 0
            }

            # ----------------------------
            # TIME LOOP (SAFE)
            # ----------------------------
            step = timedelta(minutes=15)
            current = start_dt
            loop_count = 0

            while current < end_dt:

                loop_count += 1
                if loop_count > 2000:
                    break  # prevents freeze

                next_step = min(current + step, end_dt)
                duration = (next_step - current).total_seconds() / 3600

                hour = current.hour + current.minute / 60
                is_day = DAY_START <= hour < DAY_END

                day_type = get_day_type(current)
                is_bh = current.date() in bank_holidays

                if is_bh:
                    shift_has_bh_hours = True

                # ----------------------------
                # OT RULE
                # ----------------------------
                if day_type == "sunday":
                    is_ot = False
                else:
                    is_ot = running >= OVERTIME_LIMIT

                # ----------------------------
                # RATE SELECTION
                # ----------------------------
                if is_bh:
                    key = "bh_"
                else:
                    if day_type == "weekday":
                        key = "weekday_ot_" if is_ot else "weekday_"
                    elif day_type == "saturday":
                        key = "saturday_ot_" if is_ot else "saturday_"
                    else:
                        key = "sunday_"

                key += "day" if is_day else "night"
                rates[key] += duration

                # ----------------------------
                # OT TRACKING
                # ----------------------------
                if not is_bh:
                    if running < OVERTIME_LIMIT:
                        use = min(duration, OVERTIME_LIMIT - running)
                    else:
                        use = duration

                    running += use

                current = next_step

            # ----------------------------
            # OUTPUT
            # ----------------------------
            output.append({
                "ID": emp_id,
                "Date": row["Date"].strftime("%d/%m/%Y"),

                "Weekday Day": round(rates["weekday_day"], 2),
                "Weekday Night": round(rates["weekday_night"], 2),
                "Weekday OT Day": round(rates["weekday_ot_day"], 2),
                "Weekday OT Night": round(rates["weekday_ot_night"], 2),

                "Saturday Day": round(rates["saturday_day"], 2),
                "Saturday Night": round(rates["saturday_night"], 2),
                "Saturday OT Day": round(rates["saturday_ot_day"], 2),
                "Saturday OT Night": round(rates["saturday_ot_night"], 2),

                "Sunday Day": round(rates["sunday_day"], 2),
                "Sunday Night": round(rates["sunday_night"], 2),

                "Bank Holiday Day": round(rates["bh_day"], 2),
                "Bank Holiday Night": round(rates["bh_night"], 2),

                "Total Hours": round(sum(rates.values()), 2),

                "Start Time": row["Start"],
                "Finish": row["Finish"],
                "Running Total": running,
                "Shift Contains BH Hours": shift_has_bh_hours
            })

    return pd.DataFrame(output)


# ----------------------------
# STREAMLIT UI
# ----------------------------
st.title("Hours Converter Warehouse")

scotland_mode = st.toggle("Use Scottish BH List")
Min_hours = st.number_input("Min Hours", value=Min_hours)

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file is not None:

    df = pd.read_excel(uploaded_file, engine="openpyxl")
    df.columns = df.columns.astype(str)

    df["Start"] = df["Start "]
    df["Finish"] = df["Finish"]

    result = process(df)

    st.write("### Processed Output")
    st.dataframe(result)

    st.download_button(
        "Download CSV",
        result.to_csv(index=False),
        file_name="processed_timesheet.csv",
        mime="text/csv"
    )
