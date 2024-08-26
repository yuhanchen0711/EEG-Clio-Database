import base64
import io
from dash import Dash, dash_table, html, dcc, callback, Output, Input, State
import plotly.express as px
import pandas as pd
import dash_bootstrap_components as dbc
from Pipeline import get_choices, generate_df, insert_new_data, insert_new_data_bulk, PROPERTIES, convert_date, DATE_FORMATS
from io import StringIO
import datetime

app = Dash(__name__, suppress_callback_exceptions=True)
input_properties = ["CompositionID"]
GUID_LENGTH = 32

# Define the layout of the app
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Link('Home', href='/'),
    dcc.Link('Input data', href='/input-page'),
    html.Div(id='page-content')
])

home_content = [
    html.H1(children='Select Properties, solvents, and salts', style={'textAlign': 'center'}),
    html.Div(id='container', style={'display': 'flex', 'padding': '10px', 'flex-direction': 'row'}),
    html.Div([
        html.Button('Show Table', id='table-button', n_clicks=0),
        html.Button('Show Graphs', id='graph-button', n_clicks=0)
    ], id='button-container', style={'display': 'flex', 'padding': '10px', 'flex-direction': 'row'}),
    html.Div(id='plot-container'),
    dcc.Store(id='form-options', data={}),
    dcc.Store(id='displayed-form', data=None)
    ]

input_content = [
    html.H1('Please input new data'),
    html.Div('Please upload a csv file. Make sure it has all the columns specified below.'),
    dcc.Upload(
        id='upload-file',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        multiple=False,
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
    ),
    dbc.Alert(id='file-alert', is_open=False, duration=4000),
    html.Div('Alternatively, you can manually enter the lab data.'),
    html.Div([item for pair in zip(
        [html.Label(current) for current in input_properties + PROPERTIES + ['Date', 'Trial']], 
        [dcc.Input(id= current + '-input', type='text', value=None) for current in input_properties]
      + [dcc.Input(id= current + '-input', type='number', value=None) for current in PROPERTIES]
      + [dcc.DatePickerSingle(
            id='date-picker-single',
            date=datetime.date.today()  # set today's date as the default
        ), dcc.Input(id='Trial-input', type='number', value=None)]
        ) for item in pair], id='inputs'),
    dbc.Alert(id='alert', is_open=False, duration=4000),
    html.Button('Add Data', id='add-data-button', n_clicks=0),
]

# Switch page function
@app.callback(
    Output('page-content', 'children'), 
    Input('url', 'pathname')
)
def display_page(pathname):
    if (pathname == '/input-page'):
        return input_content
    else:
        return home_content

# Input page callback functions.
@app.callback(
    [Output('alert', 'children'), Output('alert', 'is_open')],
    Input('add-data-button', 'n_clicks'),
    [State(current + '-input', 'value') for current in input_properties + PROPERTIES] + [State('date-picker-single', 'date'), State('Trial-input', 'value')],
    prevent_initial_call=True
)
def input_data(n_clicks, CompositionID, Density, Conductivity, cP_mean, Temperature, date, Trial):
        #Check the correctness of the input
    compositions = check_validity(CompositionID, Density, Conductivity, cP_mean, Temperature, date, Trial)
    if isinstance(compositions, str):
        return [compositions, True]
    insert_new_data(CompositionID, compositions, Density, Conductivity, cP_mean, Temperature, date, Trial)
    return ['Data submitted successfully', True]

@app.callback([Output('file-alert', 'children'), Output('file-alert', 'is_open')],
              Input('upload-file', 'contents'),
              State('upload-file', 'filename'),
              prevent_initial_call=True)
def update_output(contents, filename):
    if contents is not None:
        children = parse_contents(contents, filename)
        return [children, True]

