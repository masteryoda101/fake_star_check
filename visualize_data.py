import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime
import os
from collections import Counter


def visualize_star_pattern(repo, stargazers):
    star_times = [datetime.datetime.fromisoformat(star[1].rstrip('Z')) for star in stargazers]
    star_dates = [star_time.date() for star_time in star_times]

    stars_per_day = Counter(star_dates)
    dates, counts = zip(*sorted(stars_per_day.items()))

    with plt.style.context('fivethirtyeight'):
        plt.figure(figsize=(12, 6))
        plt.plot(dates, counts, marker='o', linestyle='-', color='#0073B7', linewidth=2, markersize=4)

    total_stars = sum(counts)
    cum_sum_stars = [sum(counts[:i + 1]) for i in range(len(counts))]

    threshold = 0.7 * total_stars
    start_idx, end_idx, min_length = 0, 0, float('inf')

    for i in range(len(cum_sum_stars)):
        for j in range(i, len(cum_sum_stars)):
            if cum_sum_stars[j] - cum_sum_stars[i] >= threshold:
                if (j - i) < min_length:
                    min_length = j - i
                    start_idx, end_idx = i, j
                break

    if min_length < float('inf'):
        stars_in_period = cum_sum_stars[end_idx] - cum_sum_stars[start_idx]
        percentage_of_total = (stars_in_period / total_stars) * 100

        plt.axvspan(dates[start_idx], dates[end_idx], color='#FDB202', alpha=0.2)

        annotation_text = f'{percentage_of_total:.2f}% ({stars_in_period} stars) in {min_length} days'
        mid_point = dates[start_idx + (end_idx - start_idx) // 2]
        plt.annotate(annotation_text, xy=(mid_point, max(counts)),
                     xytext=(190, 25), textcoords='offset points', ha='center', va='bottom',
                     arrowprops=dict(facecolor='black', arrowstyle='->'),
                     bbox=dict(boxstyle="round4,pad=0.9", fc="0.9"),
                     fontsize=8, color='black')

    peak_counts = sorted(list(set(counts)), reverse=True)[:2]
    peak_dates = [dates[i] for i, count in enumerate(counts) if count in peak_counts[:2]]

    for date, count in zip(dates, counts):
        if count in peak_counts:
            percentage_of_total = (count / total_stars) * 100
            plt.scatter(date, count, color='crimson', zorder=3, s=50)
            annotation_text = f'{date.strftime("%Y-%m-%d")}: {percentage_of_total:.2f}% ({count} stars)'
            plt.annotate(annotation_text, xy=(date, count), xytext=(5, 15),
                         textcoords='offset points', ha='center', va='center',
                         color='black', fontsize=9,
                         bbox=dict(boxstyle="round,pad=0.3", edgecolor='black', facecolor='white', alpha=0.9))

    plt.gcf().autofmt_xdate()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%y-%m-%d'))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator())
    plt.title(f'Star History for {repo}\nTotal Stars: {total_stars}', fontsize=16, fontweight='bold', loc='left')
    plt.xlabel('Date', fontsize=14)
    plt.ylabel('Stars Count', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.7)

    plt.tick_params(axis='both', which='major', labelsize=12)
    plt.tight_layout()

    if not os.path.exists('graphs'):
        os.makedirs('graphs')
    graph_file_path = os.path.join('graphs', f'{repo}_star_history.png')
    plt.savefig(graph_file_path, bbox_inches='tight')
    plt.show()
