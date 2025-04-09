import pigpio
import time

# GPIO pins (BCM numbering)
ENCODER_A = 26
ENCODER_B = 21

def callback_A(gpio, level, tick):
    print(f"Interrupt on A! Level: {level}, Time: {tick}")

def callback_B(gpio, level, tick):
    print(f"Interrupt on B! Level: {level}, Time: {tick}")

# Connect to pigpiod
pi = pigpio.pi()
if not pi.connected:
    print("Failed to connect to pigpiod.")
    exit(1)

# Set up pins
pi.set_mode(ENCODER_A, pigpio.INPUT)
pi.set_pull_up_down(ENCODER_A, pigpio.PUD_UP)
pi.set_mode(ENCODER_B, pigpio.INPUT)
pi.set_pull_up_down(ENCODER_B, pigpio.PUD_UP)

# Register callbacks
cb_A = pi.callback(ENCODER_A, pigpio.EITHER_EDGE, callback_A)
cb_B = pi.callback(ENCODER_B, pigpio.EITHER_EDGE, callback_B)

print("Listening for interrupts on GPIO 5 (A) and GPIO 6 (B)...")
print("Rotate your encoder now. Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("Exiting.")
    cb_A.cancel()
    cb_B.cancel()
    pi.stop()
