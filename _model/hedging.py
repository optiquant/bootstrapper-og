import _model.model_drivers as model_drivers
import _model.model_control as model_control
from _model.useful_functions import *
import _model.lookup as lookup
import _model.prices as pr

import re
# import bootstrapper_charts as bc

#-----------------------------------------------------------------------------------------------------------------#
#--------------------------------------------# MODEL LEVEL VARIABLES #--------------------------------------------#
#-----------------------------------------------------------------------------------------------------------------#
model_period = model_drivers.model_period
bootstrap_prices = model_drivers.bootstrap_prices
current_hedges = model_drivers.current_hedges
strip_pricing_date = model_control.strip_pricing_date
scenario_time_stamp = model_control.scenario_time_stamp
data_source = model_control
string_default_percentiles = model_control.string_default_percentiles
local_scenario_folder = model_control.get_scenario_root_folders()['local_scenario_folder']
network_scenario_folder = model_control.get_scenario_root_folders()['network_scenario_folder']
# print(model_period, bootstrap_prices)
print(current_hedges)


hedge_type_short_name_dict = {'SWAPS - FIXED PRICE': 'swaps',
                              'COLLARS - 2-WAY': 'collars'}
#---------------------------------------------------------------------------------------------------------------------#
#---------------------------------------------# HEDGE MODULE VARIABLES #---------------------------------------------#
#---------------------------------------------------------------------------------------------------------------------#


def build_hedge_filter():
    '''Builds a dict of the unique values in current_hedges'''
    global current_hedges
    global hedge_filter_dict
    hedge_filter_dict = {}
    for col in current_hedges.columns:
        # make hedge filter
        data = sorted(list_unique(current_hedges[col]))
        hedge_filter_dict[col] = dict(enumerate(data))
    return hedge_filter_dict

build_hedge_filter()
print(hedge_filter_dict)

#---------------------------------------------------------------------------------------------------------------------#
#-----------------------------------------------------# CLASSES #-----------------------------------------------------#
#---------------------------------------------------------------------------------------------------------------------#

