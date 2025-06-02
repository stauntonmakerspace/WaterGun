<!-- Vue.js Frontend with Icons -->
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
          <!-- WebRTC Video Element -->
          <video
            ref="videoElement"
            class="video-element"
            v-show="isConnected && webrtcConnected"
            autoplay
            playsinline
            muted
          ></video>

          <!-- No Connection Placeholder -->
          <div v-if="!isConnected || !webrtcConnected" class="no-connection-placeholder">
            <div class="placeholder-icon">
              <VideoOff size="64" />
            </div>
            <div class="placeholder-text">
              <h4 v-if="!isConnected">No Device Connection</h4>
              <h4 v-else-if="!webrtcConnected && connectionStatus.includes('External Browser')">WebRTC Not Supported</h4>
              <h4 v-else-if="!webrtcConnected">No Video Stream</h4>
              <p v-if="!isConnected">Connect to device to view live video</p>
              <p v-else-if="!webrtcConnected && connectionStatus.includes('External Browser')">
                Open video in browser: <br>
                <code style="color: #007bff; background: #333; padding: 4px; border-radius: 4px;">
                  http://{{ settings.deviceAddress }}:{{ settings.videoPort + 1 }}/video
                </code>
              </p>
              <p v-else-if="!webrtcConnected">Waiting for WebRTC video stream...</p>
            </div>
          </div>

          <!-- Video Overlays (only when connected and video active) -->
          <div v-if="isConnected && webrtcConnected" class="video-overlays">
            <!-- Crosshair -->
            <div 
              v-if="showCrosshair"
              class="crosshair"
              :style="crosshairStyle"
              :class="{ 'firing': isFiring }"
            ></div>

            <!-- Debug Overlay -->
            <div v-if="debugMode" class="debug-overlay">
              <div class="debug-line">Target: {{ currentTarget.x.toFixed(1) }}%, {{ currentTarget.y.toFixed(1) }}%</div>
              <div class="debug-line">Mode: {{ settings.targetingMode }}</div>
              <div class="debug-line">Firing: {{ isFiring ? 'Yes' : 'No' }}</div>
              <div class="debug-line">Tracks: {{ trackingData.tracks.length }}</div>
              <div class="debug-line">Frame: {{ frameWidth }}x{{ frameHeight }}</div>
              <div class="debug-line">WebRTC: {{ webrtcConnected ? 'Connected' : 'Disconnected' }}</div>
            </div>

            <!-- Tracking Boxes (Automatic mode) -->
            <div 
              v-for="(track, index) in trackingData.tracks"
              :key="track.id"
              class="tracking-box"
              :class="{ 'selected': index === trackingData.currentTargetIndex }"
              :style="getTrackingBoxStyle(track)"
            >
              <div class="track-label">ID: {{ track.id }}</div>
            </div>
          </div>
        </div>

        <!-- Video Instructions -->
        <div v-if="isConnected && webrtcConnected" class="video-instructions">
          <div v-if="settings.targetingMode === 'cursor'" class="instruction">
            <strong>Mouse Control:</strong> 
            Move to aim • {{ settings.firingMode === 'toggle' ? 'Click to toggle firing' : 'Hold to fire' }}
          </div>
          <div v-else-if="settings.targetingMode === 'automatic'" class="instruction">
            <strong>Automatic Mode:</strong> 
            AI tracking targets • Click to {{ isFiring ? 'stop' : 'start' }} firing
          </div>
          <div v-else-if="settings.targetingMode === 'joystick'" class="instruction">
            <strong>Joystick Mode:</strong> 
            Left stick to aim • Right trigger to fire
          </div>
        </div>
      </section>

      <!-- Control Panel -->
      <aside class="control-panel">
        <h3 class="panel-title"><Settings class="section-icon" /> Control Panel</h3>

        <!-- Connection Section (Always Visible) -->
        <div class="panel-section">
          <h4 class="section-title">Connection</h4>
          
          <div class="form-group">
            <label>Device Address:</label>
            <input 
              type="text" 
              v-model="settings.deviceAddress"
              class="input-field"
              :disabled="isConnecting"
              placeholder="127.0.0.1"
            />
          </div>
          
          <div class="connection-info" :class="connectionStatusClass">
            {{ connectionStatus }}
          </div>
          
          <button 
            @click="refreshConnection"
            class="button primary"
            :disabled="isConnecting"
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
                  value="joystick" 
                  v-model="settings.targetingMode"
                  @change="onTargetingModeChange"
                />
                <span><Gamepad2 class="radio-icon" /> Joystick</span>
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
                  @change="onSettingsChange"
                />
                <span>Toggle</span>
              </label>
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="hold" 
                  v-model="settings.firingMode"
                  @change="onSettingsChange"
                />
                <span>Hold to Fire</span>
              </label>
            </div>
          </div>

          <!-- Target Hold Time (Automatic only) -->
          <div v-if="settings.targetingMode === 'automatic'" class="panel-section">
            <h4 class="section-title">Target Hold Time</h4>
            <div class="slider-container">
              <input 
                type="range" 
                min="1" 
                max="10" 
                step="0.5"
                v-model.number="settings.targetHoldTime"
                @input="onSettingsChange"
                class="slider"
              />
              <span class="slider-value">{{ settings.targetHoldTime }}s</span>
            </div>
          </div>

          <!-- Gamepad Status (Joystick only) -->
          <div v-if="settings.targetingMode === 'joystick'" class="panel-section">
            <h4 class="section-title">Gamepad</h4>
            <div class="gamepad-status" :class="gamepadStatusClass">
              <div class="status-indicator">
                <span class="status-dot"></span>
                {{ gamepadStatus }}
              </div>
              <p v-if="!gamepadConnected" class="gamepad-help">
                Connect a gamepad and press any button to activate it.
              </p>
            </div>
          </div>

          <!-- Firing Control -->
          <div class="panel-section">
            <h4 class="section-title">Firing Control</h4>
            <div class="firing-status" :class="{ 'active': isFiring }">
              <div class="firing-indicator">
                <span class="firing-dot"></span>
                {{ isFiring ? 'FIRING' : 'READY' }}
              </div>
            </div>
            
            <button 
              v-if="settings.targetingMode === 'automatic'"
              @click="toggleFiring"
              class="button"
              :class="{ 'danger': isFiring }"
            >
              <Zap v-if="isFiring" class="button-icon" />
              <Play v-else class="button-icon" />
              {{ isFiring ? 'Stop Firing' : 'Start Firing' }}
            </button>
          </div>

          <!-- System Actions -->
          <div class="panel-section">
            <h4 class="section-title">System</h4>
            <button @click="loadCalibration" class="button">
              <Compass class="button-icon" />
              Load Calibration
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
          <p>Connect to the sprayer to access control features</p>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { listen } from '@tauri-apps/api/event'
