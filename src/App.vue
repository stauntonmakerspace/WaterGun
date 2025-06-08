<!-- Vue.js Frontend for Sprayer Control with Gamepad Support -->
<template>
  <div class="sprayer-app">
    <!-- Header -->
    <header class="app-header">
      <div class="app-title">
        <Target class="icon" />
        Sprayer Control App
      </div>
      <div class="connection-status" :class="connectionStatusClass">
        <span class="status-dot"></span>
        {{ connectionStatus }}
      </div>
    </header>

    <!-- Main Layout -->
    <main class="main-layout">
      <!-- Video Display Section -->
      <section class="video-section">
        <div class="section-header">
          <h3><Video class="section-icon" /> Video Display</h3>
          <div class="video-controls" v-if="isConnected && webrtcConnected">
            <span class="resolution-info">{{ frameWidth }}x{{ frameHeight }}</span>
            <span class="stream-status">WebRTC Connected</span>
            <span v-if="settings.targetingMode === 'gamepad'" class="gamepad-status" :class="{ 'connected': gamepadConnected }">
              {{ gamepadConnected ? `Gamepad: ${connectedGamepad?.id || 'Connected'}` : 'No Gamepad' }}
            </span>
          </div>
        </div>

        <div 
          ref="videoContainer"
          class="video-display"
          :class="{ 'no-video': !isConnected || !webrtcConnected }"
          @mousemove="onMouseMove"
          @mousedown="onMouseDown"
          @mouseup="onMouseUp"
          @mouseleave="onMouseUp"
        >
          <!-- MJPEG Video Stream -->
          <img
            ref="videoElement"
            class="video-element"
            v-show="isConnected"
            :src="videoStreamUrl"
            alt="Video Stream"
            @load="onVideoLoad"
          />

          <!-- No Connection Placeholder -->
          <div v-if="!isConnected" class="no-connection-placeholder">
            <div class="placeholder-icon">
              <VideoOff size="64" />
            </div>
            <div class="placeholder-text">
              <h4>No Server Connection</h4>
              <p>Connect to video server to view live stream</p>
            </div>
          </div>

          <!-- Video Overlays (only when connected) -->
          <div v-if="isConnected" class="video-overlays">
            <!-- Crosshair -->
            <div 
              v-if="showCrosshair"
              class="crosshair"
              :style="crosshairStyle"
              :class="{ 'firing': controlState.trigger }"
            ></div>

            <!-- Debug Overlay -->
            <div v-if="debugMode" class="debug-overlay">
              <div class="debug-line">Pan: {{ controlState.pan.toFixed(1) }}°</div>
              <div class="debug-line">Tilt: {{ controlState.tilt.toFixed(1) }}°</div>
              <div class="debug-line">Trigger: {{ controlState.trigger ? 'FIRING' : 'OFF' }}</div>
              <div class="debug-line">Mode: {{ settings.targetingMode }}</div>
              <div v-if="settings.targetingMode === 'gamepad'">
                <div class="debug-line">Gamepad Mode: {{ settings.gamepadMode }}</div>
                <div class="debug-line">Stick X: {{ gamepadState.leftStick.x.toFixed(2) }}</div>
                <div class="debug-line">Stick Y: {{ gamepadState.leftStick.y.toFixed(2) }}</div>
                <div class="debug-line">R Trigger: {{ gamepadState.rightTrigger.toFixed(2) }}</div>
              </div>
              <div class="debug-line">Frame: {{ frameWidth }}x{{ frameHeight }}</div>
              <div class="debug-line">Connected: {{ isConnected ? 'Yes' : 'No' }}</div>
              <div class="debug-line">Gamepad: {{ gamepadConnected ? 'Yes' : 'No' }}</div>
            </div>

            <!-- Center Reference Point -->
            <div class="center-point"></div>
          </div>
        </div>

        <!-- Video Instructions -->
        <div v-if="isConnected" class="video-instructions">
          <div v-if="settings.targetingMode === 'cursor'" class="instruction">
            <strong>Mouse Control:</strong> 
            Move to aim • {{ settings.firingMode === 'toggle' ? 'Click to toggle firing' : 'Hold to fire' }}
          </div>
          <div v-else-if="settings.targetingMode === 'automatic'" class="instruction">
            <strong>Automatic Mode:</strong> 
            AI tracking targets • Click to {{ controlState.trigger ? 'stop' : 'start' }} firing
          </div>
          <div v-else-if="settings.targetingMode === 'gamepad'" class="instruction">
            <strong>Gamepad Control:</strong> 
            Left stick to aim ({{ settings.gamepadMode }}) • Right trigger to fire
            <span v-if="!gamepadConnected" class="warning"> • No gamepad detected</span>
          </div>
        </div>
      </section>

      <!-- Control Panel -->
      <aside class="control-panel">
        <h3 class="panel-title"><Settings class="section-icon" /> Control Panel</h3>

        <!-- Connection Section -->
        <div class="panel-section">
          <h4 class="section-title">Connection</h4>
          
          <div class="form-group">
            <label>Server Address:</label>
            <input 
              type="text" 
              v-model="settings.serverAddress"
              class="input-field"
              :disabled="isConnecting"
              placeholder="localhost:5000"
            />
          </div>
          
          <div class="connection-info" :class="connectionStatusClass">
            {{ connectionStatus }}
          </div>
          
          <button 
            @click="connect"
            class="button primary"
            :disabled="isConnecting || isConnected"
          >
            <Wifi class="button-icon" />
            {{ isConnecting ? 'Connecting...' : 'Connect' }}
          </button>

          <button 
            v-if="isConnected"
            @click="disconnect"
            class="button secondary"
          >
            <WifiOff class="button-icon" />
            Disconnect
          </button>
        </div>

        <!-- Settings Sections (Only show when connected) -->
        <template v-if="isConnected">
          <!-- Display Options -->
          <div class="panel-section">
            <h4 class="section-title">Display</h4>
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="debugMode"
              />
              <span>Debug Mode</span>
            </label>
          </div>

          <!-- Targeting Mode -->
          <div class="panel-section">
            <h4 class="section-title">Targeting Mode</h4>
            <div class="radio-group">
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="automatic" 
                  v-model="settings.targetingMode"
                  @change="onTargetingModeChange"
                />
                <span><Play class="radio-icon" /> Automatic</span>
              </label>
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="cursor" 
                  v-model="settings.targetingMode"
                  @change="onTargetingModeChange"
                />
                <span><Mouse class="radio-icon" /> Cursor</span>
              </label>
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="gamepad" 
                  v-model="settings.targetingMode"
                  @change="onTargetingModeChange"
                />
                <span><Gamepad2 class="radio-icon" /> Gamepad</span>
              </label>
            </div>
          </div>

          <!-- Firing Mode (Cursor only) -->
          <div v-if="settings.targetingMode === 'cursor'" class="panel-section">
            <h4 class="section-title">Firing Mode</h4>
            <div class="radio-group">
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="toggle" 
                  v-model="settings.firingMode"
                />
                <span>Toggle</span>
              </label>
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="hold" 
                  v-model="settings.firingMode"
                />
                <span>Hold to Fire</span>
              </label>
            </div>
          </div>

          <!-- Gamepad Mode (Gamepad only) -->
          <div v-if="settings.targetingMode === 'gamepad'" class="panel-section">
            <h4 class="section-title">Gamepad Mode</h4>
            <div class="radio-group">
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="follow" 
                  v-model="settings.gamepadMode"
                />
                <span><Move class="radio-icon" /> Follow (Position)</span>
              </label>
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="drag" 
                  v-model="settings.gamepadMode"
                />
                <span><Navigation class="radio-icon" /> Drag (Velocity)</span>
              </label>
            </div>
            <div class="mode-description">
              <p v-if="settings.gamepadMode === 'follow'">
                <strong>Follow Mode:</strong> Crosshair position directly matches stick position
              </p>
              <p v-if="settings.gamepadMode === 'drag'">
                <strong>Drag Mode:</strong> Stick controls movement speed and direction
              </p>
            </div>
          </div>

          <!-- Gamepad Settings (Gamepad only) -->
          <div v-if="settings.targetingMode === 'gamepad'" class="panel-section">
            <h4 class="section-title">Gamepad Settings</h4>
            
            <!-- Gamepad Status -->
            <div class="gamepad-status-section">
              <div class="gamepad-info" :class="{ 'connected': gamepadConnected }">
                <Gamepad2 class="gamepad-icon" />
                <span v-if="gamepadConnected">{{ connectedGamepad?.id || 'Gamepad Connected' }}</span>
                <span v-else>No Gamepad Detected</span>
              </div>
              <button @click="detectGamepad" class="button secondary small">
                <RefreshCw class="button-icon" />
                Detect
              </button>
            </div>

            <!-- Dead Zone -->
            <div class="slider-container">
              <label>Dead Zone:</label>
              <input 
                type="range" 
                min="0.05" 
                max="0.3" 
                step="0.01"
                v-model.number="settings.gamepadDeadZone"
                class="slider"
              />
              <span class="slider-value">{{ (settings.gamepadDeadZone * 100).toFixed(0) }}%</span>
            </div>

            <!-- Trigger Threshold -->
            <div class="slider-container">
              <label>Fire Threshold:</label>
              <input 
                type="range" 
                min="0.1" 
                max="0.9" 
                step="0.05"
                v-model.number="settings.gamepadTriggerThreshold"
                class="slider"
              />
              <span class="slider-value">{{ (settings.gamepadTriggerThreshold * 100).toFixed(0) }}%</span>
            </div>

            <!-- Drag Mode Speed (only in drag mode) -->
            <div v-if="settings.gamepadMode === 'drag'" class="slider-container">
              <label>Drag Speed:</label>
              <input 
                type="range" 
                min="0.5" 
                max="3.0" 
                step="0.1"
                v-model.number="settings.gamepadDragSpeed"
                class="slider"
              />
              <span class="slider-value">{{ settings.gamepadDragSpeed.toFixed(1) }}x</span>
            </div>
          </div>

          <!-- Pan/Tilt Sensitivity (Non-gamepad modes) -->
          <div v-if="settings.targetingMode !== 'gamepad'" class="panel-section">
            <h4 class="section-title">Pan/Tilt Sensitivity</h4>
            <div class="slider-container">
              <label>Pan:</label>
              <input 
                type="range" 
                min="0.1" 
                max="2.0" 
                step="0.1"
                v-model.number="settings.panSensitivity"
                class="slider"
              />
              <span class="slider-value">{{ settings.panSensitivity }}x</span>
            </div>
            <div class="slider-container">
              <label>Tilt:</label>
              <input 
                type="range" 
                min="0.1" 
                max="2.0" 
                step="0.1"
                v-model.number="settings.tiltSensitivity"
                class="slider"
              />
              <span class="slider-value">{{ settings.tiltSensitivity }}x</span>
            </div>
          </div>

          <!-- Firing Control -->
          <div class="panel-section">
            <h4 class="section-title">Firing Control</h4>
            <div class="firing-status" :class="{ 'active': controlState.trigger }">
              <div class="firing-indicator">
                <span class="firing-dot"></span>
                {{ controlState.trigger ? 'FIRING' : 'READY' }}
              </div>
            </div>
            
            <button 
              v-if="settings.targetingMode === 'automatic'"
              @click="toggleFiring"
              class="button"
              :class="{ 'danger': controlState.trigger }"
            >
              <Zap v-if="controlState.trigger" class="button-icon" />
              <Play v-else class="button-icon" />
              {{ controlState.trigger ? 'Stop Firing' : 'Start Firing' }}
            </button>
          </div>

          <!-- System Actions -->
          <div class="panel-section">
            <h4 class="section-title">System</h4>
            <button @click="centerPosition" class="button">
              <Compass class="button-icon" />
              Center Position
            </button>
            <button @click="saveSettings" class="button">
              <Save class="button-icon" />
              Save Settings
            </button>
            <button @click="resetSettings" class="button danger">
              <RotateCcw class="button-icon" />
              Reset Defaults
            </button>
          </div>

        </template>

        <!-- Connection Required Message -->
        <div v-else class="connection-required">
          <div class="icon">
            <Cable size="48" />
          </div>
          <h4>Connection Required</h4>
          <p>Connect to the video server to access control features</p>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

