import hashlib
import string
import base64

def hash_datapoint(CompositionID, density, cP_mean, conductivity, temperature, experimentDate, trial):
    # Convert the components into strings
    density_str = f"{density:.10f}" if density is not None else "None"
    cP_mean_str = f"{cP_mean:.10f}" if cP_mean is not None else "None"
    conductivity_str = f"{conductivity:.10f}" if conductivity is not None else "None"
    temperature_str = f"{temperature:.10f}" if temperature is not None else "None"
    experimentDate_str = experimentDate.strftime('%Y-%m-%d') if experimentDate is not None else "None"
    trial_str = str(trial)
    
    # Concatenate all components into a single string
    hash_input = f"{CompositionID}|{density_str}|{cP_mean_str}|{conductivity_str}|{temperature_str}|{experimentDate_str}|{trial_str}"
    
    # Generate the hash using SHA-384
    hash_object = hashlib.sha256(hash_input.encode('utf-8'))
    hash_bytes = hash_object.digest()[8:32]
    hash_base64 = base64.b64encode(hash_bytes).decode('utf-8')
    return hash_base64


# Example usage
import datetime

hash_value = hash_datapoint(
    CompositionID="solvent1_solvent2|50.0_50.0|salt1|1.0",
    density=0.997,
    cP_mean=1.002,
    conductivity=0.015,
    temperature=26.0,
    experimentDate=datetime.date(2024, 8, 22),
    trial=1
)

print(hash_value)