import { useGamepad, mapGamepadToXbox360Controller } from '@vueuse/core'
import { invoke } from '@tauri-apps/api/core'

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
  Gamepad2, 
  Zap, 
  Compass, 
  Save, 
  RotateCcw, 
  Cable 
} from 'lucide-vue-next'

// Types
interface Settings {
  targetingMode: 'automatic' | 'cursor' | 'joystick'
  firingMode: 'toggle' | 'hold'
  targetHoldTime: number
  deviceAddress: string
  devicePort: number
  videoPort: number
}

interface TrackingData {
  tracks: Array<{
    id: number
    x1: number
    y1: number
    x2: number
    y2: number
    confidence: number
  }>
  currentTargetIndex: number
}

// Reactive State
const settings = ref<Settings>({
  targetingMode: 'cursor',
  firingMode: 'toggle',
  targetHoldTime: 5.0,
  deviceAddress: '127.0.0.1', // Default to localhost for testing
  devicePort: 5632,
  videoPort: 8080
})

const debugMode = ref(false) // UI-only feature
const connectionStatus = ref('Disconnected')
const isConnecting = ref(false)
const currentTarget = ref({ x: 50, y: 50 }) // Percentages 0-100
const isFiring = ref(false)
const gamepadStatus = ref('No gamepad detected')
const gamepadConnected = ref(false)