# Input page helper function
def check_validity(CompositionID, Density, Conductivity, cP_mean, Temperature, Date, Trial):
    # Check Dates
    Date = convert_date(Date)
    try:
        datetime.datetime.strptime(Date, DATE_FORMATS[0])
    except ValueError:
        return Date
    if Density is not None and Density < 0:
        return 'Density must be greater than zero!'
    if Conductivity is not None and Conductivity < 0:
        return 'Conductivity must be greater than zero!'
    if cP_mean is not None and cP_mean < 0:
        return 'cP_mean must be greater than zero!'
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
                composition = check_validity(row['CompositionID'], row['Density'], row['Conductivity'], row['cP_mean'], row['Temperature'], row['Date'], row['Trial'])
            except KeyError as e:
                return 'Your CSV file must have a ' + e.args[0] + ' column!'
            if isinstance(composition, str):
                return 'Error on line ' + str(index + 2) + ': ' + composition
            compositions.append(composition)
        insert_new_data_bulk(df['CompositionID'], compositions, df['Density'], df['Conductivity'], df['cP_mean'], df['Temperature'], df['Date'], df['Trial'])
        return 'Data uploaded successfully.'
    else:
        return 'You must upload a CSV file'
    #except Exception as e:
        #return f'There was an error processing this file: {e}'

@app.callback(
    Output('container', 'children'),
    Input('form-options', 'data')
)

def generate_options(a):
    form_options = get_choices()
    form_elements = []
    for category in form_options:
        column = html.Form(id=category["Title"], className='column', style={'flex': '1', 'padding': '10px', 'flex-direction': 'row'}, children=[
            html.Div(category["Title"], className='title'),
            html.Div(
                dcc.Checklist(
                    className = category["Title"],
                    options=[{'label': option, 'value': option} for option in category["Options"]],
                    value=[]
                )
            ) 
        ])
        form_elements.append(column)
    
    return form_elements

def generate_options_df(form_elements):
    options = {}
    for current in form_elements:
        current_column = current['props']['children']
        options[current_column[0]['props']['children']] = current_column[1]['props']['children']['props']['value']
    df = generate_df(options['Basic Properties'], options['Solvents'], options['Salts'])
    return options, df

@app.callback(
    [Output('plot-container', 'children', allow_duplicate=True), Output('displayed-form', 'data')],
    Input('table-button', 'n_clicks'),
    [State('container', 'children')],
    prevent_initial_call=True
)
def show_table(n_clicks, form_elements):
    # Extract selected options from form_elements
    options, df = generate_options_df(form_elements)
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    csv_string = buffer.getvalue()
    return [[dash_table.DataTable(
        id='table',
        columns=[{"name": i, "id": i} for i in df.columns],
        data=df.to_dict('records')), 
    dcc.Download(id="download-table"),
    html.Button('Download', id='download-table-button', n_clicks=0)], csv_string]

@app.callback(
    Output("download-table", "data"),
    Input('download-table-button', "n_clicks"),
    State('displayed-form', 'data'),
    prevent_initial_call=True
)
def download_table(n_clicks, data):
    csv_bytes = io.BytesIO(data.encode())
    return dcc.send_bytes(csv_bytes.getvalue(), "exported_data.csv")


@app.callback(
    Output('plot-container', 'children', allow_duplicate=True),
    Input('graph-button', 'n_clicks'),
    State('container', 'children'),
    prevent_initial_call=True
)
def show_graph(n_clicks, form_elements=None):
    # Extract selected options from form_elements
    options, df = generate_options_df(form_elements)
    # Replace with your logic to generate base64 images
    # For now, use a placeholder image       
    for i in range(len(options['Solvents'])):
        options['Solvents'][i] += '_Percentage'
    for i in range(len(options['Salts'])):
        options['Salts'][i] += '_Molality'
    interest = options['Solvents'] + options['Salts']
    if len(options['Basic Properties']) < 1:
        return html.Div('Please select at least one basic properties.')
    if len(interest) < 1:
        return html.Div('Please select at least one solvent or salt.')
    result = []
    if len(interest) == 1:
        result = [px.scatter(df, x=interest[0], y=i, hover_data=interest) for i in options['Basic Properties']]
    elif len(interest) == 2:
        result = [px.scatter_3d(df, x=interest[0], y=interest[1], z=i, hover_data=interest) for i in options['Basic Properties']]
    else:
        result = [px.scatter_3d(df.dropna(subset=[i]), x=interest[0], y=interest[1], z=interest[2], color=i, hover_data=interest) for i in options['Basic Properties']]
    return [dcc.Graph(figure=i) for i in result]

if __name__ == '__main__':
    app.run_server(debug=True)