// Import Lucide icons
import { 
  Target, 
  Video, 
  VideoOff, 
  Settings, 
  Wifi, 
  WifiOff, 
  Play, 
  Mouse, 
  Zap, 
  Compass, 
  Save, 
  RotateCcw, 
  Cable,
  Gamepad2,
  Move,
  Navigation,
  RefreshCw
} from 'lucide-vue-next'

// Types and Reactive State
const settings = ref({
  targetingMode: 'cursor',
  firingMode: 'toggle',
  gamepadMode: 'follow', // 'follow' or 'drag'
  serverAddress: 'localhost:5000',
  panSensitivity: 1.0,
  tiltSensitivity: 1.0,
  gamepadDeadZone: 0.15,
  gamepadTriggerThreshold: 0.3,
  gamepadDragSpeed: 1.5
})

const debugMode = ref(false)
const connectionStatus = ref('Disconnected')
const isConnecting = ref(false)

// Control state (pan/tilt in degrees, trigger boolean)
const controlState = ref({
  pan: 0,    // degrees from center (-90 to +90)
  tilt: 0,   // degrees from center (-45 to +45)  
  trigger: false
})

// Video display refs
const videoContainer = ref(null)
const videoElement = ref(null)
const frameWidth = ref(800)
const frameHeight = ref(600)

