import numpy as np
from scipy.optimize import minimize

from watergun.common import calculate_pan_tilt
'http://192.168.1.161:8000/stream.mjpg'

def error_function(params, calibration_points, measured_angles):
    """
    Calculate the total error between measured angles and calculated angles for all calibration points.
    
    :param params: list of [height, initial_pan, initial_tilt, initial_roll]
    :param calibration_points: list of (x, y, z) coordinates for calibration points
    :param measured_angles: list of (pan, tilt) angles measured for each calibration point
    :return: total squared error
    """
    total_error = 0
    for (x, y, z), (measured_pan, measured_tilt) in zip(calibration_points, measured_angles):
        calculated_pan, calculated_tilt = calculate_pan_tilt(x, y, z, params)
        total_error += (calculated_pan - measured_pan)**2 + (calculated_tilt - measured_tilt)**2
    return total_error

def calibrate_system(calibration_points, measured_angles, initial_guess):
    """
    Calibrate the system by finding the best parameters that minimize the error.
    
    :param calibration_points: list of (x, y, z) coordinates for calibration points
    :param measured_angles: list of (pan, tilt) angles measured for each calibration point
    :param initial_guess: initial guess for [height, initial_pan, initial_tilt, initial_roll]
    :return: optimized parameters [height, initial_pan, initial_tilt, initial_roll]
    """
    result = minimize(error_function, initial_guess, args=(calibration_points, measured_angles),
                      method='Nelder-Mead')
    return result.x

# Example usage
if __name__ == "__main__":
    calibration_points = [
        (1, 1, 0),    # 1 meter right, 1 meter forward
        (0, 2, 0),    # 2 meters directly forward
        (-1, 1, 0),   # 1 meter left, 1 meter forward
        (3, 0, 0),    # 3 meters directly right
    ]

    # These would be the manually measured angles for each calibration point
    measured_angles = [
        (45, -30),    # Example pan and tilt angles for point (1, 1, 0)
        (0, -35),     # Example pan and tilt angles for point (0, 2, 0)
        (-45, -30),   # Example pan and tilt angles for point (-1, 1, 0)
        (90, -25),    # Example pan and tilt angles for point (3, 0, 0)
    ]

    # Initial guess for [height, initial_pan, initial_tilt, initial_roll]
    initial_guess = [1.5, 0, 0, 0]

    # Perform calibration
    calibrated_params = calibrate_system(calibration_points, measured_angles, initial_guess)

    print("Calibrated parameters:")
    print(f"Height: {calibrated_params[0]:.2f} meters")
    print(f"Initial Pan: {calibrated_params[1]:.2f} degrees")
    print(f"Initial Tilt: {calibrated_params[2]:.2f} degrees")
    print(f"Initial Roll: {calibrated_params[3]:.2f} degrees")

    # Test the calibrated system
    test_point = (2, 2, 0)
    pan, tilt = calculate_pan_tilt(*test_point, calibrated_params)
    print(f"\nFor test point {test_point}:")
    print(f"Calculated Pan: {pan:.2f} degrees")
    print(f"Calculated Tilt: {tilt:.2f} degrees")