import pandas as pd
import json
import re

DICT_PATH = "C:/Users/harsh/Downloads/fage new/fage-master/Description.xlsx"
DATA_PATH = "data/raw.csv"

def analyze():
    # Phase 1: Read Official Data Dictionary
    print("--- Phase 1: Reading Data Dictionary ---")
    df_dict = pd.read_excel(DICT_PATH, sheet_name="Data_Dicitionary")
    df_dict = df_dict.dropna(subset=['Feature', 'Description'])
    
    # Store mapping
    feature_map = {}
    for _, row in df_dict.iterrows():
        feature_map[row['Feature']] = {
            'Variable_Name': str(row.get('Variable Name', '')),
            'Description': str(row['Description']).strip()
        }
    
    print(f"Loaded {len(feature_map)} features from dictionary.")
    
    if 'F3924' in feature_map:
        print(f"F3924: {feature_map['F3924']}")
    else:
        print("F3924 not found in dictionary.")

    # Phase 2: Semantic Feature Grouping
    print("\n--- Phase 2: Semantic Feature Grouping ---")
    groups = {
        'cash': 0, 'cheque': 0, 'credit': 0, 'debit': 0, 'amount': 0,
        'count': 0, 'ratio': 0, 'velocity': 0, 'behavioral': 0, 
        'balance': 0, 'historical': 0, 'customer': 0, 'time_window': 0, 'other': 0
    }
    
    time_windows = []
    suspicious_features = []
    leakage_keywords = ['fraud', 'suspicious', 'investigation', 'alert', 'confirmed', 
                        'chargeback', 'recovery', 'disposition', 'case', 'outcome', 
                        'post-event', 'review', 'sar', 'status']

    for feat, meta in feature_map.items():
        desc_lower = meta['Description'].lower()
        var_lower = meta['Variable_Name'].lower()
        combined = f"{desc_lower} {var_lower}"
        
        # Categorization
        categorized = False
        if 'cash' in combined: groups['cash'] += 1; categorized = True
        if 'cheque' in combined or 'check' in combined: groups['cheque'] += 1; categorized = True
        if 'credit' in combined or 'cr' in var_lower: groups['credit'] += 1; categorized = True
        if 'debit' in combined or 'dr' in var_lower: groups['debit'] += 1; categorized = True
        if 'amount' in combined or 'amt' in var_lower: groups['amount'] += 1; categorized = True
        if 'count' in combined or 'num' in combined or 'cnt' in var_lower: groups['count'] += 1; categorized = True
        if 'ratio' in combined or 'pct' in combined or 'proportion' in combined: groups['ratio'] += 1; categorized = True
        if 'velocity' in combined or 'speed' in combined: groups['velocity'] += 1; categorized = True
        if 'behav' in combined or 'pattern' in combined: groups['behavioral'] += 1; categorized = True
        if 'balance' in combined or 'bal' in var_lower: groups['balance'] += 1; categorized = True
        if 'hist' in combined or 'past' in combined: groups['historical'] += 1; categorized = True
        if 'cust' in combined or 'acct' in combined or 'account' in combined: groups['customer'] += 1; categorized = True
        
        # Lookback extraction
        lookback = re.search(r'([l_])?(\d{1,3})d', var_lower)
        if lookback or 'day' in combined or 'month' in combined or 'week' in combined:
            groups['time_window'] += 1
            if lookback: time_windows.append(lookback.group(0))
            categorized = True
            
        if not categorized:
            groups['other'] += 1
            
        # Phase 5 Leakage Detection
        for kw in leakage_keywords:
            if kw in combined:
                suspicious_features.append({
                    'Feature': feat,
                    'Variable_Name': meta['Variable_Name'],
                    'Description': meta['Description'],
                    'Why_suspicious': f"Matched keyword: '{kw}'"
                })
                break

    print("Groups:\n", json.dumps(groups, indent=2))
    print(f"\nUnique time window tokens found: {set(time_windows)}")
    
    print(f"\n--- Phase 5: Suspicious Features Found --- ({len(suspicious_features)})")
    for s in suspicious_features:
        print(s)

if __name__ == "__main__":
    analyze()
