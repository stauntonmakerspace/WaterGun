import hid
import struct
import time

class DS4Controller:
    def __init__(self):
        self.report_id = 0
        self.left_stick_x = 0
        self.left_stick_y = 0
        self.right_stick_x = 0
        self.right_stick_y = 0
        self.dpad = 0
        self.buttons = 0
        self.t_pad_click = 0
        self.left_trigger = 0
        self.right_trigger = 0
        self.timestamp = 0
        self.battery_level = 0
        self.gyro_x = 0
        self.gyro_y = 0
        self.gyro_z = 0
        self.accel_x = 0
        self.accel_y = 0
        self.accel_z = 0
        self.ext_headset = 0
        self.t_pad_active = 0
        self.t_pad_data = []
        
        self.gamepad = None
        self.vendor_id = 0x054c  # Sony Corporation
        self.product_id = 0x09cc  # DualShock 4 [CUH-ZCT2x]

    def connect(self):
        print("Available HID devices:")
        for device in hid.enumerate():
            print(f"0x{device['vendor_id']:04x}:0x{device['product_id']:04x} {device['product_string']}")

        self.gamepad = hid.device()
        self.gamepad.open(self.vendor_id, self.product_id)
        self.gamepad.set_nonblocking(True)
        print(f"Connected to DualShock 4 controller")

    def read_input(self):
        report = self.gamepad.read(64)
        if report:
            self.parse_report(report)
            return True
        return False

    def parse_report(self, report):
        if len(report) < 64:
            raise ValueError("Invalid report length")

        self.report_id = report[0]
        self.left_stick_x = report[1]
        self.left_stick_y = report[2]
        self.right_stick_x = report[3]
        self.right_stick_y = report[4]
        self.dpad = report[5] & 0x0F
        self.buttons = (report[5] >> 4) | (report[6] << 4)
        self.t_pad_click = report[7] & 0x03
        self.left_trigger = report[8]
        self.right_trigger = report[9]
        self.timestamp = struct.unpack('<H', bytes(report[10:12]))[0]
        self.battery_level = report[12]
        self.gyro_x = struct.unpack('<h', bytes(report[13:15]))[0]
        self.gyro_y = struct.unpack('<h', bytes(report[15:17]))[0]
        self.gyro_z = struct.unpack('<h', bytes(report[17:19]))[0]
        self.accel_x = struct.unpack('<h', bytes(report[19:21]))[0]
        self.accel_y = struct.unpack('<h', bytes(report[21:23]))[0]
        self.accel_z = struct.unpack('<h', bytes(report[23:25]))[0]
        self.ext_headset = report[30]
        self.t_pad_active = report[33]

        self.t_pad_data = []
        for i in range(2):
            finger_down = report[35 + i * 4] == 0
            if finger_down:
                x, y = self._decode_t_pad_coords(report[36 + i * 4:39 + i * 4])
                self.t_pad_data.append((x, y))

    def _decode_t_pad_coords(self, data):
        raw_x = (data[0] << 4) | ((data[1] & 0xF0) >> 4)
        raw_y = ((data[1] & 0x0F) << 8) | data[2]
        return raw_x, raw_y

    def get_button_states(self):
        button_names = ['Square', 'X', 'Circle', 'Triangle', 'L1', 'R1', 'L2', 'R2', 
                        'Share', 'Options', 'L3', 'R3', 'PS', 'T-Pad Click']
        return {name: bool(self.buttons & (1 << i)) for i, name in enumerate(button_names)}

    def get_dpad_state(self):
        dpad_states = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'Released']
        return dpad_states[self.dpad] if self.dpad < 8 else dpad_states[8]

    def __str__(self):
        return f"""DS4 Controller State:
        Left Stick: ({self.left_stick_x}, {self.left_stick_y})
        Right Stick: ({self.right_stick_x}, {self.right_stick_y})
        D-Pad: {self.get_dpad_state()}
        Buttons: {self.get_button_states()}
        Triggers: L2: {self.left_trigger}, R2: {self.right_trigger}
        Gyro: ({self.gyro_x}, {self.gyro_y}, {self.gyro_z})
        Accel: ({self.accel_x}, {self.accel_y}, {self.accel_z})
        T-Pad: {self.t_pad_data}
        Battery: {self.battery_level}
        """

    def close(self):
        if self.gamepad:
            self.gamepad.close()
            print("Disconnected from DualShock 4 controller")

# Example usage:
if __name__ == "__main__":
    controller = DS4Controller()
    try:
        controller.connect()
        print("Reading controller input. Press Ctrl+C to exit.")
        while True:
            if controller.read_input():
                print(controller)
            # time.sleep(0.01)  # Small delay to prevent excessive CPU usage
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        controller.close()