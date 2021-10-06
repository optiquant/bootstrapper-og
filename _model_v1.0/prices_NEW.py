import pandas as pd


url = 'https://www.cmegroup.com/ftp/settle/nymex.settle.20210723.s.csv'
data = pd.read_csv(url)

print(data)