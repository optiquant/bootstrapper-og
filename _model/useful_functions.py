import pandas as pd
import numpy as np
from collections import *
from functools import *
from time import *
import os
from pyexcelerate import *



def useful_functions(func_to_add=None, toPrint=False):
    '''prints a list of useful functions __doc__. Use func_to_add to add a new function to the dict.'''
    global uf
    try:
        uf = globals()['uf']
    except (NameError, KeyError):
        uf = {}

    if func_to_add and func_to_add not in uf.keys():
        # add string function name and __doc__ to useful functions dict
        uf[func_to_add] = globals()[func_to_add].__doc__
        uf = dict(sorted(uf.items()))
        if toPrint:
            print(uf)

    else:
        return uf


def root_folder_model_input():
    '''Root folder for csv drivers'''
    filepath = f'C:/Users/vdesai/Git/bootstrapper-og/_model_input/_csv_drivers/'
    print(f'\n| Model input root folder: {filepath}')
    return {'parent_folder': filepath.strip('_csv_drivers/'),
            'root_folder': filepath}


commodity_reference = {
    'WTI CMA': ['nymex',
                'CS',
                'Wti Financial Futures',
                'wti_cma',
                '$/Bbl',
                5.00],
    'WTI Oil': ['nymex',
                'CL',
                'Light Sweet Crude Oil Futures',
                'wti',
                '$/Bbl',
                5.00],
    'MidCush - WTT': ['nymex',
                      'WTT',
                      'Wti Midland (argus) Vs. Wti Trade Month Futures',
                      'midcush_wtt',
                      '$/Bbl',
                      1.00],
    'MidCush - FF': ['nymex',
                     'FF',
                     'Wti Midland(argus) Vs. Wti Financial Futures',
                     'midcush_ff',
                     '$/Bbl',
                     1.00],
    'Brent Oil': ['nymex',
                  'CY',
                  'Brent Financial Futures',
                  'brent',
                  '$/Bbl',
                  5.00],
    'WTI Houston Oil': ['nymex',
                        'HCL',
                        'Wti Houston Crude Oil Futures',
                        'wti_hou',
                        '$/Bbl',
                        5.00],
    'HH Gas': ['nymex',
               'NG',
               'Henry Hub Natural Gas Futures',
               'hh',
               '$/MMBtu',
               0.50],
    'Waha Diff': ['nymex',
                  'NW',
                  'Waha Natural Gas (platts Iferc) Basis Futures',
                  'waha_gas_diff',
                  '$/MMBtu',
                  0.50],
    'HSC Gas Diff': ['nymex',
                     'NHN',
                     'Houston Ship Channel Natural Gas (platts Iferc) Ba',
                     'hsc_gas_diff',
                     '$/MMBtu',
                     0.50],
    'Ethane Mt.Belvieu': ['nymex',
                          'C0',
                          'Mont Belvieu Ethane (opis) Futures',
                          'ethane',
                          '$/gal',
                          0.05],
    'Propane Mt.Belvieu LDH': ['nymex',
                               'B0',
                               'Mont Belvieu Ldh Propane (opis) Futures',
                               'propane',
                               '$/gal',
                               0.10],
    'n-Butane': ['nymex',
                 'D0',
                 'Mont Belvieu Normal Butane (opis) Futures',
                 'n_butane',
                 '$/gal',
                 0.1],
    'iso-Butane': ['nymex',
                   '8I',
                   'Mont Belvieu Iso-butane (opis) Futures',
                   'iso_butane',
                   '$/gal',
                   0.1],
    'Nat. Gasoline': ['nymex',
                      '7Q',
                      'Mont Belvieu Natural Gasoline (opis) Futures',
                      'nat_gasoline',
                      '$/gal',
                      0.20]}

oil_list = list(commodity_reference)[0:6]
print(oil_list)
gas_list = list(commodity_reference)[6:9]
print(gas_list)
ngl_list = list(commodity_reference)[9:]
print(ngl_list)



def get_chart_axis_unit(c_nick: str, print_result=False):
    '''Returns base unit for charts from nickname.'''
    c = \
    [chart_unit for name, (exch, code, desc, nick, unit, chart_unit) in commodity_reference.items() if nick == c_nick][
        0]
    if print_result:
        print(f"Chart axis unit for '{c_nick}': {c}")
    useful_functions('get_chart_axis_unit')
    return c



