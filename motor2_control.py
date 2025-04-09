import time
import pigpio
import motoron
import rotary_encoder
import os
import sys

class FilteredPID:
    def __init__(self, Kp, Ki, Kd, d_filter_alpha=0.3, static_feedforward=0):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = 0
        self.integral = 0
        self.integral_limit = 20
        self.output_max = 600
        self.output_min = -600
        self.last_error = 0
        self.last_derivative = 0
        self.last_time = None
        self.d_filter_alpha = d_filter_alpha
        self.static_feedforward = static_feedforward

    def compute(self, measurement):
        current_time = time.time()
        dt = current_time - self.last_time if self.last_time is not None else 0.01
        self.last_time = current_time

        error = self.setpoint - measurement

        raw_derivative = (error - self.last_error) / dt if dt > 0 else 0
        self.last_derivative = (
            self.d_filter_alpha * raw_derivative + (1 - self.d_filter_alpha) * self.last_derivative
        )

        P_term = self.Kp * error
        D_term = self.Kd * self.last_derivative
        FF_term = self.static_feedforward * (1 if error > 0 else -1.2 if error < 0 else 0)

        pre_output = P_term + D_term + FF_term

        if ((self.integral + error * dt) * error < 0) or (self.output_min < pre_output < self.output_max):
            self.integral += error * dt
            self.integral = max(min(self.integral, self.integral_limit), -self.integral_limit)

        I_term = self.Ki * self.integral
        output = pre_output + I_term
        

        output += I_term

        self.last_error = error

        print(f"P: {P_term:.2f}, I: {I_term:.2f}, D: {D_term:.2f}, FF: {FF_term:.2f}, Output: {output:.2f}, {self.output_max}")
        return max(min(output, self.output_max), self.output_min)

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
mc.set_max_acceleration(2, 20)
mc.set_max_deceleration(2, 500)
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
ENCODER_A = 26
ENCODER_B = 21
position = 0
ENCODER_GAIN = 0.45

def callback(way):
    global position
    position += way

pi = pigpio.pi()
decoder = rotary_encoder.decoder(pi, ENCODER_A, ENCODER_B, callback)

# PID Controller Setup
Kp, Ki, Kd, alpha, static_feedforward = 6, 4, 1, 0.2, 118
pid = FilteredPID(Kp, Ki, Kd, alpha, static_feedforward)
pid.setpoint = 0

last_setpoint = 0
setpoint_active = False
settle_counter = 0
settle_threshold = 20
last_position = None

try:
    while True:
        try:
            with open("motor2_target.txt", "r") as f:
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

            if abs(error) < 10:
                max_speed = int(600 * (abs(error) / 10))
                max_speed = max(600, max_speed)
                pid.output_max = max_speed
            else:
                pid.output_max = 600

            motor_speed = int(pid.compute(current_position))

            if abs(motor_speed) < 5:
                motor_speed = 0

            try:
                mc.set_speed(2, motor_speed)
            except Exception as e:
                print("I2C Error:", e)
                mc.reset()
                break

            print(f"Position: {current_position}deg, Target: {target_position}deg, Speed: {motor_speed}")

            if error < 1:
                settle_counter += 1
                if settle_counter >= settle_threshold:
                    mc.set_speed(2, 0)
                    setpoint_active = False
                    pid.setpoint = 0
                    with open("motor2_target.txt", "w") as f:
                        f.write("0")
                    settle_counter = 0
                    position -= target_position/ENCODER_GAIN
            else:
                settle_counter = 0
                last_position = None
        else:
            mc.set_speed(2, 0)

        time.sleep(0.05)

except KeyboardInterrupt:
    mc.set_speed(2, 0)
    decoder.cancel()
    pi.stop()