import scipy.optimize
import numpy_financial as npf
import numpy as np

def xnpv(rate, values, dates):
    '''Equivalent of Excel's XNPV function.
        #>>> from datetime import date
        #>>> dates = [date(2010, 12, 29), date(2012, 1, 25), date(2012, 3, 8)]
        #>>> values = [-10000, 20, 10100]
        #>>> xnpv(0.1, values, dates)
    -966.4345'''

    if rate <= -1.0:
        return float('inf')

    d0 = dates[0]    # or min(dates)
    try:
        return sum(
            [vi / ((1.0000 + rate)**((di - d0)/np.timedelta64(1, 'D')/365.25)) for vi, di in zip(values, dates)]
        )
    except OverflowError:
        return np.nan

def xirr(values, dates):
    '''Equivalent of Excel's XIRR function.
        #>>> from datetime import date
        #>>> dates = [date(2010, 12, 29), date(2012, 1, 25), date(2012, 3, 8)]
        #>>> values = [-10000, 20, 10100]
        #>>> xirr(values, dates)
        0.0100612...
    '''
    if values.sum() > 0:
        try:
            return scipy.optimize.newton(lambda r: xnpv(r, values, dates), 0.0)
        except RuntimeError:    # Failed to converge?
            return scipy.optimize.brentq(lambda r: xnpv(r, values, dates), -1.0, 1e10)
    else:
        # if the cumulative sum is negative, return negative
        # todo: learn more about scipy.optimize
        return npf.irr(values)