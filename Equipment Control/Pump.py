from enum import Enum

# Define an enumeration called 'Color'
class Mode(Enum):
    SET_ROTATION_SPEED = 0
    READ_ROTATION_SPEED = 1
    SET_FLOW_RATE = 2
    READ_FLOW_RATE = 3
    FLOW_CALIBRATION = 4

class State1(Enum):
    STOP_PUMP = 0
    START_PUMP = 1
    PRIME_PUMP = 17

class State2(Enum):
    COUNTER_CLOCKWISE = 0
    CLOCKWISE = 1

baud_rate = {1200:1, 2400:2, 4800:3, 9600:4, 19200:5, 38400:6}

class Parity(Enum):
    NO_PARITY = 1
    ODD_PARITY = 2
    EVEN_PARITY = 3

def get_pdu(mode):
    if mode == Mode.SET_ROTATION_SPEED:
        return [6, 87, 74]
    if mode == Mode.READ_ROTATION_SPEED:
        return [2, 82, 74]
    if mode == Mode.SET_FLOW_RATE:
        return [8, 87, 76]
    if mode == Mode.READ_FLOW_RATE:
        return [2, 82, 76]
    if mode == Mode.FLOW_CALIBRATION:
        return [8, 87, 73, 68, 13, 0]

def xor_bytes(int_list):
    # Initialize the result to 0
    result = 0
    
    # XOR each integer in the list
    for num in int_list:
        # Ensure the number is treated as a byte (i.e., in range 0-255)
        result ^= num & 0xFF  # Mask to treat the number as a byte
    
    return result

def generate_bytes(num, n):
    result = []
    for i in range(n):
        result.append(num % 256)
        num = num // 256
    result.reverse()
    return result

def generate_command(*args):
    pdu = get_pdu(args[0])
    command = [233, args[1]]
    #Default Read mode: # (Mode, Pump address)
    # (Mode, Pump address, State1, State2, Speed)
    if args[0] == Mode.SET_ROTATION_SPEED:
        pdu += generate_bytes(args[4], 2) + [args[2].value, args[3].value]
    # (Mode, Pump address, State1, State2, Flow rate)
    elif args[0] == Mode.SET_FLOW_RATE:
        pdu += generate_bytes(args[4], 4) + [args[2].value, args[3].value]
    # (Mode, Pump address, Baud rate, Parity, Stop bit)
    elif args[0] == Mode.FLOW_CALIBRATION:
        pdu += [baud_rate[args[2]], args[3].value, args[4]]
    fcs = xor_bytes([args[1]] + pdu)
    command = ' '.join([format(i, '02X') for i in [233, args[1]] + pdu + [fcs]])
    return command

print(generate_command(Mode.FLOW_CALIBRATION, 13, 19200, Parity.EVEN_PARITY, 1))