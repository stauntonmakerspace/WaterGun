// Data structures for sprayer control
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settings {
    targeting_mode: String, // "automatic", "cursor", "joystick"
    firing_mode: String,    // "toggle", "hold"
    target_hold_time: f64,
    device_address: String,
    device_port: u16,       // UDP command port
    video_port: u16,        // WebRTC video port
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalibrationResults {
    height: f64,
    initial_pan: f64,
    initial_tilt: f64,
    initial_roll: f64,
    perspective_matrix: Vec<f64>, // 3x3 perspective transformation matrix
    camera_matrix: Vec<f64>,      // 3x3 camera intrinsic matrix
    dist_coeffs: Vec<f64>,        // Distortion coefficients
}
