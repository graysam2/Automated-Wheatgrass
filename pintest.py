

import pigpio
import time

VALVE_1 = 18
VALVE_2 = 27
pi = pigpio.pi()

pi.set_mode(VALVE_1, pigpio.OUTPUT)
pi.set_mode(VALVE_2, pigpio.OUTPUT)

# Turn them on/off
try:
    while(True):
        pi.write(VALVE_1, 1)  # ON
        time.sleep(30)
        pi.write(VALVE_1, 0)  # OFF
        time.sleep(1)

except KeyboardInterrupt:
    print("Exiting.")
    pi.write(VALVE_1, 0)  # OFF
    cb_A.cancel()
    cb_B.cancel()
    pi.stop()
