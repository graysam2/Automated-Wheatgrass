#!/bin/bash

echo "Automation script starting" >> /home/pi/automation_debug.log
date >> /home/pi/automation_debug.log

# Ensure pigpiod is running
sudo /usr/bin/pigpiod -s 5
sleep 3

# Activate environment and launch scripts
source /home/pi/motoron_env/bin/activate
echo "Starting motor and schedule scripts..." >> /home/pi/automation_debug.log
/home/pi/motoron_env/bin/python3 /home/pi/Schedule_Runner.py >> /home/pi/schedule.log 2>&1 &
/home/pi/motoron_env/bin/python3 /home/pi/motor1_control.py >> /home/pi/motor1.log 2>&1 &
/home/pi/motoron_env/bin/python3 /home/pi/motor2_control.py >> /home/pi/motor2.log 2>&1 &

# Keep script alive so systemd doesn't stop it
tail -f /dev/null
