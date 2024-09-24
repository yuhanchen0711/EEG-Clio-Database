import serial
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='Balance.log', filemode='a')
STABLE_COUNT = 5  # Define your stable count threshold here

def makeMeasurement(port_num, baud_rate, period, accuracy):
    try:
        ser = serial.Serial(port_num, baud_rate, timeout=1)
        logging.info(f'Successfully opened serial port {port_num} at baud rate {baud_rate}.')
    except serial.SerialException as e:
        logging.error(f"Error opening serial port: {e}")
        return None

    prev_measurement = 0
    stable_count = 0
    
    while True:
        try:
            data = ser.readline().decode().strip()
            if data:
                try:
                    measurement = float(data[:-1])
                    logging.info(f'Received measurement: {measurement}')
                except ValueError:
                    logging.warning(f"Invalid data received: {data}")
                    continue
                
                difference = abs(measurement - prev_measurement)
                if difference < accuracy:
                    stable_count += 1
                    logging.info(f'Measurement stable count: {stable_count}')
                else:
                    stable_count = 0
                
                if stable_count >= STABLE_COUNT:
                    logging.info(f'Measurement stabilized: {measurement}')
                    ser.close()
                    return measurement
                
                prev_measurement = measurement
                time.sleep(period)
        except Exception as e:
            logging.error(f"Error reading from serial port: {e}")
            break

    ser.close()
    return None

print(makeMeasurement('COM3', 9600, 0.1, 10E-5))