// WebSocket for real-time communication
let socket = null
const webrtcConnected = ref(false)

// Mouse state
const mousePosition = ref({ x: 50, y: 50 }) // percentage from center
let isMouseDown = false

// Gamepad state
const gamepadConnected = ref(false)
const connectedGamepad = ref(null)
const gamepadState = ref({
  leftStick: { x: 0, y: 0 },
  rightTrigger: 0,
  lastUpdate: 0
})

let gamepadAnimationFrame = null

// Computed Properties
const isConnected = computed(() => connectionStatus.value === 'Connected')

const connectionStatusClass = computed(() => ({
  'status-connected': isConnected.value,
  'status-connecting': isConnecting.value,
  'status-disconnected': !isConnected.value && !isConnecting.value,
  'status-error': connectionStatus.value.includes('failed') || connectionStatus.value.includes('error')
}))

const videoStreamUrl = computed(() => {
  if (!isConnected.value) return ''
  return `http://${settings.value.serverAddress}/video_feed?t=${Date.now()}`
})

const showCrosshair = computed(() => 
  isConnected.value && (settings.value.targetingMode === 'cursor' || settings.value.targetingMode === 'gamepad')
)

const crosshairStyle = computed(() => {
  // Convert pan/tilt to screen position
  // Pan: -90 to +90 degrees -> 0 to 100% screen width
  // Tilt: -45 to +45 degrees -> 0 to 100% screen height
  const xPercent = ((controlState.value.pan + 90) / 180) * 100
  const yPercent = ((controlState.value.tilt + 45) / 90) * 100
  
  return {
    left: `${Math.max(0, Math.min(100, xPercent))}%`,
    top: `${Math.max(0, Math.min(100, yPercent))}%`,
    transform: 'translate(-50%, -50%)'
  }
})

