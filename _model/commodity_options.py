import prices as pr
import pandas as pd
import numpy as np

options_raw = pd.read_csv(r'ftp://ftp.cmegroup.com/pub/settle/nymex_option.csv')

# WTI options
product_keywords = 'Wti Average Price Option'

desired_columns = ["PRODUCT SYMBOL", "CONTRACT MONTH", "CONTRACT YEAR", "CONTRACT DAY", "PUT/CALL", "STRIKE",
                   "CONTRACT", "PRODUCT DESCRIPTION", "SETTLE", "PT CHG", "PRIOR SETTLE", "PRIOR INT",
                   "TRADEDATE"]


options_raw = options_raw.loc[:, desired_columns]
options_raw.dropna(axis='index', subset=['PRIOR INT'], inplace=True)

options_clean = options_raw.loc[[product_keywords in _ for _ in options_raw['PRODUCT DESCRIPTION']]]

print(options_clean)
