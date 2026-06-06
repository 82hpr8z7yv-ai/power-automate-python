import pandas as pd
import io
import re
import os
from playwright.sync_api import sync_playwright

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

def run_headless_browser_upload(csv_path, target_url, api_token, user_email):
    print("🚀 Launching pre-baked virtual browser engine...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        try:
            # 1. Manually go to the login portal route
            print("🔑 Accessing Roadmunk secure entry gate...")
            page.goto("https://login.roadmunk.com/", timeout=30000)
            page.wait_for_load_state("networkidle")
            
            # 2. Type your work email directly into the active field box
            print(f"✍️ Typing target identification string: {user_email}")
            page.fill("input[type='email'], input[name='email'], #email", user_email)
            page.wait_for_timeout(500)
            
            # 3. Click the 'Next' or 'Log In' submit tracking button
            print("➡️ Advancing past identity checkpoint field...")
            submit_btn = page.locator("button:has-text('Next'), button:has-text('Log In'), input[type='submit']").first
            submit_btn.click()
            
            # 4. Give the SSO system ample time to authenticate the identity packet via background tokens
            print("⏳ Allowing authorization pathways and credentials to settle...")
            page.wait_for_timeout(8000) 
            
            # 5. Inject your API validation token back up into storage to cement the login session state
            print("💾 Binding authorization token to secure active local storage context...")
            page.evaluate(f"window.localStorage.setItem('token', 'Bearer {api_token}');")
            
            # 6. Navigate directly into your comprehensive timeline workspace map layout URL
            print(f"🗺️ Steering context straight to target view layout: {target_url}")
            page.goto(target_url, timeout=45000)
            
            # 7. Wait securely for the main dashboard interface layers to draw
            print("⏳ Waiting for main roadmap layout container to render...")
            page.wait_for_selector("#app, .roadmap-view, .grid-container, canvas, [class*='Roadmap']", timeout=30000)
            page.wait_for_timeout(6000)
            
            print("鼠标 Locating data control interaction elements...")
            selectors = [
                "button:has-text('Import')",
                "[aria-label*='Import']",
                ".import-btn",
                "[data-testid*='import']",
                "text=Import",
                ".bi-plus",
                ".roadmap-toolbar button"
            ]
            
            import_menu = None
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    if locator.is_visible():
                        import_menu = locator
                        print(f"🎯 Matched import target selector: '{selector}'")
                        break
                except:
                    continue
            
            if not import_menu:
                print("⚠️ Specific match missed. Attempting broad structural fallback...")
                import_menu = page.locator(".roadmap-top-nav-item, [class*='Toolbar'] button, button").first
                
            print("✨ Performing virtual mouse interactions...")
            import_menu.scroll_into_view_if_needed()
            import_menu.hover(timeout=5000)
            page.wait_for_timeout(500)
            import_menu.click(timeout=5000)
            print("✅ Main import target interaction executed.")
            
            print("📋 Activating the CSV drop-zone overlay...")
            csv_option = page.locator("text=Import CSV, text=From CSV, [data-testid*='csv'], text=CSV").first
            csv_option.click(timeout=10000)
            page.wait_for_timeout(1000)
            
            print("📤 Transmitting calculated file data array...")
            page.set_input_files("input[type='file']", csv_path)
            page.wait_for_timeout(2000)
            
            print("➡️ Advancing past schema configuration panel...")
            page.wait_for_selector("button:has-text('Next')", timeout=10000)
            page.click("button:has-text('Next')")
            page.wait_for_timeout(1000)
            
            print("💾 Finalizing updates: Clicking 'Update & Overwrite All'...")
            page.wait_for_selector("button:has-text('Overwrite'), button:has-text('Update')", timeout=10000)
            page.click("button:has-text('Update & Overwrite All'), button:has-text('Update and Overwrite All'), button:has-text('Overwrite All')")
            
            page.wait_for_timeout(6000)
            print("🎉 Success! The synchronization interaction loop completed beautifully.")
            
        except Exception as e:
            print(f"❌ Automation process stalled: {e}")
            try:
                page_text = page.evaluate("() => document.body.innerText")
                print(f"🔍 Diagnostic Dump (Current Page Layout Text):\n{page_text[:600]}")
            except:
                pass
            raise e
        finally:
            browser.close()

def run_transfer_pipeline(project_excel_bytes, demand_excel_bytes, roadmap_id, api_token, user_email):
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

    temp_csv_path = "/tmp/roadmunk_sync_payload.csv"
    rm.to_csv(temp_csv_path, index=False)
    print(f"Saved cleaned file asset locally to {temp_csv_path}")
    
    run_headless_browser_upload(temp_csv_path, roadmap_id, api_token, user_email)

    if os.path.exists(temp_csv_path):
        os.remove(temp_csv_path)
        
    return {"status": "Complete"}
