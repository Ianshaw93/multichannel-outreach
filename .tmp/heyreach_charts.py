import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO

data = """category,Connections Sent,Connections Accepted,Messages Sent,Message Replies,InMails Sent,InMail Replies
Wed Dec 24 2025,25,5,0,1,0,0
Thu Dec 25 2025,25,6,1,0,0,0
Fri Dec 26 2025,25,8,0,0,0,0
Sat Dec 27 2025,25,5,0,0,0,0
Sun Dec 28 2025,25,5,0,0,0,0
Mon Dec 29 2025,25,8,0,0,0,0
Tue Dec 30 2025,25,8,0,1,0,0
Wed Dec 31 2025,25,5,0,2,0,0
Thu Jan 01 2026,18,7,0,0,0,0
Fri Jan 02 2026,0,8,7,3,0,0
Sat Jan 03 2026,0,2,0,0,0,0
Sun Jan 04 2026,25,5,1,0,0,0
Mon Jan 05 2026,30,11,2,1,0,0
Tue Jan 06 2026,30,10,11,2,0,0
Wed Jan 07 2026,30,11,6,2,0,0
Thu Jan 08 2026,31,17,9,4,0,0
Fri Jan 09 2026,31,9,12,1,0,0
Sat Jan 10 2026,15,7,8,2,0,0
Sun Jan 11 2026,0,5,7,3,0,0
Mon Jan 12 2026,0,4,3,2,0,0
Tue Jan 13 2026,0,2,1,2,0,0
Wed Jan 14 2026,30,10,1,1,0,0
Thu Jan 15 2026,30,7,5,1,0,0
Fri Jan 16 2026,30,12,8,3,0,0
Sat Jan 17 2026,16,3,11,1,0,0
Sun Jan 18 2026,0,2,5,3,0,0
Mon Jan 19 2026,0,0,1,2,0,0
Tue Jan 20 2026,0,3,2,4,0,0
Wed Jan 21 2026,30,15,2,3,0,0
Thu Jan 22 2026,30,7,15,4,0,0
Fri Jan 23 2026,30,9,7,2,0,0
Sat Jan 24 2026,3,0,0,0,0,0"""

df = pd.read_csv(StringIO(data))
df['date'] = pd.to_datetime(df['category'], format='%a %b %d %Y')
df = df.sort_values('date')

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('HeyReach LinkedIn Outreach Analytics (Dec 24 - Jan 24)', fontsize=14, fontweight='bold')

# Chart 1: Daily activity over time
ax1 = axes[0, 0]
ax1.plot(df['date'], df['Connections Sent'], label='Connections Sent', marker='o', markersize=3)
ax1.plot(df['date'], df['Connections Accepted'], label='Connections Accepted', marker='s', markersize=3)
ax1.set_title('Connection Activity Over Time')
ax1.set_xlabel('Date')
ax1.set_ylabel('Count')
ax1.legend()
ax1.tick_params(axis='x', rotation=45)
ax1.grid(True, alpha=0.3)

# Chart 2: Messages sent vs replies
ax2 = axes[0, 1]
ax2.bar(df['date'], df['Messages Sent'], label='Messages Sent', alpha=0.7)
ax2.bar(df['date'], df['Message Replies'], label='Message Replies', alpha=0.7)
ax2.set_title('Messages Sent vs Replies')
ax2.set_xlabel('Date')
ax2.set_ylabel('Count')
ax2.legend()
ax2.tick_params(axis='x', rotation=45)
ax2.grid(True, alpha=0.3)

# Chart 3: Totals summary
ax3 = axes[1, 0]
totals = {
    'Conn. Sent': df['Connections Sent'].sum(),
    'Conn. Accepted': df['Connections Accepted'].sum(),
    'Msgs Sent': df['Messages Sent'].sum(),
    'Msg Replies': df['Message Replies'].sum()
}
colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63']
bars = ax3.bar(totals.keys(), totals.values(), color=colors)
ax3.set_title('Total Activity Summary')
ax3.set_ylabel('Count')
for bar, val in zip(bars, totals.values()):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, str(val), ha='center', fontweight='bold')

# Chart 4: Conversion rates
ax4 = axes[1, 1]
accept_rate = (df['Connections Accepted'].sum() / df['Connections Sent'].sum()) * 100
reply_rate = (df['Message Replies'].sum() / df['Messages Sent'].sum()) * 100 if df['Messages Sent'].sum() > 0 else 0
rates = {'Connection Accept Rate': accept_rate, 'Message Reply Rate': reply_rate}
colors = ['#4CAF50', '#E91E63']
bars = ax4.bar(rates.keys(), rates.values(), color=colors)
ax4.set_title('Conversion Rates')
ax4.set_ylabel('Percentage (%)')
ax4.set_ylim(0, 100)
for bar, val in zip(bars, rates.values()):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f'{val:.1f}%', ha='center', fontweight='bold')

plt.tight_layout()
plt.savefig('.tmp/heyreach_charts.png', dpi=150, bbox_inches='tight')
print("Charts saved to .tmp/heyreach_charts.png")

# Print summary stats
print(f"\n=== SUMMARY ===")
print(f"Total Connections Sent: {df['Connections Sent'].sum()}")
print(f"Total Connections Accepted: {df['Connections Accepted'].sum()}")
print(f"Connection Accept Rate: {accept_rate:.1f}%")
print(f"Total Messages Sent: {df['Messages Sent'].sum()}")
print(f"Total Message Replies: {df['Message Replies'].sum()}")
print(f"Message Reply Rate: {reply_rate:.1f}%")
