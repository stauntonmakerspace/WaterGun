// Prevent console window from appearing on Windows in release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{State, Manager};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use std::net::UdpSocket;
use std::time::{Duration, Instant};

mod config;
mod schemas;

use schemas::*;
use config::{Settings, CalibrationResults};

// Application state
pub struct AppState {
    settings: Arc<Mutex<Settings>>,
    current_target: Arc<Mutex<TargetCoords>>,
    is_firing: Arc<Mutex<bool>>,
    udp_socket: Arc<Mutex<Option<UdpSocket>>>,
    tracking_data: Arc<Mutex<TrackingData>>,
    calibration_results: Arc<Mutex<Option<CalibrationResults>>>,
    frame_width: Arc<Mutex<u32>>,
    frame_height: Arc<Mutex<u32>>,
    last_command_time: Arc<Mutex<Instant>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            settings: Arc::new(Mutex::new(Settings::default())),
            current_target: Arc::new(Mutex::new(TargetCoords { x: 50.0, y: 50.0 })),
            is_firing: Arc::new(Mutex::new(false)),
            udp_socket: Arc::new(Mutex::new(None)),
            tracking_data: Arc::new(Mutex::new(TrackingData {
                tracks: Vec::new(),
                current_target_index: 0,
            })),
            calibration_results: Arc::new(Mutex::new(None)),
            frame_width: Arc::new(Mutex::new(800)),
            frame_height: Arc::new(Mutex::new(600)),
            last_command_time: Arc::new(Mutex::new(Instant::now())),
        }
    }
}

// Tauri commands for sprayer control
#[tauri::command]
async fn connect_to_device(
    address: String,
    port: u16,
    state: State<'_, AppState>,
) -> Result<String, String> {
    println!("🔌 Connecting to device at {}:{}", address, port);
    
    // Update settings
    {
        let mut settings = state.settings.lock().map_err(|e| format!("Failed to lock settings: {}", e))?;
        settings.device_address = address.clone();
        settings.device_port = port;
    }
    
    // Close existing UDP connection
    {
        let mut socket = state.udp_socket.lock().map_err(|e| format!("Failed to lock socket: {}", e))?;
        *socket = None;
    }
    
    // Create new UDP socket for commands
    match UdpSocket::bind("0.0.0.0:0") {
        Ok(socket) => {
            // Set a timeout for the socket
            socket.set_read_timeout(Some(Duration::from_secs(5)))
                .map_err(|e| format!("Failed to set socket timeout: {}", e))?;
            
            match socket.connect(format!("{}:{}", address, port)) {
                Ok(_) => {
                    {
                        let mut udp_socket = state.udp_socket.lock()
                            .map_err(|e| format!("Failed to lock socket for storage: {}", e))?;
                        *udp_socket = Some(socket);
                    }
                    
                    // Test UDP connection with a status command
                    test_udp_connection(&state).await?;
                    
                    println!("✅ UDP connection established");
                    Ok("Connected".to_string())
                }
                Err(e) => Err(format!("Failed to connect UDP socket: {}", e)),
            }
        }
        Err(e) => Err(format!("Failed to create UDP socket: {}", e)),
    }
}

#[tauri::command]
async fn update_settings(
    settings: Settings,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let mut app_settings = state.settings.lock()
        .map_err(|e| format!("Failed to lock settings: {}", e))?;
    *app_settings = settings;
    println!("⚙️ Settings updated");
    Ok(())
}

#[tauri::command]
async fn update_targeting(
    target: TargetCoords,
    is_firing: bool,
    _mode: String,
    state: State<'_, AppState>,
) -> Result<(), String> {
    // Update current target and firing state
    {
        let mut current_target = state.current_target.lock()
            .map_err(|e| format!("Failed to lock target: {}", e))?;
        *current_target = target.clone();
    }
    
    {
        let mut firing_state = state.is_firing.lock()
            .map_err(|e| format!("Failed to lock firing state: {}", e))?;
        *firing_state = is_firing;
    }
    
    // Convert percentage coordinates to pan/tilt and send command
    send_pan_tilt_command(&state, target.x, target.y, is_firing).await?;
    
    Ok(())
}

