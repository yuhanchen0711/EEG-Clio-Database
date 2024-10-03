import datetime
import pandas as pd
from dash import Dash, dash_table, html, dcc
import dash_bootstrap_components as dbc
def getverifyNumberFunction(min, max, integer=False):
    def result(property, number):
        if not isinstance(number, (int, float)):
            return f'{property} must be a number!'
        if number < min:
            return f'{property} must be greater than {min}!'
        elif number > max:
            return f'{property} must be less than {max}!'
        elif integer and not isinstance(number, int):
            return f'{property} must be integer!'
        return number
    return result

def verifyCompositionID(property, str):
    # Check compositionID
    error_comp_id = 'Please enter a valid composition ID.'
    splitted_string = str.split('|')
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
    return {'Solvents': {'solvent':solvents, 'percentage':percentage}, 'Salts': {'salt':salts, 'molality':molality}}

def getVerifyDateFunction(allowed_formats):
    def verifyDate(property, date_string):
        epoch = datetime.date(1970, 1, 1)
        for input_format in allowed_formats:
            try:
                date_obj = datetime.datetime.strptime(date_string, input_format).date()
                result = (date_obj - epoch).days
                return result
            except ValueError as e:
                pass
        return f'{property} must be in MM/DD/YY format!'
    return verifyDate

def getNumberInput(id):
    return dcc.Input(id=id, type='number', value=None), 'value'

def getStringInput(id):
    return dcc.Input(id=id, type='text', value=None), 'value'

def getDateInput(id):
    return dcc.DatePickerSingle(
            id=id,
            date=datetime.date.today()  # set today's date as the default
        ), 'date'

def getNumberFilter(id):
    return html.Div([
        # Checkbox
        dcc.Checklist(
            id=id + '-checkbox',
            options=[id],
            value=[],
        ),

        # Min input with label
        dbc.Col([
            dbc.Row([html.Label('Min:'), dcc.Input(
                id=id + '-min',
                type='number',
                disabled=False,
                value=None
            )])
        ]),

        # Max input with label
        dbc.Col([
            dbc.Row([html.Label('Max:'), dcc.Input(
                id=id + '-max',
                type='number',
                disabled=False,
                value=None
            )])
        ]),
    ])

def getDateFilter(id):
    return html.Div([
        # Checkbox
        dcc.Checklist(
            id=id + '-checkbox',
            options=[id],
            value=[],
        ),

        # Min input with label
        dbc.Col([
            dbc.Row([html.Label('From:'), dcc.DatePickerSingle(
            id=id + '-min',
            date=datetime.date.today()  # set today's date as the default
            )])
        ]),

        # Max input with label
        dbc.Col([
            dbc.Row([html.Label('To:'), dcc.DatePickerSingle(
            id=id + '-max',
            date=datetime.date.today()  # set today's date as the default
            )])
        ])
    ])

def displayDate(day):
    epoch = datetime.date(1970, 1, 1)
    return epoch + datetime.timedelta(days=day)