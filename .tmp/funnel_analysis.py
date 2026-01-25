import pandas as pd
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Daily stats data
daily_data = """date,Connections Sent,Connections Accepted,Messages Sent,Message Replies
2025-12-24,25,5,0,1
2025-12-25,25,6,1,0
2025-12-26,25,8,0,0
2025-12-27,25,5,0,0
2025-12-28,25,5,0,0
2025-12-29,25,8,0,0
2025-12-30,25,8,0,1
2025-12-31,25,5,0,2
2026-01-01,18,7,0,0
2026-01-02,0,8,7,3
2026-01-03,0,2,0,0
2026-01-04,25,5,1,0
2026-01-05,30,11,2,1
2026-01-06,30,10,11,2
2026-01-07,30,11,6,2
2026-01-08,31,17,9,4
2026-01-09,31,9,12,1
2026-01-10,15,7,8,2
2026-01-11,0,5,7,3
2026-01-12,0,4,3,2
2026-01-13,0,2,1,2
2026-01-14,30,10,1,1
2026-01-15,30,7,5,1
2026-01-16,30,12,8,3
2026-01-17,16,3,11,1
2026-01-18,0,2,5,3
2026-01-19,0,0,1,2
2026-01-20,0,3,2,4
2026-01-21,30,15,2,3
2026-01-22,30,7,15,4
2026-01-23,30,9,7,2
2026-01-24,3,0,0,0"""

from io import StringIO
daily = pd.read_csv(StringIO(daily_data))

# Load lead-level data
files = [
    '.tmp/Smiths Competition.csv',
    '.tmp/Smiths Agentic 3.csv',
    '.tmp/Smiths Agentic 2 (1).csv'
]

all_leads = []
for f in files:
    df = pd.read_csv(f)
    all_leads.append(df)
leads = pd.concat(all_leads, ignore_index=True)

# Calculate funnel metrics
total_conn_sent = daily['Connections Sent'].sum()
total_conn_accepted = daily['Connections Accepted'].sum()
total_msgs_sent = daily['Messages Sent'].sum()
total_replies = daily['Message Replies'].sum()

# From lead data
replied_leads = leads[leads['Sender Status'] == 'REPLIED']
awaiting_reply = leads[leads['Sender Status'] == 'AWAITING_REPLY']

print("=" * 70)
print("FULL FUNNEL ANALYSIS - Dec 24 to Jan 24 (31 days)")
print("=" * 70)

print("\n### STAGE 1: CONNECTIONS ###")
print(f"Connections Sent:     {total_conn_sent}")
print(f"Connections Accepted: {total_conn_accepted}")
print(f"Accept Rate:          {total_conn_accepted/total_conn_sent*100:.1f}%")

print("\n### STAGE 2: FIRST MESSAGES ###")
print(f"Follow-up Msgs Sent:  {total_msgs_sent}")
print(f"Replies Received:     {total_replies}")
print(f"Reply Rate:           {total_replies/total_msgs_sent*100:.1f}%")

# Bottleneck analysis
print("\n### STAGE 3: YOUR RESPONSE (BOTTLENECK) ###")
replied_count = len(replied_leads)
awaiting_count = len(awaiting_reply)

# From user's CRM data - only 1 pitched
pitched = 1
meetings_booked = 0  # assumed from context

print(f"People who replied:   {replied_count}")
print(f"You responded to:     ~{pitched} (estimated from your CRM)")
print(f"Response Rate:        {pitched/replied_count*100:.1f}%")

print("\n### STAGE 4: MEETINGS ###")
print(f"Meetings Pitched:     {pitched}")
print(f"Meetings Booked:      {meetings_booked}")

print("\n" + "=" * 70)
print("FUNNEL VISUALIZATION")
print("=" * 70)

def bar(value, max_val, label, pct=None):
    width = int((value / max_val) * 40)
    pct_str = f" ({pct:.1f}%)" if pct else ""
    print(f"{label:25} {'#' * width} {value}{pct_str}")

print()
bar(total_conn_sent, total_conn_sent, "Connections Sent")
bar(total_conn_accepted, total_conn_sent, "Accepted", total_conn_accepted/total_conn_sent*100)
bar(total_msgs_sent, total_conn_sent, "Messages Sent", total_msgs_sent/total_conn_sent*100)
bar(total_replies, total_conn_sent, "Replies", total_replies/total_conn_sent*100)
bar(replied_count, total_conn_sent, "Unique Repliers", replied_count/total_conn_sent*100)
bar(pitched, total_conn_sent, "Pitched Meeting", pitched/total_conn_sent*100)
bar(meetings_booked, total_conn_sent, "Meetings Booked", 0)

print("\n" + "=" * 70)
print("BOTTLENECK DIAGNOSIS")
print("=" * 70)

print("""
STAGE              CONVERSION    STATUS
-----              ----------    ------
Conn Sent->Accept  35.5%         GOOD (industry avg 20-30%)
Accept->Reply      40.0%         GOOD (industry avg 15-25%)
Reply->You Reply   ~2%           BOTTLENECK - 46 people waiting
You Reply->Pitch   ???           Unknown - not enough data
Pitch->Meeting     ???           Unknown - only 1 pitch so far

>>> PRIMARY BOTTLENECK: Responding to replies <<<

You have 46 people who took the time to respond and are waiting.
28 of them have been waiting >7 days.

The top of funnel is performing well. The leak is in Stage 3.
""")

print("=" * 70)
print("RECOMMENDATIONS")
print("=" * 70)
print("""
1. IMMEDIATE: Work through the 46 pending replies
   - Start with recent ones (last 3 days) - still warm
   - Then hit the 7-day ones before they go cold

2. DAILY HABIT: Check HeyReach inbox every morning
   - Reply within 24hrs to maintain momentum

3. BATCH PROCESS: Dedicate 30min blocks for replies
   - Aim to clear inbox same-day

4. TRACK: Add "replied" and "pitched" columns to your CRM
   - So you can measure Stage 3 and 4 conversion
""")
