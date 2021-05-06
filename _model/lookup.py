
def lookup(lookup_identifier='rev_boots'):
    '''A collection of dictionaries to map more complex relationships.'''
    global rev_boots
    # use this to group and sum up the right boots objects for each revenue stream
    rev_boots = {
        'Revenue - Oil ($k)': ['oil_0_wti',
                               'oil_1_midcush_ff'],

        'Revenue - Gas - All ($k)': ['gas_waha_0_hh',
                                     'gas_waha_1_waha_gas_diff',
                                     'gas_hsc_0_hh',
                                     'gas_hsc_1_hsc gas diff'],

        'Revenue - Gas - Waha ($k)': ['gas_waha_0_hh',
                                      'gas_waha_1_waha_gas_diff'],

        'Revenue - Gas - HSC ($k)': ['gas_hsc_0_hh',
                                     'gas_hsc_1_hsc gas diff'],

        'Revenue - NGL - All ($k)': ['ngl_ethane_0_ethane',
                                     'ngl_propane_0_propane',
                                     'ngl_n_butane_0_n_butane',
                                     'ngl_iso_butane_0_iso_butane',
                                     'ngl_nat_gasoline_0_nat_gasoline'],

        'Revenue - NGL - Ethane ($k)': ['ngl_ethane_0_ethane'],
        'Revenue - NGL - Propane ($k)': ['ngl_propane_0_propane'],
        'Revenue - NGL - n-Butane ($k)': ['ngl_n_butane_0_n_butane'],
        'Revenue - NGL - iso-Butane ($k)': ['ngl_iso_butane_0_iso_butane'],
        'Revenue - NGL - Nat. Gasoline ($k)': ['ngl_nat_gasoline_0_nat_gasoline']
    }

    global boots_prod_splitter
    # this identifies the % multiplier to be applied to a HedgeTrade's volumes and settlements.
    # the multiplier should allocate a proportionate share of hedge volumes and settlements to the bootstrapper object
    boots_prod_splitter = {
        'oil_0_wti': 'oil_all_pct',
        'oil_1_midcush_ff': 'oil_all_pct',
        'gas_waha_0_hh': 'gas_waha_pct',
        'gas_waha_1_waha_gas_diff': 'gas_waha_pct',
        'gas_hsc_0_hh': 'gas_hsc_pct',
        'gas_hsc_1_hsc gas diff': 'gas_hsc_pct',
        'ngl_ethane_0_ethane': 'ngl_ethane_pct',
        'ngl_propane_0_propane': 'ngl_propane_pct',
        'ngl_n_butane_0_n_butane': 'ngl_n_butane_pct',
        'ngl_iso_butane_0_iso_butane': 'ngl_iso_butane_pct',
        'ngl_nat_gasoline_0_nat_gasoline': 'ngl_nat_gasoline_pct'
    }

    global rev_hedge
    # use this to connect revenue streams with the right set of hedges
    rev_hedge = {
        'Revenue - Oil ($k)': ['WTI', 'MIDCUSH DIFF'],
        'Revenue - Gas - All ($k)': ['HENRY HUB', 'WAHA DIFF', 'WAHA'],
        'Revenue - Gas - Waha ($k)': ['WAHA DIFF', 'WAHA'],
        'Revenue - Gas - HSC ($k)': ['HENRY HUB'],
        'Revenue - NGL - All ($k)': ['NON-TET ETHANE', 'NON-TET PROPANE'],
        'Revenue - NGL - Ethane ($k)': ['NON-TET ETHANE'],
        'Revenue - NGL - Propane ($k)': ['NON-TET PROPANE'],
        'Revenue - NGL - n-Butane ($k)': ['N-BUTANE'],
        'Revenue - NGL - iso-Butane ($k)': ['ISO-BUTANE'],
        'Revenue - NGL - Nat. Gasoline ($k)': ['NON-TET NAT. GASOLINE']
    }

    global hedge_comdty_price_strip
    # use this to connect hedge contracts with the right comdty price index/nickname
    hedge_comdty_price_strip = {
        'WTI': ['wti_cma'],
        'MIDCUSH DIFF': ['midcush_ff'],
        'HENRY HUB': ['hh'],
        'WAHA DIFF': ['waha_gas_diff'],
        'WAHA': ['hh', 'waha_gas_diff'],
        'NON-TET ETHANE': ['ethane'],
        'NON-TET PROPANE': ['propane'],
        'N-BUTANE': ['n_butane'],
        'ISO-BUTANE': ['iso_butane'],
        'NON-TET NAT. GASOLINE': ['nat_gasoline']
    }

    global hedge_comdty_price_bootstrap
    # use this to connect hedge contracts with the right comdty price index/nickname
    hedge_comdty_price_bootstrap = {
        'WTI': ['wti'],
        'MIDCUSH DIFF': ['midcush_ff'],
        'HENRY HUB': ['hh'],
        'WAHA DIFF': ['waha_gas_diff'],
        'WAHA': ['hh', 'waha_gas_diff'],
        'NON-TET ETHANE': ['ethane'],
        'NON-TET PROPANE': ['propane'],
        'N-BUTANE': ['n_butane'],
        'ISO-BUTANE': ['iso_butane'],
        'NON-TET NAT. GASOLINE': ['nat_gasoline']
    }

    global boots_hedge_contract
    # use this to connect bootstrapper objects to their hedge contracts
    boots_hedge_contract = {
        'oil_0_wti': ['WTI'],
        'oil_1_midcush_ff': ['MIDCUSH DIFF'],
        'gas_waha_0_hh': ['HENRY HUB'],
        'gas_waha_1_waha_gas_diff': ['WAHA DIFF'],
        'gas_hsc_0_hh': ['HENRY HUB'],
        'gas_hsc_1_hsc_gas_diff': [],
        'ngl_ethane_0_ethane': ['NON-TET ETHANE'],
        'ngl_propane_0_propane': ['NON-TET PROPANE'],
        'ngl_n_butane_0_n_butane': ['N-BUTANE'],
        'ngl_iso_butane_0_iso_butane': ['ISO-BUTANE'],
        'ngl_nat_gasoline_0_nat_gasoline': ['NON-TET NAT. GASOLINE']
    }

    global hedge_prod_splitter
    # this identifies the % multiplier to be applied to a HedgeTrade's volumes and settlements.
    # the multiplier should allocate a proportionate share of volumes and settlements to the
    # boots.revenue_net_hedges property. The revenue will already be adjusted by using a the correct NRI volume
    hedge_prod_splitter = {
        'WTI': ['oil_midland_pct'],
        'MIDCUSH DIFF': ['oil_midland_pct'],
        'HENRY HUB': ['gas_hsc_pct', 'gas_waha_pct', 'gas_all_pct'],
        'WAHA DIFF': [],
        'WAHA': [],
        'NON-TET ETHANE': ['ngl_ethane_pct'],
        'NON-TET PROPANE': ['ngl_propane_pct'],
        'N-BUTANE': ['ngl_n_butane_pct'],
        'ISO-BUTANE': ['ngl_iso_butane_pct'],
        'NON-TET NAT. GASOLINE': ['ngl_nat_gasoline_pct'],
    }

    lookup = {'rev_boots': rev_boots,
              'rev_hedge': rev_hedge,
              'boots_prod_splitter': boots_prod_splitter,
              'boots_hedge_contract': boots_hedge_contract,
              'hedge_comdty_price_strip': hedge_comdty_price_strip,
              'hedge_comdty_price_bootstrap': hedge_comdty_price_bootstrap,
              'hedge_prod_splitter': hedge_prod_splitter}
    try:
        return lookup[lookup_identifier]
    except (KeyError, ValueError):
        raise Exception(f'| lookup_identifier not passed. Pass one of: {[_ for _ in lookup]}')