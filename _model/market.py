from useful_functions import *
import model_drivers
import pprint

fees_schedule = model_drivers.get_model_level_drivers()['fees_schedule']
bootstrap_prices = model_drivers.get_bootstrap_prices()

# benchmark prices and diffs for each production stream
prices_for_prod_stream = {
    'oil_midland_mbbl': ['wti', 'midcush_ff'],
    'oil_houston_mbbl': ['wti_hou'],
    'gas_waha_bbtu_shrunk': ['hh', 'waha_gas_diff'],
    'gas_hsc_bbtu_shrunk': ['hh', 'hsc_gas_diff'],
    'ngl_ethane_mbbl': ['ethane'],
    'ngl_propane_mbbl': ['propane'],
    'ngl_n_butane_mbbl': ['n_butane'],
    'ngl_iso_butane_mbbl': ['iso_butane'],
    'ngl_nat_gasoline_mbbl': ['nat_gasoline']
}
print(f'\n| Prices for production streams: {prices_for_prod_stream}')

# fees for each production stream
fees_for_prod_stream = {
    'oil_midland_mbbl': fees_schedule.loc[:, 'oil_trucking_fee_per_bbl'],
    'oil_houston_mbbl': fees_schedule.loc[:, 'oil_trucking_fee_per_bbl'],
    'gas_waha_bbtu_shrunk': fees_schedule.loc[:, 'gas_waha_fee_per_mmbtu'],
    'gas_hsc_bbtu_shrunk': fees_schedule.loc[:, 'gas_hsc_fee_per_mmbtu'],
    'ngl_ethane_mbbl': fees_schedule.loc[:, 'ngl_tnf_per_gal'],
    'ngl_propane_mbbl': fees_schedule.loc[:, 'ngl_tnf_per_gal'],
    'ngl_n_butane_mbbl': fees_schedule.loc[:, 'ngl_tnf_per_gal'],
    'ngl_iso_butane_mbbl': fees_schedule.loc[:, 'ngl_tnf_per_gal'],
    'ngl_nat_gasoline_mbbl': fees_schedule.loc[:, 'ngl_tnf_per_gal']
}
print(f'\n| Fee schedules for production streams:\n{fees_for_prod_stream}')


# get the net realized prices for a set of single well NRI production
# streams (NRIVolume namedtuple, defined in economics.py)
def get_net_realized_prices(nri_prod_by_stream: namedtuple,
                            include_fees=True):
    '''Returns realized unit prices (net of fees if desired) for each single well NRI production stream, by referencing the prices_for_prod_stream and fees_for_prod_stream dictionaries.

    Arguments:

    -- nri_volumes_total, namedtuple: an instance of NRIVolume namedtuple, with the NRI production streams for a single well

    -- include_fees, bool: include fees for each production stream, as defined in the fees_schedule

    Returns:
        net_realized_price_dict, dict: a dict of dataframes. keys --> nri_volumes_total production stream attributes. values --> net unit price dataframes with index = model_period, columns = MCS flat price scenarios + Strip pricing
    '''
    net_realized_price_dict = {}
    # create net realized price dataframe for each production stream
    # add the dataframe to net_realized_price_dict for return to caller
    for prod_stream_name, prod_stream_values in nri_prod_by_stream._asdict().items():
        if not (any([_ in prod_stream_name for _ in ['_all', '_mmcf']])):
            print(f'\n| Getting net realized prices for: {prod_stream_name}...')

            # net_realized_price --> dataframe with the same index/columns as model.bootstrap_prices (index = model_period, columns = MCS price scenarios + strip pricing)
            net_realized_price = pd.DataFrame().reindex_like(model_drivers.boots_template_df)
            net_realized_price.fillna(0, inplace=True)

            # get the price index list for this production stream
            price_index_list = prices_for_prod_stream[prod_stream_name]
            for price_index in price_index_list:
                # add the bootstrap_prices dataframe for this price index to net_realized_price
                print(
                    f'\n| Raw bootstrap_prices for {prod_stream_name} >> {price_index}:\n{bootstrap_prices[price_index]}')
                # before fees
                net_realized_price += bootstrap_prices[price_index]
            print(f'\n| Net realized price (ex. fees) for {prod_stream_name}:\n{net_realized_price}')

            # include fees to net_realized_price if desired
            if include_fees:
                print(f'\n| Adding fees for {prod_stream_name}:\n{fees_for_prod_stream[prod_stream_name]}')
                for col in net_realized_price:
                    net_realized_price[col] += fees_for_prod_stream[prod_stream_name].values
            print(f'\n| Net realized price (with fees) for {prod_stream_name}:\n{net_realized_price}')

            net_realized_price_dict[prod_stream_name] = net_realized_price
            print(f'\n| net_realized_price_dict updated for {prod_stream_name} >> {price_index_list}')

    # pprint.pprint(net_realized_price_dict)
    print(f'\n>>> Production streams with net realized prices:\n{[_ for _ in net_realized_price_dict]}\n')
    return net_realized_price_dict
