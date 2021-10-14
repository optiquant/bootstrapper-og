from _model_v1.useful_functions import *
import model_control
import pandas as pd
import numpy as np
import re
import pprint
from collections import namedtuple

# todo: connect to model control
input_folder = 'C:\\Users\\vdesai\\Git\\bootstrapper-og\\_model_input\\_csv_drivers\\'
asset_level_drivers = pd.read_csv(input_folder+'asset_level_drivers.csv')

# type curve namedtuple for TCs and EURs by production stream
TypeCurve = namedtuple('TypeCurve',
                       ['name',
                        'oil',
                        'gas',
                        'water',
                        'ethane',
                        'propane',
                        'n_butane',
                        'iso_butane',
                        'nat_gasoline',
                        'oil_eur',
                        'gas_eur',
                        'water_eur',
                        'ethane_eur',
                        'propane_eur',
                        'n_butane_eur',
                        'iso_butane_eur',
                        'nat_gasoline_eur'])


class TypeCurves:
    def __init__(self):
        # read in type curves and sort alphabetically
        self.type_curves_oil = pd.read_csv(input_folder + "type_curves_oil.csv")
        self.type_curves_oil.columns = [_.replace(" Oil", "") for _ in self.type_curves_oil.columns]
        self.type_curves_oil = self.type_curves_oil[sorted(self.type_curves_oil.columns)]

        self.type_curves_gas = pd.read_csv(input_folder + "type_curves_gas.csv")
        self.type_curves_gas.columns = [_.replace(" Gas", "") for _ in self.type_curves_gas.columns]
        self.type_curves_gas = self.type_curves_gas[sorted(self.type_curves_gas.columns)]

        self.type_curves_water = pd.read_csv(input_folder + "type_curves_water.csv")
        self.type_curves_water.columns = [_.replace(" Water", "") for _ in self.type_curves_water.columns]
        self.type_curves_water = self.type_curves_water[sorted(self.type_curves_water.columns)]

        # print(f'\n| Oil type curves input:\n{self.type_curves_oil}')
        # print(f'\n| Gas type curves input:\n{self.type_curves_gas}')
        # print(f'\n| Water type curves input:\n{self.type_curves_water}')

        self.tc_eur_oil = self.type_curves_oil.sum(axis=0)
        self.tc_eur_gas = self.type_curves_gas.sum(axis=0)
        self.tc_eur_water = self.type_curves_water.sum(axis=0)
        # print(f'\n| Oil type curves EUR (MBbl):\n{self.tc_eur_oil}')
        # print(f'\n| Gas type curves EUR (MMcf):\n{self.tc_eur_gas}')
        # print(f'\n| Water type curves EUR (MBbl):\n{self.tc_eur_water}')

        self.tc_dict = dict(enumerate([_ for _ in self.type_curves_oil.columns]))
        # print(f'\n| Type Curves Modeled:')
        # pprint.pprint(self.tc_dict)

        self.gross_type_curves()

    def __repr__(self):
        return f"TypeCurves object: attributes --> {[_ for _ in self.__dict__.keys()]}"

    def gross_type_curves(self):
        return {'type_curves_oil': self.type_curves_oil,
                'type_curves_gas': self.type_curves_gas,
                'type_curves_water': self.type_curves_water
                }

    def get_type_curve(self, sub_asset, type_curve_name=''):
        '''Returns a namedtuple TypeCurve instance whose attributes are gross type curves and EURs for each production stream.'''
        for tc_name in self.tc_dict.values():
            if type_curve_name == tc_name:
                name = tc_name
                oil = self.type_curves_oil[tc_name]
                gas = self.type_curves_gas[tc_name]
                water = self.type_curves_water[tc_name]
                oil_eur = self.tc_eur_oil[tc_name]
                gas_eur = self.tc_eur_gas[tc_name]
                water_eur = self.tc_eur_water[tc_name]

                ### NGL YIELDS ###
                ngl_fields = [_ for _ in asset_level_drivers.columns if
                              'NGL Yield - Actual - ' in _]

                # calc actual ngl yields based on ethane recovery/rejection
                ngl_yields_actual = {
                    k: float(v) for k, v in dict(asset_level_drivers.loc[sub_asset, ngl_fields])
                }

                ngl_fixed_recoveries = model_control.ngl_fixed_recoveries[model_control.ethane_mode]

                ngl_yields_theoretical = dict(asset_level_drivers.loc[sub_asset, ngl_fields])
                # convert string numerals to float
                ngl_yields_theoretical = {
                    fixed_recov_k: yields_v / fixed_recov_v for (yields_k, yields_v), (fixed_recov_k, fixed_recov_v) in zip(ngl_yields_actual.items(), ngl_fixed_recoveries.items())
                }

                # ngl_fixed_recoveries = model_control.ngl_fixed_recoveries[model_control.ethane_mode]
                #
                # ngl_yields_theoretical = dict(asset_level_drivers.loc[sub_asset, ngl_fields])
                # # convert string numerals to float
                # ngl_yields_theoretical = {
                #     k: float(v) for k, v in ngl_yields_theoretical.items()
                # }
                #
                # ngl_yields_actual = {
                #     fr_k: yields_v * fr_v for (yields_k, yields_v), (fr_k, fr_v) in zip(
                #         ngl_yields_theoretical.items(), ngl_fixed_recoveries.items()
                #     )
                # }

                print('\n| Theoretical NGL yields (Bbl/Mcf):', ngl_yields_theoretical)
                print('| Ethane model modeled:', model_control.ethane_mode)
                print('| Actual NGL yields (Bbl/Mcf):', ngl_yields_actual)


                # make NGL type curves for the single well
                ethane = gas * ngl_yields_actual['ethane'] / 1000
                propane = gas * ngl_yields_actual['propane'] / 1000
                n_butane = gas * ngl_yields_actual['n_butane'] / 1000
                iso_butane = gas * ngl_yields_actual['iso_butane'] / 1000
                nat_gasoline = gas * ngl_yields_actual['nat_gasoline'] / 1000

                ethane_eur = ethane.sum(axis=0)
                propane_eur = propane.sum(axis=0)
                n_butane_eur = n_butane.sum(axis=0)
                iso_butane_eur = iso_butane.sum(axis=0)
                nat_gasoline_eur = nat_gasoline.sum(axis=0)

                sw_tc_gross = TypeCurve(name=name,
                                        oil=oil,
                                        gas=gas,
                                        ethane=ethane,
                                        propane=propane,
                                        n_butane=n_butane,
                                        iso_butane=iso_butane,
                                        nat_gasoline=nat_gasoline,
                                        water=water,
                                        oil_eur=oil_eur,
                                        gas_eur=gas_eur,
                                        ethane_eur=ethane_eur,
                                        propane_eur=propane_eur,
                                        n_butane_eur=n_butane_eur,
                                        iso_butane_eur=iso_butane_eur,
                                        nat_gasoline_eur=nat_gasoline_eur,
                                        water_eur=water_eur)
                print(f'| Single well EURs >>')
                print(f'|-- oil (mbbl): {sw_tc_gross.oil_eur: .2f}')
                print(f'|-- gas (mmcf): {sw_tc_gross.gas_eur: .2f}')
                print(f'|-- water (mbbl): {sw_tc_gross.water_eur: .2f}')
                print(f'|-- ethane (mbbl): {sw_tc_gross.ethane_eur: .2f}')
                print(f'|-- propane (mbbl): {sw_tc_gross.propane_eur: .2f}')
                print(f'|-- n_butane (mbbl): {sw_tc_gross.n_butane_eur: .2f}')
                print(f'|-- iso_butane (mbbl): {sw_tc_gross.iso_butane_eur: .2f}')
                print(f'|-- nat_gasoline (mbbl): {sw_tc_gross.nat_gasoline_eur: .2f}')

        return sw_tc_gross


def load_gross_type_curves():
    return TypeCurves()
