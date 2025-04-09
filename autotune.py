import time
import pigpio
import motoron
import rotary_encoder

ENCODER_A = 25
ENCODER_B = 24
ENCODER_GAIN = 0.01

position = 0
def callback(way):
    global position
    position += way

# Init pigpio and encoder
pi = pigpio.pi()
pi.set_mode(ENCODER_A, pigpio.INPUT)
pi.set_mode(ENCODER_B, pigpio.INPUT)
pi.set_pull_up_down(ENCODER_A, pigpio.PUD_UP)
pi.set_pull_up_down(ENCODER_B, pigpio.PUD_UP)
decoder = rotary_encoder.decoder(pi, ENCODER_A, ENCODER_B, callback)

# Init motor
mc = motoron.MotoronI2C(bus=3)
mc.reinitialize()
mc.clear_reset_flag()
mc.set_error_response(motoron.ERROR_RESPONSE_COAST)
mc.set_command_timeout_milliseconds(500)
mc.set_max_acceleration(1, 150)
mc.set_max_deceleration(1, 300)
mc.clear_motor_fault()

# PID test target
target_position = 50  # mm

# Tuning parameters
Ku = 0.0
Pu = None
P = 200.0  # start from low P
step = 100.0
max_P = 1000
oscillation_threshold = 1.0  # mm
sample_interval = 0.01

print("Starting autotune...")

try:
    while P <= max_P:
        print(f"Testing P={P:.2f}")
        position = 0
        history = []
        start_time = time.time()
        last_error_sign = None
        zero_crossings = []
        period_detected = False

        while time.time() - start_time < 15:  # 10 second test
            current_position = position * ENCODER_GAIN
            error = target_position - current_position
            control = -P * error
            control = max(min(int(control), 800), -800)
            mc.set_speed(1, control)
            print(f"current position {current_position}, target: {target_position}, speed: {control}")
            history.append((time.time() - start_time, current_position))

            sign = error > 0
            if last_error_sign is not None and sign != last_error_sign:
                zero_crossings.append(time.time())
                if len(zero_crossings) >= 6:
                    period = (zero_crossings[-1] - zero_crossings[-5]) / 5
                    Pu = period
                    Ku = P
                    period_detected = True
                    break
            last_error_sign = sign

            time.sleep(sample_interval)

        mc.set_speed(1, 0)
        time.sleep(2)

        if period_detected:
            print(f"Oscillation detected. Ku={Ku:.2f}, Pu={Pu:.2f}")
            break

        P += step

    if Ku and Pu:
        Kp = 0.6 * Ku
        Ki = 2 * Kp / Pu
        Kd = Kp * Pu / 8
        print("Suggested PID gains:")
        print(f"Kp = {Kp:.3f}, Ki = {Ki:.3f}, Kd = {Kd:.3f}")
    else:
        print("Failed to find sustained oscillation within P range")

except KeyboardInterrupt:
    mc.set_speed(1, 0)
    decoder.cancel()
    pi.stop()
    print("Autotune aborted.")