def get_comdty_unit(c_nick: str, print_result=False):
    '''Returns trading commodity product unit from nickname.'''
    c = [unit for name, (exch, code, desc, nick, unit, chart_unit) in commodity_reference.items() if \
         nick == c_nick or name == c_nick][0]
    if print_result:
        print(f"Commodity product unit for '{c_nick}': {c}")
    useful_functions('get_comdty_unit')
    return c

#################################
def get_ngl_nicks():
    '''Returns a list of ngl c_nick nicknames.'''
    ngl_comdty_nicks = []
    for c_name in ngl_list:
        ngl_comdty_nicks.append(get_comdty_nick(c_name))
    return ngl_comdty_nicks


def get_comdty_name(c_nick: str, print_result=False):
    '''Returns trading commodity product name from nickname.'''
    c = [name for name, (exch, code, desc, nick, unit, chart_unit) in commodity_reference.items() if nick == c_nick][0]
    if print_result:
        print(f"Commodity product name for '{c_nick}': {c}")
    useful_functions('get_comdty_name')
    return c



def get_comdty_desc(c_nick: str, print_result=False):
    '''Returns trading commodity product description from nickname.'''
    c = [desc for name, (exch, code, desc, nick, unit, chart_unit) in commodity_reference.items() if nick == c_nick][0]
    if print_result:
        print(f"Commodity description for '{c_nick}': {c}")
    useful_functions('get_comdty_name')
    return c


def get_comdty_code(c_nick: str, print_result=False):
    '''Returns trading commodity product code from nickname.'''
    c = [code for name, (exch, code, desc, nick, unit, chart_unit) in commodity_reference.items() if nick == c_nick][0]
    if print_result:
        print(f"Commodity product code for '{c_nick}': {c}")
    useful_functions('get_comdty_code')
    return c



def get_comdty_nick(search_term: str, search_term_type='comdty_name', print_result=False):
    '''Returns trading commodity nickname from name.
    Args:
        |-- search_term, str: the term to look up in the commodity reference
        |-- type, str: any of ["comdty_name", "comdty_desc"]
        |-- print_result, bool: print the result
    Returns:
        The commodity nickname used within the model
        '''

    if search_term_type == 'comdty_name':
        c = [nick for name, (exch,
                             code,
                             desc,
                             nick,
                             unit,
                             chart_unit) in commodity_reference.items() if name == search_term
             ][0]
    elif search_term_type =='comdty_desc':
        c = [nick for name, (exch,
                             code,
                             desc,
                             nick,
                             unit,
                             chart_unit
                             ) in commodity_reference.items() if desc == search_term
             ][0]
    else:
        print(f'!! Invalid search term: {search_term} or type: {search_term_type}')

    if print_result:
        print(f"Commodity nickname for '{search_term}': {c}")
    useful_functions('get_comdty_nick')
    return c



def to_df_to_dict(d):
    '''Passes d to a DataFrame constructor and then converts it to a dict.'''
    return dict(pd.DataFrame(d))


def add_days(datetime, days_to_add):
    '''Passes d to a DataFrame constructor and then converts it to a dict.'''
    return datetime + pd.to_timedelta(days_to_add, unit='D')


def dict_nested_levels(d, recursive=False):
    '''Returns the number of nested dictionaries (levels) within d. If d has no nested dictionaries, function returns 0.'''

    def inner(d, levels):
        if type(d) == dict or type(d) == OrderedDict:
            levels += 1
            key = list(d.keys())[0]
            return inner(d[key], levels)
        else:
            return levels

    useful_functions('dict_nested_levels')
    return inner(d, levels=-1)



