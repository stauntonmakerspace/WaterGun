<template>
  <div class="sprayer-app">
    <!-- Header -->
    <header class="app-header">
      <div class="app-title">
        <Target class="icon" />
        Sprayer Control App
      </div>
      <div class="status-container">
        <div v-if="isServedByServer" class="connection-status" :class="cameraStatusClass">
          <span class="status-dot"></span>
          {{ cameraStatus }}
        </div>
        <template v-else>
          <div class="connection-status" :class="connectionStatusClass">
            <span class="status-dot"></span>
            Server: {{ connectionStatus }}
          </div>
          <div class="connection-status" :class="cameraStatusClass">
            <span class="status-dot"></span>
            Camera: {{ cameraStatus }}
          </div>
        </template>
        <div v-if="trackingStatus.yolo_available && isFullyConnected" class="connection-status" :class="trackingStatusClass">
          <span class="status-dot"></span>
          Tracking: {{ trackingStatus.tracking_enabled ? 'ON' : 'OFF' }}
        </div>
      </div>
    </header>

    <!-- Main Layout -->
    <main class="main-layout">
      <!-- Video Display Section -->
      <section class="video-section">
        <div class="section-header">
          <h3><Video class="section-icon" /> Video Display</h3>
          <div class="video-controls" v-if="isFullyConnected">
            <span class="resolution-info">{{ frameWidth && frameHeight ? frameWidth + 'x' + frameHeight : 'Loading...' }}</span>
            <span class="stream-status">WebRTC Connected</span>
            <span v-if="settings.targetingMode === 'gamepad'" class="gamepad-status" :class="{ 'connected': gamepadConnected }">
              {{ gamepadConnected ? ('Gamepad: ' + (connectedGamepad?.id || 'Connected')) : 'No Gamepad' }}
            </span>
            <span v-if="settings.targetingMode === 'automatic'" class="auto-targeting-status" :class="autoTargetingStatusClass">
              {{ autoTargetingDisplayText }}
            </span>
          </div>
        </div>

        <div class="video-container-wrapper">
          <div 
            ref="videoContainer"
            class="video-display"
            :class="{ 'no-video': !isFullyConnected }"
            :style="videoContainerStyle"
            @mousemove="onMouseMove"
            @mousedown="onMouseDown"
            @mouseup="onMouseUp"
            @mouseleave="onMouseUp"
            @dragstart.prevent
            @drag.prevent
            @dragover.prevent
            @drop.prevent
            @selectstart.prevent
            @contextmenu.prevent
          >
            <!-- MJPEG Video Stream -->
            <img
              ref="videoElement"
              class="video-element"
              v-show="isFullyConnected"
              :src="videoStreamUrl"
              alt="Video Stream"
              draggable="false"
              @load="onVideoLoad"
              @dragstart.prevent
              @selectstart.prevent
            />

            <!-- No Connection Placeholder -->
            <div v-if="!isFullyConnected" class="no-connection-placeholder">
              <div class="placeholder-icon">
                <VideoOff :size="64" />
              </div>
              <div class="placeholder-text">
                <h4 v-if="isServedByServer">No Camera Connection</h4>
                <h4 v-else>{{ !isServerConnected ? 'No Server Connection' : 'No Camera Connection' }}</h4>
                <p v-if="isServedByServer">Connect to camera to view live stream</p>
                <p v-else>{{ !isServerConnected ? 'Connect to video server first' : 'Connect to camera to view live stream' }}</p>
              </div>
            </div>

            <!-- Video Overlays -->
            <div v-if="isFullyConnected" class="video-overlays">
              <!-- Crosshair -->
              <div 
                v-if="showCrosshair"
                class="crosshair"
                :style="crosshairStyle"
                :class="{ 'firing': controlState.trigger }"
              ></div>

              <!-- Auto Targeting Overlays -->
              <div v-if="settings.targetingMode === 'automatic'" class="auto-targeting-overlays">
                <!-- Tracked Objects Display -->
                <div v-for="obj in trackingData.objects" :key="obj.id" 
                     class="tracked-object-overlay"
                     :class="{ 'target-object': obj.is_target }"
                     :style="getObjectOverlayStyle(obj)">
                  <div class="object-label">
                    ID: {{ obj.id }} | {{ obj.class }} | {{ (obj.confidence * 100).toFixed(0) }}%
                    <span v-if="obj.is_target" class="target-indicator">TARGET</span>
                  </div>
                  <div class="object-bbox"></div>
                  <div class="target-point"></div>
                </div>
                
                <!-- Auto Targeting Status -->
                <div class="auto-targeting-status-overlay">
                  <div class="tracking-info">
                    <div>Objects: {{ trackingData.objects.length }}</div>
                    <div v-if="trackingData.current_target">Target: ID {{ trackingData.current_target }}</div>
                    <div v-else>No Target</div>
                    <div>Fire: {{ trackingData.fire_status }}</div>
                  </div>
                </div>
              </div>

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
                <div v-if="settings.targetingMode === 'automatic'">
                  <div class="debug-line">Tracking: {{ trackingStatus.tracking_enabled ? 'ON' : 'OFF' }}</div>
                  <div class="debug-line">Objects: {{ trackingData.objects.length }}</div>
                  <div class="debug-line">Target: {{ trackingData.current_target || 'None' }}</div>
                  <div class="debug-line">Auto Fire: {{ trackingData.auto_fire_enabled ? 'ON' : 'OFF' }}</div>
                </div>
                <div class="debug-line">Container: {{ actualVideoWidth || 'auto' }}x{{ actualVideoHeight || 'auto' }}</div>
                <div class="debug-line">Mouse: {{ mouseDebugInfo }}</div>
                <div class="debug-line">Server: {{ isServerConnected ? 'Yes' : 'No' }}</div>
                <div class="debug-line">Camera: {{ isCameraConnected ? 'Yes' : 'No' }}</div>
                <div class="debug-line">Gamepad: {{ gamepadConnected ? 'Yes' : 'No' }}</div>
              </div>

              <!-- Center Reference Point -->
              <div class="center-point"></div>
            </div>
          </div>
        </div>

        <!-- Video Instructions -->
        <div v-if="isFullyConnected" class="video-instructions">
          <div v-if="settings.targetingMode === 'cursor'" class="instruction">
            <strong>Mouse Control:</strong> 
            Move to aim • {{ settings.firingMode === 'toggle' ? 'Click to toggle firing' : 'Hold to fire' }}
          </div>
          <div v-else-if="settings.targetingMode === 'automatic'" class="instruction">
            <strong>Automatic Mode:</strong> 
            AI tracking {{ trackingData.objects.length }} targets
            <span v-if="trackingData.current_target"> • Targeting ID {{ trackingData.current_target }}</span>
            <span v-if="settings.autoFireEnabled"> • Auto-firing {{ trackingData.fire_status }}</span>
            <span v-else> • Click to {{ controlState.trigger ? 'stop' : 'start' }} firing</span>
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

        <!-- Server Connection Section (only show if not served by server) -->
        <div v-if="!isServedByServer" class="panel-section">
          <h4 class="section-title">Server Connection</h4>
          
          <div v-if="!isServerConnected" class="form-group">
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
            {{ isServerConnected ? ('Connected to ' + settings.value.serverAddress) : connectionStatus }}
          </div>
          
          <button 
            v-if="!isServerConnected"
            @click="connectToServer"
            class="button primary"
            :disabled="isConnecting"
          >
            <Wifi class="button-icon" />
            {{ isConnecting ? 'Connecting...' : 'Connect to Server' }}
          </button>

          <button 
            v-if="isServerConnected"
            @click="disconnectFromServer"
            class="button secondary"
          >
            <WifiOff class="button-icon" />
            Disconnect from Server
          </button>
        </div>

        <!-- Camera Connection Section -->
        <div v-if="isServerConnected" class="panel-section">
          <h4 class="section-title">Camera Connection</h4>
          
          <div v-if="!isCameraConnected" class="form-group">
            <label>Camera Address:</label>
            <input 
              type="text" 
              v-model="settings.cameraAddress"
              class="input-field"
              :disabled="isConnectingCamera"
              placeholder="127.0.0.1:9999"
            />
          </div>
          
          <div class="connection-info" :class="cameraStatusClass">
            {{ isCameraConnected ? ('Connected to ' + settings.cameraAddress) : cameraStatus }}
          </div>
          
          <button 
            v-if="!isCameraConnected"
            @click="connectToCamera"
            class="button primary"
            :disabled="isConnectingCamera"
          >
            <Camera class="button-icon" />
            {{ isConnectingCamera ? 'Connecting...' : 'Connect to Camera' }}
          </button>

          <button 
            v-if="isCameraConnected"
            @click="disconnectFromCamera"
            class="button secondary"
          >
            <Camera class="button-icon" />
            Disconnect Camera
          </button>
        </div>

        <!-- Settings Sections (Only show when fully connected) -->
        <template v-if="isFullyConnected">
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
                  :disabled="!trackingStatus.yolo_available"
                />
                <span>
                  <Play class="radio-icon" /> 
                  Automatic
                  <span v-if="!trackingStatus.yolo_available" class="feature-disabled">(YOLO Required)</span>
                </span>
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

          <!-- Auto Targeting Settings -->
          <div v-if="settings.targetingMode === 'automatic'" class="panel-section">
            <h4 class="section-title">Auto Targeting</h4>
            
            <div class="targeting-status">
              <div class="status-row">
                <span>YOLO Available:</span>
                <span class="status-value" :class="{ 'enabled': trackingStatus.yolo_available }">
                  {{ trackingStatus.yolo_available ? 'Yes' : 'No' }}
                </span>
              </div>
              <div class="status-row">
                <span>Objects Tracked:</span>
                <span class="status-value">{{ trackingData.objects.length }}</span>
              </div>
              <div class="status-row">
                <span>Current Target:</span>
                <span class="status-value">{{ trackingData.current_target || 'None' }}</span>
              </div>
            </div>
            
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="settings.autoFireEnabled"
                @change="onAutoFireToggle"
              />
              <span>Enable Auto-Fire</span>
            </label>
            
            <div class="slider-container">
              <label>Target Hold Time (Min):</label>
              <input 
                type="range" 
                min="1" 
                max="10" 
                step="0.5"
                v-model.number="settings.targetHoldTimeMin"
                class="slider"
              />
              <span class="slider-value">{{ settings.targetHoldTimeMin }}s</span>
            </div>
            
            <div class="slider-container">
              <label>Target Hold Time (Max):</label>
              <input 
                type="range" 
                min="2" 
                max="15" 
                step="0.5"
                v-model.number="settings.targetHoldTimeMax"
                class="slider"
              />
              <span class="slider-value">{{ settings.targetHoldTimeMax }}s</span>
            </div>
            
            <div v-if="settings.autoFireEnabled" class="fire-settings">
              <div class="slider-container">
                <label>Fire Duration:</label>
                <input 
                  type="range" 
                  min="0.5" 
                  max="5" 
                  step="0.1"
                  v-model.number="settings.fireDuration"
                  class="slider"
                />
                <span class="slider-value">{{ settings.fireDuration }}s</span>
              </div>
              
              <div class="slider-container">
                <label>Fire Cooldown:</label>
                <input 
                  type="range" 
                  min="0.5" 
                  max="5" 
                  step="0.1"
                  v-model.number="settings.fireCooldown"
                  class="slider"
                />
                <span class="slider-value">{{ settings.fireCooldown }}s</span>
              </div>
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

          <!-- Gamepad Settings -->
          <div v-if="settings.targetingMode === 'gamepad'" class="panel-section">
            <h4 class="section-title">Gamepad Settings</h4>
            
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
              v-if="settings.targetingMode === 'automatic' && !settings.autoFireEnabled"
              @click="toggleFiring"
              class="button"
              :class="{ 'danger': controlState.trigger }"
            >
              <Zap v-if="controlState.trigger" class="button-icon" />
              <Play v-else class="button-icon" />
              {{ controlState.trigger ? 'Stop Firing' : 'Start Firing' }}
            </button>
            
            <button 
              v-if="settings.targetingMode === 'automatic' && settings.autoFireEnabled"
              @click="toggleAutoFire"
              class="button"
              :class="{ 'danger': trackingData.auto_fire_enabled }"
            >
              <Zap v-if="trackingData.auto_fire_enabled" class="button-icon" />
              <Play v-else class="button-icon" />
              {{ trackingData.auto_fire_enabled ? 'Disable Auto-Fire' : 'Enable Auto-Fire' }}
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

            <!-- Advanced Settings -->
            <div class="collapsible-section">
              <div class="collapsible-header" @click="toggleAdvancedSettings">
                <h5><Settings class="section-icon" /> Advanced Settings</h5>
                <ChevronDown 
                  class="collapsible-arrow" 
                  :class="{ 'expanded': showAdvancedSettings }"
                />
              </div>
              <div 
                class="collapsible-content" 
                :class="{ 'expanded': showAdvancedSettings }"
              >
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="debugMode"
                  />
                  <span>Debug Mode</span>
                </label>

                <div v-if="settings.targetingMode !== 'gamepad'" class="sensitivity-section">
                  <div class="sensitivity-title">Pan/Tilt Sensitivity</div>
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

                <button @click="resetSettings" class="button danger">
                  <RotateCcw class="button-icon" />
                  Reset Defaults
                </button>
              </div>
            </div>
          </div>
        </template>

        <!-- Connection Required Message -->
        <div v-else class="connection-required">
          <div class="icon">
            <Cable :size="48" />
          </div>
          <h4>Camera Connection Required</h4>
          <p>Connect to camera to access control features</p>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import io from 'socket.io-client'

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
  RefreshCw,
  ChevronDown,
  Camera
} from 'lucide-vue-next'