// Gamepad Functions
const detectGamepad = () => {
  const gamepads = navigator.getGamepads()
  for (let i = 0; i < gamepads.length; i++) {
    if (gamepads[i]) {
      connectedGamepad.value = gamepads[i]
      gamepadConnected.value = true
      console.log('Gamepad detected:', gamepads[i].id)
      return
    }
  }
  gamepadConnected.value = false
  connectedGamepad.value = null
}

const applyDeadZone = (value, deadZone) => {
  if (Math.abs(value) < deadZone) {
    return 0
  }
  // Scale the value to maintain full range after dead zone
  const sign = Math.sign(value)
  const scaledValue = (Math.abs(value) - deadZone) / (1 - deadZone)
  return sign * scaledValue
}

const updateGamepadState = () => {
  if (!gamepadConnected.value) {
    detectGamepad()
    if (!gamepadConnected.value) {
      gamepadAnimationFrame = requestAnimationFrame(updateGamepadState)
      return
    }
  }

  const gamepad = navigator.getGamepads()[connectedGamepad.value?.index]
  if (!gamepad) {
    gamepadConnected.value = false
    connectedGamepad.value = null
    gamepadAnimationFrame = requestAnimationFrame(updateGamepadState)
    return
  }

  // Read left stick (axes 0 and 1)
  const rawX = gamepad.axes[0] || 0
  const rawY = gamepad.axes[1] || 0
  
  // Apply dead zone
  const stickX = applyDeadZone(rawX, settings.value.gamepadDeadZone)
  const stickY = applyDeadZone(rawY, settings.value.gamepadDeadZone)
  
  // Read right trigger (varies by gamepad, try button 7 then axes 5)
  let triggerValue = 0
  if (gamepad.buttons[7]) {
    triggerValue = gamepad.buttons[7].value
  } else if (gamepad.axes[5] !== undefined) {
    // Convert from -1 to 1 range to 0 to 1 range
    triggerValue = (gamepad.axes[5] + 1) / 2
  }

  // Update gamepad state
  gamepadState.value.leftStick.x = stickX
  gamepadState.value.leftStick.y = stickY
  gamepadState.value.rightTrigger = triggerValue
  gamepadState.value.lastUpdate = Date.now()

  // Handle gamepad input if in gamepad mode
  if (settings.value.targetingMode === 'gamepad' && isConnected.value) {
    handleGamepadInput(stickX, stickY, triggerValue)
  }

  gamepadAnimationFrame = requestAnimationFrame(updateGamepadState)
}

