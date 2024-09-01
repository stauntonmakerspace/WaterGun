#include <Servo.h>

// Pin definitions
#define PAN_SERVO_PIN 9
#define TILT_SERVO_PIN 10
#define H_BRIDGE_PIN_1 7
#define H_BRIDGE_PIN_2 8

// Servo configuration
#define PAN_GEAR_RATIO 5.0
#define TILT_GEAR_RATIO 3.0
#define PAN_ZERO_OFFSET 0  // Adjust this value to set the zero position for pan
#define TILT_ZERO_OFFSET 0 // Adjust this value to set the zero position for tilt

// Serial configuration
#define BAUD_RATE 115200

// Control parameters
#define MIN_ANGLE 0
#define MAX_ANGLE 180

Servo panServo;
Servo tiltServo;

int panAngle, tiltAngle;
bool trigger, redButton;
bool hBridgeDirection = true;
bool lastTriggerState = false;
bool lastRedButtonState = false;

void setup() {
  Serial.begin(BAUD_RATE);
  panServo.attach(PAN_SERVO_PIN);
  tiltServo.attach(TILT_SERVO_PIN);
  pinMode(H_BRIDGE_PIN_1, OUTPUT);
  pinMode(H_BRIDGE_PIN_2, OUTPUT);
  digitalWrite(H_BRIDGE_PIN_1, LOW);
  digitalWrite(H_BRIDGE_PIN_2, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    panAngle = Serial.parseInt();
    tiltAngle = Serial.parseInt();
    trigger = Serial.parseInt() != 0;  // Convert to bool
    redButton = Serial.parseInt() != 0;  // Convert to bool
    
    // Clear any remaining data in the buffer
    while (Serial.available() > 0) {
      Serial.read();
    }
    
    updateOutputs();
  }
}

void updateOutputs() {
  // Apply gear reduction and zero offsets to servo angles
  int adjustedPanAngle = constrain((panAngle * PAN_GEAR_RATIO) + PAN_ZERO_OFFSET, MIN_ANGLE, MAX_ANGLE);
  int adjustedTiltAngle = constrain((tiltAngle * TILT_GEAR_RATIO) + TILT_ZERO_OFFSET, MIN_ANGLE, MAX_ANGLE);
  
  // Control pan servo
  panServo.write(adjustedPanAngle);
  
  // Control tilt servo
  tiltServo.write(adjustedTiltAngle);
  
  // Handle red button (toggle H-bridge direction)
  if (redButton && !lastRedButtonState) {
    hBridgeDirection = !hBridgeDirection;
    updateHBridge();
  }
  lastRedButtonState = redButton;
  
  // Handle trigger (activate H-bridge)
  if (trigger && !lastTriggerState) {
    updateHBridge();
  } else if (!trigger && lastTriggerState) {
    digitalWrite(H_BRIDGE_PIN_1, LOW);
    digitalWrite(H_BRIDGE_PIN_2, LOW);
  }
  lastTriggerState = trigger;
}

void updateHBridge() {
  digitalWrite(H_BRIDGE_PIN_1, hBridgeDirection ? HIGH : LOW);
  digitalWrite(H_BRIDGE_PIN_2, hBridgeDirection ? LOW : HIGH);
}