const trackingData = ref<TrackingData>({
  tracks: [],
  currentTargetIndex: 0
})

// Video display refs
const videoContainer = ref<HTMLDivElement>()
const videoElement = ref<HTMLVideoElement>()
const frameWidth = ref(800)
const frameHeight = ref(600)

// WebRTC
const webrtcConnection = ref<RTCPeerConnection | null>(null)
const webrtcConnected = ref(false)

// Gamepad support
const { isSupported: gamepadSupported, gamepads, onConnected, onDisconnected } = useGamepad()
const gamepad = computed(() => gamepads.value.find(g => g?.mapping === 'standard'))
const controller = computed(() => gamepad.value ? mapGamepadToXbox360Controller(gamepad.value) : null)

// Gamepad state for continuous movement
const gamepadTarget = ref({ x: 50, y: 50 }) // Start at center position (percentages)
let gamepadInterval: number | null = null

// Computed Properties
const isConnected = computed(() => connectionStatus.value === 'Connected')

const connectionStatusClass = computed(() => ({
  'status-connected': isConnected.value,
  'status-connecting': isConnecting.value,
  'status-disconnected': !isConnected.value && !isConnecting.value,
  'status-error': connectionStatus.value.includes('failed') || connectionStatus.value.includes('error')
}))

const gamepadStatusClass = computed(() => ({
  'gamepad-connected': gamepadConnected.value,
  'gamepad-disconnected': !gamepadConnected.value
}))

// Update gamepad status based on VueUse
watch(gamepad, (newGamepad) => {
  if (newGamepad) {
    gamepadConnected.value = true
    gamepadStatus.value = `Connected: ${newGamepad.id || 'Unknown Controller'}`
  } else {
    gamepadConnected.value = false
    gamepadStatus.value = 'No gamepad detected'
  }
})

const showCrosshair = computed(() => 
  isConnected.value && webrtcConnected.value && (
    settings.value.targetingMode === 'cursor' || 
    (settings.value.targetingMode === 'automatic' && trackingData.value.tracks.length > 0)
  )
)

const crosshairStyle = computed(() => {
  // Convert percentage to pixel coordinates based on actual video element size
  if (!videoElement.value) return { left: '50%', top: '50%' }
  
  const rect = videoElement.value.getBoundingClientRect()
  const x = (currentTarget.value.x / 100) * rect.width
  const y = (currentTarget.value.y / 100) * rect.height
  
  return {
    left: `${x}px`,
    top: `${y}px`,
    transform: 'translate(-50%, -50%)'
  }
})

// Methods - Direct device connection
const refreshConnection = async () => {
  isConnecting.value = true
  connectionStatus.value = 'Connecting...'
  
  try {
    // Connect UDP socket for commands
    const result = await invoke('connect_to_device', {
      address: settings.value.deviceAddress,
      port: settings.value.devicePort
    })
    
    if (result === 'Connected') {
      connectionStatus.value = 'Connected'
      
      // Setup WebRTC connection directly to device
      await setupDeviceWebRTC()
    } else {
      connectionStatus.value = result as string
    }
  } catch (error) {
    connectionStatus.value = `Connection failed: ${error}`
  } finally {
    isConnecting.value = false
  }
}

