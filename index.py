import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import geopandas as gpd
import folium

swim_lakes = [
    {"id": "bgwl0085", "name": "Kulkwitzer See", "lat": 51.30716868956218, "lon": 12.247896347253004},
    {"id": "bgwm0071", "name": "Albrechtshainer See", "lat": 51.31249082838858, "lon": 12.570372341129078},
    {"id": "bgwm0072", "name": "Moritz/Ammelshainer See", "lat": 51.29749712405867, "lon": 12.606977342144106},
    {"id": "bwwl0092", "name": "Speicherbecken Borna", "lat": 51.11011090686556, "lon": 12.451590688757843},
    {"id": "bwwl0101", "name": "Harthsee", "lat": 51.085874010632715, "lon": 12.54802432292868},
    {"id": "bwwl0119", "name": "Markkleeberger See", "lat": 51.26603400515653, "lon": 12.40812975334591},
    {"id": "bwwm0078", "name": "Spannbetonwerk See", "lat": 51.252215631525644,"lon": 12.61683371411002},
    {"id": "bwls0088", "name": "Cospudener See", "lat": 51.26915113014249,"lon": 12.334952110757772}
    ]

'''
All the lakes URL: https://www.gesunde.sachsen.de/badegewaesser.html#EINSTUFUNG
Specific quality URL = "https://www.gesunde.sachsen.de/badegewaesser-detail.html?id="
Problem is, this url fetches dinamically the data to display the tables > so i take the info from snippet_url instead
'''

"""
DATA ADQUISITION
################
"""

def scrap_lake_web(df_lake_info, lake_dict):
    lake_id = lake_dict["id"]
    snippet_url = f"https://www.gesunde.sachsen.de/lua/badegewaesser/{lake_id}-de-content.snippet"
    data = requests.get(snippet_url).text
    soup = BeautifulSoup(data, 'html.parser')

    tables = soup.find_all("table")
    if len(tables) == 2:
        #get data from table 1 (Observations)
        for row in tables[0].tbody.find_all('tr'):
            columns = row.find_all('td')
            table_dict = {"id": lake_dict["id"], "name": lake_dict["name"], "lat": lake_dict["lat"], "lon": lake_dict["lon"], "date": columns[0].text, "abn": columns[1].text, "sight": columns[2].text}
            df_lake_info.loc[len(df_lake_info)] = table_dict

        #get data from table 2 (Laboratory)
        for row in tables[1].tbody.find_all('tr'):
            columns = row.find_all('td')
            table_df = pd.DataFrame({"date": [columns[0].text], "entero": [columns[1].text], "coli": [columns[2].text], "micro": [columns[3].text]})
            df_lake_info.set_index("date", inplace=True)
            table_df.set_index("date", inplace=True)
            df_lake_info.update(table_df)
            df_lake_info.reset_index(inplace=True)
    else:
        error_code = f"> information not available for lake {lake_dict['name']}! the web has no data: {snippet_url}"
        print(error_code)
    return df_lake_info

df_lake_info = pd.DataFrame(columns=["id", "name", "lat", "lon", "date", "abn", "sight", "entero", "coli", "micro"])
for lake in swim_lakes:
    df_lake_info = scrap_lake_web(df_lake_info, lake)
    
    

"""
DATA CLEANSING
##############
"""
df_lake_info = df_lake_info[df_lake_info["name"] != "Harthsee"]

df_lake_info['date'] = pd.to_datetime(df_lake_info['date'])

df_lake_info = df_lake_info.sort_values("date").drop_duplicates("name", keep="last")

df_lake_info["sight"] = df_lake_info["sight"].str.replace(" ", "", regex=False).str.split(",").str[0]
df_lake_info["abn"] = df_lake_info["abn"].str.replace(" ", "", regex=False)
df_lake_info["entero"] = df_lake_info["entero"].str.replace(" ", "", regex=False).str.split(",").str[0]
df_lake_info["coli"] = df_lake_info["coli"].str.replace(" ", "", regex=False).str.split(",").str[0]
df_lake_info["micro"] = df_lake_info["micro"].str.replace(" ", "", regex=False)


"""
color ref:
yellow =  outdated, more than 1 month since last sample
green = good water quality (date<=1month AND entero<=700 AND coli<=1800 AND abn="nein")
red = problem reported (something else)
"""
def assign_color(row):
  if(datetime.now() - row["date"]).days > 30:
      return "#ffff00" #yellow
  elif (row["entero"] <= 700 and row["coli"] <= 1800 and row["abn"].lower() == "nein"):
      return "#66ff99" #green
  else:
      return "#ff3333" #red

df_lake_info["color"] = df_lake_info.apply(assign_color, axis=1)




"""
DATA MAPPING
############
"""
lakes_gdf = gpd.GeoDataFrame(
    df_lake_info,
    geometry=gpd.points_from_xy(df_lake_info["lon"], df_lake_info["lat"]),
    crs="EPSG:4326"
)

m = folium.Map(
    location=[lakes_gdf["lat"].mean(), lakes_gdf["lon"].mean()],
    zoom_start=11,
    tiles="CartoDB positron"
)

legend_html = """
<div style="position: fixed; top: 100px; left: 200px; width: 440px; height: 120px; background-color:#ddd;border:2px solid grey; padding: 10px; font-size:16px;z-index:9999;">
<b>Water Quality</b><br>
<span style="color:green">⬤</span> <i>Good water quality</i><br>
<span style="color:yellow">⬤</span> <i>Last sample Outdated (taken more than 1 month ago)</i><br>
<span style="color:red">⬤</span> <i>Problem reported. Do not swim!</i>
</div>
"""

leipzig_gdf = gpd.read_file("https://github.com/manquintana/leipzschwimm/blob/main/data/leipzig_UTM33N.json").to_crs(epsg=4326)
folium.GeoJson(
     leipzig_gdf,
     name="City of Leipzig",
     style_function=lambda x: {
         "fillColor": "lightgreen",
         "color": "grey",
         "weight": 1,
         "fillOpacity": 0.2
     }
 ).add_to(m)


# Add lakes to map
for _, row in lakes_gdf.iterrows():
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=12,
        color=row["color"],
        fill=True,
        fill_color=row["color"],
        fill_opacity=0.7,
        popup=f"""
        <div style='width:500px; font-size:14px;'>
        <b>{row['name']}</b><br>
        Last sample: {row['date']}<br>
        Sight[m]: {row['sight']}<br>
        Intestinale Enterokokken[KBE/100 ml]: {row['entero']}<br>
        Escherichia coli[KBE/100 ml]: {row['coli']}<br>
        Microscopy: {row['micro']}
        </div>
        """,
        tooltip=row["name"]
    ).add_to(m)
folium.LayerControl().add_to(m)

title_html = '''<h3 align="center" style="font-size:20px; font-weight:bold; margin-top:5px; z-index:9999">Leipzschwimm</h3>'''
m.get_root().html.add_child(folium.Element(title_html))
m.get_root().html.add_child(folium.Element(legend_html))

m