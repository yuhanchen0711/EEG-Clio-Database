import hashlib
import string
import base64
import datetime
DATE_FORMATS = ["%m/%d/%y", "%m/%d/%Y"]

def convert_to_mmddyyyy(date_string):
    for input_format in DATE_FORMATS:
        try:
            # Parse the date string according to the given input format
            date_obj = datetime.datetime.strptime(date_string, input_format)
            
            # Convert the date object to "MM/DD/YYYY" format
            formatted_date = date_obj.strftime("%m/%d/%Y")
            return formatted_date
        except ValueError as e:
            pass
    return 'Your date must be in MM/DD/YY format!'

print(convert_to_mmddyyyy('7/22/24'))