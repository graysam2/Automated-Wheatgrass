import time
import pigpio
import motoron
import rotary_encoder
import numpy as np
from scipy.signal import detrend

# Initialize Motoron
mc = motoron.MotoronI2C(bus=3)
mc.reinitialize()
mc.clear_reset_flag()
mc.set_error_response(motoron.ERROR_RESPONSE_COAST)
mc.set_command_timeout_milliseconds(500)
mc.set_max_acceleration(1, 32767)
mc.set_max_deceleration(1, 32767)
mc.clear_motor_fault()

# Rotary Encoder Setup
ENCODER_A = 25
ENCODER_B = 24
position = 0

def callback(way):
    global position
    position += way

pi = pigpio.pi()
decoder = rotary_encoder.decoder(pi, ENCODER_A, ENCODER_B, callback)

# Frequency response test parameters
frequencies = np.logspace(-1, 1.3, num=15)  # ~0.1 Hz to 20 Hz
amplitude = 800
duration_per_freq = 4  # cycles
sample_interval = 0.01  # 100 Hz
warmup_cycles = 2

# Output data
gain_phase_data = []

print("Starting frequency response test...")

for freq in frequencies:
    print(f"Testing frequency: {freq:.2f} Hz")
    position = 0
    warmup_time = warmup_cycles / freq
    test_time = duration_per_freq / freq

    # Warm-up phase
    start_time = time.time()
    while time.time() - start_time < warmup_time:
        t = time.time() - start_time
        control_input = int(amplitude * np.sin(2 * np.pi * freq * t))
        mc.set_speed(1, control_input)
        time.sleep(sample_interval)

    # Measurement phase
    local_times = []
    local_positions = []
    local_inputs = []
    start_time = time.time()

    while time.time() - start_time < test_time:
        t = time.time() - start_time
        control_input = int(amplitude * np.sin(2 * np.pi * freq * t))
        mc.set_speed(1, control_input)
        local_times.append(t)
        local_positions.append(position)
        local_inputs.append(control_input)
        time.sleep(sample_interval)

    mc.set_speed(1, 0)
    time.sleep(1)

    # Convert to numpy arrays and detrend
    t_arr = np.array(local_times)
    u_arr = detrend(np.array(local_inputs))
    y_arr = detrend(np.array(local_positions))

    # Fit sine and cosine terms to output
    omega = 2 * np.pi * freq
    sin_component = np.sin(omega * t_arr)
    cos_component = np.cos(omega * t_arr)
    A = np.vstack([sin_component, cos_component]).T
    coeffs, _, _, _ = np.linalg.lstsq(A, y_arr, rcond=None)
    a, b = coeffs

    gain = np.sqrt(a**2 + b**2)
    phase = np.rad2deg(np.arctan2(b, a))

    gain_phase_data.append((freq, gain, phase))

# Save results
with open("frequency_response_gain_phase.csv", "w") as f:
    f.write("frequency_hz,gain,phase_deg\n")
    for freq, gain, phase in gain_phase_data:
        f.write(f"{freq:.4f},{gain:.4f},{phase:.2f}\n")

# Cleanup
decoder.cancel()
pi.stop()
print("Frequency response gain and phase calculation complete. Results saved to frequency_response_gain_phase.csv")