// Reactive State
const settings = ref({
  targetingMode: 'cursor',
  firingMode: 'toggle',
  gamepadMode: 'follow',
  serverAddress: window.location.host,
  cameraAddress: '127.0.0.1:9999',
  panSensitivity: 1.0,
  tiltSensitivity: 1.0,
  gamepadDeadZone: 0.15,
  gamepadTriggerThreshold: 0.3,
  gamepadDragSpeed: 1.5,
  autoFireEnabled: false,
  targetHoldTimeMin: 3.0,
  targetHoldTimeMax: 8.0,
  fireDuration: 2.0,
  fireCooldown: 1.0
})

const debugMode = ref(false)
const showAdvancedSettings = ref(false)
const connectionStatus = ref('Connected')
const cameraStatus = ref('Disconnected')
const isConnecting = ref(false)
const isConnectingCamera = ref(false)
const isServedByServer = ref(true)

// Control state
const controlState = ref({
  pan: 0,
  tilt: 0,
  trigger: false
})

// Auto targeting state
const trackingStatus = ref({
  yolo_available: false,
  tracking_enabled: false,
  auto_fire_enabled: false
})

const trackingData = ref({
  objects: [],
  current_target: null,
  auto_fire_enabled: false,
  fire_status: 'OFF'
})

// Video display refs
const videoContainer = ref(null)
const videoElement = ref(null)
const frameWidth = ref(0)
const frameHeight = ref(0)
const actualVideoWidth = ref(0)
const actualVideoHeight = ref(0)

