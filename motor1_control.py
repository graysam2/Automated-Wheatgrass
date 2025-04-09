import time
import pigpio
import motoron
import rotary_encoder
import os
import sys

class FilteredPID:
    def __init__(self, Kp, Ki, Kd, d_filter_alpha=0.3):
        self.Kp = -Kp
        self.Ki = -Ki
        self.Kd = -Kd
        self.setpoint = 0
        self.integral = 0
        self.integral_limit = 10
        self.output_limit = 800
        self.last_error = 0
        self.last_derivative = 0
        self.last_time = None
        self.d_filter_alpha = d_filter_alpha

    def compute(self, measurement):
        current_time = time.time()
        dt = current_time - self.last_time if self.last_time is not None else 0.01
        self.last_time = current_time

        error = self.setpoint - measurement

        # Derivative
        raw_derivative = (error - self.last_error) / dt if dt > 0 else 0
        self.last_derivative = (
            self.d_filter_alpha * raw_derivative + (1 - self.d_filter_alpha) * self.last_derivative
        )

        # Proportional and derivative terms
        P_term = self.Kp * error
        D_term = self.Kd * self.last_derivative

        # Preliminary output without integral
        output = P_term + D_term
        potential_integral = error * dt
        

        # Only integrate if output is not saturated
        if abs(output) < self.output_limit or ((self.integral + error * dt) * error) < 0:
            self.integral += error * dt
            # Clamp integral
            self.integral = max(min(self.integral, self.integral_limit), -self.integral_limit)

        I_term = self.Ki * self.integral
        output += I_term

        self.last_error = error

        #print(f"P: {P_term:.2f}, I: {I_term:.2f}, D: {D_term:.2f}, Output: {output:.2f}")
        return max(min(output, self.output_limit), -self.output_limit)

def safe_get_status_flags(mc, retries=3, delay=0.05):
    for i in range(retries):
        try:
            return mc.get_status_flags()
        except RuntimeError as e:
            print(f"[WARN] CRC error (attempt {i+1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Failed to get status flags after retries.")

# Initialize Motoron
reference_mv = 3300
vin_type = motoron.VinSenseType.MOTORON_256
min_vin_voltage_mv = 4500

mc = motoron.MotoronI2C(bus=3)
mc.reinitialize()
mc.clear_reset_flag()
mc.set_error_response(motoron.ERROR_RESPONSE_COAST)
mc.set_command_timeout_milliseconds(500)
mc.set_max_acceleration(1, 150)
mc.set_max_deceleration(1, 300)
mc.clear_motor_fault()

error_mask = (
  (1 << motoron.STATUS_FLAG_PROTOCOL_ERROR) |
  (1 << motoron.STATUS_FLAG_CRC_ERROR) |
  (1 << motoron.STATUS_FLAG_COMMAND_TIMEOUT_LATCHED) |
  (1 << motoron.STATUS_FLAG_MOTOR_FAULT_LATCHED) |
  (1 << motoron.STATUS_FLAG_NO_POWER_LATCHED) |
  (1 << motoron.STATUS_FLAG_RESET) |
  (1 << motoron.STATUS_FLAG_COMMAND_TIMEOUT))

def safe_get_vin_voltage_mv(mc, reference_mv, vin_type, retries=3, delay=0.05):
    for i in range(retries):
        try:
            return mc.get_vin_voltage_mv(reference_mv, vin_type)
        except RuntimeError as e:
            print(f"[WARN] CRC error on VIN read (attempt {i+1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Failed to read VIN voltage after retries.")


def check_for_problems():
    status = safe_get_status_flags(mc)
    if (status & error_mask):
        mc.reset()
        print("Controller error: 0x%x" % status, file=sys.stderr)
        sys.exit(1)

    voltage_mv = mc.get_vin_voltage_mv(reference_mv, vin_type)
    if voltage_mv < min_vin_voltage_mv:
        mc.reset()
        print("VIN voltage too low:", voltage_mv, file=sys.stderr)
        sys.exit(1)

# Rotary Encoder Setup
ENCODER_A = 24
ENCODER_B = 25
position = 0
ENCODER_GAIN = 0.01127088464

def callback(way):
    global position
    position += way

pi = pigpio.pi()
decoder = rotary_encoder.decoder(pi, ENCODER_A, ENCODER_B, callback)

# PID Controller Setup
Kp, Ki, Kd, alpha = 1000, 400, 100, 0.2
pid = FilteredPID(Kp, Ki, Kd, alpha)
pid.setpoint = 0

last_setpoint = 0
setpoint_active = False
settle_counter = 0
settle_threshold = 20
last_position = None

try:
    while True:
        try:
            with open("motor1_target.txt", "r") as f:
                file_value = float(f.read().strip())
        except Exception:
            file_value = 0

        current_position = position * ENCODER_GAIN

        if file_value != 0 and not setpoint_active:
            target_position = file_value
            pid.setpoint = target_position
            setpoint_active = True

        if setpoint_active:
            loop_start = time.time()
            #check_for_problems()
            current_position = position * ENCODER_GAIN
            error = target_position - current_position

            if abs(error) < 30:
                max_speed = int(800 * (abs(error) / 30))
                max_speed = max(800, max_speed)
                pid.output_limit = max_speed
            else:
                pid.output_limit = 800

            motor_speed = int(pid.compute(current_position))

            if abs(motor_speed) < 15:
                motor_speed = 0

            try:
                mc.set_speed(1, motor_speed)
            except Exception as e:
                print("I2C Error:", e)
                mc.reset()
                break

            print(f"Position: {current_position}mm, Target: {target_position}mm, Speed: {motor_speed}")

            if abs(error) < 0.15:
                settle_counter += 1
                if settle_counter >= settle_threshold:
                    mc.set_speed(1, 0)
                    setpoint_active = False
                    pid.setpoint = 0
                    with open("motor1_target.txt", "w") as f:
                        f.write("0")
                    settle_counter = 0
                    position -= target_position/ENCODER_GAIN
            else:
                settle_counter = 0
                last_position = None
        else:
            mc.set_speed(1, 0)

        time.sleep(0.05)

except KeyboardInterrupt:
    mc.set_speed(1, 0)
    decoder.cancel()
    pi.stop()