#[tauri::command]
async fn set_frame_dimensions(
    width: u32,
    height: u32,
    state: State<'_, AppState>,
) -> Result<(), String> {
    {
        let mut frame_w = state.frame_width.lock()
            .map_err(|e| format!("Failed to lock frame width: {}", e))?;
        let mut frame_h = state.frame_height.lock()
            .map_err(|e| format!("Failed to lock frame height: {}", e))?;
        *frame_w = width;
        *frame_h = height;
    }
    
    println!("📐 Frame dimensions set to {}x{}", width, height);
    Ok(())
}

#[tauri::command]
async fn load_calibration_file(state: State<'_, AppState>) -> Result<(), String> {
    match std::fs::read_to_string("calibration_results.json") {
        Ok(contents) => {
            match serde_json::from_str::<CalibrationResults>(&contents) {
                Ok(calibration) => {
                    let mut calib_results = state.calibration_results.lock()
                        .map_err(|e| format!("Failed to lock calibration: {}", e))?;
                    *calib_results = Some(calibration);
                    println!("📏 Calibration data loaded successfully");
                    Ok(())
                }
                Err(e) => Err(format!("Failed to parse calibration file: {}", e)),
            }
        }
        Err(e) => Err(format!("Failed to read calibration file: {}", e)),
    }
}

#[tauri::command]
async fn save_settings(
    settings: Settings,
    state: State<'_, AppState>,
) -> Result<(), String> {
    match serde_json::to_string_pretty(&settings) {
        Ok(json) => {
            match std::fs::write("settings.json", json) {
                Ok(_) => {
                    let mut app_settings = state.settings.lock()
                        .map_err(|e| format!("Failed to lock settings for save: {}", e))?;
                    *app_settings = settings;
                    println!("💾 Settings saved successfully");
                    Ok(())
                }
                Err(e) => Err(format!("Failed to save settings: {}", e)),
            }
        }
        Err(e) => Err(format!("Failed to serialize settings: {}", e)),
    }
}

#[tauri::command]
async fn cleanup_resources(state: State<'_, AppState>) -> Result<(), String> {
    // Close UDP connection
    {
        let mut socket = state.udp_socket.lock()
            .map_err(|e| format!("Failed to lock socket for cleanup: {}", e))?;
        *socket = None;
    }
    
    println!("🧹 Resources cleaned up");
    Ok(())
}

// Helper functions
async fn test_udp_connection(state: &AppState) -> Result<(), String> {
    // Send a test/status command to verify UDP connection
    let test_command = PanTiltCommand {
        pan: 90.0,   // Center position
        tilt: 90.0,  // Center position
        trigger: false,
    };
    
    send_udp_command(state, &test_command).await?;
    println!("🧪 UDP connection test successful");
    Ok(())
}

async fn send_pan_tilt_command(
    state: &AppState,
    target_x_percent: f64,
    target_y_percent: f64,
    is_firing: bool,
) -> Result<(), String> {
    // Rate limiting - don't send commands too frequently
    {
        let mut last_time = state.last_command_time.lock()
            .map_err(|e| format!("Failed to lock last command time: {}", e))?;
        let now = Instant::now();
        if now.duration_since(*last_time) < Duration::from_millis(50) { // Max 20 Hz
            return Ok(());
        }
        *last_time = now;
    }
    
    // Convert percentage coordinates to pan/tilt angles
    let (pan, tilt) = convert_coordinates_to_pan_tilt(
        state,
        target_x_percent,
        target_y_percent,
    ).await?;
    
    let command = PanTiltCommand {
        pan,
        tilt,
        trigger: is_firing,
    };
    
    // Send UDP command
    send_udp_command(state, &command).await?;
    
    Ok(())
}