// WebSocket and connection state
let socket = null
const webrtcConnected = ref(false)

// Mouse state
const mousePosition = ref({ x: 50, y: 50 })
const mouseDebugInfo = ref('400, 300 (50.0%, 50.0%)')
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
let resizeObserver = null
let statusCheckInterval = null

// Computed Properties
const isServerConnected = computed(() => connectionStatus.value === 'Connected')
const isCameraConnected = computed(() => cameraStatus.value === 'Connected')
const isFullyConnected = computed(() => isServerConnected.value && isCameraConnected.value)

const connectionStatusClass = computed(() => ({
  'status-connected': isServerConnected.value,
  'status-connecting': isConnecting.value,
  'status-disconnected': !isServerConnected.value && !isConnecting.value,
  'status-error': connectionStatus.value.includes('failed') || connectionStatus.value.includes('error')
}))

const cameraStatusClass = computed(() => ({
  'status-connected': isCameraConnected.value,
  'status-connecting': isConnectingCamera.value,
  'status-disconnected': !isCameraConnected.value && !isConnectingCamera.value,
  'status-error': cameraStatus.value.includes('failed') || cameraStatus.value.includes('error')
}))

const trackingStatusClass = computed(() => ({
  'status-connected': trackingStatus.value.tracking_enabled,
  'status-disconnected': !trackingStatus.value.tracking_enabled
}))