const setupDeviceWebRTC = async () => {
  try {
    console.log('🔗 Connecting to device WebRTC...')
    
    // Create peer connection
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    })
    
    // Handle incoming video stream
    pc.ontrack = (event) => {
      console.log('📺 Received video from device')
      if (videoElement.value && event.streams[0]) {
        videoElement.value.srcObject = event.streams[0]
        videoElement.value.play().catch(e => console.warn('Video play failed:', e))
        
        // Get actual video dimensions and update frame size dynamically
        videoElement.value.onloadedmetadata = () => {
          const video = videoElement.value!
          frameWidth.value = video.videoWidth
          frameHeight.value = video.videoHeight
          
          // Notify backend of frame dimensions for coordinate transformation
          invoke('set_frame_dimensions', {
            width: video.videoWidth,
            height: video.videoHeight
          }).catch(console.error)
          
          console.log(`✅ Video stream: ${video.videoWidth}x${video.videoHeight}`)
        }
        
        webrtcConnected.value = true
      }
    }
    
    // Handle connection state
    pc.onconnectionstatechange = () => {
      console.log(`🔄 Device WebRTC state: ${pc.connectionState}`)
      webrtcConnected.value = pc.connectionState === 'connected'
      
      if (pc.connectionState === 'failed') {
        console.log('❌ Device WebRTC connection failed')
        webrtcConnected.value = false
      }
    }
    
    // Connect to device's WebRTC signaling server using configured port
    const signalingUrl = `ws://${settings.value.deviceAddress}:${settings.value.videoPort}/websocket`
    await connectToDeviceSignaling(pc, signalingUrl)
    
    webrtcConnection.value = pc
    
  } catch (error) {
    console.error('❌ Device WebRTC setup failed:', error)
    webrtcConnected.value = false
  }
}

const connectToDeviceSignaling = async (pc: RTCPeerConnection, url: string) => {
  return new Promise<void>((resolve, reject) => {
    const ws = new WebSocket(url)
    
    ws.onopen = () => {
      console.log('📡 Connected to device signaling server')
      
      // Request video stream from device
      ws.send(JSON.stringify({
        type: 'request_stream',
        client_id: 'sprayer_controller'
      }))
    }
    
    ws.onmessage = async (event) => {
      try {
        const message = JSON.parse(event.data)
        
        switch (message.type) {
          case 'offer':
            await pc.setRemoteDescription(message.offer)
            const answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            ws.send(JSON.stringify({
              type: 'answer',
              answer: answer
            }))
            break
            
          case 'ice-candidate':
            if (message.candidate) {
              await pc.addIceCandidate(message.candidate)
            }
            break
            
          case 'stream_ready':
            console.log('✅ Device stream ready')
            resolve()
            break
        }
      } catch (error) {
        console.error('Signaling error:', error)
        reject(error)
      }
    }
    
    // Handle ICE candidates from our side
    pc.onicecandidate = (event) => {
      if (event.candidate && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'ice-candidate',
          candidate: event.candidate
        }))
      }
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      reject(error)
    }
    
    ws.onclose = () => {
      console.log('📡 Signaling connection closed')
    }
  })
}

const disconnect = async () => {
  try {
    await invoke('cleanup_resources')
    connectionStatus.value = 'Disconnected'
    isFiring.value = false
    webrtcConnected.value = false
    
    // Close WebRTC
    if (webrtcConnection.value) {
      webrtcConnection.value.close()
      webrtcConnection.value = null
    }
  } catch (error) {
    console.error('Disconnect error:', error)
  }
}

const onMouseMove = (event: MouseEvent) => {
  if (!isConnected.value || settings.value.targetingMode !== 'cursor') return
  
  const rect = videoElement.value?.getBoundingClientRect()
  if (!rect) return
  
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // Convert pixel coordinates to percentages
  const xPercent = Math.max(0, Math.min(100, (x / rect.width) * 100))
  const yPercent = Math.max(0, Math.min(100, (y / rect.height) * 100))
  
  currentTarget.value = { x: xPercent, y: yPercent }
  updateTargeting()
}

const onMouseDown = () => {
  if (!isConnected.value || settings.value.targetingMode !== 'cursor') return
  
  if (settings.value.firingMode === 'toggle') {
    isFiring.value = !isFiring.value
  } else if (settings.value.firingMode === 'hold') {
    isFiring.value = true
  }
  
  updateTargeting()
}

