import random
import csv
import json
from faker import Faker

fake = Faker()

# ---------- CONFIG ----------
ENTRIES_PER_BIN = 10000

INTERNAL_DOMAIN = "yuva.com"
FTC_DOMAIN = "yuvaext.com"

PERSONAL_DOMAINS = ["gmail.com", "yahoo.com"]
BUSINESS_DOMAINS = ["partner.com", "vendor.com"]

PII_POLICIES = ["PII_PAN", "PII_AADHAAR", "PII_DL"]
BU_POLICIES = [f"BU_CONTENT_G{i}" for i in range(1, 10)]
SOURCE_CODE = ["SOURCE_CODE"]

CONFIDENCE = ["low", "medium", "high"]

# ---------- HELPERS ----------
def email(name, domain):
    return f"{name}@{domain}"

def internal_email():
    return email(fake.user_name(), INTERNAL_DOMAIN)

def ftc_email():
    return email(fake.user_name(), FTC_DOMAIN)

def personal_email():
    return email(fake.user_name(), random.choice(PERSONAL_DOMAINS))

def business_email():
    return email(fake.user_name(), random.choice(BUSINESS_DOMAINS))

# ---------- BIN GENERATORS ----------
def generate_bin_001():
    data = []
    for _ in range(ENTRIES_PER_BIN):
        data.append({
            "bin_id": "BIN_001",
            "sender": internal_email(),
            "receiver": personal_email(),
            "cc": "",
            "sender_type": "FTE",
            "receiver_type": "Personal",
            "dlp_policy": random.choice(PII_POLICIES),
            "dlp_category":"PII-Content"
        })
    return data

def generate_bin_002():
    data = []
    for _ in range(ENTRIES_PER_BIN):
        data.append({
            "bin_id": "BIN_002",
            "sender": internal_email(),
            "receiver": business_email(),
            "cc": internal_email(),  # manager / peer
            "sender_type": "FTE",
            "receiver_type": "Business",
            "dlp_policy": "SOURCE_CODE",
            "dlp_category":"Code-Content"
        })
    return data

def generate_bin_003():
    data = []
    for _ in range(ENTRIES_PER_BIN):
        data.append({
            "bin_id": "BIN_003",
            "sender": ftc_email(),
            "receiver": personal_email(),
            "cc": "",
            "sender_type": "FTC",
            "receiver_type": "Personal",
            "dlp_policy": random.choice(BU_POLICIES),
            "dlp_category": "BU-Content"
        })
    return data

# ---------- MAIN ----------
bin1 = generate_bin_001()
bin2 = generate_bin_002()
bin3 = generate_bin_003()

# Write JSONL files
def write_jsonl(filename, data):
    with open(filename, "w") as f:
        for row in data:
            f.write(json.dumps(row) + "\n")

write_jsonl("bin_001.jsonl", bin1)
write_jsonl("bin_002.jsonl", bin2)
write_jsonl("bin_003.jsonl", bin3)

# Write combined CSV
with open("all_bins.csv", "w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=bin1[0].keys()
    )
    writer.writeheader()
    for row in bin1 + bin2 + bin3:
        writer.writerow(row)

print("✅ 30,000+ events generated successfully.")
