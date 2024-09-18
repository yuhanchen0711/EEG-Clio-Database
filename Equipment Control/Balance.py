import serial
import time

STABLE_COUNT = 5
#Port num by default is COM3, serial number by default is 9600
def makeMeasurement(port_num, serial_num, period, accuracy):
    ser = serial.Serial(port_num, serial_num)
    prev_measurement = -1
    count = 0
    while True:
        try:
            data = ser.readline().decode().strip()
            ratio = accuracy * 100 if data == 0 else prev_measurement / data
            count = count + 1 if abs(ratio - 1) < accuracy else 0
            if count >= STABLE_COUNT:
                ser.close()
                return data
            prev_measurement = data
            time.sleep(period)
        except Exception as e:
            print(e)

makeMeasurement('COM3', 9600, 0.1, 0.001)