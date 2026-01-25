import pandas as pd
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Load all three files
files = [
    '.tmp/Smiths Competition.csv',
    '.tmp/Smiths Agentic 3.csv',
    '.tmp/Smiths Agentic 2 (1).csv'
]

all_leads = []
for f in files:
    df = pd.read_csv(f)
    df['source'] = f.split('/')[-1]
    all_leads.append(df)

df = pd.concat(all_leads, ignore_index=True)

# Parse dates
df['Last action time'] = pd.to_datetime(df['Last action time'], format='%m/%d/%Y %H:%M:%S')

# People who REPLIED = they responded to you, you need to follow up
replied = df[df['Sender Status'] == 'REPLIED'].copy()
replied = replied.sort_values('Last action time')

# Calculate days since reply
now = datetime.now()
replied['days_ago'] = (now - replied['Last action time']).dt.days

print("=" * 80)
print("PEOPLE WHO REPLIED - NEED YOUR RESPONSE (oldest first)")
print("=" * 80)
print(f"\nTotal: {len(replied)} people waiting for your reply\n")

for _, row in replied.iterrows():
    name = f"{row['Lead first name']} {row['Lead last name']}"
    date = row['Last action time'].strftime('%b %d')
    days = row['days_ago']
    position = str(row['Lead position'])[:50] if pd.notna(row['Lead position']) else ''
    company = str(row['Lead company name'])[:30] if pd.notna(row['Lead company name']) else ''
    url = row['Lead LinkedIn URL']

    urgency = "[!!!]" if days > 7 else "[!!]" if days > 3 else "[OK]"
    print(f"{urgency} {name} | {date} ({days}d ago)")
    print(f"     {position}")
    print(f"     {url}")
    print()

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"[!!!] Overdue (>7 days): {len(replied[replied['days_ago'] > 7])}")
print(f"[!!]  Getting stale (4-7 days): {len(replied[(replied['days_ago'] > 3) & (replied['days_ago'] <= 7)])}")
print(f"[OK]  Recent (0-3 days): {len(replied[replied['days_ago'] <= 3])}")

# Also show AWAITING_REPLY for context
awaiting = df[df['Sender Status'] == 'AWAITING_REPLY']
print(f"\nAwaiting their reply: {len(awaiting)} people")

# Export to CSV for easy tracking
replied_export = replied[['Lead first name', 'Lead last name', 'Lead LinkedIn URL', 'Lead position', 'Lead company name', 'Last action time', 'days_ago']].copy()
replied_export.to_csv('.tmp/needs_followup.csv', index=False)
print("\nExported to .tmp/needs_followup.csv")