class HedgeTrade():
    def __init__(self, args_dict={}, **kwargs):
        if args_dict:
            self.__dict__.update(args_dict)
        else:
            self.__dict__.update(kwargs)

        # these correspond to columns of current_hedges
        self.trade_id = self.__dict__.get('trade_id')
        self.trade_date = self.__dict__.get('trade_date')
        self.counterparty = self.__dict__.get('counterparty')
        self.commodity = self.__dict__.get('commodity')
        self.contract = self.__dict__.get('contract')
        self.hedge_type = self.__dict__.get('hedge_type')
        self.contract_year = self.__dict__.get('contract_year')
        self.contract_months = self.__dict__.get('contract_months')
        self.vol_per_month = self.__dict__.get('vol_per_month')
        self.unit = self.__dict__.get('vol_unit')
        self.swap_price = self.__dict__.get('swap_price')
        self.call_price = self.__dict__.get('call_price')
        self.short_call_price = self.__dict__.get('short_call_price')
        self.long_call_price = self.__dict__.get('long_call_price')
        self.short_put_price = self.__dict__.get('short_put_price')
        self.long_put_price = self.__dict__.get('long_put_price')
        self.premium = self.__dict__.get('premium')
        self.start_mth = self.__dict__.get('contract_start_mth')
        self.end_mth = self.__dict__.get('contract_end_mth')
        self.contract_length_months = self.__dict__.get('contract_length_months')
        self.total_volume = self.__dict__.get('contract_total_volume')

        self.comdty_nick = lookup.lookup('hedge_comdty_price_strip')[self.contract]
        self.settlements = {}
        self.update_master_hedges()


    def __str__(self):
        '''A string description of the object, maybe with properties.'''
        return f'''HedgeTrade object:
        | -- {self.trade_id} > {self.trade_date} > {self.commodity} 
        | -- {self.contract} > {self.hedge_type} 
        | -- {self.contract_months} > {self.contract_year}'''


    def __repr__(self):
        '''A string that represents how one would recreate an object of this class.'''
        return f'''HedgeTrade(
        trade_id = {self.trade_id}, 
        trade_date = {self.trade_date}, commodity = {self.commodity}, contract = {self.contract},
        hedge_type = {self.hedge_type}, contract_year = {self.contract_year}, contract_months = {self.contract_months})'''


    @property
    def info(self):
        return self.__dict__

    def __call__(self):
        return self.info

    def null_fields(self):
        return [_ for _ in self._info.keys() if self._info[_] == None]


    def settle(self, settle_type='bootstrap'):
        '''Settlements for this trade using appropriate price deck. Returns a 3-tuple of
        (model_mth_idx, model_month, settlement_df).

        '''
        global model_period
        global comdty_for_hedge_contract
        global strip_pricing_date

        start_end_range = pd.date_range(start=self.start_mth, end=self.end_mth, freq='M', tz='UTC')
        contract_months_in_model = inclusive_range(
            [_ for _ in start_end_range], [_ for _ in model_period],
            silent=True)
        contract_months_in_model = pd.date_range(
            start=contract_months_in_model[0],
            end=contract_months_in_model[-1],
            tz='UTC'
        )

        settlement_dict = {}

        # get the right comdty_list for the bootstrap or strip pricing case
        comdty_list = lookup.lookup('hedge_comdty_price_bootstrap')[self.contract]

        # make a settlement_df for each comdty in the comdty_list
        for comdty_nick in comdty_list:
            if settle_type == 'bootstrap':
                price_scenarios = string_default_percentiles
            elif settle_type == 'strip':
                price_scenarios = [model_control.get_non_mcs_scenario_label()]

            for price_scenario in price_scenarios:
                # prices for the contracts months, for this price _scenario
                prices = bootstrap_prices[comdty_nick].loc[
                    [_ for _ in bootstrap_prices[comdty_nick].index if _ in contract_months_in_model],
                    price_scenario
                ]
                print(f'\n| Pricing for hedge settlements >> comdty: {comdty_nick} // price_scenario: {price_scenario}:\n{prices}')
                settlement_df = pd.DataFrame(
                    index=prices.index,
                    columns=['commodity', 'contract', 'comdty_nick', 'hedge_type',
                             'volume_hedged', 'volume_unit', 'price_unit', 'swap_price',
                             'call_price', 'market_price', 'swap_spread', 'call_spread',
                             'swap_value_k', 'call_value_k', 'market_value_k',
                             'net_settlement_k']
                )
                settlement_df.fillna(0, inplace=True)
                self.comdty_nick = comdty_nick
                settlement_df['commodity'] = self.commodity
                settlement_df['contract'] = self.contract
                settlement_df['comdty_nick'] = self.comdty_nick
                settlement_df['hedge_type'] = self.hedge_type
                settlement_df['volume_unit'] = self.unit
                settlement_df['price_unit'] = get_comdty_unit(comdty_nick)

                # volumes
                settlement_df['volume_hedged'] = [self.vol_per_month for _ in prices.index]
                # prices
                settlement_df['swap_price'] = [self.swap_price for _ in prices.index]
                settlement_df['call_price'] = [self.call_price for _ in prices.index]
                settlement_df['market_price'] = prices.values  # feed the MCS prices or strip prices here

                ##### settle 'em!
                settlement_df['swap_value_k'] = settlement_df['volume_hedged'] * settlement_df['swap_price'] / 1000
                settlement_df['call_value_k'] = settlement_df['volume_hedged'] * settlement_df['call_price'] / 1000
                settlement_df['market_value_k'] = settlement_df['volume_hedged'] * settlement_df['market_price'] / 1000

                #----------------------------------------------# SWAPS #----------------------------------------------#
                settlement_df['swap_spread'] = ((settlement_df[
                                                     'swap_value_k'] - settlement_df[
                                                     'market_value_k']) / settlement_df[
                                                    'volume_hedged']).fillna(0) * 1000
                if self.hedge_type == 'SWAPS - FIXED PRICE':
                    settlement_df['net_settlement_k'] = settlement_df['swap_value_k'] - settlement_df['market_value_k']
                    settlement_df['call_spread'] = 0

                #-----------------------------------------# COLLARS - 2-WAY #-----------------------------------------#
                if self.hedge_type == 'COLLARS - 2-WAY':
                    settlement_df['call_spread'] = ((settlement_df[
                                                         'call_value_k'] - settlement_df[
                                                         'market_value_k']) / settlement_df[
                                                        'volume_hedged']).fillna(0) * 1000
                    for model_mth in prices.index:
                        if settlement_df.loc[model_mth, 'swap_price'] <= settlement_df.loc[model_mth,'market_price'
                        ] <= settlement_df.loc[model_mth,'call_price'
                        ]:
                            settlement_df.loc[model_mth, 'net_settlement_k'] = 0
                        elif settlement_df.loc[model_mth, 'market_price'] < settlement_df.loc[model_mth,
                                                                                              'swap_price'
                        ]:
                            settlement_df.loc[model_mth, 'net_settlement_k'] = settlement_df.loc[model_mth,
                                                                                                 'swap_value_k'
                                                                               ] - settlement_df.loc[model_mth,
                                                                                                     'market_value_k']
                        elif settlement_df.loc[model_mth, 'market_price'] > settlement_df.loc[
                            model_mth, 'call_price'
                        ]:
                            settlement_df.loc[model_mth, 'net_settlement_k'] = settlement_df.loc[
                                                                                   model_mth, 'call_value_k'] - \
                                                                               settlement_df.loc[
                                                                                   model_mth, 'market_value_k']
                # ADD TO SETTLEMENT DICT
                hedge_type_short_name = hedge_type_short_name_dict[self.hedge_type]
                key = "_".join(
                    [comdty_nick,
                     hedge_type_short_name,
                     'trade',
                     str(self.trade_id),
                     price_scenario]
                )
                settlement_dict[key] = settlement_df

        # update the self.settlements attribute with the settlement_dict
        # (keys: generated identifier above, values = settlement dataframes)
        self.settlements.update(settlement_dict)
        # add the full settlement dictionary to the global master_settlements_dict
        self.add_settlements_to_master()
        # add this HedgeTrade instance to the master_hedge_dict
        # (keys --> trade id, vals --> HedgeTrade objects)
        self.update_master_hedges()

        self.save()

        return self.settlements


    def update_master_hedges(self):
        '''Adds self to the global master_hedge_dict (keys: trade ids, vals: HedgeTrade instances).'''
        global master_hedge_dict
        if 'master_hedge_dict' not in globals():
            master_hedge_dict = {}

        master_hedge_dict[self.trade_id] = self
        print(f'\n| Trade added to master_hedge_dict[ trade_id ]: {self}')


    def add_settlements_to_master(self):
        '''Adds only the settlement dict attribute to the all_hedge_settlements -->
        (keys: trade ids, vals: settlement dictionaries for different price scenarios).
        all_hedge_settlements is a dictionary of hedge settlement dataframes. Its values contain nearly all variables
            that may be required outside the hedging.py module.
                |-- keys >> identifiers for each trade (incl price scenario) e.g. 'hh_swaps_trade_243_Strip 2020-11-11'
                                key format >> f'{comdty_nick}_{hedge_type_short_name}_trade_{trade_id}_{price_scenario}'
                |-- values >> settlement dataframes
                    |---- index = contract months (so dataframes vary in len)
                    |---- columns = commodity (oil, gas, ngl), contract, comdty_nick, hedge_type, volume_hedged,
                    volume_unit,price_unit, swap_price, call_price, market_price, swap_spread, call_spread, swap_value_k,
                    call_value_k, market_value_k, net_settlement_k
        '''
        global all_hedge_settlements
        if 'all_hedge_settlements' not in globals():
            all_hedge_settlements = {}

        all_hedge_settlements[self.trade_id] = self.settlements
        print(f'| Settlements added to all_hedge_settlements[{self.trade_id}] >>>')

        print(f'| -- keys:\n   {[_ for _ in self.settlements]}')
        df = [_ for _ in self.settlements.values()][0]
        columns, index = [_ for _ in df.columns], [_ for _ in df.index]
        print(f'| -- values (dataframe columns):\n   {columns}')
        print(f'| -- values (dataframe index):\n   {index}')
        #p = input('\n >>> Hit enter to continue >>> ')


    def save(self):
        global scenario_time_stamp
        global local_scenario_folder
        global network_scenario_folder
        # save to json
        local_folder = local_scenario_folder + '/hedges/'
        network_folder = network_scenario_folder + '/hedges/'
        ht = self.hedge_type.replace(" ", "_").lower()
        ct = self.contract.replace(" ", "_").lower()
        filename = f'{scenario_time_stamp}_{self.trade_id}_{ct}_{ht}.json'

        save_to_json(pd.DataFrame(self().items()), local_folder, local_folder + filename)
        save_to_json(pd.DataFrame(self().items()), network_folder, network_folder + filename)



