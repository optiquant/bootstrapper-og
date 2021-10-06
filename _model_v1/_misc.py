from sklearn.neighbors import KernelDensity


def run_KDE(data, series_name, rand_samples=10 ** 5):
    '''Pass data = y values, series_name = the name for this dataseries which will be used as the key the returned random_samples_dict.
    Returns tuple of:
    (random samples (random_samples_dict[series_name]),
    linear space of 5000 points between min() and max() of data (x_d),
    log probability density function (logprob = kde.score_samples(x_d)))
    '''
    # create KDE model and random samples
    data = np.array(data).squeeze()  # y_vals

    global random_samples_dict

    if 'random_samples_dict' not in globals():
        # make dictionary to store random samples
        random_samples_dict = {}
    else:
        # initialize storage
        random_samples_dict[series_name] = []

    # bandwidth for KDE
    kde_bandwidth = get_kde_bandwidth()

    # instantiate and fit the KDE model
    kde = KernelDensity(bandwidth=kde_bandwidth[series_name], kernel='gaussian')
    kde.fit(data[:, None])

    global x_d
    x_d = np.linspace(min(data), max(data), 5000)

    global logprob
    # score_samples returns the log of the probability density
    logprob = kde.score_samples(x_d[:, None])

    N = rand_samples
    global random_samples
    random_samples = kde.sample(n_samples=N)
    random_samples = random_samples.squeeze()  # reduce dimensionality
    random_samples_dict[series_name] = list(random_samples)

    results_dict = {'random_samples': random_samples_dict[series_name],
                    'logprob': logprob,
                    'x_d_linspace': x_d}

    # print(results_dict)
    return results_dict


def get_kde_bandwidth(update = {}):
    '''Returns dictionary with KDE bandwifth by commodity (keys = comdty_nick).
    Pass update = {comdty_nick: bandwidth} to update bandwidth for a commodity.'''

    global kde_bandwidth
    if 'kde_bandwidth' not in globals():
        kde_bandwidth = {'wti': 0.3,
                         'wti_hou': 0.3,
                         'midcush_ff': 0.04,
                         'midcush_wtt': 0.04,
                         'hh': 0.008,
                         'waha_gas_diff': 0.008,
                         'hsc_gas_diff': 0.008,
                         'ethane': 0.001,
                         'propane': 0.004,
                         'n_butane': 0.005,
                         'iso_butane': 0.005,
                         'nat_gasoline': 0.005
                         }
    try:
        for k in update:
            kde_bandwidth[k] = update[k]
    except (NameError, TypeError, KeyError, ValueError):
        print('Invalid / no update dict passed. Returning default bandwidths.')

    return kde_bandwidth