const autoTargetingStatusClass = computed(() => ({
  'targeting': trackingData.value.current_target !== null,
  'firing': trackingData.value.fire_status === 'FIRING'
}))

const autoTargetingDisplayText = computed(() => {
  if (!trackingStatus.value.yolo_available) return 'YOLO Required'
  if (!trackingStatus.value.tracking_enabled) return 'Tracking OFF'
  if (trackingData.value.current_target) {
    return `Target: ${trackingData.value.current_target} | ${trackingData.value.fire_status}`
  }
  return `Searching (${trackingData.value.objects.length})`
})

const videoStreamUrl = computed(() => {
  if (!isServerConnected.value) return ''
  const baseUrl = isServedByServer.value 
    ? `${window.location.protocol}//${window.location.host}`
    : `http://${settings.value.serverAddress}`
  return `${baseUrl}/video_feed?t=${Date.now()}`
})

const showCrosshair = computed(() => 
  isFullyConnected.value && (settings.value.targetingMode === 'cursor' || settings.value.targetingMode === 'gamepad')
)

const videoContainerStyle = computed(() => {
  if (actualVideoWidth.value > 0 && actualVideoHeight.value > 0) {
    return {
      width: `${actualVideoWidth.value}px`,
      height: `${actualVideoHeight.value}px`,
      maxWidth: 'calc(100vw - 2rem)',
      maxHeight: 'calc(100vh - 200px)'
    }
  }
  return {
    maxWidth: 'calc(100vw - 2rem)',
    maxHeight: 'calc(100vh - 200px)',
    minWidth: '320px',
    minHeight: '240px'
  }
})

const crosshairStyle = computed(() => {
  const xPercent = ((controlState.value.pan + 90) / 180) * 100
  const yPercent = ((controlState.value.tilt + 45) / 90) * 100
  
  return {
    left: `${Math.max(0, Math.min(100, xPercent))}%`,
    top: `${Math.max(0, Math.min(100, yPercent))}%`,
    transform: 'translate(-50%, -50%)'
  }
})

// Auto targeting methods
const getObjectOverlayStyle = (obj) => {
  if (!videoContainer.value) return {}
  
  const containerRect = videoContainer.value.getBoundingClientRect()
  const [x1, y1, x2, y2] = obj.bbox
  
  // Convert frame coordinates to container coordinates
  const scaleX = containerRect.width / frameWidth.value
  const scaleY = containerRect.height / frameHeight.value
  
  return {
    left: `${x1 * scaleX}px`,
    top: `${y1 * scaleY}px`,
    width: `${(x2 - x1) * scaleX}px`,
    height: `${(y2 - y1) * scaleY}px`
  }
}

const onAutoFireToggle = () => {
  sendSettingsUpdate()
}

const toggleAutoFire = async () => {
  try {
    const baseUrl = isServedByServer.value 
      ? `${window.location.protocol}//${window.location.host}`
      : `http://${settings.value.serverAddress}`
    
    const response = await fetch(`${baseUrl}/targeting/toggle_fire`, {
      method: 'POST'
    })
    
    const result = await response.json()
    if (result.status === 'success') {
      trackingData.value.auto_fire_enabled = result.auto_fire_enabled
      settings.value.autoFireEnabled = result.auto_fire_enabled
    }
  } catch (error) {
    console.error('Failed to toggle auto fire:', error)
  }
}

