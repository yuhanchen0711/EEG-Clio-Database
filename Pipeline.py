import pandas as pd
import sqlite3
import matplotlib
import uuid
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os
import io
import base64
from io import BytesIO
from datetime import datetime
import base64
import hashlib
PROPERTIES = ['Density', 'Conductivity', 'Viscosity', 'Temperature']
UNITS = ['g/cm^3', 'mS/cm', 'cP', 'C']
TABLE_NAMES = ['experiments', 'solvents', 'salts']
INSERT_EXPERIMENT_STRING = "INSERT INTO experiments (GUID, Density, Conductivity, Viscosity, Temperature, CompositionID) VALUES (?, ?, ?, ?, ?, ?)"
INSERT_SOLVENT_STRING = "INSERT INTO solvents (GUID, Solvent, Percentage) VALUES (?, ?, ?)"
INSERT_SALT_STRING = "INSERT INTO salts (GUID, Salt, Molality) VALUES (?, ?, ?)"
DEFAULT_DB = "Database.db"
DATE_FORMATS = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"]


def get_data_from_database(query, db_file=DEFAULT_DB):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_file)
    try:
        # Use pandas to execute the SQL query and return a DataFrame
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        # Close the database connection
        conn.close()

def edit_database(queries, db_file=DEFAULT_DB):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    for query in queries:
        cursor.execute(query[0], query[1])  # None is used to insert a NULL value
    conn.commit()
    conn.close()

def insert_new_data(compositionID, compositions, density, conductivity, viscosity, temperature, date, trial, db_file=DEFAULT_DB):
    queries = generate_edit_queries([compositionID], [compositions], [density], [conductivity], [viscosity], [temperature], [date], [trial])
    edit_database(queries, db_file)

def insert_new_data_bulk(compositionID, compositions, density, conductivity, viscosity, temperature, date, trial, db_file=DEFAULT_DB):
    queries = generate_edit_queries(compositionID, compositions, density, conductivity, viscosity, temperature, date, trial)
    edit_database(queries, db_file)

def generate_edit_queries(compositionIDs, compositionss, densitys, conductivitys, viscositys, temperatures, dates, trials):
    queries = []
    for compositionID, compositions, density, conductivity, viscosity, temperature, date, trial in zip(compositionIDs, compositionss, densitys, conductivitys, viscositys, temperatures, dates, trials):
        GUID = hash_datapoint(compositionID, density, viscosity, conductivity, temperature, date, trial)
        for current in TABLE_NAMES:
            delete_query = 'DELETE FROM ' + current + ' where GUID = ?'
            queries.append((delete_query, (GUID,)))
        queries.append((INSERT_EXPERIMENT_STRING, (GUID, density, conductivity, viscosity, temperature, compositionID)))
        solvents = compositions[0]
        percentage = compositions[1]
        salts = compositions[2]
        molality = compositions[3]
        for solvent, percent in zip(solvents, percentage):
            queries.append((INSERT_SOLVENT_STRING, (GUID, solvent, percent)))
        for salt, molality in zip(salts, molality):
            queries.append((INSERT_SALT_STRING, (GUID, salt, molality)))
    return queries
    

def generate_query(properties, solvents, salts, logic='and'):
    query = "SELECT e.GUID AS ExperimentID, CompositionID"
    for current in properties:
        query += ', ' + current
    for current in solvents:
        query += ',' + ' COALESCE(' + current.lower() + '_P, 0) AS ' + current + '_Percentage'
    for current in salts:
        query += ',' + ' COALESCE(' + current.lower() + '_M, 0) AS ' + current + '_Molality'
    
    way = ' INNER'
    previous = 'e'
    if logic == 'or':
        way = ' FULL'
        query += ' FROM dummy d'
        previous = 'd'
    else:
        query += ' FROM experiments e'
    for current in solvents:
        query += way + " JOIN (SELECT GUID, Percentage as " + current.lower() + "_P FROM solvents WHERE Solvent = '" + current + "') " + current.lower() + " ON " + previous + ".GUID = " + current.lower() + ".GUID"
        previous = current.lower()
    for current in salts:
        query += " INNER JOIN (SELECT GUID, Molality as " + current.lower() + "_M FROM salts WHERE Salt = '" + current + "') " + current.lower() + " ON " + previous + ".GUID = " + current.lower() + ".GUID"
        previous = current.lower()
    if logic == 'or':
        query += ' INNER JOIN experiments e ON ' + previous + '.GUID = e.GUID'
    return query

