import base64
import io
from dash import Dash, dash_table, html, dcc, callback, Output, Input, State
import plotly.express as px
import pandas as pd
import numpy as np
import dash_bootstrap_components as dbc
from Pipeline import *
from io import StringIO
import datetime
import binascii

app = Dash(__name__, suppress_callback_exceptions=True)
input_properties = ["CompositionID"]
GUID_LENGTH = 32
labels = []
MARGIN = 0.3

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
    
    html.Div([item for pair in zip([f"{ALL_INPUT['Property'].iloc[i]} {ALL_INPUT['Units'].iloc[i]}" for i in range(len(ALL_INPUT['Property']))], 
    [current[1]['Type'].inputstructure(current[1]['Property'] + '-input') for current in ALL_INPUT.iterrows()]) for item in pair], id='inputs'),
        
    dbc.Alert(id='alert', is_open=False, duration=4000),
    html.Button('Add Data', id='add-data-button', n_clicks=0)
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
    [State(current[1]['Property'] + '-input', current[1]['Type'].getStructureValue()) for current in ALL_INPUT.iterrows()],
    prevent_initial_call=True
)
def input_data(n_clicks, *args):
        #Check the correctness of the input
    compositions = check_validity(args)
    if isinstance(compositions, str):
        return [compositions, True]
    insert_new_data(compositions)
    return ['Data submitted successfully', True]

@app.callback([Output('file-alert', 'children'), Output('file-alert', 'is_open')],
              Input('upload-file', 'contents'),
              State('upload-file', 'filename'),
              prevent_initial_call=True)
def update_output(contents, filename):
    if contents is not None:
        children = parse_contents(contents, filename)
        return [children, True]

@app.callback(
    Output('container', 'children'),
    Input('form-options', 'data')
)
def generate_options(a):
    form_options = get_choices()
    form_elements = []
    for category in form_options:
        column = [html.Label(category['Title']), 
        dcc.RadioItems(
            id=category['Title'] + '-radio',  # ID for callback reference
            options=[
                {'label': 'and', 'value': 'and'},
                {'label': 'or', 'value': 'or'},
            ],
            value='or'  # Default selected value
        )]
        variables = PROPERTY if category['Title'] == 'Dependent variables' else INPUT
        if category['Title'] == 'Dependent variables' or category['Title'] == 'Independent variables':
            for index, row in variables.iterrows():
                structure = row['Type'].selectstructure(row['Property'])
                labels.append(row['Property'])
                if structure:
                    column.append(structure)
            column = html.Form(id=category["Title"], className='column', style={'flex': '1', 'padding': '10px', 'flex-direction': 'row'}, children=column)
        else:
            for label in category['Options']:
                labels.append(label)
                checkbox = dcc.Checklist(id=label + '-checkbox', options=[label], value=[])
                min_input = dcc.Input(id=label + '-min', type='number', disabled=False, value=None)
                max_input = dcc.Input(id=label + '-max',type='number', disabled=False, value=None)
                column += [
                    html.Div([checkbox,

                        # Min input with label
                        dbc.Col([
                            dbc.Row([html.Label('Min:'), min_input])
                        ]),

                        # Max input with label
                        dbc.Col([
                            dbc.Row([html.Label('Max:'), max_input])
                        ]),
                    ])]
            column = html.Form(id=category["Title"], className='column', style={'flex': '1', 'padding': '10px', 'flex-direction': 'row'}, children=column)
        form_elements.append(column)
    return form_elements

# Home page call back functions
def generate_options_df(form_elements):
    options = {}
    for current in form_elements:
        current_column = current['props']['children']
        column_name = current_column[0]['props']['children']
        options[column_name] = {LOGIC:current_column[1]['props']['value']}
        for i in range(2, len(current_column)):
            current_variable = current_column[i]
            current_structure = current_variable['props']['children']
            if current_structure[0]['props']['value']:
                current_label = current_structure[0]['props']['value'][0]
                options[column_name][current_label] = {}
                try:
                    current_type = ALL_INPUT.loc[ALL_INPUT['Property'] == current_label, 'Type'].values[0]
                    min_value = current_type.verify(current_label, current_structure[1]['props']['children'][0]['props']['children'][1]['props'][current_type.structureValue])
                    options[column_name][current_label]['min'] = None if isinstance(min_value, str) else min_value
                    max_value = current_type.verify(current_label, current_structure[2]['props']['children'][0]['props']['children'][1]['props'][current_type.structureValue])
                    options[column_name][current_label]['max'] = None if isinstance(max_value, str) else max_value
                except IndexError as e:
                    options[column_name][current_label]['min'] = current_structure[1]['props']['children'][0]['props']['children'][1]['props']['value']
                    options[column_name][current_label]['max'] = current_structure[2]['props']['children'][0]['props']['children'][1]['props']['value']

    df = generate_df(options)
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
    if 'ExperimentID' in df.columns:
        df['ExperimentID'] = df['ExperimentID'].apply(lambda x: binascii.hexlify(x).decode('utf-8'))
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
    variable_names = set(df.columns.tolist())
    variable_names.discard('ID')
    properties = set()
    for current in variable_names:
        if current in set(PROPERTY['Property']):
            properties.add(current)
    for current in properties:
        variable_names.discard(current)
    variable_names = list(variable_names)
    properties = list(properties)
    if len(variable_names) < 1:
        return html.Div('Please select at least one independent variables.')
    result = []
    hover_template_parts = [f"{current}: %{{customdata[{i}]}}" for i, current in enumerate(properties)]
    hover_template = '<br>'.join(hover_template_parts) + '<extra></extra>'
    property_minmax = {}
    for current in properties:
        property_minmax[current] = [min(df[current]), max(df[current])]
        property_minmax[current].append(property_minmax[current][1] - property_minmax[current][0])
    if len(variable_names) == 1:
        result = [px.scatter(df, x=variable_names[0], y=i) for i in properties]
        for current, property in zip(result, properties):
            current.update_traces(customdata=df[properties].to_numpy(), 
                    hovertemplate=
                        variable_names[0] + ': %{x}<br>' +
                        hover_template
                    )
            current.update_layout(
                        scene=dict(
                            yaxis=dict(range=[property_minmax[property][0] - MARGIN * property_minmax[property][2], 
                            property_minmax[property][1] + MARGIN * property_minmax[property][2]])
                        )
                    )
    else:
        for i in range(len(variable_names)):
            for j in range(i + 1, len(variable_names)):
                new = [px.scatter_3d(df, x=df[variable_names[i]], y=df[variable_names[j]], z=k) for k in properties]
                for current, property in zip(new, properties):
                    current.update_traces(customdata=df[properties].to_numpy(), 
                    hovertemplate=
                        variable_names[i] + ': %{x}<br>' +
                        variable_names[j] + ': %{y}<br>' +
                        hover_template
                    )
                    current.update_layout(
                        scene=dict(
                            zaxis=dict(range=[property_minmax[property][0] - MARGIN * property_minmax[property][2], 
                            property_minmax[property][1] + MARGIN * property_minmax[property][2]])
                        )
                    )
                result += new
    return [dcc.Graph(figure=i) for i in result]

if __name__ == '__main__':
    app.run_server(debug=True)