#---------------------------------------------------------------------------------------------------------------------#
#----------------------------------------------------# FUNCTIONS #----------------------------------------------------#
#---------------------------------------------------------------------------------------------------------------------#

def get_all_hedge_settlements():
    '''all_hedge_settlements is a dictionary of hedge settlement dataframes. Its values contain nearly all variables
    that may be required outside the hedging.py module.
    |-- keys >> identifiers for each trade (incl price scenario) e.g. 'hh_swaps_trade_243_Strip 2020-11-11'
                key format >> f'{comdty_nick}_{hedge_type_short_name}_trade_{trade_id}_{price_scenario}'
    |-- values >> settlement dataframes
    |---- index = contract months (so dataframes vary in len)
    |---- columns = commodity (oil, gas, ngl), contract, comdty_nick, hedge_type, volume_hedged, volume_unit,
                    price_unit, swap_price, call_price, market_price, swap_spread, call_spread, swap_value_k,
                    call_value_k, market_value_k, net_settlement_k
    '''
    global all_hedge_settlements
    if 'all_hedge_settlements' not in globals():
        print(f'>>> Running hedge settlements / building hedging.all_hedge_settlements...')
        build_all_hedge_settlements_dict()
        return all_hedge_settlements
    else:
        return all_hedge_settlements


