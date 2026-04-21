import streamlit as st
import pandas as pd
from datetime import datetime, timedelta,date
from Bank_holidays import get_all_bank_holidays
from zoneinfo import ZoneInfo
from Scottish_Bank_Holidays import get_scotland_bank_holidays


DAY_START = 4
DAY_END = 18
OVERTIME_LIMIT = 47.5
SCOTLAND = True
Min_hours= 8



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

        # UK timezone (handles DST automatically)
        return dt.replace(tzinfo=ZoneInfo("Europe/London"))

    except:
        return None


# ----------------------------
# SHIFT SPLIT
# ----------------------------
def split_shift(start, end):
    day = 0
    night = 0

    step = timedelta(minutes=15)
    current = start

    while current < end:
        next_step = min(current + step, end)

        hour = current.hour + current.minute / 60
        duration = (next_step - current).total_seconds() / 3600

        if DAY_START <= hour < DAY_END:
            day += duration
        else:
            night += duration

        current = next_step

    return day, night


# ----------------------------
# PROCESS
# ----------------------------
def process(df):

    # ----------------------------
    # CLEAN + SAFE DATE PARSING
    # ----------------------------
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"])

    df = df.sort_values(by=["ID Number", "Date"]).reset_index(drop=True)

    df["Start_dt"] = df.apply(lambda r: parse_time(r["Date"], r["Start"]), axis=1)
    df["End_dt"] = df.apply(lambda r: parse_time(r["Date"], r["Finish"]), axis=1)

    df = df.dropna(subset=["Start_dt", "End_dt"])

    df.loc[df["End_dt"] <= df["Start_dt"], "End_dt"] += pd.Timedelta(days=1)

    output = []

    # ----------------------------
    # BANK HOLIDAYS
    # ----------------------------
    bank_holidays = (
        get_scotland_bank_holidays()
        if scotland_mode
        else get_all_bank_holidays()
    )

    # ----------------------------
    # PROCESS PER EMPLOYEE
    # ----------------------------
    for emp_id, group in df.groupby("ID Number"):

        running = 0  # overtime tracker (GLOBAL per employee)

        for _, row in group.iterrows():

            is_bh = row["Date"].date() in bank_holidays

            start_dt = row["Start_dt"]
            end_dt = row["End_dt"]

            # ----------------------------
            # MIN HOURS ADJUSTMENT
            # ----------------------------
            total_hours = (end_dt - start_dt).total_seconds() / 3600

            if total_hours < Min_hours:
                end_dt = start_dt + pd.Timedelta(hours=Min_hours)

            # ----------------------------
            # SPLIT INTO DAY/NIGHT
            # ----------------------------
            day, night = split_shift(start_dt, end_dt)

            std_day = std_night = ot_day = ot_night = 0

            # ----------------------------
            # ALLOCATION ENGINE
            # ----------------------------
            step = timedelta(minutes=15)
            current = start_dt

            while current < end_dt:

                next_step = min(current + step, end_dt)
                duration = (next_step - current).total_seconds() / 3600

                hour = current.hour + current.minute / 60
                is_day = DAY_START <= hour < DAY_END

                # overtime check (GLOBAL ONLY)
                if running < OVERTIME_LIMIT:
                    space = OVERTIME_LIMIT - running
                    use = min(space, duration)

                    if is_day:
                        std_day += use
                    else:
                        std_night += use
                else:
                    use = duration

                    if is_day:
                        ot_day += use
                    else:
                        ot_night += use

                # BH rule (time still counts, OT doesn't progress)
                if not is_bh:
                    running += use

                current = next_step

            # ----------------------------
            # OUTPUT ROW
            # ----------------------------
            output.append({
                "ID": emp_id,
                "Date": row["Date"].strftime("%d/%m/%Y"),
                "Days Standard": round(std_day, 2),
                "Days OT": round(ot_day, 2),
                "Nights Standard": round(std_night, 2),
                "Nights OT": round(ot_night, 2),
                "Total Hours": round(day + night, 2),
                "Start Time": row["Start"],
                "Finish": row["Finish"],
                "Bank Holiday": is_bh,
                "Running Total": running
            })

    return pd.DataFrame(output)

# ----------------------------
# STREAMLIT UI
# ----------------------------
st.title("Hours Converter Driving")
scotland_mode = st.toggle("Use Scottish BH List")
Min_hours = st.number_input("Min Hours",value =Min_hours)
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])


if uploaded_file is not None:

    df = pd.read_excel(uploaded_file, engine="openpyxl")

    # clean headers
    df.columns = df.columns.astype(str)

    # IMPORTANT: keep your "Start " column (space)
    df["Start"] = df["Start "]
    df["Finish"] = df["Finish"]

    # remove blank IDs
    df = df[df["ID Number"].notna()]
    df = df[df["ID Number"].astype(str).str.strip() != ""]

    #st.write("### Cleaned Data")
    #st.dataframe(df)

    result = process(df)

    st.write("### Processed Output")
    st.dataframe(result)

    st.download_button(
        "Download CSV",
        result.to_csv(index=False),
        file_name="processed_timesheet.csv",
        mime="text/csv"
    )
