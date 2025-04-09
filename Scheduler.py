import csv
from datetime import datetime, timedelta
import os
import sys

FILENAME = "automation_schedule.csv"

# Ensure file has header if missing or empty
if not os.path.exists(FILENAME) or os.stat(FILENAME).st_size == 0:
    with open(FILENAME, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "device", "action", "value"])

# Read existing schedule into a set and list for duplicate detection and merging
existing_tasks = set()
schedule_rows = []
with open(FILENAME, newline="") as f:
    reader = csv.reader(f)
    next(reader, None)  # Skip header if present
    for row in reader:
        if row:
            task = (row[0], row[1], row[2], row[3])
            existing_tasks.add(task)
            schedule_rows.append(task)

# Helper to queue a row if it's not a duplicate
def add_schedule_entry(timestamp, device, action, value):
    task = (timestamp.strftime("%Y-%m-%d %H:%M:%S"), device, action, str(value))
    if task not in existing_tasks:
        schedule_rows.append(task)
        existing_tasks.add(task)

print("Grass Growing Batch Scheduler")

if len(sys.argv) != 4:
    print("Usage: python3 Scheduler.py <start|end> <month> <day>")
    sys.exit(1)

specifier = sys.argv[1].strip().lower()
month = int(sys.argv[2])
day = int(sys.argv[3])

if specifier not in ["start", "end"]:
    print("Invalid specifier. Must be 'start' or 'end'.")
    exit(1)

base_date = datetime(datetime.now().year, month, day, 0, 0)

if specifier == "end":
    base_date = base_date - timedelta(days=9)

# Warn if base date is in the past
if base_date < datetime.now():
    confirm = input("This schedule starts in the past. Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Aborting schedule creation.")
        exit(0)

# Day 1
day1 = base_date
add_schedule_entry(day1.replace(hour=8, minute=45), "motor2", "move", 90)
add_schedule_entry(day1.replace(hour=8, minute=50), "motor1", "move", 140)
add_schedule_entry(day1.replace(hour=9, minute=0), "valve2", "on", 60)

# Valve2 every hour for 48 hours
for h in range(1, 48):
    ts = day1 + timedelta(hours=9 + h)
    add_schedule_entry(ts, "valve2", "on", 60)

# Motor1 moves 140 every 24 hours at 8:50 AM for 10 days
for d in range(1, 10):
    ts = day1 + timedelta(days=d)
    add_schedule_entry(ts.replace(hour=8, minute=50), "motor1", "move", 140)

# Day 3 onward: Valve1 on every 3 hours for 7 days (starting from day 3), ending at 9am on day 10
day3 = day1 + timedelta(days=2)
valve1_end_time = day1 + timedelta(days=9, hours=9)
current = day3.replace(hour=0, minute=0)
while current < valve1_end_time:
    add_schedule_entry(current, "valve1", "on", 60)
    current += timedelta(hours=3)

# Add a batch finished flag at the end of the last day
completion_time = day1 + timedelta(days=9, hours=10)
add_schedule_entry(completion_time, "system", "batch_complete", 1)

# Sort all tasks and write full CSV
schedule_rows.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S"))
with open(FILENAME, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "device", "action", "value"])
    for task in schedule_rows:
        writer.writerow(task)

print("Schedule updated and saved to automation_schedule.csv")