def dict_drill_down(d,
                    levels=0,
                    key_sequence=[0],
                    return_values=False,
                    silent=False
                    ):
    '''Returns the object (key-value) within a nested dictionary d that is "levels" levels deep.
    >> Arguments:
    | -- d: a nested dictionary
    | -- levels (int): the number of levels to drill down into for nested dict "d"
    | -- key_sequence (list): list of key indexes for each *level* of the nested dictionary. Total
                elements (length of) key_sequence list must equal (levels+1). If key_sequence
                is not specified correctly for a particular level, the returned key-value defaults
                to the *final* key at that level.
    | -- return_values (bool): returns object at nested level. Use return_values = False (default) to speed
                up exploration of the nested dictionary.
                e.g. levels = 0 (default) --> will return key-value information for the input dictionary d (level 0)
                e.g. levels = 1 --> will return object at *first nested level* of the input dictionary d
                e.g. Correct specification of key_sequence:
                    >> ...key_sequence = [0,2,1], levels=2) --> will return *first* key at level 0, *third*
                        key at level 1, and *second* key at level 2.
                e.g. Incorrect specification of key_sequence:
                    >> ...key_sequence = [0,2], levels=2) --> will return *first* key at level 0, *third*
                        key at level 1, and *final* key at level 2.
    | -- silent (bool): Passing True will not print text responses to the console. Default is False.'''

    if not (silent):
        if len(key_sequence) != levels + 1:
            print('''\n!! WARNING: key_sequence does not specify an index for each level requested. Using
                    final keys for unspecified levels.\n''')

    # inner function to add level_index argument
    def inner(d, levels, key_sequence, level_index=0):
        try:
            key = list(d.keys())[key_sequence[level_index]]
        except IndexError:
            # if key does not exist, use final key
            key = list(d.keys())[len(d.keys()) - 1]
        except AttributeError:
            # if not a dict, return object
            return d

        if not (silent):
            print('\n| Level {0} total keys = {1}\n| --- {2}\n| --- Return type: {3}'.format(
                level_index,
                len(d.keys()),
                list(enumerate(d.keys())),
                type(d[key])
            ))
            print(f'| >>> Drilling down on Level {level_index} key: {key}')

        if type(d) == dict or type(d) == OrderedDict and level_index < levels:
            # if d is a dictionary, drill down again to the next level_index
            return inner(d[key], levels, key_sequence, level_index=level_index + 1)
        else:
            if return_values:
                if not (silent):
                    print(f'| >>> RETURNING Level {level_index} value for key: {key}')
                # return the value if drill_down_level has been reached
                return d[key]

    useful_functions('dict_drill_down')
    return inner(d, levels, key_sequence, level_index=0)



def dict_structure(d, drilldown=False, key_sequence=[0], silent=False):
    '''Shows the key structure of a nested dictionary.
    Arguments:
    | -- d (dict or OrderedDict): nested dictionary.
    | -- drilldown (bool): False = display the dict_structure only. True = return values according to key_sequence
    |       and levels.
    | -- key_sequence (list of int): List of integer indexes for nested keys to be returned. One key should be
    |        specified for each level requested. Default is the first key at each level, and the last value at the final
    |        nested level.
    | -- levels (int): Number of levels to drill down if drilldown == False.
    | -- silent (bool): Passing True will not print text responses to the console. Default is False.'''

    useful_functions('dict_structure')
    nested_levels = dict_nested_levels(d)

    if not (drilldown):
        return dict_drill_down(d,
                               key_sequence=[0],
                               levels=nested_levels,
                               return_values=False,
                               silent=False
                               )
    else:
        return dict_drill_down(d,
                               key_sequence=key_sequence,
                               levels=len(key_sequence) - 1,
                               return_values=True,
                               silent=silent
                               )



def dict_deep_loop(d, key_sequence=[0]):
    '''Coming soon: Returns objects from the deepest nested level of nested dict d.
    Arguments:
    | -- d: dict or OrderedDict(). nested dictionary
    | -- key_sequence: list of ints. key sequence to drill down on, and return the deepest object.
    '''
    useful_functions('dict_deep_loop')
    print('Coming soon.')



# function timer
def timer(fn):
    '''Use as decorator to time functions. Adds the time for this function to the function_timer_dict.'''
    global function_timer_dict
    if 'function_timer_dict' not in globals():
        function_timer_dict = dict()

    @wraps(fn)
    def inner(*args, **kwargs):
        start = perf_counter()
        result = fn(*args, **kwargs)
        end = perf_counter()
        elapsed = end - start
        print(f'\n| {fn.__name__} ran in: {elapsed:.5f} seconds.\n')
        function_timer_dict[fn.__name__] = f'{elapsed:.5f} seconds'
        return result

    useful_functions('timer')
    return inner



