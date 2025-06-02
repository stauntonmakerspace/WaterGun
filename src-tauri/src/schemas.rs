// src-tauri/src/schemas.rs
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetCoords {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrackingData {
    pub tracks: Vec<Track>,
    pub current_target_index: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Track {
    pub id: u32,
    pub x1: f64,
    pub y1: f64,
    pub x2: f64,
    pub y2: f64,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PanTiltCommand {
    pub pan: f64,
    pub tilt: f64,
    pub trigger: bool,
}