const onMouseUp = () => {
  if (!isConnected.value || settings.value.targetingMode !== 'cursor') return
  
  if (settings.value.firingMode === 'hold') {
    isFiring.value = false
    updateTargeting()
  }
}

const toggleFiring = () => {
  isFiring.value = !isFiring.value
  updateTargeting()
}

const updateTargeting = async () => {
  try {
    await invoke('update_targeting', {
      target: currentTarget.value,
      isFiring: isFiring.value,
      mode: settings.value.targetingMode
    })
  } catch (error) {
    console.error('Failed to update targeting:', error)
  }
}

const onSettingsChange = async () => {
  try {
    await invoke('update_settings', { 
      settings: {
        targeting_mode: settings.value.targetingMode,
        firing_mode: settings.value.firingMode,
        target_hold_time: settings.value.targetHoldTime,
        device_address: settings.value.deviceAddress,
        device_port: settings.value.devicePort,
        video_port: settings.value.videoPort
      }
    })
  } catch (error) {
    console.error('Failed to update settings:', error)
  }
}

const onTargetingModeChange = () => {
  // Reset firing state when changing modes
  isFiring.value = false
  onSettingsChange()
  
  // Handle gamepad processing based on mode
  if (settings.value.targetingMode === 'joystick') {
    startGamepadProcessing()
  } else {
    stopGamepadProcessing()
  }
}

// Gamepad processing
const startGamepadProcessing = () => {
  if (gamepadInterval) return
  
  gamepadInterval = setInterval(() => {
    if (settings.value.targetingMode === 'joystick' && controller.value) {
      processGamepadInput()
    }
  }, 16) // ~60 FPS
}

const stopGamepadProcessing = () => {
  if (gamepadInterval) {
    clearInterval(gamepadInterval)
    gamepadInterval = null
  }
}

const processGamepadInput = () => {
  if (!controller.value) return
  
  const leftStick = controller.value.axes.leftStick
  const rightTrigger = controller.value.triggers.right
  
  // Process stick movement (similar to original Python logic)
  const deadzone = 0.75
  const moveSpeed = 5 // Percentage per frame
  
  if (Math.abs(leftStick.x) > deadzone) {
    gamepadTarget.value.x += leftStick.x > 0 ? moveSpeed : -moveSpeed
  }
  
  if (Math.abs(leftStick.y) > deadzone) {
    gamepadTarget.value.y += leftStick.y > 0 ? moveSpeed : -moveSpeed
  }
  
  // Clamp values to 0-100 percentage range
  gamepadTarget.value.x = Math.max(0, Math.min(100, gamepadTarget.value.x))
  gamepadTarget.value.y = Math.max(0, Math.min(100, gamepadTarget.value.y))
  
  // Update current target
  const wasFiring = isFiring.value
  currentTarget.value = { ...gamepadTarget.value }
  
  // Handle firing (right trigger)
  isFiring.value = rightTrigger.value > 0.5
  
  // Send update if target or firing state changed
  if (wasFiring !== isFiring.value || 
      Math.abs(currentTarget.value.x - gamepadTarget.value.x) > 0.1 || 
      Math.abs(currentTarget.value.y - gamepadTarget.value.y) > 0.1) {
    updateTargeting()
  }
}

const loadCalibration = async () => {
  try {
    await invoke('load_calibration_file')
    console.log('Calibration loaded successfully')
  } catch (error) {
    console.error('Failed to load calibration:', error)
  }
}