const handleGamepadInput = (stickX, stickY, triggerValue) => {
  if (settings.value.gamepadMode === 'follow') {
    // Follow mode: directly map stick position to pan/tilt
    controlState.value.pan = stickX * 90 // -90 to +90 degrees
    controlState.value.tilt = stickY * 45 // -45 to +45 degrees
  } else if (settings.value.gamepadMode === 'drag') {
    // Drag mode: stick controls velocity
    const deltaTime = 16 / 1000 // Assume ~60fps for smooth movement
    const speed = settings.value.gamepadDragSpeed
    
    // Calculate velocity in degrees per second
    const panVelocity = stickX * 90 * speed // max 90 deg/sec * speed multiplier
    const tiltVelocity = stickY * 45 * speed // max 45 deg/sec * speed multiplier
    
    // Update position based on velocity
    controlState.value.pan += panVelocity * deltaTime
    controlState.value.tilt += tiltVelocity * deltaTime
    
    // Clamp to valid ranges
    controlState.value.pan = Math.max(-90, Math.min(90, controlState.value.pan))
    controlState.value.tilt = Math.max(-45, Math.min(45, controlState.value.tilt))
  }

  // Handle trigger for firing
  const shouldFire = triggerValue > settings.value.gamepadTriggerThreshold
  if (shouldFire !== controlState.value.trigger) {
    controlState.value.trigger = shouldFire
  }

  sendControlUpdate()
}

// Methods
const connect = async () => {
  isConnecting.value = true
  connectionStatus.value = 'Connecting...'
  
  try {
    // Test connection with a simple HTTP request first
    const response = await fetch(`http://${settings.value.serverAddress}/`)
    if (response.ok) {
      connectionStatus.value = 'Connected'
      setupWebSocket()
      // Set a timer to refresh video stream
      startVideoRefresh()
      
      // Start gamepad polling if in gamepad mode
      if (settings.value.targetingMode === 'gamepad') {
        startGamepadPolling()
      }
    } else {
      connectionStatus.value = 'Connection failed'
    }
  } catch (error) {
    connectionStatus.value = `Connection failed: ${error.message}`
  } finally {
    isConnecting.value = false
  }
}

const setupWebSocket = () => {
  const wsUrl = `ws://${settings.value.serverAddress.replace('http://', '')}/socket.io/`
  socket = io(`http://${settings.value.serverAddress}`)
  
  socket.on('connect', () => {
    console.log('WebSocket connected')
    webrtcConnected.value = true
  })
  
  socket.on('disconnect', () => {
    console.log('WebSocket disconnected')
    webrtcConnected.value = false
  })
  
  socket.on('video_frame', (frameData) => {
    // Handle real-time video frames if needed
  })
}

const disconnect = () => {
  if (socket) {
    socket.disconnect()
    socket = null
  }
  connectionStatus.value = 'Disconnected'
  webrtcConnected.value = false
  controlState.value.trigger = false
  stopVideoRefresh()
  stopGamepadPolling()
}

