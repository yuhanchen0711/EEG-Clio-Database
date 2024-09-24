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
float_customtype = CustomType(getverifyNumberFunction(0, float('inf')), getNumberInput, selectstructure=getNumberFilter)
PROPERTY = pd.DataFrame({'Property':['Density', 'Conductivity', 'Viscosity', 'Mass', 'Volume'], 'Type':[float_customtype, float_customtype, float_customtype, float_customtype, float_customtype], 'Units':['g', 'cm^3', 'g/cm^3', 'mS/cm', 'cP']})
INPUT = pd.DataFrame({'Property':['Temperature', 'CompositionID', 'Date', 'Trial'], 
    'Type':[CustomType(getverifyNumberFunction(-273.15, float('inf')), getNumberInput, selectstructure=getNumberFilter), 
    CustomType(verifyCompositionID, getStringInput), 
    CustomType(getVerifyDateFunction(DATE_FORMATS), getDateInput, displayMethod=displayDate, selectstructure=getDateFilter),
    CustomType(getverifyNumberFunction(0, float('inf'), integer=True), getNumberInput)], 
    'Units':['C', '', '', '#']})
ALL_INPUT = pd.concat([PROPERTY, INPUT])
MAIN_NAME = 'experiments'
ASSOCIATE_NAME = 'dummy'
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
        table_name = current
        columns = ', '.join(compositions[0][current].keys())

        # Generate SQL query to create table
        create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} (ID INTEGER(32), {', '.join(compositions[0][current].keys())})"
        queries.append((create_table_query, ""))
    for current_composition in compositions:
        GUID = hash_datapoint(current_composition['experiments'])
        for current_table in current_composition.keys():
            new_df = 0
            try:
                new_df = pd.DataFrame(current_composition[current_table])
            except ValueError:
                new_df = pd.DataFrame(current_composition[current_table], index=['row1'])
            
            for index, row in new_df.iterrows():
                columns = ', '.join(new_df.columns)
                placeholders = ', '.join(["?" for _ in row])
                if current_table == MAIN_NAME:
                    query = f"INSERT OR REPLACE INTO {current_table} (ID, {columns}) VALUES (?, {placeholders})"
                else:
                    query = f"INSERT INTO {current_table} (ID, {columns}) VALUES (?, {placeholders})"
                queries.append((query, (GUID,) + tuple(row)))
    return queries
    

def generate_query(dependent_variables, independent_variables, solvents, salts, logic='and'):
    query = "SELECT e.ID AS ExperimentID"
    query2 = ') AS ID'
    query3 = "COALESCE(d.ID"
    for current in dependent_variables + independent_variables:
        query += ', ' + current
    for current in solvents:
        if logic == 'or':
            query += ', ' + current + '_Percentage'
            query3 += ', ' + current.lower() + '.ID'
            query2 += ',' + ' MAX(COALESCE(' + current.lower() + '_P, 0)) AS ' + current + '_Percentage'
        else:
            query += ',' + ' COALESCE(' + current.lower() + '_P, 0) AS ' + current + '_Percentage'
    for current in salts:
        if logic == 'or':
            query += ', ' + current + '_Molality'
            query3 += ', ' + current.lower() + '.ID'
            query2 += ',' + ' MAX(COALESCE(' + current.lower() + '_M, 0)) AS ' + current + '_Molality'
        else:
            query += ',' + ' COALESCE(' + current.lower() + '_M, 0) AS ' + current + '_Molality'
    
    way = ' INNER'
    salt_way = ' INNER'
    previous = 'e'
    if logic == 'or':
        way = ' FULL'
        salt_way = ' LEFT'
        query += ' FROM (SELECT ' + query3 + query2 + ' FROM dummy d'
        previous = 'd'
    else:
        query += ' FROM experiments e'
    for current in solvents:
        query += way + " JOIN (SELECT ID, percentage as " + current.lower() + "_P FROM solvents WHERE solvent = '" + current + "') " + current.lower() + " ON " + previous + ".ID = " + current.lower() + ".ID"
        previous = current.lower()
    for current in salts:
        query += salt_way + " JOIN (SELECT ID, molality as " + current.lower() + "_M FROM salts WHERE salt = '" + current + "') " + current.lower() + " ON " + previous + ".ID = " + current.lower() + ".ID"
        previous = current.lower()
    if logic == 'or':
        query = query + ' GROUP BY ' + query3 + ')) ex'
        query += ' LEFT JOIN experiments e ON ex.ID = e.ID'
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
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))[ALL_INPUT['Property']]
        compositions = []
        for index, row in df.iterrows():
            try:
                composition = check_validity(tuple(row))
            except KeyError as e:
                return 'Your CSV file must have a ' + e.args[0] + ' column!'
            if isinstance(composition, str):
                return 'Error on line ' + str(index + 2) + ': ' + composition
            compositions.append(composition)
        insert_new_data_bulk(compositions)
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

def generate_df(dependent_variables, independent_variables, solvents, salts):
    query = generate_query(dependent_variables, independent_variables, solvents, salts, logic='or')
    df = get_data_from_database(query, db_file=DEFAULT_DB)
    column_names = set(df.columns)
    for index, row in ALL_INPUT.iterrows():
        if row['Property'] in column_names:
            current_type = row['Type']
            df[row['Property']] = df[row['Property']].apply(current_type.displayMethod)
    return df

    

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
    solvents = get_data_from_database(solvent_query)['solvent'].tolist()
    salts = get_data_from_database(salt_query)['salt'].tolist()
    form_names = get_data_from_database("SELECT name FROM sqlite_master WHERE type = 'table'")['name'].tolist()
    options = [{"Title":"Dependent variables", "Options":sorted(PROPERTY['Property'], key=str.lower)},
      {"Title":"Independent variables", "Options":sorted(INPUT['Property'], key=str.lower)},
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

