import pandas as pd
import io
import re
import requests

def sanitize_list(raw_value):
    if pd.isna(raw_value) or raw_value == "":
        return []
    cleaned = []
    for p in str(raw_value).split(","):
        val = p.replace('"', '').strip().upper()
        val = val.replace("&AMP;", "&")
        if re.search(r'\d', val):
            continue
        if val in ["C & BS", "C &AMP; BS"]:
            val = "B&CS"
        cleaned.append(val)
    return list(dict.fromkeys(cleaned))

def normalize_multiselect(values):
    if not values:
        return ""
    return ",".join(f'"{v}"' for v in values if v)

def normalize_date(value):
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except:
        return ""

def normalize_percent(value):
    try:
        return float(value) / 100
    except:
        return None

def derive_fiscal_year_from_date(value):
    try:
        dt = pd.to_datetime(value)
        return f"FY{str(dt.year)[-2:]}"
    except:
        return ""

STATE_TO_STATUS = {
    "Work in Progress": "Work In Progress",
    "Open": "Open",
    "Pending": "Pending",
    "Closed Complete": "Closed Complete",
    "Closed Incomplete": "Closed Incomplete",
    "Closed Skipped": "Closed Skipped",
}

def process_df(df, is_project=True):
    def get_column(options):
        for col in options:
            if col in df.columns:
                return col
        return None

    goals_col = get_column(["Goals", "Goal", "Goal(s)"])
    invest_col = get_column(["Investment Type", "Investment", "Investment Category"])
    assign_col = get_column(["Assignment Group", "Assignment group", "Assigned Group"])
    portfolio_col = get_column(["Portfolio", "Portfolio Name"])
    start_col = get_column(["Approved start date", "Planned start date", "Start date", "Desired Start date"])
    end_col = get_column(["Approved end date", "Planned end date", "End date", "Desired End date"])

    if start_col is None or end_col is None:
        raise ValueError("❌ Missing required date columns")

    out = pd.DataFrame()
    out["SN Project Number"] = df["Number"]
    out["Original ID"] = df["Number"]
    out["External ID"] = df["Number"]
    out["Item (REQUIRED)"] = df["Project Name"] if is_project else df["Title"]
    out["Start Date"] = df[start_col].apply(normalize_date)
    out["End Date"] = df[end_col].apply(normalize_date)

    if is_project:
        out["Status"] = df["State"].map(STATE_TO_STATUS).fillna(df["State"])
        out["% Complete"] = df["Percent complete"].apply(normalize_percent)
        out["Project Manager"] = df.get("Project manager", "")
    else:
        out["Status"] = "Demand"
        out["% Complete"] = None
        out["Project Manager"] = df.get("Project Manager", "")

    out["Type"] = "Project" if is_project else "Demand"

    goals_raw = df[goals_col] if goals_col else ""
    goals_lists = goals_raw.apply(sanitize_list) if goals_col else []
    out["Area"] = goals_lists.apply(normalize_multiselect) if goals_col else ""

    invest_raw = df[invest_col] if invest_col else ""
    invest_lists = invest_raw.apply(sanitize_list) if invest_col else []
    out["Focus Area"] = invest_lists.apply(normalize_multiselect) if invest_col else ""

    assign_raw = df[assign_col] if assign_col else ""
    assign_lists = assign_raw.apply(sanitize_list) if assign_col else []
    out["Teams"] = assign_lists.apply(normalize_multiselect) if assign_col else ""

    portfolio_raw = df[portfolio_col] if portfolio_col else ""
    portfolio_lists = portfolio_raw.apply(sanitize_list) if portfolio_col else []
    out["Functional Committee"] = portfolio_lists.apply(normalize_multiselect) if portfolio_col else ""

    out["Fiscal Year"] = df[end_col].apply(derive_fiscal_year_from_date)
    campus_lists = df["Impacted Companies"].apply(sanitize_list)
    out["Campus"] = campus_lists.apply(normalize_multiselect)

    pillar_lists = df["Impacted Pillars"].apply(sanitize_list)
    out["Pillar_List"] = pillar_lists
    out["Pillar_Count"] = pillar_lists.apply(len)
    out = out.explode("Pillar_List")
    out["Pillar"] = out["Pillar_List"].fillna("")
    out.drop(columns=["Pillar_List"], inplace=True)

    def build_id(row):
        if row["Pillar_Count"] <= 1 or not row["Pillar"]:
            return row["Original ID"]
        return f"{row['Original ID']}_{row['Pillar']}"

    out["External ID"] = out.apply(build_id, axis=1)
    return out

def upload_via_direct_api(csv_string, roadmap_id, api_token):
    """
    Pushes the clean CSV string directly into the Roadmunk file processing endpoint,
    bypassing headless UI limitations and staying well under memory restrictions.
    """
    print("📡 Preparing direct API multipart file upload...")
    
    # Extract the short roadmap ID from the URL if a full link was passed
    short_id = roadmap_id.split("/roadmap/rm3/")[-1].split("/")[0] if "/roadmap/" in roadmap_id else roadmap_id
    print(f"🎯 Targeted Roadmunk ID: {short_id}")

    # FIX: Corrected the target endpoint to use Roadmunk's dedicated upload ingestion gate
    upload_url = f"https://app.roadmunk.com/api/v1/roadmaps/{short_id}/import"
    
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    
    # Pack the CSV data directly into an in-memory file structure
    files = {
        'file': ('service_now_sync.csv', csv_string, 'text/csv')
    }
    
    # Tell Roadmunk to overwrite existing matching external IDs
    data = {
        'overwrite': 'true',
        'matchBy': 'External ID'
    }

    print(f"Sending payload to: {upload_url}")
    response = requests.post(upload_url, headers=headers, files=files, data=data, timeout=30)
    
    if response.status_code in [200, 201, 202]:
        print("🎉 Success! Roadmunk API accepted the CSV upload matrix cleanly.")
    else:
        print(f"❌ API Gate Error ({response.status_code}): {response.text}")
        raise Exception(f"Roadmunk API upload rejected: {response.text}")

def run_transfer_pipeline(project_excel_bytes, demand_excel_bytes, roadmap_id, api_token):
    print("Reading Project Excel matrix...")
    proj = pd.read_excel(io.BytesIO(project_excel_bytes))
    proj.columns = proj.columns.str.strip()
    projects_rm = process_df(proj, True)

    print("Reading Demand Excel matrix...")
    dmd = pd.read_excel(io.BytesIO(demand_excel_bytes))
    dmd.columns = dmd.columns.str.strip()
    dmd = dmd[dmd.get("State", "").astype(str).str.lower() != "completed"]
    demands_rm = process_df(dmd, False)

    project_names = projects_rm["Item (REQUIRED)"].str.lower().str.strip()
    demands_rm = demands_rm[~demands_rm["Item (REQUIRED)"].str.lower().str.strip().isin(project_names)]

    rm = pd.concat([projects_rm, demands_rm], ignore_index=True)
    rm = rm.drop_duplicates(subset=["External ID"])

    # Generate a clean CSV string directly in memory (No local files, saving RAM)
    csv_buffer = io.StringIO()
    rm.to_csv(csv_buffer, index=False)
    csv_string = csv_buffer.getvalue()
    
    # Ship to Roadmunk
    upload_via_direct_api(csv_string, roadmap_id, api_token)
    return {"status": "Complete"}
