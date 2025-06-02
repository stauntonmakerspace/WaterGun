#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetCoords {
    x: f64, // Percentage 0-100
    y: f64, // Percentage 0-100
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PanTiltCommand {
    pan: f64,  // Degrees 0-180
    tilt: f64, // Degrees 0-180
    trigger: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrackingData {
    tracks: Vec<Track>,
    current_target_index: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Track {
    id: u32,
    x1: f64,
    y1: f64,
    x2: f64,
    y2: f64,
    confidence: f64,
}
