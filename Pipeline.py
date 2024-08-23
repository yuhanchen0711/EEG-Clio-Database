import pandas as pd
import sqlite3
import matplotlib
import uuid
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os
import base64
from io import BytesIO
from datetime import datetime
PROPERTIES = ['Density', 'Conductivity', 'cP_mean', 'Temperature']
TABLE_NAMES = ['experiments', 'solvents', 'salts']
INSERT_EXPERIMENT_STRING = "INSERT INTO experiments (GUID, Density, Conductivity, cP_mean, Temperature, CompositionID) VALUES (?, ?, ?, ?, ?, ?)"
INSERT_SOLVENT_STRING = "INSERT INTO solvents (GUID, Solvent, Percentage) VALUES (?, ?, ?)"
INSERT_SALT_STRING = "INSERT INTO salts (GUID, Salt, Molality) VALUES (?, ?, ?)"
DEFAULT_DB = "Dummy.db"


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

def insert_new_data(GUID, compositionID, compositions, density, conductivity, cP_mean, temperature, db_file=DEFAULT_DB):
    queries = generate_edit_queries([GUID], [compositionID], [compositions], [density], [conductivity], [cP_mean], [temperature])
    edit_database(queries, db_file)

def insert_new_data_bulk(GUID, compositionID, compositions, density, conductivity, cP_mean, temperature, db_file=DEFAULT_DB):
    queries = generate_edit_queries(GUID, compositionID, compositions, density, conductivity, cP_mean, temperature)
    edit_database(queries, db_file)

def generate_edit_queries(GUIDs, compositionIDs, compositionss, densitys, conductivitys, cP_means, temperatures):
    queries = []
    for GUID, compositionID, compositions, density, conductivity, cP_mean, temperature in zip(GUIDs, compositionIDs, compositionss, densitys, conductivitys, cP_means, temperatures):
        if GUID == None or not isinstance(GUID, str):
            GUID = str(uuid.uuid4()).replace('-', '').upper()
        for current in TABLE_NAMES:
            delete_query = 'DELETE FROM ' + current + ' where GUID = ?'
            queries.append((delete_query, (GUID,)))
        queries.append((INSERT_EXPERIMENT_STRING, (GUID, density, conductivity, cP_mean, temperature, compositionID)))
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

#insert_new_data(1, 'DMC|100|LiPF6|2.5', 1.2, 1.3, 1.4, 0, db_file='Dummy.db')