# @timer
def list_unique(s, silent = False):
    '''Returns unique elements of a list s.'''
    # set/list version

    unique_dict = {v:k for k,v in dict(s).items()}
    if not(silent):
        print(f'\n| # of unique elements >> {len(unique_dict)} --> {[_ for _ in unique_dict.keys()]}')
    useful_functions('list_unique')
    return [_ for _ in unique_dict]


def datetime_from_ymd(year=1969, month=12, day=28, end_period=False):
    '''Returns pd.to_datetime() for input year, month, and day. Setting end_period = True will return end-of-period date.'''
    string_date = str(year) + '/' + str(month) + '/' + str(day)

    if end_period:
        datetime = pd.to_datetime(string_date) + MonthEnd(0)
    else:
        datetime = pd.to_datetime(string_date)

    useful_functions('datetime_from_ymd')
    return datetime



def string_date(date):
    '''Returns yyyy-mm-dd from pd.to_datetime() date.'''
    useful_functions('string_date')
    return pd.to_datetime(date).strftime('%Y-%m-%d')



def xldate_to_datetime(xldate):
    '''Converts excel date formate to string_date'''
    temp = pd.to_datetime('1899/12/30')
    if xldate != np.nan:
        delta = pd.to_timedelta(xldate, unit='D')
    else:
        delta = pd.to_timedelta(0, unit='D')
    useful_functions('xldate_to_datetime')
    return temp + delta



def intersect(a, b, silent=True):
    '''Returns a tuple comprised of: (intersection of a and b, unique elements in a, unique elements in b)'''
    intersection = [value for value in a if value in b]
    remainder_a = [value for value in a if value not in b]
    remainder_b = [value for value in b if value not in a]

    if not (silent):
        print('\n| Intersection: {0} | Unique in 1: {1} | Unique in 2: {2}'.format(
            intersection, remainder_a, remainder_b))

    useful_functions('intersect')
    return intersection, remainder_a, remainder_b



def xl_column(num):
    '''Returns an alphabetical excel column reference from a numerical column reference.
    i.e. "1" returns "A". "27" returns "AA".'''
    base = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U",
            "V", "W", "X", "Y", "Z"]
    baseln = len(base)
    idx = [""] + base
    num = num - 1

    # current excel version has 16384 columns (A --> XFD), so multiindex needs to have a minimum of 3 levels:
    #   (26x26x26 = 17576 > 16384 columns)

    index = pd.MultiIndex.from_product([idx, idx, idx], names=['level 1', 'level 2', 'level 3'])
    df = pd.DataFrame(index=index)
    df = df.drop("", level='level 3')
    df = df.iloc[:baseln].append(df.drop("", level='level 2'))
    df['val'] = 1

    if num < baseln:
        xlcol = str(df.iloc[num].name[2])
    elif num >= baseln and num < baseln ** 2:
        xlcol = str(df.iloc[num].name[1]) + str(df.iloc[num].name[2])
    else:
        xlcol = str(df.iloc[num].name[0]) + str(df.iloc[num].name[1]) + str(df.iloc[num].name[2])

    useful_functions('xl_column')
    return xlcol