const onMouseMove = (event) => {
  if (!isConnected.value || settings.value.targetingMode !== 'cursor') return
  
  const rect = videoContainer.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // Convert pixel coordinates to percentages relative to center
  const xPercent = (x / rect.width) * 100
  const yPercent = (y / rect.height) * 100
  
  mousePosition.value = { x: xPercent, y: yPercent }
  
  // Convert to pan/tilt angles
  // X: 0-100% -> -90 to +90 degrees
  // Y: 0-100% -> -45 to +45 degrees
  const pan = ((xPercent - 50) / 50) * 90 * settings.value.panSensitivity
  const tilt = ((yPercent - 50) / 50) * 45 * settings.value.tiltSensitivity
  
  controlState.value.pan = Math.max(-90, Math.min(90, pan))
  controlState.value.tilt = Math.max(-45, Math.min(45, tilt))
  
  sendControlUpdate()
}

const onMouseDown = () => {
  if (!isConnected.value || settings.value.targetingMode !== 'cursor') return
  
  isMouseDown = true
  
  if (settings.value.firingMode === 'toggle') {
    controlState.value.trigger = !controlState.value.trigger
  } else if (settings.value.firingMode === 'hold') {
    controlState.value.trigger = true
  }
  
  sendControlUpdate()
}

const onMouseUp = () => {
  if (!isConnected.value || settings.value.targetingMode !== 'cursor') return
  
  isMouseDown = false
  
  if (settings.value.firingMode === 'hold') {
    controlState.value.trigger = false
    sendControlUpdate()
  }
}

const toggleFiring = () => {
  controlState.value.trigger = !controlState.value.trigger
  sendControlUpdate()
}

const sendControlUpdate = async () => {
  if (!isConnected.value) return
  
  const payload = {
    pan: controlState.value.pan,
    tilt: controlState.value.tilt,
    trigger: controlState.value.trigger,
    mode: settings.value.targetingMode
  }
  
  try {
    // Send via WebSocket if available
    if (socket && socket.connected) {
      socket.emit('control_update', payload)
    } else {
      // Fallback to HTTP
      await fetch(`http://${settings.value.serverAddress}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    }
  } catch (error) {
    console.error('Failed to send control update:', error)
  }
}

const onTargetingModeChange = () => {
  // Reset firing state when changing modes
  controlState.value.trigger = false
  
  // Start or stop gamepad polling based on mode
  if (settings.value.targetingMode === 'gamepad') {
    startGamepadPolling()
  } else {
    stopGamepadPolling()
  }
  
  sendControlUpdate()
}

const startGamepadPolling = () => {
  if (!gamepadAnimationFrame) {
    detectGamepad()
    gamepadAnimationFrame = requestAnimationFrame(updateGamepadState)
  }
}

const stopGamepadPolling = () => {
  if (gamepadAnimationFrame) {
    cancelAnimationFrame(gamepadAnimationFrame)
    gamepadAnimationFrame = null
  }
}

const centerPosition = () => {
  controlState.value.pan = 0
  controlState.value.tilt = 0
  controlState.value.trigger = false
  sendControlUpdate()
}

const saveSettings = async () => {
  try {
    await fetch(`http://${settings.value.serverAddress}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value)
    })
    console.log('Settings saved successfully')
  } catch (error) {
    console.error('Failed to save settings:', error)
  }
}

const resetSettings = () => {
  settings.value = {
    targetingMode: 'cursor',
    firingMode: 'toggle',
    gamepadMode: 'follow',
    serverAddress: 'localhost:5000',
    panSensitivity: 1.0,
    tiltSensitivity: 1.0,
    gamepadDeadZone: 0.15,
    gamepadTriggerThreshold: 0.3,
    gamepadDragSpeed: 1.5
  }
  debugMode.value = false
  centerPosition()
}

const onVideoLoad = () => {
  if (videoElement.value) {
    frameWidth.value = videoElement.value.naturalWidth || 800
    frameHeight.value = videoElement.value.naturalHeight || 600
  }
}

// Video refresh for MJPEG stream
let videoRefreshInterval = null

const startVideoRefresh = () => {
  if (videoRefreshInterval) return
  
  videoRefreshInterval = setInterval(() => {
    if (videoElement.value && isConnected.value) {
      const timestamp = Date.now()
      videoElement.value.src = `http://${settings.value.serverAddress}/video_feed?t=${timestamp}`
    }
  }, 100) // 10 FPS refresh
}