// Video sizing methods
const updateVideoContainerSize = () => {
  if (!videoElement.value) return
  
  nextTick(() => {
    const videoEl = videoElement.value
    if (videoEl && videoEl.naturalWidth > 0 && videoEl.naturalHeight > 0) {
      const imageAspectRatio = videoEl.naturalWidth / videoEl.naturalHeight
      const containerRect = videoEl.getBoundingClientRect()
      
      if (containerRect.width > 0 && containerRect.height > 0) {
        const containerAspectRatio = containerRect.width / containerRect.height
        
        let actualWidth, actualHeight
        
        if (imageAspectRatio > containerAspectRatio) {
          actualWidth = containerRect.width
          actualHeight = containerRect.width / imageAspectRatio
        } else {
          actualHeight = containerRect.height
          actualWidth = containerRect.height * imageAspectRatio
        }
        
        if (actualWidth > 0 && actualHeight > 0) {
          actualVideoWidth.value = Math.round(actualWidth)
          actualVideoHeight.value = Math.round(actualHeight)
        }
      }
    }
  })
}

// Connection methods
const checkServerConnection = async () => {
  if (window.location.protocol !== 'file:') {
    isServedByServer.value = true
    connectionStatus.value = 'Connected'
    settings.value.serverAddress = window.location.host
    setupWebSocket()
    startStatusCheck()
    
    if (settings.value.targetingMode === 'gamepad') {
      startGamepadPolling()
    }
    return true
  }
  return false
}

const connectToServer = async () => {
  if (isServedByServer.value) return true
  
  isConnecting.value = true
  connectionStatus.value = 'Connecting...'
  
  try {
    const response = await fetch(`http://${settings.value.serverAddress}/`)
    if (response.ok) {
      connectionStatus.value = 'Connected'
      setupWebSocket()
      startStatusCheck()
      
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

const connectToCamera = async () => {
  if (!isServerConnected.value) {
    alert('Server connection required')
    return
  }

  isConnectingCamera.value = true
  cameraStatus.value = 'Connecting...'
  
  try {
    const baseUrl = isServedByServer.value 
      ? `${window.location.protocol}//${window.location.host}`
      : `http://${settings.value.serverAddress}`
    
    const response = await fetch(`${baseUrl}/camera/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        camera_address: settings.value.cameraAddress
      })
    })
    
    const result = await response.json()
    
    if (result.status === 'success' && result.connected) {
      cameraStatus.value = 'Connected'
      webrtcConnected.value = true
      trackingStatus.value.yolo_available = result.yolo_available || false
      startVideoRefresh()
    } else {
      cameraStatus.value = `Camera connection failed: ${result.error || 'Unknown error'}`
    }
  } catch (error) {
    cameraStatus.value = `Camera connection failed: ${error.message}`
  } finally {
    isConnectingCamera.value = false
  }
}

const disconnectFromCamera = async () => {
  try {
    const baseUrl = isServedByServer.value 
      ? `${window.location.protocol}//${window.location.host}`
      : `http://${settings.value.serverAddress}`
    
    await fetch(`${baseUrl}/camera/disconnect`, {
      method: 'POST'
    })
    cameraStatus.value = 'Disconnected'
    webrtcConnected.value = false
    controlState.value.trigger = false
    trackingStatus.value.tracking_enabled = false
    trackingData.value.objects = []
    trackingData.value.current_target = null
    stopVideoRefresh()
  } catch (error) {
    console.error('Error disconnecting from camera:', error)
  }
}

const disconnectFromServer = () => {
  if (socket) {
    socket.disconnect()
    socket = null
  }
  connectionStatus.value = 'Disconnected'
  cameraStatus.value = 'Disconnected'
  webrtcConnected.value = false
  controlState.value.trigger = false
  trackingStatus.value.tracking_enabled = false
  trackingData.value.objects = []
  trackingData.value.current_target = null
  stopVideoRefresh()
  stopGamepadPolling()
  stopStatusCheck()
}

const setupWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = isServedByServer.value 
    ? `${protocol}//${window.location.host}` 
    : `http://${settings.value.serverAddress}`
  
  socket = io(wsUrl)
  
  socket.on('connect', () => {
    console.log('WebSocket connected')
  })
  
  socket.on('disconnect', () => {
    console.log('WebSocket disconnected')
  })
  
  socket.on('video_frame', (frameData) => {
    // Handle real-time video frames if needed
  })
  
  socket.on('tracking_update', (data) => {
    trackingData.value = data
  })
  
  socket.on('targeting_status', (data) => {
    trackingStatus.value = { ...trackingStatus.value, ...data }
  })
}

// Status checking
const startStatusCheck = () => {
  if (statusCheckInterval) return
  
  statusCheckInterval = setInterval(async () => {
    if (!isServerConnected.value) return
    
    try {
      const baseUrl = isServedByServer.value 
        ? `${window.location.protocol}//${window.location.host}`
        : `http://${settings.value.serverAddress}`
      
      const response = await fetch(`${baseUrl}/device/status`)
      const status = await response.json()
      
      if (status.webrtc_connected && cameraStatus.value !== 'Connected') {
        cameraStatus.value = 'Connected'
        webrtcConnected.value = true
      } else if (!status.webrtc_connected && cameraStatus.value === 'Connected') {
        cameraStatus.value = 'Disconnected'
        webrtcConnected.value = false
      }
      
      // Update tracking status
      if (status.tracking_status) {
        trackingStatus.value = { 
          ...trackingStatus.value, 
          ...status.tracking_status 
        }
      }
    } catch (error) {
      console.warn('Status check failed:', error)
    }
  }, 2000)
}

const stopStatusCheck = () => {
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval)
    statusCheckInterval = null
  }
}

// Gamepad functions
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

  const rawX = gamepad.axes[0] || 0
  const rawY = gamepad.axes[1] || 0
  
  const stickX = applyDeadZone(rawX, settings.value.gamepadDeadZone)
  const stickY = applyDeadZone(rawY, settings.value.gamepadDeadZone)
  
  let triggerValue = 0
  if (gamepad.buttons[7]) {
    triggerValue = gamepad.buttons[7].value
  } else if (gamepad.axes[5] !== undefined) {
    triggerValue = (gamepad.axes[5] + 1) / 2
  }

  gamepadState.value.leftStick.x = stickX
  gamepadState.value.leftStick.y = stickY
  gamepadState.value.rightTrigger = triggerValue
  gamepadState.value.lastUpdate = Date.now()

  if (settings.value.targetingMode === 'gamepad' && isFullyConnected.value) {
    handleGamepadInput(stickX, stickY, triggerValue)
  }

  gamepadAnimationFrame = requestAnimationFrame(updateGamepadState)
}

