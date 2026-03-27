# author: manquintana

import pandas as pd

'''
All the lakes URL: https://www.gesunde.sachsen.de/badegewaesser.html#EINSTUFUNG
Specific quality URL = "https://www.gesunde.sachsen.de/badegewaesser-detail.html?id="
Problem is, this url fetches dinamically the data to display the tables > so i take the info from snippet_url instead
'''

weather_codes = pd.read_csv("data/weather_codes.csv", sep = ";", skiprows = 2, nrows = 13,  names = ["code", "description", "icon"])

print(weather_codes)

"""
DATA ADQUISITION
################
"""
