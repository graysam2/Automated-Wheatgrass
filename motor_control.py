import time
import pigpio
import motoron
import sys
import select
from simple_pid import PID
import rotary_encoder

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




mc = motoron.MotoronI2C(bus=3)

# Parameters for the VIN voltage measurement.
reference_mv = 3300
vin_type = motoron.VinSenseType.MOTORON_256
min_vin_voltage_mv = 4500

error_mask = (
  (1 << motoron.STATUS_FLAG_PROTOCOL_ERROR) |
  (1 << motoron.STATUS_FLAG_CRC_ERROR) |
  (1 << motoron.STATUS_FLAG_COMMAND_TIMEOUT_LATCHED) |
  (1 << motoron.STATUS_FLAG_MOTOR_FAULT_LATCHED) |
  (1 << motoron.STATUS_FLAG_NO_POWER_LATCHED) |
  (1 << motoron.STATUS_FLAG_RESET) |
  (1 << motoron.STATUS_FLAG_COMMAND_TIMEOUT))

mc.reinitialize()
mc.clear_reset_flag()
mc.set_error_response(motoron.ERROR_RESPONSE_COAST)
mc.set_error_mask(error_mask)
mc.set_command_timeout_milliseconds(500)
mc.set_max_acceleration(1, 100)
mc.set_max_deceleration(1, 300)

start_time = time.time()
while mc.get_motor_driving_flag():
    if time.time() - start_time > 2:
        break
mc.clear_motor_fault()

def check_for_problems():
    status = mc.get_status_flags()
    if (status & error_mask):
        mc.reset()
        #print("Controller error: 0x%x" % status, file=sys.stderr)
        sys.exit(1)

    voltage_mv = mc.get_vin_voltage_mv(reference_mv, vin_type)
    if voltage_mv < min_vin_voltage_mv:
        mc.reset()
        #print("VIN voltage too low:", voltage_mv, file=sys.stderr)
        sys.exit(1)

# Rotary Encoder Setup
ENCODER_A = 24
ENCODER_B = 25
position = 0
ENCODER_GAIN = 0.01127088464 # NOT TUNED YET.


def callback(way):
    global position
    position += way

pi = pigpio.pi()
pi.set_mode(ENCODER_A, pigpio.INPUT)
pi.set_mode(ENCODER_B, pigpio.INPUT)
pi.set_pull_up_down(ENCODER_A, pigpio.PUD_UP)
pi.set_pull_up_down(ENCODER_B, pigpio.PUD_UP)
pi.set_glitch_filter(ENCODER_A, 100)  # 100 μs
pi.set_glitch_filter(ENCODER_B, 100)
decoder = rotary_encoder.decoder(pi, ENCODER_A, ENCODER_B, callback)


# PID Controller Setup
target_position = 0
Kp, Ki, Kd, alpha = 1000, 300, 100, 0.2
pid = FilteredPID(Kp, Ki, Kd, alpha)
pid.setpoint = target_position
pid.integral_limit = 100  # Add this after defining PID
pid.output_limit = 800

def prompt_new_target_with_keepalive():
    global target_position, pid

    print("Target reached. Enter new target position: ", end="", flush=True)
    input_str = ""
    while True:
        try:
            mc.set_speed(1, 0)
        except Exception as e:
            #print("I2C Error during keep-alive:", e)
            mc.reset()
            sys.exit(1)

        if sys.stdin in select.select([sys.stdin], [], [], 0.09)[0]:
            input_str = sys.stdin.readline().strip()
            break

    try:
        new_target = int(input_str)
        #print(f"Target was {target_position}, final position: {position}")
        target_position = new_target
        pid.setpoint = new_target
    except ValueError:
        print("Invalid input. Keeping previous target.")

    mc.clear_motor_fault()

try:
    settle_counter = 0
    settle_threshold = 20
    last_position = None

    while True:
        loop_start = time.time()
        check_for_problems()
        current_position = position * ENCODER_GAIN
        error = abs(target_position - current_position)
        #print(f"Error: {error}")

        if error < 10:
            pass
            #max_speed = int(800 * error / 10)
            #max_speed = max(600, max_speed)
            #pid.output_limit = max_speed
        else:
            pid.output_limit = 800

        motor_speed = int(pid.compute(current_position))

        if abs(motor_speed) < 15:
            motor_speed = 0

        try:
            mc.set_speed(1, motor_speed)
        except Exception as e:
            #print("I2C Error:", e)
            mc.reset()
            break

        print(f"Position: {current_position}mm, Target: {target_position}mm, Speed: {motor_speed}")

        if error < 0.1:
            if error < 0.1:
                settle_counter += 1
            else:
                settle_counter = 0
                last_position = current_position

            if settle_counter >= settle_threshold:
                mc.set_speed(1, 0)
                prompt_new_target_with_keepalive()
                settle_counter = 0
                last_position = None
        else:
            settle_counter = 0
            last_position = None

        loop_duration = time.time() - loop_start
        time.sleep(max(0,0.005 - loop_duration))
        loop_duration = time.time() - loop_start
        ##print(f"Loop took {loop_duration*1000:.2f} ms")

except KeyboardInterrupt:
    #print("Stopping motor")
    mc.set_speed(1, 0)
    decoder.cancel()
    pi.stop()