const stopVideoRefresh = () => {
  if (videoRefreshInterval) {
    clearInterval(videoRefreshInterval)
    videoRefreshInterval = null
  }
}

// Gamepad event listeners
const onGamepadConnected = (event) => {
  console.log('Gamepad connected:', event.gamepad.id)
  detectGamepad()
}

const onGamepadDisconnected = (event) => {
  console.log('Gamepad disconnected:', event.gamepad.id)
  if (connectedGamepad.value?.index === event.gamepad.index) {
    gamepadConnected.value = false
    connectedGamepad.value = null
  }
}

// Lifecycle
onMounted(() => {
  console.log('Sprayer Control App mounted')
  
  // Load settings from localStorage if available
  const savedSettings = localStorage.getItem('sprayerSettings')
  if (savedSettings) {
    try {
      settings.value = { ...settings.value, ...JSON.parse(savedSettings) }
    } catch (e) {
      console.warn('Failed to load saved settings')
    }
  }

  // Add gamepad event listeners
  window.addEventListener('gamepadconnected', onGamepadConnected)
  window.addEventListener('gamepaddisconnected', onGamepadDisconnected)
  
  // Initial gamepad detection
  detectGamepad()
})

onUnmounted(() => {
  disconnect()
  stopVideoRefresh()
  stopGamepadPolling()
  
  // Remove gamepad event listeners
  window.removeEventListener('gamepadconnected', onGamepadConnected)
  window.removeEventListener('gamepaddisconnected', onGamepadDisconnected)
})

// Watch settings and save to localStorage
watch(settings, (newSettings) => {
  localStorage.setItem('sprayerSettings', JSON.stringify(newSettings))
}, { deep: true })
</script>

<style scoped>
.sprayer-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #1a1a1a;
  color: #ffffff;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  overflow: hidden;
}

/* Header */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: #2d2d2d;
  border-bottom: 2px solid #404040;
  flex-shrink: 0;
}

.app-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.5rem;
  font-weight: bold;
}

.icon {
  color: #007bff;
}

.section-icon {
  margin-right: 0.5rem;
  vertical-align: text-bottom;
}

.button-icon {
  width: 16px;
  height: 16px;
  margin-right: 0.5rem;
}

