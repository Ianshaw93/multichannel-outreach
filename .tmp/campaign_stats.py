import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Set dark theme
plt.style.use('dark_background')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.facecolor'] = '#1a1a2e'
plt.rcParams['axes.facecolor'] = '#16213e'
plt.rcParams['axes.edgecolor'] = '#333'
plt.rcParams['grid.color'] = '#333'

fig = plt.figure(figsize=(16, 12))
fig.patch.set_facecolor('#1a1a2e')

# Data
funnel_stages = ['Connection\nRequests', 'Accepted', 'Messages\nSent', 'Positive\nReplies', 'Pitched']
funnel_values = [609, 216, 125, 13, 1]
funnel_colors = ['#60a5fa', '#38bdf8', '#22d3ee', '#a78bfa', '#f472b6']

# 1. Funnel Chart (top left)
ax1 = fig.add_subplot(2, 2, 1)
bars = ax1.barh(funnel_stages[::-1], funnel_values[::-1], color=funnel_colors[::-1], height=0.6)
ax1.set_xlabel('Count', fontsize=11, color='#888')
ax1.set_title('Campaign Funnel', fontsize=14, fontweight='bold', color='white', pad=15)
ax1.set_xlim(0, 700)

# Add value labels
for bar, val in zip(bars, funnel_values[::-1]):
    ax1.text(val + 15, bar.get_y() + bar.get_height()/2, f'{val}',
             va='center', ha='left', fontsize=12, fontweight='bold', color='white')

# Add conversion rates
conversions = ['', '35.5%', '57.9%', '10.4%', '7.7%']
for i, (bar, conv) in enumerate(zip(bars, conversions[::-1])):
    if conv:
        ax1.text(bar.get_width() - 10, bar.get_y() + bar.get_height()/2, conv,
                va='center', ha='right', fontsize=10, color='#1a1a2e', fontweight='bold')

ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)

# 2. Positive Reply Quality (top right)
ax2 = fig.add_subplot(2, 2, 2)
pos_labels = ['Engaged\nResponse', 'Minimal\n(thumbs)', 'Confused']
pos_values = [9, 3, 1]
pos_colors = ['#4ade80', '#facc15', '#fb923c']

bars2 = ax2.bar(pos_labels, pos_values, color=pos_colors, width=0.5)
ax2.set_ylabel('Count', fontsize=11, color='#888')
ax2.set_title('Positive Reply Quality (13 total)', fontsize=14, fontweight='bold', color='white', pad=15)
ax2.set_ylim(0, 12)

for bar, val in zip(bars2, pos_values):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, str(val),
             ha='center', fontsize=14, fontweight='bold', color='white')

ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

# 3. Conversion Rates Bar Chart (bottom left) - Highlight PRR
ax3 = fig.add_subplot(2, 2, 3)
rate_labels = ['Connection\nRate', 'PRR\n(Positive Reply)', 'Pitched\nRate']
rate_values = [35.5, 10.4, 0.8]
rate_colors = ['#38bdf8', '#a78bfa', '#f472b6']

bars3 = ax3.bar(rate_labels, rate_values, color=rate_colors, width=0.5, edgecolor=['none', '#fff', 'none'], linewidth=[0, 3, 0])
ax3.set_ylabel('Percentage (%)', fontsize=11, color='#888')
ax3.set_title('Key Rates (% of messages sent)', fontsize=14, fontweight='bold', color='white', pad=15)
ax3.set_ylim(0, 45)

rate_details = ['216/609', '13/125', '1/125']
for i, (bar, val, detail) in enumerate(zip(bars3, rate_values, rate_details)):
    label = f'{val}%\n({detail})'
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, label,
             ha='center', fontsize=12 if i != 1 else 14, fontweight='bold', color='white' if i != 1 else '#a78bfa')

ax3.spines['top'].set_visible(False)
ax3.spines['right'].set_visible(False)

# 4. Positive Replies Status (bottom right)
ax4 = fig.add_subplot(2, 2, 4)
status_labels = ['Qualified\nAwaiting F/U', 'Not ICP\n(just starting)', 'Pitched\n(Declined)']
status_values = [10, 2, 1]
status_colors = ['#60a5fa', '#666', '#ef4444']

bars4 = ax4.bar(status_labels, status_values, color=status_colors, width=0.5)
ax4.set_ylabel('Count', fontsize=11, color='#888')
ax4.set_title('Positive Replies Pipeline (13 total)', fontsize=14, fontweight='bold', color='white', pad=15)
ax4.set_ylim(0, 13)

for bar, val in zip(bars4, status_values):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, str(val),
             ha='center', fontsize=14, fontweight='bold', color='white')

ax4.spines['top'].set_visible(False)
ax4.spines['right'].set_visible(False)

plt.tight_layout(pad=3)
plt.savefig('.tmp/campaign_stats.png', dpi=150, facecolor='#1a1a2e', edgecolor='none', bbox_inches='tight')
plt.close()

print("Charts saved to .tmp/campaign_stats.png")
