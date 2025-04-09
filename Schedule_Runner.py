import time
import csv
import pigpio
import subprocess
import psutil
import os
from datetime import datetime

# Setup pigpio and devices
pi = pigpio.pi()

# Valve (relay) pins
VALVE_1 = 17
VALVE_2 = 27
FAN = 18
pi.set_mode(FAN, pigpio.OUTPUT)
pi.set_mode(VALVE_1, pigpio.OUTPUT)
pi.set_mode(VALVE_2, pigpio.OUTPUT)
pi.write(FAN, 1)
# Check if motor control process is running
def is_process_running(name):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if name in ' '.join(proc.info['cmdline']):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def start_motor_control_if_not_running():
    if not is_process_running("motor1_control.py"):
        print("Starting Motor1 Controller")
        subprocess.Popen(["python3", "motor1_control.py"])
    if not is_process_running("motor2_control.py"):
        print("Starting Motor2 Controller")
        subprocess.Popen(["python3", "motor2_control.py"])

# Load all tasks from schedule
def load_schedule(path):
    tasks = []
    if not os.path.exists(path):
        return tasks

    valid_rows = []
    updated = False

    with open(path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                task_time = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                value = float(row["value"])
                tasks.append({
                    "time": task_time,
                    "device": row["device"],
                    "action": row["action"],
                    "value": value
                })
                valid_rows.append(row)
            except ValueError:
                print(f"[WARNING] Skipping invalid task: {row}")
                updated = True

    # If invalid tasks were found, overwrite with cleaned list
    if updated:
        with open(path, "w", newline='') as csvfile:
            fieldnames = ["timestamp", "device", "action", "value"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(valid_rows)

    return tasks


def save_schedule(path, tasks):
    with open(path, "w", newline="") as csvfile:
        fieldnames = ["timestamp", "device", "action", "value"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for task in tasks:
            writer.writerow({
                "timestamp": task["time"].strftime("%Y-%m-%d %H:%M:%S"),
                "device": task["device"],
                "action": task["action"],
                "value": task["value"]
            })

import psutil
import signal

def pause_process_by_name(name):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if name in ' '.join(proc.info['cmdline']):
                proc.suspend()
        except psutil.Error:
            pass

def resume_process_by_name(name):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if name in ' '.join(proc.info['cmdline']):
                proc.resume()
        except psutil.Error:
            pass


# Run continuously and execute tasks
try:
    start_motor_control_if_not_running()
    schedule_path = "automation_schedule.csv"

    while True:
        now = datetime.now()
        tasks = load_schedule(schedule_path)
        tasks.sort(key=lambda t: t["time"])

        if tasks and tasks[0]["time"] <= now:
            task = tasks.pop(0)
            print(f"Running: {task}")
            if task["device"] == "motor1":
                resume_process_by_name("motor1_control.py")
                pause_process_by_name("motor2_control.py")
                print(f"{now} Moving Motor 1")
                with open("motor1_target.txt", "w") as f:
                    f.write(str(task["value"]))
            elif task["device"] == "motor2":
                resume_process_by_name("motor2_control.py")
                pause_process_by_name("motor1_control.py")
                print(f"{now} Moving Motor 2")
                with open("motor2_target.txt", "w") as f:
                    f.write(str(task["value"]))
            elif task["device"] == "valve1":
                print(f"{now} Turning Valve 1 on")
                pi.write(FAN, 0)
                pi.write(VALVE_1, 1)
                time.sleep(task["value"])
                print(f"{now} Turning Valve 1 off")
                pi.write(VALVE_1, 0)
                pi.write(FAN, 1)
            elif task["device"] == "valve2":
                print(f"{now} Turning Valve 2 on")
                pi.write(FAN, 0)
                pi.write(VALVE_2, 1)
                time.sleep(task["value"])
                print(f"{now} Turning Valve 2 off")
                pi.write(VALVE_2, 0)
                pi.write(FAN, 1)

            save_schedule(schedule_path, tasks)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("Stopping")
    pi.write(VALVE_1, 0)
    pi.write(VALVE_2, 0)
    pi.stop()