def save_to_excel(output_dataframe, folder='default', filename='test_file.xlsx'):
    '''Outputs a dataframe data to the desired folder and filename. Will create new folder if folder does not exist.
     Default save folder is: 'C:/Users/vdesai/Desktop/Model/Python/__model tests/'''
    output_dataframe = pd.DataFrame(output_dataframe).copy(deep=True)
    # make sure it's a valid dataframe
    if isinstance(output_dataframe, pd.DataFrame):
        if folder == 'default':
            save_folder = f'C:/Users/vdesai/Desktop/Model/Python/__model tests/'
            full_filepath = f'{save_folder}{filename}'
        elif not (os.path.exists(f'{folder}')):
            # if folder does not exist, create it
            os.makedirs(f'{folder}')
            full_filepath = f'{folder}{filename}'
        else:
            full_filepath = f'{folder}{filename}'
        output_dataframe.reset_index(inplace=True)
        print(full_filepath)
        data_array = np.array(output_dataframe)
        data_array = np.append([output_dataframe.columns],data_array, axis=0)

        wb = Workbook()
        output_sheet = wb.new_sheet('Data')
        output_sheet.range('A1', xl_column(len(data_array[0])) + str(len(data_array))).value = data_array
        try:
            wb.save(full_filepath)
            print(f'| File saved successfully to: {full_filepath}')
        except (PermissionError, FileNotFoundError):
            input(f'!! {full_filepath} not found or currently open. Close and hit enter >>>')
            wb.save(full_filepath)
            print(f'| File saved successfully to: {full_filepath}')
    else:
        raise TypeError('!! Invalid datatype passed. Must pass a dataframe.')

    useful_functions('save_to_excel')



def save_to_json(df, folder, filepath, df_name='DataFrame'):
    """
    Saves dataframe to .json file at filepath. df_name is optional.
    """
    useful_functions('save_to_json')

    try:
        df.to_json(filepath, date_format='iso')
        print(f'| {df_name} saved to {filepath}')
    except (FileNotFoundError, ValueError, PermissionError):
        os.makedirs(folder)
        df.to_json(filepath, date_format='iso')
        print(f'| New folder created. {df_name} saved to {filepath}')
    except FileExistsError:
        df.to_json(filepath, date_format='iso')
        print(f'| New file created. {df_name} saved to {filepath}')



def save_chart(fig, folder, filepath):
    '''Saves plotly requested_chart to .html file at filepath.
    Arguments:
    | -- folder: parent folder for the filepath. Will create folder if it does not exist.
    | -- filepath: full filepath (= folder+filename) to save the file'''

    useful_functions('save_chart')
    try:
        fig.write_html(filepath, include_plotlyjs='True')
        print(f'| Chart saved to {filepath}')
    except TypeError:
        raise
    except (FileNotFoundError, ValueError, PermissionError):
        os.makedirs(folder)
        fig.write_html(filepath, include_plotlyjs='True')
        print(f'| New folder created. Chart saved to {filepath}')
    except FileExistsError:
        fig.write_html(filepath, include_plotlyjs='True')
        print(f'| New file created. Chart saved to {filepath}')



def delete_file(filepath):
    global os
    if 'os' not in globals():
        import os
    os.remove(filepath)
    print(f'| File deleted: {filepath}')



def load_colors():
    '''Returns a dict of commodity requested_chart colors for oil (green), gas (red), and NGLs (blue).'''
    global oil_green
    global gas_red
    global ngl_blue

    # enter requested_chart colors in hex
    oil_green_hex = '#005500'
    gas_red_hex = '#ff0025'
    ngl_blue_hex = '#0555ff'

    # RGBA colors as a list
    oil_green = list(int(oil_green_hex.lstrip('#')[i:i + 2], base=16) for i in (0, 2, 4))
    oil_green.append(1.0)
    gas_red = list(int(gas_red_hex.lstrip('#')[i:i + 2], base=16) for i in (0, 2, 4))
    gas_red.append(1.0)
    ngl_blue = list(int(ngl_blue_hex.lstrip('#')[i:i + 2], base=16) for i in (0, 2, 4))
    ngl_blue.append(1.0)

    comdty_colors = {'oil_green': (oil_green, oil_green_hex),
                     'gas_red': (gas_red, gas_red_hex),
                     'ngl_blue': (ngl_blue, ngl_blue_hex)}
    return comdty_colors



def midrange_color(med_color, lim_color, percentile=0.5, to_print=False):
    '''Returns mid-range color for a symmetric color distribution between med_color and lim_color.'''
    med_color = med_color[:3]
    lim_color = lim_color[:3]
    delta_vector = [abs(x - y) for x, y in zip(lim_color, med_color)]
    if percentile <= 0.5:
        delta_pct = percentile / 0.5
    elif percentile > 0.5:
        delta_pct = 1 - (percentile - 0.5) / 0.5
    midrange_color = [round(m * (delta_pct) + l * (1 - delta_pct), 0) for m, l in zip(med_color, lim_color)]
    midrange_color.append(1.0)
    if to_print:
        print(
            f'p: {percentile}\n| --- med_color: {med_color}\n| --- lim_color:{lim_color},\n| --- mid_range_color: {midrange_color}')
    return midrange_color


