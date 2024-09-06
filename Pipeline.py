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
from CustomTypes import CustomType
from TypeFunctions import *
import json

DATE_FORMATS = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"]
float_customtype = CustomType(getverifyNumberFunction(0, float('inf')), getNumberInput)
PROPERTY = pd.DataFrame({'Property':['Density', 'Conductivity', 'Viscosity'], 'Type':[float_customtype, float_customtype, float_customtype], 'Units':['g/cm^3', 'mS/cm', 'cP']})
INPUT = pd.DataFrame({'Property':['Temperature', 'CompositionID', 'Date', 'Trial'], 
    'Type':[CustomType(getverifyNumberFunction(-273.15, float('inf')), getNumberInput), 
    CustomType(verifyCompositionID, getStringInput), 
    CustomType(getVerifyDateFunction(DATE_FORMATS), getDateInput),
    CustomType(getverifyNumberFunction(0, float('inf'), integer=True), getNumberInput)], 
    'Units':['C', '', '', '#']})
ALL_INPUT = pd.concat([PROPERTY, INPUT])
PROPERTIES = ['Density', 'Conductivity', 'Viscosity', 'Temperature']
UNITS = ['g/cm^3', 'mS/cm', 'cP', 'C']
TABLE_NAMES = ['experiments', 'solvents', 'salts']
INSERT_EXPERIMENT_STRING = "INSERT INTO experiments (GUID, Density, Conductivity, Viscosity, Temperature, CompositionID) VALUES (?, ?, ?, ?, ?, ?)"
INSERT_SOLVENT_STRING = "INSERT INTO solvents (GUID, Solvent, Percentage) VALUES (?, ?, ?)"
INSERT_SALT_STRING = "INSERT INTO salts (GUID, Salt, Molality) VALUES (?, ?, ?)"
DEFAULT_DB = "Database.db"



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

def insert_new_data(compositions):
    queries = generate_edit_queries([compositions])
    edit_database(queries, DEFAULT_DB)

def insert_new_data_bulk(compositions):
    queries = generate_edit_queries(compositions)
    edit_database(queries, DEFAULT_DB)

def generate_edit_queries(compositions):
    queries = []
    for current in compositions[0]:
        table_name = "current"
        columns = ', '.join(compositions[0][current].keys())
        placeholders = ', '.join('?' for _ in compositions[0][current])

        # Generate SQL query to create table
        create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join([f'{key} TEXT' for key in compositions[0][current].keys()])})"
        queries.append(create_table_query)
        '''
    for current_composition in compositions:
        GUID = hash_datapoint(current_composition['experiments'])
        for current in current_composition:
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
    '''
    return queries
    

def generate_query(properties, solvents, salts, logic='and'):
    query = "SELECT e.GUID AS ExperimentID, CompositionID"
    query2 = ') AS GUID'
    query3 = "COALESCE(d.GUID"
    for current in properties:
        query += ', ' + current
    for current in solvents:
        if logic == 'or':
            query += ', ' + current + '_Percentage'
            query3 += ', ' + current.lower() + '.GUID'
            query2 += ',' + ' MAX(COALESCE(' + current.lower() + '_P, 0)) AS ' + current + '_Percentage'
        else:
            query += ',' + ' COALESCE(' + current.lower() + '_P, 0) AS ' + current + '_Percentage'
    for current in salts:
        query += ',' + ' COALESCE(' + current.lower() + '_M, 0) AS ' + current + '_Molality'
    
    way = ' INNER'
    previous = 'e'
    if logic == 'or':
        way = ' FULL'
        query += ' FROM (SELECT ' + query3 + query2 + ' FROM dummy d'
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
        query = query + ' GROUP BY ' + query3 + ')) ex'
        query += ' LEFT JOIN experiments e ON ex.GUID = e.GUID'
    return query

# Input page helper function
def check_validity(args):
    store_dict = {}
    result = {}
    for i in range(len(args)):
        current_type = ALL_INPUT['Type'].iloc[i]
        verify_result = current_type.verify(ALL_INPUT['Property'].iloc[i], args[i])
        if type(verify_result) == str:
            return verify_result
        elif type(verify_result) == dict:
            result.update(verify_result)
        else:
            store_dict[ALL_INPUT['Property'].iloc[i]] = verify_result
    
    result['experiments'] = store_dict
    return result
        

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
    query = generate_query(properties, solvents, salts, logic='or')
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

def hash_datapoint(experiment_data):
    # Convert the components into strings
    dict_str = json.dumps(experiment_data, sort_keys=True)
    hash_object = hashlib.sha256(dict_str.encode('utf-8'))
    hash_bytes = hash_object.digest()
    return hash_bytes

