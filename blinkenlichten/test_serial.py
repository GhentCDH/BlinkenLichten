
import serial
import time

SERIAL_DEVICE="/dev/ttyUSB0"
SERIAL_BAUDRATE = 115200

def send_serial_command(command,ser):
    """Send a command to the serial device."""
    try:
        ser.write(f'{command}\n'.encode("ascii"))
        ser.flush()
        print(f"Command sent: {command}")
        return True, f'Command sent: {command}'
    except Exception as e:
        print(f"Error sending command: {command} - {str(e)}")
        return False, f'Error: {str(e)}'

with serial.Serial(SERIAL_DEVICE, SERIAL_BAUDRATE, timeout=None) as ser:
    send_serial_command("rainbow 10000",ser)
    time.sleep(10000)
    
