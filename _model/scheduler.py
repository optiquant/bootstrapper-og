import model_control
import model_drivers
import economics
import financing
import rolling_nav
import bootstrapper_charts


#----------------------------------------------------------------------------------------------------------------------#
#----------------------------------------------------# ATTRIBUTES #----------------------------------------------------#
#----------------------------------------------------------------------------------------------------------------------#

model_control.initialize()
model_drivers.initialize()

live_ds = model_drivers.live_ds
modeled_wells_all = model_control.modeled_wells_all
asset_level_drivers = model_drivers.get_asset_level_drivers()
modeled_sub_assets = [
    _ for _ in asset_level_drivers[asset_level_drivers['Run Model For Sub-Asset?'] == 'Yes'].index
]


#---------------------------------------------------------------------------------------------------------------------#
#----------------------------------------------------# FUNCTIONS #----------------------------------------------------#
#---------------------------------------------------------------------------------------------------------------------#

def sequence_generic_pads():
    '''Builds a sequence of generic pads and appends them to the drilling schedule.'''
    # number of generic wells --> dict: {subasset: int}
    if model_control.generic_wells_on:
        g_well_count_by_sub_asset = {
            k:v for k,v in model_control.generic_well_count_by_sub_asset.items() if k in modeled_sub_assets
        }
        # make generic well names for each sub-asset
        g_well_names = {k: [k+"//GENERIC "+str(_+1) for _ in range(v)] for k,v in g_well_count_by_sub_asset.items()}

        # generic pads order dict (flips keys/values) --> {pad order: subasset}
        generic_pad_order = dict(asset_level_drivers['Generic Pad Order'])
        generic_pad_order = sorted([(v,k) for k, v in generic_pad_order.items()])
        generic_pad_order = dict(generic_pad_order)
        # pads drilled in generic sequence --> {subasset: str(# of pads drilled in sequence)}
        pads_in_sequence = dict(asset_level_drivers['Pads Completed In Sequence'])
        # a list of the sub-asset names according to pads in sequence
        pad_list_by_sub_asset = [_subasset for _subasset, _pads in pads_in_sequence.items() for p in range(int(_pads))]
        # wells per pad dict --> {subasset: str(# of wells per pad)}
        wells_on_pad = dict(asset_level_drivers['WELLS ON PAD'])
        print(f'\n| Generic pad order: {generic_pad_order}\n| Pads Drilled in Sequence: {pads_in_sequence}\n| Wells Per Pad: {wells_on_pad}')

        # total generic wells and well counter
        total_gws = sum([_ for _ in g_well_count_by_sub_asset.values()])
        g_well_counter = 0

        # list for generic wells in sequence
        g_well_list = []

        while g_well_counter < total_gws:
            # build generic well names in sequence
            # for each sub-asset (in drilling order)
            for g_pad_order, sub_asset in generic_pad_order.items():
                # for each pad in sequence, get the wells per pad
                for pad_in_seq in range(int(pads_in_sequence[sub_asset])):
                    _wpp = int(wells_on_pad[sub_asset])
                    # get this number of wells from the g_well_names dict
                    g_well_list.extend(g_well_names[sub_asset][:_wpp])
                    # drop the appended wells from g_well_names
                    g_well_names[sub_asset] = g_well_names[sub_asset][_wpp:]
                    g_well_counter = len(g_well_list)
        print(f'\n| Generic wells modeled: {g_well_list}')
        # add generics to modeled_wells_all
        modeled_wells_all.extend(g_well_list)
    else:
        print(f'\n!! No generic wells modeled.')

    model_control.add_to_model_control({'modeled_wells_all': modeled_wells_all})
    return modeled_wells_all



#---------------------------------------------------------------------------------------------------------------------#
#----------------------------------------------------# EXECUTION #----------------------------------------------------#
#---------------------------------------------------------------------------------------------------------------------#


# sequence generic pads according to inputs if generic wells are on, else just do modeled_wells_all
modeled_wells_all = sequence_generic_pads()

print(f'\n| Model running for: {modeled_wells_all} >>>')

economics.calc_production_capex_opex()

if model_control.pdp_on:
    economics.load_pdp_prod_opex()

# roll up production, capex, opex
economics.parentco_roll_up()
economics.update_model_data()
# calculate cash flow
economics.calc_cash_flow()
financing.run_financing()
bootstrapper_charts.run_econs_charts()
rolling_nav.run_rolling_nav()
model_control.notify_complete(caller_name='scheduler')
