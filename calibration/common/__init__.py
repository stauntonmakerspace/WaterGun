import numpy as np
from scipy.optimize import minimize

def pixel_to_meter(pixel_x, pixel_y, perspective_transform):
    px_homogeneous = np.array([[pixel_x, pixel_y, 1]], dtype=np.float32).T
    meter_homogeneous = perspective_transform @ px_homogeneous
    meter_x, meter_y, _ = meter_homogeneous.ravel() / meter_homogeneous[2]
    return meter_x, meter_y

def rotation_matrix(roll, pitch, yaw):
    """
    Create a rotation matrix from roll, pitch, and yaw angles.
    
    :param roll: rotation around x-axis (in radians)
    :param pitch: rotation around y-axis (in radians)
    :param yaw: rotation around z-axis (in radians)
    :return: 3x3 rotation matrix
    """
    Rx = np.array([[1, 0, 0],
                   [0, np.cos(roll), -np.sin(roll)],
                   [0, np.sin(roll), np.cos(roll)]])
    
    Ry = np.array([[np.cos(pitch), 0, np.sin(pitch)],
                   [0, 1, 0],
                   [-np.sin(pitch), 0, np.cos(pitch)]])
    
    Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0],
                   [np.sin(yaw), np.cos(yaw), 0],
                   [0, 0, 1]])
    
    return np.dot(Rz, np.dot(Ry, Rx))

def calculate_pan_tilt(x, y, z, params):
    """
    Calculate pan and tilt angles for a given target point, accounting for calibrated parameters.
    
    :param x: x-coordinate of the target point (in meters)
    :param y: y-coordinate of the target point (in meters)
    :param z: z-coordinate of the target point (in meters, usually 0 for floor)
    :param params: list of [height, initial_pan, initial_tilt, initial_roll]
    :return: tuple of (pan_angle, tilt_angle) in degrees
    """
    h, init_pan, init_tilt, init_roll = params
    
    # Convert initial rotations to radians
    init_pan_rad = np.radians(init_pan)
    init_tilt_rad = np.radians(init_tilt)
    init_roll_rad = np.radians(init_roll)
    
    # Create rotation matrix
    R = rotation_matrix(init_roll_rad, init_tilt_rad, init_pan_rad)
    
    # Apply rotation to target point
    target_vector = np.array([x, y, z - h])
    rotated_vector = np.dot(R.T, target_vector)
    
    x_rot, y_rot, z_rot = rotated_vector
    
    # Calculate pan and tilt angles
    pan_angle = np.arctan2(y_rot, x_rot)
    tilt_angle = np.arctan2(np.sqrt(x_rot**2 + y_rot**2), -z_rot) - np.pi/2
    
    return np.degrees(pan_angle), np.degrees(tilt_angle)