.radio-icon {
  width: 14px;
  height: 14px;
  margin-right: 0.25rem;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-weight: bold;
  text-transform: uppercase;
  font-size: 0.8rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.status-connected {
  background: #28a745;
  color: white;
}

.status-connecting {
  background: #ffc107;
  color: black;
}

.status-disconnected {
  background: #6c757d;
  color: white;
}

.status-error {
  background: #dc3545;
  color: white;
}

/* Main Layout */
.main-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Video Section */
.video-section {
  flex: 3;
  padding: 1rem;
  background: #000000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h3 {
  margin: 0;
  color: #ffffff;
  display: flex;
  align-items: center;
}

.video-controls {
  display: flex;
  gap: 1rem;
  font-size: 0.9rem;
  color: #cccccc;
}

.gamepad-status {
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  font-size: 0.8rem;
}

.gamepad-status.connected {
  background: #28a745;
  color: white;
}

.gamepad-status:not(.connected) {
  background: #dc3545;
  color: white;
}

.video-display {
  position: relative;
  flex: 1;
  border: 2px solid #404040;
  border-radius: 8px;
  overflow: hidden;
  cursor: crosshair;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-display.no-video {
  cursor: default;
}

.video-element {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.no-connection-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: #666;
}

.placeholder-icon {
  color: #666;
}

.placeholder-text {
  text-align: center;
}

.placeholder-text h4 {
  margin: 0 0 0.5rem 0;
  color: #888;
}

.placeholder-text p {
  margin: 0;
  color: #666;
}

/* Video Overlays */
.video-overlays {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.crosshair {
  position: absolute;
  width: 20px;
  height: 20px;
  z-index: 10;
}

.crosshair::before,
.crosshair::after {
  content: '';
  position: absolute;
  background: #ff0000;
}

.crosshair::before {
  left: 50%;
  top: 0;
  width: 2px;
  height: 100%;
  transform: translateX(-50%);
}

.crosshair::after {
  top: 50%;
  left: 0;
  height: 2px;
  width: 100%;
  transform: translateY(-50%);
}

.crosshair.firing {
  animation: pulse 0.5s ease-in-out infinite alternate;
}

@keyframes pulse {
  0% { opacity: 1; }
  100% { opacity: 0.5; }
}

.center-point {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 4px;
  height: 4px;
  background: #00ff00;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 5;
}

.debug-overlay {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.8);
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  color: #00ff00;
  z-index: 20;
}

.debug-line {
  margin-bottom: 2px;
}

.video-instructions {
  margin-top: 1rem;
  padding: 0.75rem;
  background: #2d2d2d;
  border-radius: 4px;
  border: 1px solid #404040;
}

.instruction {
  font-size: 0.9rem;
  color: #cccccc;
}

.warning {
  color: #ffc107;
  font-weight: bold;
}

/* Control Panel */
.control-panel {
  flex: 1;
  background: #2d2d2d;
  border-left: 2px solid #404040;
  min-width: 320px;
  max-width: 400px;
  overflow-y: auto;
  padding: 1.5rem;
}

.panel-title {
  margin: 0 0 1.5rem 0;
  color: #ffffff;
  font-size: 1.2rem;
  display: flex;
  align-items: center;
}

.panel-section {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #404040;
}

.panel-section:last-child {
  border-bottom: none;
}

.section-title {
  margin: 0 0 1rem 0;
  color: #ffffff;
  font-size: 1rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #cccccc;
}

.input-field {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #404040;
  border-radius: 4px;
  background: #1a1a1a;
  color: #ffffff;
  font-size: 0.9rem;
}

.input-field:focus {
  outline: none;
  border-color: #007bff;
}

.input-field:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 0.5rem;
}

.checkbox-label input[type="checkbox"] {
  transform: scale(1.2);
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.radio-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 0.5rem;
}

.radio-label input[type="radio"] {
  transform: scale(1.2);
}

.radio-label span {
  display: flex;
  align-items: center;
}

.mode-description {
  margin-top: 0.75rem;
  padding: 0.5rem;
  background: #1a1a1a;
  border-radius: 4px;
  border: 1px solid #404040;
}

.mode-description p {
  margin: 0;
  font-size: 0.85rem;
  color: #cccccc;
}

.gamepad-status-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.gamepad-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  padding: 0.5rem;
  border-radius: 4px;
  background: #dc3545;
  color: white;
  font-size: 0.85rem;
}

.gamepad-info.connected {
  background: #28a745;
}

.gamepad-icon {
  width: 16px;
  height: 16px;
}

.slider-container {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.slider-container label {
  min-width: 80px;
  font-size: 0.9rem;
}

.slider {
  flex: 1;
  height: 6px;
  background: #404040;
  border-radius: 3px;
  outline: none;
  -webkit-appearance: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  background: #007bff;
  border-radius: 50%;
  cursor: pointer;
}

.slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  background: #007bff;
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

.slider-value {
  font-weight: bold;
  color: #007bff;
  min-width: 50px;
  text-align: right;
}

.button {
  width: 100%;
  padding: 0.75rem;
  border: none;
  border-radius: 4px;
  background: #007bff;
  color: white;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.button:hover {
  background: #0056b3;
}

.button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.button.primary {
  background: #007bff;
}

.button.secondary {
  background: #6c757d;
}

.button.small {
  width: auto;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
}

.button.danger {
  background: #dc3545;
}

.button.danger:hover {
  background: #c82333;
}

.connection-info {
  padding: 0.75rem;
  border-radius: 4px;
  font-weight: bold;
  text-align: center;
  margin-bottom: 1rem;
}

.firing-status {
  padding: 1rem;
  border-radius: 4px;
  background: #404040;
  margin-bottom: 1rem;
}

.firing-status.active {
  background: #dc3545;
  animation: fireAlert 1s ease-in-out infinite alternate;
}

@keyframes fireAlert {
  0% { opacity: 1; }
  100% { opacity: 0.7; }
}

.firing-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: bold;
  justify-content: center;
}

.firing-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: currentColor;
}

.connection-required {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.connection-required .icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  color: #666;
  display: flex;
  justify-content: center;
}

.connection-required h4 {
  margin: 0 0 0.5rem 0;
  color: #888;
}

.connection-required p {
  margin: 0;
  font-size: 0.9rem;
}
</style>