const saveSettings = async () => {
  try {
    await invoke('save_settings', { 
      settings: {
        targeting_mode: settings.value.targetingMode,
        firing_mode: settings.value.firingMode,
        target_hold_time: settings.value.targetHoldTime,
        device_address: settings.value.deviceAddress,
        device_port: settings.value.devicePort,
        video_port: settings.value.videoPort
      }
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
    targetHoldTime: 5.0,
    deviceAddress: '127.0.0.1',
    devicePort: 5632,
    videoPort: 8080
  }
  debugMode.value = false
  onSettingsChange()
}

const getTrackingBoxStyle = (track: any) => {
  // Convert absolute pixel coordinates to percentages for display
  const xPercent = (track.x1 / frameWidth.value) * 100
  const yPercent = (track.y1 / frameHeight.value) * 100
  const widthPercent = ((track.x2 - track.x1) / frameWidth.value) * 100
  const heightPercent = ((track.y2 - track.y1) / frameHeight.value) * 100
  
  return {
    left: `${xPercent}%`,
    top: `${yPercent}%`,
    width: `${widthPercent}%`,
    height: `${heightPercent}%`
  }
}

// Lifecycle
onMounted(async () => {
  console.log('Sprayer Control App mounted')
  
  // Setup gamepad event listeners
  if (gamepadSupported.value) {
    onConnected((index) => {
      const gamepadInfo = gamepads.value[index]
      gamepadConnected.value = true
      gamepadStatus.value = `Connected: ${gamepadInfo?.id || 'Unknown Controller'}`
      console.log(`Gamepad connected: ${gamepadInfo?.id}`)
    })
    
    onDisconnected((index) => {
      gamepadConnected.value = false
      gamepadStatus.value = 'No gamepad detected'
      console.log(`Gamepad ${index} disconnected`)
    })
  }
  
  // Listen for tracking updates (automatic mode only)
  listen('tracking-update', (event: any) => {
    const data = event.payload
    trackingData.value = data
    
    // Update current target for automatic mode
    if (settings.value.targetingMode === 'automatic' && data.tracks.length > 0) {
      const selectedTrack = data.tracks[data.currentTargetIndex]
      if (selectedTrack) {
        // Convert bottom center of selected track to percentage coordinates
        const centerX = (selectedTrack.x1 + selectedTrack.x2) / 2
        const bottomY = selectedTrack.y2
        
        currentTarget.value = {
          x: (centerX / frameWidth.value) * 100,
          y: (bottomY / frameHeight.value) * 100
        }
      }
    }
  })
})

onUnmounted(async () => {
  stopGamepadProcessing()
  await disconnect()
})
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
  font-size: 1em;
  font-weight: bold;
  color: #007bff;
}

.section-icon {
  display: inline;
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

.tracking-box {
  position: absolute;
  border: 2px solid #00ff00;
  background: transparent;
  z-index: 15;
}

.tracking-box.selected {
  border-color: #ff0000;
  border-width: 3px;
}

.track-label {
  position: absolute;
  top: -20px;
  left: 0;
  background: #00ff00;
  color: black;
  padding: 2px 6px;
  font-size: 10px;
  border-radius: 2px;
}

.tracking-box.selected .track-label {
  background: #ff0000;
  color: white;
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

.slider-container {
  display: flex;
  align-items: center;
  gap: 1rem;
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
  min-width: 40px;
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

.gamepad-status .status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: 4px;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.gamepad-connected .status-indicator {
  background: #28a745;
  color: white;
}

.gamepad-disconnected .status-indicator {
  background: #6c757d;
  color: white;
}

.gamepad-help {
  font-size: 0.8rem;
  color: #cccccc;
  font-style: italic;
  margin: 0;
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
  color: #e1b394;
}

.connection-required p {
  margin: 0;
  font-size: 0.9rem;
}

/* Responsive Design */
@media (max-width: 1024px) {
  .main-layout {
    flex-direction: column;
  }
  
  .control-panel {
    border-left: none;
    border-top: 2px solid #404040;
    min-width: unset;
    max-width: unset;
    max-height: 300px;
  }
  
  .video-section {
    flex: 1;
    min-height: 400px;
  }
}

@media (max-width: 768px) {
  .app-header {
    padding: 1rem;
    flex-direction: column;
    gap: 1rem;
  }
  
  .main-layout {
    padding: 0.5rem;
  }
  
  .panel-section {
    margin-bottom: 1.5rem;
  }
}
</style>