async fn convert_coordinates_to_pan_tilt(
    state: &AppState,
    x_percent: f64,
    y_percent: f64,
) -> Result<(f64, f64), String> {
    let calibration = state.calibration_results.lock()
        .map_err(|e| format!("Failed to lock calibration: {}", e))?;
    
    if let Some(calib) = calibration.as_ref() {
        // Get frame dimensions
        let frame_w = *state.frame_width.lock()
            .map_err(|e| format!("Failed to lock frame width: {}", e))? as f64;
        let frame_h = *state.frame_height.lock()
            .map_err(|e| format!("Failed to lock frame height: {}", e))? as f64;
        
        // Convert percentage to pixel coordinates
        let pixel_x = (x_percent / 100.0) * frame_w;
        let pixel_y = (y_percent / 100.0) * frame_h;
        
        // Apply perspective transformation if available
        let (world_x, world_y) = if calib.perspective_matrix.len() == 9 {
            apply_perspective_transformation(pixel_x, pixel_y, &calib.perspective_matrix)
        } else {
            (pixel_x, pixel_y)
        };
        
        // Convert world coordinates to pan/tilt angles
        let pan_offset = (world_x - frame_w / 2.0) / frame_w * 90.0; // ±45° range
        let tilt_offset = (world_y - frame_h / 2.0) / frame_h * 90.0; // ±45° range
        
        let pan = (calib.initial_pan + pan_offset).max(0.0).min(180.0);
        let tilt = (calib.initial_tilt + tilt_offset).max(0.0).min(180.0);
        
        Ok((pan, tilt))
    } else {
        // Simple linear mapping without calibration
        let pan = (x_percent / 100.0) * 180.0;
        let tilt = (y_percent / 100.0) * 180.0;
        Ok((pan, tilt))
    }
}

fn apply_perspective_transformation(
    x: f64,
    y: f64,
    matrix: &[f64],
) -> (f64, f64) {
    // Apply 3x3 perspective transformation matrix
    let w = matrix[6] * x + matrix[7] * y + matrix[8];
    if w != 0.0 {
        let transformed_x = (matrix[0] * x + matrix[1] * y + matrix[2]) / w;
        let transformed_y = (matrix[3] * x + matrix[4] * y + matrix[5]) / w;
        (transformed_x, transformed_y)
    } else {
        (x, y) // Return original coordinates if transformation fails
    }
}

async fn send_udp_command(
    state: &AppState,
    command: &PanTiltCommand,
) -> Result<(), String> {
    let socket = state.udp_socket.lock()
        .map_err(|e| format!("Failed to lock socket: {}", e))?;
    
    if let Some(ref udp) = *socket {
        // Format command as expected by device: "tilt,pan,trigger,1\n"
        let command_str = format!("{},{},{},1\n", 
                                  command.tilt as i32,
                                  command.pan as i32,
                                  if command.trigger { 1 } else { 0 });
        
        match udp.send(command_str.as_bytes()) {
            Ok(_) => Ok(()),
            Err(e) => Err(format!("Failed to send UDP command: {}", e)),
        }
    } else {
        Err("UDP socket not connected".to_string())
    }
}

fn main() {
    tauri::Builder::default()
        .manage(AppState::default())
        .setup(|app| {
            println!("🚀 Sprayer Control App starting...");
            
            // Load settings if they exist
            let app_handle = app.handle();
            let state = app_handle.state::<AppState>();
            
            if let Ok(contents) = std::fs::read_to_string("settings.json") {
                if let Ok(settings) = serde_json::from_str::<Settings>(&contents) {
                    if let Ok(mut app_settings) = state.settings.lock() {
                        *app_settings = settings;
                        println!("📁 Settings loaded from file");
                    }
                }
            }
            
            println!("✅ Sprayer Control App initialized");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            connect_to_device,
            update_settings,
            update_targeting,
            set_frame_dimensions,
            load_calibration_file,
            save_settings,
            cleanup_resources
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}