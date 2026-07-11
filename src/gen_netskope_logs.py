import os
import csv
import random
import uuid
from datetime import datetime, timedelta

def generate_netskope_logs(num_events=10000, output_path="netskope_sample.csv"):
    headers = [
        "Acting User", "Receiver", "Cc", "Application", "Assignee", "Incident Id",
        "# Violations", "DLP Profile", "DLP Rule", "DLP Policy", "Severity",
        "Status", "True File Type", "Time (GMT)", "Timestamp"
    ]
    
    policies = ["aadhaar", "DL", "sourcecode", "BU", "ENCRYPTED"]
    file_types = ["Plain Text", "Tag Image", "PDF Document", "Zip Archive"]
    
    start_date = datetime.utcnow() - timedelta(days=90)
    
    records = []
    
    for i in range(num_events):
        # 1. User & Receiver
        is_ftc = random.random() < 0.15
        if is_ftc:
            acting_user = f"contractor_{random.randint(1,100)}@yuvaext.com"
        else:
            acting_user = f"user_{random.randint(1,500)}@yuva.com"
            
        if random.random() < 0.5:
            receiver = f"personal_{random.randint(1,100)}@gmail.com"
            is_personal = True
        else:
            receiver = f"vendor_{random.randint(1,50)}@partner.com"
            is_personal = False
            
        # 2. CCs
        num_ccs = random.choices([0, 1, 2], weights=[0.7, 0.2, 0.1])[0]
        ccs = []
        has_manager_cc = False
        for _ in range(num_ccs):
            if random.random() < 0.3:
                ccs.append(f"manager_{random.randint(1,20)}@yuva.com")
                has_manager_cc = True
            else:
                ccs.append(f"colleague_{random.randint(1,100)}@yuva.com")
        cc_str = ",".join(ccs)
        
        # 3. Policy & Violations
        policy = random.choice(policies)
        if policy == "ENCRYPTED":
            violations = 1
        else:
            violations = random.randint(1, 150)
            
        # 4. Legacy Netskope Severity (Count-based, NO CONTEXT)
        if violations >= 50:
            netskope_severity = "Critical"
        elif violations >= 15:
            netskope_severity = "High"
        else:
            netskope_severity = "Medium"
            
        # 5. Analyst Status (Ground Truth Contextual Logic)
        is_false_positive = random.random() < 0.05
        
        if is_false_positive:
            analyst_status = "FalsePositive"
        elif policy == "ENCRYPTED":
            analyst_status = "Critical_Escalation"
        elif is_ftc and is_personal:
            analyst_status = "Critical_Escalation"
        elif not is_personal and has_manager_cc:
            analyst_status = "businessrequirement"
        else:
            # If nothing extreme, just map it to standard triage
            if netskope_severity == "Critical":
                analyst_status = "pending review"
            else:
                analyst_status = "low_priority"
                
        # 6. Metadata
        dt = start_date + timedelta(minutes=random.randint(1, 129600))
        ts_epoch = dt.timestamp()
        time_gmt = dt.strftime("%m/%d/%Y %H:%M:%S")
        
        record = {
            "Acting User": acting_user,
            "Receiver": receiver,
            "Cc": cc_str,
            "Application": "email",
            "Assignee": f"analyst{random.randint(1,5)}",
            "Incident Id": str(uuid.uuid4().int)[:16],
            "# Violations": violations,
            "DLP Profile": policy,
            "DLP Rule": policy,
            "DLP Policy": policy,
            "Severity": netskope_severity,
            "Status": analyst_status,
            "True File Type": random.choice(file_types) if policy != "ENCRYPTED" else "Zip Archive",
            "Time (GMT)": time_gmt,
            "Timestamp": ts_epoch
        }
        records.append(record)
        
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)
        
    print(f"Successfully generated {num_events} synthetic Netskope logs at {output_path}")
    print("Notice how 'Severity' is purely count-based, while 'Status' reflects true context!")

if __name__ == "__main__":
    generate_netskope_logs()