def build_all_hedge_settlements_dict():
    '''
    Settles all hedges in the all_hedge_settlements dictionary. all_hedge_settlements is a 2-level nested dictionary of
    hedge settlement dataframes. Its values contain nearly all variables that may be required outside the hedging
     module (see "columns" below).
    |-- keys > trade_ids (0 to number of trades in model period)
    |-- values > dict of settlement dataframes
    |------ keys >> identifiers for each trade (including the price scenario) e.g. 'hh_swaps_trade_243_Strip 2020-11-11'
                key format: f'{comdty_nick}_{hedge_type_short_name}_trade_{trade_id}_{price_scenario}'
    |------ values >>
    |--------- index = contract months (so dataframes vary in len)
    |--------- columns = commodity (oil, gas, ngl), contract, comdty_nick, hedge_type, volume_hedged, volume_unit,
                        price_unit, swap_price, call_price, market_price, swap_spread, call_spread, swap_value_k,
                                            call_value_k, market_value_k, net_settlement_k
    '''
    search_vals = {idx: _ for idx, _ in enumerate(current_hedges['contract_end_mth']) if pd.to_datetime(_) in model_period}
    modeled_hedges = current_hedges.loc[search_vals.keys(), :]
    modeled_hedges.reset_index(inplace=True, drop=True)
    print(modeled_hedges)

    # make a bootstrapper format dataframe for each trade to be settled
    for idx in modeled_hedges.index:
        trade_dict = dict(modeled_hedges.loc[idx, :])
        # create HedgeTrades and settle them
        trade = HedgeTrade(args_dict=trade_dict)
        trade.settle(settle_type='bootstrap')
        trade.settle(settle_type='strip')
    #q = input(f'>>> Master hedge settlement dictionary loaded. Hit enter to continue...')





# todo: put analysis / buy out ceiling of collars
# todo: NEXT: build_hedge_settlement_charts() --> use the results of aggregate_hedges