def hex_to_rgba(hex_color='#ffffff', a=None, values=True):
    r, g, b = list(int(hex_color.lstrip('#')[i:i + 2], base=16) for i in (0, 2, 4))
    if a is not None:
        if not (values):
            rgb_color = f'rgba({r},{g},{b},{a})'
        else:
            rgb_color = r, g, b, a
    else:
        if not (values):
            rgb_color = f'rgb({r},{g},{b})'
        else:
            rgb_color = r, g, b

    return rgb_color



def inclusive_range(array, comparison_range, silent=False):
    '''Returns sub-array in comparison_range that includes array.'''
    # array  = [_ for _ in np.arange(-35,15, step = 2)]
    # comparison_range = [_ for _ in np.arange(-35,50, step = 5)]
    if not(silent):
        print(f'| array: {array}')
        print(f'| comparison_range: {comparison_range}')

    array_min = min(array)
    array_max = max(array)

    # lower and upper bounds of inner_range
    try:
        lower_bound = [_ for _ in comparison_range if _ <= array_min][-1]
    except IndexError:
        if not(silent):
            print(f'| Lower bound below min.')
        lower_bound = min(comparison_range)

    try:
        upper_bound = [_ for _ in comparison_range if _ >= array_max][0]
    except IndexError:
        if not(silent):
            print(f'| Upper bound above max.')
        upper_bound = max(comparison_range)

    start_idx = comparison_range.index(lower_bound)
    end_idx = min(comparison_range.index(upper_bound) + 1, len(comparison_range))
    inclusive_range = comparison_range[start_idx: end_idx]
    if min(inclusive_range) == max(inclusive_range) and min(inclusive_range) != array_min\
            and max(inclusive_range) != array_max:
        inclusive_range = []
        if not (silent):
            print(f'!! array not in comparison_range: inclusive_range is empty >> {inclusive_range}')
    else:
        print(f'| -- inclusive_range:\n   {inclusive_range}')
    return inclusive_range



def dict_like(d):
    '''Returns a dict with the same nested key structure as d, and an initialized null value at the final level (leaf).'''
    if isinstance(d, dict) or isinstance(d, OrderedDict):
        # make a dict like d
        new_dict = type(d)
        new_dict = new_dict()

        for k in d:
            new_dict[k] = dict_like(d[k])

        return new_dict
    else:
        # instantiate object like final leaf
        obj = type(d)
        obj = obj()

        return obj



def function_times():
    '''Returns a list of the time to run functions wrapped with @timer'''
    global function_timer_dict
    k_v_swap_for_sorting = {v: k for k, v in function_timer_dict.items()}

    sorted_function_times = {v: k for k, v in sorted(k_v_swap_for_sorting.items(), reverse=True)}
    print(sorted_function_times)
    return sorted_function_times



def line_to_grid(linear_range=[0, 1, 2, 3], grid_shape=[2, 3]):
    '''Return a list of 2-D coordinates corresponding to a each element of a 1-D array/list of objects, in shape = grid_shape
    Useful for converting a linear index into a coordinate grid for charting purposes. Note that elements of
    linear range that do not fit in a grid of shape = grid_shape will be truncated.
    Arguments:
    | -- linear_range, list of ints: input indexes to be converted to a 2-d grid.
    | -- grid_shape, tuple of ints: the shape of the coordinate grid returned

    Returns:
        a dict with keys = indexes of the linear_range, and values = grid coordinates.
    '''

    # make a list of indices for the linear_range
    linear_range = [_ for _ in dict(enumerate(linear_range))]
    # grid_shape = [2, 3]

    # all elements of linear range fit in grid?
    grid = pd.DataFrame(index=range(grid_shape[0]), columns=range(grid_shape[1]))

    grid_coords = []
    for r in grid.index:
        for c in grid.columns:
            grid_coords.append((r + 1, c + 1))

    return dict(zip(linear_range, grid_coords))


