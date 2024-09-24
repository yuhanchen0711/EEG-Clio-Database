import serial
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='Balance.log', filemode='a')
def go(port_num, baud_rate, dest):
    try:
        ser = serial.Serial(port_num, baud_rate, timeout=1)
        logging.info(f'Successfully opened serial port {port_num} at baud rate {baud_rate}.')
    except serial.SerialException as e:
        logging.error(f"Error opening serial port: {e}")
        return None
        
    while True:
        try:
            command = "CP\r"
            ser.write(command.encode())
            response = int(ser.read(4).decode('utf-8').strip()[2:])
            if response != dest:
                command = f"GO{dest}\r"
                ser.write(command.encode()) 
            else:
                ser.close()
                return
        except:
            return