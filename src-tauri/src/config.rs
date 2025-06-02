// src-tauri/src/config.rs
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settings {
    pub targeting_mode: String,
    pub firing_mode: String,
    pub target_hold_time: f64,
    pub device_address: String,
    pub device_port: u16,
    pub video_port: u16,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            targeting_mode: "cursor".to_string(),
            firing_mode: "toggle".to_string(),
            target_hold_time: 5.0,
            device_address: "127.0.0.1".to_string(),
            device_port: 5632,
            video_port: 8080,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalibrationResults {
    pub initial_pan: f64,
    pub initial_tilt: f64,
    pub perspective_matrix: Vec<f64>,
}

impl Default for CalibrationResults {
    fn default() -> Self {
        Self {
            initial_pan: 90.0,
            initial_tilt: 90.0,
            perspective_matrix: vec![1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0], // Identity matrix
        }
    }
}