const handleGamepadInput = (stickX, stickY, triggerValue) => {
  if (settings.value.gamepadMode === 'follow') {
    controlState.value.pan = stickX * 90
    controlState.value.tilt = stickY * 45
  } else if (settings.value.gamepadMode === 'drag') {
    const deltaTime = 16 / 1000
    const speed = settings.value.gamepadDragSpeed
    
    const panVelocity = stickX * 90 * speed
    const tiltVelocity = stickY * 45 * speed
    
    controlState.value.pan += panVelocity * deltaTime
    controlState.value.tilt += tiltVelocity * deltaTime
    
    controlState.value.pan = Math.max(-90, Math.min(90, controlState.value.pan))
    controlState.value.tilt = Math.max(-45, Math.min(45, controlState.value.tilt))
  }

  const shouldFire = triggerValue > settings.value.gamepadTriggerThreshold
  if (shouldFire !== controlState.value.trigger) {
    controlState.value.trigger = shouldFire
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

// Mouse event handlers
const onMouseMove = (event) => {
  if (!isFullyConnected.value || settings.value.targetingMode !== 'cursor') return
  
  event.preventDefault()
  event.stopPropagation()
  
  const rect = videoContainer.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  const xPercent = (x / rect.width) * 100
  const yPercent = (y / rect.height) * 100
  
  mousePosition.value = { x: xPercent, y: yPercent }
  mouseDebugInfo.value = `${Math.round(x)}, ${Math.round(y)} (${xPercent.toFixed(1)}%, ${yPercent.toFixed(1)}%)`
  
  const pan = ((xPercent - 50) / 50) * 90 * settings.value.panSensitivity
  const tilt = ((yPercent - 50) / 50) * 45 * settings.value.tiltSensitivity
  
  controlState.value.pan = Math.max(-90, Math.min(90, pan))
  controlState.value.tilt = Math.max(-45, Math.min(45, tilt))
  
  sendControlUpdate()
}

const onMouseDown = (event) => {
  if (!isFullyConnected.value || settings.value.targetingMode !== 'cursor') return
  
  event.preventDefault()
  event.stopPropagation()
  
  isMouseDown = true
  
  if (settings.value.firingMode === 'toggle') {
    controlState.value.trigger = !controlState.value.trigger
  } else if (settings.value.firingMode === 'hold') {
    controlState.value.trigger = true
  }
  
  sendControlUpdate()
}

const onMouseUp = (event) => {
  if (!isFullyConnected.value || settings.value.targetingMode !== 'cursor') return
  
  event.preventDefault()
  event.stopPropagation()
  
  isMouseDown = false
  
  if (settings.value.firingMode === 'hold') {
    controlState.value.trigger = false
    sendControlUpdate()
  }
}

// Control methods
const sendControlUpdate = async () => {
  if (!isServerConnected.value) return
  
  const payload = {
    pan: controlState.value.pan,
    tilt: controlState.value.tilt,
    trigger: controlState.value.trigger,
    mode: settings.value.targetingMode
  }
  
  try {
    if (socket && socket.connected) {
      socket.emit('control_update', payload)
    } else {
      const baseUrl = isServedByServer.value 
        ? `${window.location.protocol}//${window.location.host}`
        : `http://${settings.value.serverAddress}`
      
      await fetch(`${baseUrl}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    }
  } catch (error) {
    console.error('Failed to send control update:', error)
  }
}

const sendSettingsUpdate = async () => {
  if (!isServerConnected.value) return
  
  try {
    const baseUrl = isServedByServer.value 
      ? `${window.location.protocol}//${window.location.host}`
      : `http://${settings.value.serverAddress}`
    
    await fetch(`${baseUrl}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...settings.value,
        target_hold_time_min: settings.value.targetHoldTimeMin,
        target_hold_time_max: settings.value.targetHoldTimeMax,
        fire_duration: settings.value.fireDuration,
        fire_cooldown: settings.value.fireCooldown,
        auto_fire_enabled: settings.value.autoFireEnabled
      })
    })
  } catch (error) {
    console.error('Failed to send settings update:', error)
  }
}

const toggleFiring = () => {
  controlState.value.trigger = !controlState.value.trigger
  sendControlUpdate()
}

const centerPosition = () => {
  controlState.value.pan = 0
  controlState.value.tilt = 0
  controlState.value.trigger = false
  sendControlUpdate()
}

const onTargetingModeChange = () => {
  controlState.value.trigger = false
  
  if (settings.value.targetingMode === 'gamepad') {
    startGamepadPolling()
  } else {
    stopGamepadPolling()
  }
  
  sendControlUpdate()
  sendSettingsUpdate()
}

const toggleAdvancedSettings = () => {
  showAdvancedSettings.value = !showAdvancedSettings.value
}

const saveSettings = async () => {
  await sendSettingsUpdate()
  console.log('Settings saved successfully')
}

const resetSettings = () => {
  const serverAddress = isServedByServer.value ? window.location.host : 'localhost:5002'
  
  settings.value = {
    targetingMode: 'cursor',
    firingMode: 'toggle',
    gamepadMode: 'follow',
    serverAddress: serverAddress,
    cameraAddress: '127.0.0.1:9999',
    panSensitivity: 1.0,
    tiltSensitivity: 1.0,
    gamepadDeadZone: 0.15,
    gamepadTriggerThreshold: 0.3,
    gamepadDragSpeed: 1.5,
    autoFireEnabled: false,
    targetHoldTimeMin: 3.0,
    targetHoldTimeMax: 8.0,
    fireDuration: 2.0,
    fireCooldown: 1.0
  }
  debugMode.value = false
  showAdvancedSettings.value = false
  centerPosition()
}

const onVideoLoad = () => {
  if (!videoElement.value) return
  
  const videoEl = videoElement.value
  if (videoEl.naturalWidth > 0 && videoEl.naturalHeight > 0) {
    frameWidth.value = videoEl.naturalWidth
    frameHeight.value = videoEl.naturalHeight
    setTimeout(updateVideoContainerSize, 50)
  }
}

// Video refresh for MJPEG stream
let videoRefreshInterval = null

const startVideoRefresh = () => {
  if (videoRefreshInterval) return
  
  videoRefreshInterval = setInterval(() => {
    if (videoElement.value && isServerConnected.value) {
      const timestamp = Date.now()
      const baseUrl = isServedByServer.value 
        ? `${window.location.protocol}//${window.location.host}`
        : `http://${settings.value.serverAddress}`
      videoElement.value.src = `${baseUrl}/video_feed?t=${timestamp}`
    }
  }, 100)
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
onMounted(async () => {
  console.log('Sprayer Control App mounted')
  
  // Load settings from localStorage if available
  const savedSettings = localStorage.getItem('sprayerSettings')
  if (savedSettings) {
    try {
      const parsed = JSON.parse(savedSettings)
      if (!isServedByServer.value) {
        settings.value = { ...settings.value, ...parsed }
      } else {
        settings.value = { ...settings.value, ...parsed, serverAddress: window.location.host }
      }
    } catch (e) {
      console.warn('Failed to load saved settings')
    }
  }

  // Auto-connect to server if served by it
  await checkServerConnection()

  // Add event listeners
  window.addEventListener('gamepadconnected', onGamepadConnected)
  window.addEventListener('gamepaddisconnected', onGamepadDisconnected)
  window.addEventListener('resize', updateVideoContainerSize)
  
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(updateVideoContainerSize)
    if (videoElement.value) {
      resizeObserver.observe(videoElement.value)
    }
  }
  
  detectGamepad()
})

onUnmounted(() => {
  disconnectFromServer()
  stopVideoRefresh()
  stopGamepadPolling()
  stopStatusCheck()
  
  window.removeEventListener('gamepadconnected', onGamepadConnected)
  window.removeEventListener('gamepaddisconnected', onGamepadDisconnected)
  window.removeEventListener('resize', updateVideoContainerSize)
  
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
})

watch(settings, (newSettings) => {
  localStorage.setItem('sprayerSettings', JSON.stringify(newSettings))
  if (isServerConnected.value) {
    sendSettingsUpdate()
  }
}, { deep: true })

watch(videoElement, (newEl, oldEl) => {
  if (resizeObserver) {
    if (oldEl) resizeObserver.unobserve(oldEl)
    if (newEl) resizeObserver.observe(newEl)
  }
})
</script>

<style scoped>
/* All previous styles remain the same, plus new auto targeting styles */

.auto-targeting-status {
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  font-size: 0.8rem;
  font-weight: bold;
}

.auto-targeting-status.targeting {
  background: #007bff;
  color: white;
}

.auto-targeting-status.firing {
  background: #dc3545;
  color: white;
  animation: fireAlert 0.5s ease-in-out infinite alternate;
}

.auto-targeting-overlays {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.tracked-object-overlay {
  position: absolute;
  pointer-events: none;
}

.object-bbox {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 2px solid #00ff00;
  border-radius: 4px;
}

.target-object .object-bbox {
  border-color: #ff0000;
  border-width: 3px;
  animation: targetPulse 1s ease-in-out infinite alternate;
}

@keyframes targetPulse {
  0% { opacity: 1; }
  100% { opacity: 0.6; }
}

.object-label {
  position: absolute;
  top: -25px;
  left: 0;
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: bold;
  white-space: nowrap;
}

.target-indicator {
  color: #ff0000;
  margin-left: 5px;
}

.target-point {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 8px;
  height: 8px;
  background: #ff0000;
  border: 2px solid white;
  border-radius: 50%;
  transform: translateX(-50%);
}

.auto-targeting-status-overlay {
  position: absolute;
  top: 60px;
  left: 10px;
  background: rgba(0, 0, 0, 0.8);
  padding: 10px;
  border-radius: 6px;
  color: #00ff00;
  font-family: monospace;
  font-size: 12px;
}

.tracking-info div {
  margin-bottom: 3px;
}

.targeting-status {
  background: #1a1a1a;
  border: 1px solid #404040;
  border-radius: 4px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.status-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.status-value {
  font-weight: bold;
  color: #cccccc;
}

.status-value.enabled {
  color: #28a745;
}

.fire-settings {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #404040;
}

.feature-disabled {
  color: #dc3545;
  font-size: 0.8rem;
  font-style: italic;
}

/* All other existing styles remain unchanged */
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

.status-container {
  display: flex;
  gap: 1rem;
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
  flex: 1;
  padding: 1rem;
  background: #000000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  width: 100%;
  max-width: 1000px;
}

.section-header h3 {
  margin: 0;
  color: #ffffff;
  display: flex;
  align-items: center;
}

.section-icon {
  margin-right: 0.5rem;
  width: 20px;
  height: 20px;
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

.video-container-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  width: 100%;
  min-height: 0;
}

.video-display {
  position: relative;
  border: 2px solid #404040;
  border-radius: 8px;
  overflow: hidden;
  cursor: crosshair;
  background: #000;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.video-display.no-video {
  cursor: default;
  min-width: 320px;
  min-height: 240px;
}

.video-element {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  pointer-events: none;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  -webkit-user-drag: none;
  -khtml-user-drag: none;
  -moz-user-drag: none;
  -o-user-drag: none;
}

.no-connection-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  color: #666;
  height: 100%;
  justify-content: center;
  padding: 2rem;
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

.video-overlays {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
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
  max-width: 1000px;
  width: 100%;
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
  background: #2d2d2d;
  border-left: 2px solid #404040;
  min-width: 320px;
  max-width: 400px;
  width: 320px;
  overflow-y: auto;
  padding: 1.5rem;
  flex-shrink: 0;
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

.radio-icon {
  width: 14px;
  height: 14px;
  margin-right: 0.25rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.checkbox-label input[type="checkbox"] {
  transform: scale(1.2);
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
  margin-bottom: 0.75rem;
}

.slider-container label {
  min-width: 80px;
  font-size: 0.9rem;
  color: #cccccc;
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

.button.secondary:hover {
  background: #5a6268;
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

.button-icon {
  width: 16px;
  height: 16px;
  margin-right: 0.5rem;
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

.collapsible-section {
  margin-top: 1rem;
}

.collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  padding: 0.75rem;
  background: #404040;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.collapsible-header:hover {
  background: #4a4a4a;
}

.collapsible-header h5 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
}

.collapsible-arrow {
  transition: transform 0.2s;
  color: #cccccc;
  width: 16px;
  height: 16px;
}

.collapsible-arrow.expanded {
  transform: rotate(180deg);
}

.collapsible-content {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease-out;
}

.collapsible-content.expanded {
  max-height: 500px;
  padding-top: 1rem;
}

.sensitivity-section {
  margin-bottom: 1rem;
}

.sensitivity-title {
  font-size: 0.9rem;
  color: #cccccc;
  margin-bottom: 0.5rem;
  font-weight: 500;
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

/* Responsive */
@media (max-width: 1024px) {
  .main-layout {
    flex-direction: column;
  }

  .control-panel {
    border-left: none;
    border-top: 2px solid #404040;
    min-width: unset;
    max-width: unset;
    width: 100%;
    max-height: 300px;
    overflow-y: auto;
  }

  .video-section {
    flex: 1;
    min-height: 0;
  }
}

@media (max-width: 768px) {
  .app-header {
    padding: 0.75rem 1rem;
  }

  .app-title {
    font-size: 1.2rem;
  }

  .status-container {
    flex-direction: column;
    gap: 0.5rem;
  }

  .video-section {
    padding: 0.5rem;
  }

  .control-panel {
    padding: 1rem;
    max-height: 250px;
  }

  .panel-section {
    margin-bottom: 1rem;
    padding-bottom: 1rem;
  }
}
</style>