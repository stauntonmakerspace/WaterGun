from scipy.optimize import minimize
import json 
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
if __name__ == "__main__":
    calibration_points = [
        (1, 1, 0),
        (0, 2, 0),
        (-1, 1, 0),
        (3, 0, 0),
    ]
    measured_angles = [
        (45, -30),
        (0, -35),
        (-45, -30),
        (90, -25),
    ]
    initial_guess = [1.5, 0, 0, 0]

    calibrated_params = calibrate_system(calibration_points, measured_angles, initial_guess)
    
    # Save calibration results
    calibration_results = {
        "height": calibrated_params[0],
        "initial_pan": calibrated_params[1],
        "initial_tilt": calibrated_params[2],
        "initial_roll": calibrated_params[3]
    }
    
    with open("calibration_results.json", "w") as f:
        json.dump(calibration_results, f)
    
    print("Calibration results saved to calibration_results.json")