# Input page helper function
def check_validity(CompositionID, Density, Conductivity, Viscosity, Temperature, Date, Trial):
    # Check Dates
    Date = convert_date(Date)
    try:
        datetime.strptime(Date, DATE_FORMATS[0])
    except ValueError:
        return Date
    if Density is not None and Density < 0:
        return 'Density must be greater than zero!'
    if Conductivity is not None and Conductivity < 0:
        return 'Conductivity must be greater than zero!'
    if Viscosity is not None and Viscosity < 0:
        return 'Viscosity must be greater than zero!'
    if Temperature is not None and Temperature < -273.15:
        return 'Temperature must be greater than -273.15 Celsius!'
    if CompositionID is None:
        return 'Please enter the composition ID.'
    if not isinstance(Trial, int) and Trial.is_integer():
        return 'Trial must be integer.'
    if Trial < 0:
        return 'Trial must be greater than zero!'
    else:
        # Check compositionID
        error_comp_id = 'Please enter a valid composition ID.'
        splitted_string = CompositionID.split('|')
        if len(splitted_string) != 4:
            return error_comp_id
        solvents = splitted_string[0].split('_')
        percentage = splitted_string[1].split('_')
        if len(solvents) != len(percentage):
            return error_comp_id
        for current in solvents:
            if len(current) <= 0 or not (current[0].isupper() and current.isalnum()):
                return error_comp_id
        for i in range(len(percentage)):
            try:
                percentage[i] = float(percentage[i])
            except ValueError:
                return error_comp_id
            if percentage[i] <= 0:
                return error_comp_id
        if abs(sum(percentage) - 100) > 1E-10:
            return 'Percentages of solvents must sum up to 100.'

        salts = splitted_string[2].split('_')
        molality = splitted_string[3].split('_')
        if len(salts) != len(molality):
            return error_comp_id
        for current in salts:
            if len(current) <= 0 or not (current[0].isupper() and current.isalnum()):
                return error_comp_id
        for i in range(len(molality)):
            try:
                molality[i] = float(molality[i])
            except ValueError:
                return error_comp_id
            if percentage[i] <= 0:
                return error_comp_id
    return (solvents, percentage, salts, molality)


def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    #try:
    if 'csv' in filename:
            # Assume that the user uploaded a CSV file
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        compositions = []
        for index, row in df.iterrows():
            try:
                composition = check_validity(row['CompositionID'], row['Density'], row['Conductivity'], row['Viscosity'], row['Temperature'], row['Date'], row['Trial'])
            except KeyError as e:
                return 'Your CSV file must have a ' + e.args[0] + ' column!'
            if isinstance(composition, str):
                return 'Error on line ' + str(index + 2) + ': ' + composition
            compositions.append(composition)
        insert_new_data_bulk(df['CompositionID'], compositions, df['Density'], df['Conductivity'], df['Viscosity'], df['Temperature'], df['Date'], df['Trial'])
        return 'Data uploaded successfully.'
    else:
        return 'You must upload a CSV file'

# Home page helper functions
def generate_graph(df, file_name, c, x, y, z=None):
    fig = plt.figure()
    ax = None
    if z is not None:
        ax = fig.add_subplot(111, projection='3d')
        scatter = ax.scatter(df[x], df[y], df[z], c=df[c], marker='o')
        ax.set_zlabel(z)
    else:
        ax = fig.add_subplot(111)
        scatter = ax.scatter(df[x], df[y], c=df[c], marker='o')


    color_bar = fig.colorbar(scatter, ax=ax, pad=0.1, shrink=0.7, aspect=10)
    color_bar.set_label(c)
    #plt.subplots_adjust(left=0.1, right=1.5, top=0.9, bottom=0.1)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    plt.savefig(file_name)
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    buffer.close()

    return img_base64

def generate_df(properties, solvents, salts):
    query = generate_query(properties, solvents, salts, logic='and')
    return get_data_from_database(query, db_file=DEFAULT_DB)

def graphs(properties, solvents, salts):
    df = generate_df(properties, solvents, salts)
    cwd = os.getcwd()
    file_dir = os.path.join(cwd, 'Saved Plots')
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '-'

    for i in range(len(solvents)):
        solvents[i] += '_Percentage'
    for i in range(len(salts)):
        salts[i] += '_Molality'

    interest = solvents + salts
    if len(interest) < 2:
        return {'base_64':-1}
    x = interest[0]
    y = interest[1]
    z = None
    if len(interest) >= 3:
        z = interest[2]

    base64_list = []
    for i in range(len(properties)):
        file_name = now + str(i) + '.png'
        base64_list.append(generate_graph(df, os.path.join(file_dir, file_name), properties[i], x, y, z))
    return {'base_64':base64_list}

def get_choices():
    solvent_query = "SELECT DISTINCT solvent FROM solvents"
    salt_query = "SELECT DISTINCT salt FROM salts"
    solvents = get_data_from_database(solvent_query)['Solvent'].tolist()
    salts = get_data_from_database(salt_query)['Salt'].tolist()
    options = [{"Title":"Basic Properties", "Options":sorted(PROPERTIES, key=str.lower)},
      {"Title":"Solvents", "Options":sorted(solvents, key=str.lower)},
      {"Title":"Salts", "Options":sorted(salts, key=str.lower)}]
    return options

def convert_date(date_string):
    for input_format in DATE_FORMATS:
        try:
            # Parse the date string according to the given input format
            date_obj = datetime.strptime(date_string, input_format)
            
            # Convert the date object to "MM/DD/YYYY" format
            formatted_date = date_obj.strftime("%m/%d/%Y")
            return formatted_date
        except ValueError as e:
            pass
    return 'Your date must be in MM/DD/YY format!'

def hash_datapoint(CompositionID, density, viscosity, conductivity, temperature, date, trial):
    # Convert the components into strings
    density_str = f"{density:.10f}" if density is not None else "None"
    viscosity_str = f"{viscosity:.10f}" if viscosity is not None else "None"
    conductivity_str = f"{conductivity:.10f}" if conductivity is not None else "None"
    temperature_str = f"{temperature:.10f}" if temperature is not None else "None"
    trial_str = str(trial)
    date_str = convert_date(date)
    
    hash_input = f"{CompositionID}|{density_str}|{viscosity_str}|{conductivity_str}|{temperature_str}|{date_str}|{trial_str}"
    # Generate the hash using SHA-384
    hash_object = hashlib.sha256(hash_input.encode('utf-8'))
    hash_bytes = hash_object.digest()
    return hash_bytes

