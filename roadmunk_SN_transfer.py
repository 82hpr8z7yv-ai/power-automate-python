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
        if val in ["C & BS", "C &AMP; BS", "C & BS"]:
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

# ==========================================
# DIRECT ROADMUNK GRAPHQL PUSH AUTOMATION
# ==========================================
def push_to_roadmunk_graphql(dataframe, roadmap_id, api_token):
    # Roadmunk App Gateway Endpoint
    url = "https://app-gateway.roadmunk.com/"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # Process up to 25 rows for our automated proof of concept
    for _, row in dataframe.head(25).iterrows():
        raw_title = str(row.get("Item (REQUIRED)", "Untitled ServiceNow Item")).strip()
        ext_id = str(row.get("External ID", "Unknown_ID"))
        status = str(row.get("Status", "Unknown"))
        
        # Structure the payload using explicit GraphQL variables to ensure compliance
        query_payload = {
            "query": """
            mutation CreateItem($input: CreateRoadmapItemInput!) {
              createRoadmapItem(input: $input) {
                clientMutationId
              }
            }
            """,
            "variables": {
                "input": {
                    "roadmapId": roadmap_id,
                    "title": raw_title,
                    "description": f"ServiceNow ID: {ext_id} | Status: {status}"
                }
            }
        }
        
        try:
            # Execute the push with a clear safety timeout window
            response = requests.post(url, json=query_payload, headers=headers, timeout=10)
            
            # Log any explicit validation API warnings directly to the Render console
            if response.status_code != 200:
                print(f"⚠️ Roadmunk API Warning for Row {ext_id}: Status {response.status_code} - {response.text}")
            else:
                print(f"✅ Successfully processed and pushed item: {raw_title}")
                
        except Exception as api_err:
            print(f"❌ Network transmission failure on item {ext_id}: {api_err}")
    
        
        # Execute the programmatic push
        try:
            response = requests.post(url, json={"query": mutation}, headers=headers)
            if response.status_code != 200:
                print(f"Failed row upload: {response.text}")
        except Exception as e:
            print(f"Network processing error: {e}")

# ==========================================
# CORE PROCESSING PIPELINE
# ==========================================
def run_transfer_pipeline(project_excel_bytes, demand_excel_bytes, roadmap_id, api_token):
    proj = pd.read_excel(io.BytesIO(project_excel_bytes))
    proj.columns = proj.columns.str.strip()
    projects_rm = process_df(proj, True)

    dmd = pd.read_excel(io.BytesIO(demand_excel_bytes))
    dmd.columns = dmd.columns.str.strip()
    dmd = dmd[dmd.get("State", "").astype(str).str.lower() != "completed"]
    demands_rm = process_df(dmd, False)

    project_names = projects_rm["Item (REQUIRED)"].str.lower().str.strip()
    demands_rm = demands_rm[~demands_rm["Item (REQUIRED)"].str.lower().str.strip().isin(project_names)]

    rm = pd.concat([projects_rm, demands_rm], ignore_index=True)
    rm = rm.drop_duplicates(subset=["External ID"])

    # Trigger our direct GraphQL automation loop right here inside Render
    if roadmap_id and api_token:
        push_to_roadmunk_graphql(rm, roadmap_id, api_token)

    outputs_payload = {}
    outputs_payload["roadmunk_import_ready.csv"] = rm.to_csv(index=False)
    return outputs_payload
