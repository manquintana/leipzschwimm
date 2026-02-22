import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import geopandas as gpd
import folium
import re

'''
All the lakes URL: https://www.gesunde.sachsen.de/badegewaesser.html#EINSTUFUNG
Specific quality URL = "https://www.gesunde.sachsen.de/badegewaesser-detail.html?id="
Problem is, this url fetches dinamically the data to display the tables > so i take the info from snippet_url instead
'''

swim_lakes = pd.read_csv("data/lakes.csv") #some of my favorite lakes in leipzsch!


"""
DATA ADQUISITION
################
"""
def scrap_lake_web(df_lake_info, lake):
    snippet_url = f"https://www.gesunde.sachsen.de/lua/badegewaesser/{lake['id']}-de-content.snippet"
    print(f"> retrieving info for lake: {lake['id']}")
    data = requests.get(snippet_url).text
    soup = BeautifulSoup(data, 'html.parser')

    tables = soup.find_all("table")
    if len(tables) > 1: # usually is 2 tables (Vorort and Labor) but sometimes they have multiple extraction points, which makes thing hard to scrap... I will take the first two tables in this case
        #get data from table 1 (Observations)
        for row in tables[0].tbody.find_all('tr'):
            columns = row.find_all('td')
            table_dict = {"id": lake["id"], "name": lake["name"], "lat": lake["lat"], "lon": lake["lon"], "location": lake["location"], "date": columns[0].text, "abn": columns[1].text, "sight": columns[2].text}
            df_lake_info.loc[len(df_lake_info)] = table_dict
        #get data from table 2 (Laboratory)
        for row in tables[1].tbody.find_all('tr'):
            columns = row.find_all('td')
            table_df = pd.DataFrame({"date": [columns[0].text], "entero": [columns[1].text], "coli": [columns[2].text], "micro": [columns[3].text]}).astype({
            "date": "string",
            "entero": "string",
            "coli": "string",
            "micro": "string"
            })
            df_lake_info.set_index("date", inplace=True)
            table_df.set_index("date", inplace=True)
            df_lake_info.update(table_df)
            df_lake_info.reset_index(inplace=True)
    else:
        error_code = f" > information not available for lake {lake['name']}! the web has no data: {snippet_url}"
        print(error_code)
    print(f">> retrieved info for lake: {lake['name']}")
    return df_lake_info

df_lake_info = pd.DataFrame(columns=["id", "name", "lat", "lon", "location", "date", "abn", "sight", "entero", "coli", "micro"]).astype({
    "id": "string",
    "name": "string",
    "lat": "float",
    "lon": "float",
    "location": "string",
    "date": "string",
    "abn": "string",
    "sight": "string",
    "entero": "string",
    "coli": "string",
    "micro": "string"
})
for index, lake in swim_lakes.iterrows():
    df_lake_info = scrap_lake_web(df_lake_info, lake)


print("Starting data preparation and mapping...")

"""
DATA CLEANSING
##############
"""

#df_lake_info = df_lake_info[df_lake_info["name"] != "Harthsee"]

df_lake_info["date"] = pd.to_datetime(df_lake_info["date"], dayfirst=True)

df_lake_info = df_lake_info.sort_values("date").drop_duplicates("name", keep="last")

df_lake_info["sight"] = df_lake_info["sight"].str.replace("m", "", regex=False)
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
def get_numeric_value(string_value):
  try:
    float(string_value)
    return int(string_value)
  except ValueError:
    print("not a number")
    if string_value[0] == "<":
      return int(re.sub(r"\D", "", string_value))
    elif(string_value[0] == ">"):
      return int(re.sub(r"\D", "", string_value)) + 1
    else:
      return "error_in_data"

def assign_color(row):
  if(datetime.now() - row["date"]).days > 30:
      return "#ffff00" #yellow
  elif (get_numeric_value(row["entero"]) <= 700 and get_numeric_value(row["coli"]) <= 1800 and row["abn"].lower() == "nein" and row["micro"] == ""):
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
    zoom_start=9,
    tiles="CartoDB positron"
)

'''
folium.TileLayer(
    "OpenStreetMap",
    name="OSM",
    attr="who knows"
).add_to(m)

# Stamen Terrain
folium.TileLayer(
    "Stamen Terrain",
    name="Terrain",
    attr="who knows"
).add_to(m)

# CartoDB Positron
folium.TileLayer(
    "stamenwatercolor",
    name="Light",
    attr="who knows"
).add_to(m)
'''

leipzig_gdf = gpd.read_file("https://raw.githubusercontent.com/manquintana/leipzschwimm/refs/heads/main/data/leipzig_UTM33N.json").to_crs(epsg=4326)
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
for index, row in lakes_gdf.iterrows():
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=12,
        color=row["color"],
        fill=True,
        fill_color=row["color"],
        background_color=row["color"],
        fill_opacity=0.7,
        popup=f"""
        <div style='display:block; min-width:340px; font-size:12px;'>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
          <tr>
              <th colspan="2" style="text-align:center; font-size:16px; background-color:{row['color']}">
                  {row['name']} - <a style="color:#000;" href="https://www.google.com/maps/search/{row['lat']},{row['lon']}" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-map-fill" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M16 .5a.5.5 0 0 0-.598-.49L10.5.99 5.598.01a.5.5 0 0 0-.196 0l-5 1A.5.5 0 0 0 0 1.5v14a.5.5 0 0 0 .598.49l4.902-.98 4.902.98a.5.5 0 0 0 .196 0l5-1A.5.5 0 0 0 16 14.5zM5 14.09V1.11l.5-.1.5.1v12.98l-.402-.08a.5.5 0 0 0-.196 0zm5 .8V1.91l.402.08a.5.5 0 0 0 .196 0L11 1.91v12.98l-.5.1z"/></svg></a>
              </th>
          </tr>
          <tr>
              <td><b>Last sample</b></td>
              <td>{row['date'].strftime("%Y-%m-%d")}</td>
          </tr>
          <tr>
              <td><b>Sight [m]</b></td>
              <td>{row['sight']}</td>
          </tr>
          <tr>
              <td><b>Abnormal observations</b></td>
              <td>{row['abn']}</td>
          </tr>
          <tr>
              <td title="Dangerous if value > 700"><b>Intestinale Enterokokken [KBE/100 ml] <svg title="this is tooltip" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-info-circle" viewBox="0 0 16 16"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/><path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0"/></svg></b></td>
              <td>{row['entero']}</td>
          </tr>
          <tr>
              <td title="Dangerous if value > 1800"><b>Escherichia coli [KBE/100 ml] <svg title="this is tooltip" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-info-circle" viewBox="0 0 16 16"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/><path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0"/></svg></b></td>
              <td>{row['coli']}</td>
          </tr>
          <tr>
              <td><b>Microscopy</b></td>
              <td>{row['micro']}</td>
          </tr>
          <tr>
              <td><b>Current status</b></td>
              <td style="color:{row['color']}"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-circle-fill" viewBox="0 0 16 16"><circle cx="8" cy="8" r="8"/></svg></td>
          </tr>
          <tr>
              <td><b>Reference values (external link)</b></td>
              <td><a style="color:#000;" href="https://www.gesunde.sachsen.de/badegewaesser.html#EINSTUFUNG" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-question-circle-fill" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M5.496 6.033h.825c.138 0 .248-.113.266-.25.09-.656.54-1.134 1.342-1.134.686 0 1.314.343 1.314 1.168 0 .635-.374.927-.965 1.371-.673.489-1.206 1.06-1.168 1.987l.003.217a.25.25 0 0 0 .25.246h.811a.25.25 0 0 0 .25-.25v-.105c0-.718.273-.927 1.01-1.486.609-.463 1.244-.977 1.244-2.056 0-1.511-1.276-2.241-2.673-2.241-1.267 0-2.655.59-2.75 2.286a.237.237 0 0 0 .241.247m2.325 6.443c.61 0 1.029-.394 1.029-.927 0-.552-.42-.94-1.029-.94-.584 0-1.009.388-1.009.94 0 .533.425.927 1.01.927z"/></svg></a></td>
          </tr>
      </table>
        </div>
        """,
        tooltip=row["name"]
    ).add_to(m)
folium.LayerControl().add_to(m)


top_legend = '''
<div style="
     position: fixed;
     width: 50%;
     left: 50%;
     height:150px;
     transform: translateX(-50%);
     z-index: 9999;
     font-size: 12px;
     color: #fff;
     padding-top: 2px;
     text-align:center;
     overflow: hidden;
     border-radius: 8px;
     #background-color: #000;
     
">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320"
  style="top:0; z-index=100; position:absolute; width:100%; height:100%; left:0"
>
  <path fill="#0099ff" fill-opacity="0.7" d="M0,32L8.3,74.7C16.6,117,33,203,50,224C66.2,245,83,203,99,176C115.9,149,132,139,149,160C165.5,181,182,235,199,261.3C215.2,288,232,288,248,293.3C264.8,299,281,309,298,266.7C314.5,224,331,128,348,96C364.1,64,381,96,397,101.3C413.8,107,430,85,447,69.3C463.4,53,480,43,497,69.3C513.1,96,530,160,546,186.7C562.8,213,579,203,596,165.3C612.4,128,629,64,646,69.3C662.1,75,679,149,695,186.7C711.7,224,728,224,745,208C761.4,192,778,160,794,165.3C811,171,828,213,844,218.7C860.7,224,877,192,894,181.3C910.3,171,927,181,943,181.3C960,181,977,171,993,176C1009.7,181,1026,203,1043,224C1059.3,245,1076,267,1092,277.3C1109,288,1126,288,1142,277.3C1158.6,267,1175,245,1192,240C1208.3,235,1225,245,1241,218.7C1257.9,192,1274,128,1291,128C1307.6,128,1324,192,1341,224C1357.2,256,1374,256,1390,224C1406.9,192,1423,128,1432,96L1440,64L1440,0L1431.7,0C1423.4,0,1407,0,1390,0C1373.8,0,1357,0,1341,0C1324.1,0,1308,0,1291,0C1274.5,0,1258,0,1241,0C1224.8,0,1208,0,1192,0C1175.2,0,1159,0,1142,0C1125.5,0,1109,0,1092,0C1075.9,0,1059,0,1043,0C1026.2,0,1010,0,993,0C976.6,0,960,0,943,0C926.9,0,910,0,894,0C877.2,0,861,0,844,0C827.6,0,811,0,794,0C777.9,0,761,0,745,0C728.3,0,712,0,695,0C678.6,0,662,0,646,0C629,0,612,0,596,0C579.3,0,563,0,546,0C529.7,0,513,0,497,0C480,0,463,0,447,0C430.3,0,414,0,397,0C380.7,0,364,0,348,0C331,0,314,0,298,0C281.4,0,265,0,248,0C231.7,0,215,0,199,0C182.1,0,166,0,149,0C132.4,0,116,0,99,0C82.8,0,66,0,50,0C33.1,0,17,0,8,0L0,0Z"></path>
</svg>
<h2 style="margin-bottom:5px;position: relative; z-index: 1;">Sachsen Lake Monitoring</h2>
<div style="position: relative; z-index: 1; background-color:#0099ff; border-radius:10px; display:block; width:80%; display:block; margin-left:auto; margin-right:auto;">
  <span style="color:green;">⬤</span> <i style="margin-right:15px;color:#fff">Good water quality</i>
  <span style="color:yellow;">⬤</span> <i style="margin-right:15px;color:#fff">Last sample Outdated (taken more than 1 month ago)</i>
  <span style="color:red;">⬤</span> <i style="color:#fff">Problem reported. Do not swim!</i>
</div>


</div>
'''

m.get_root().html.add_child(folium.Element(top_legend))
from branca.element import Element
footer = f"""
<div style="
    position: fixed;
    bottom: 0px;
    left: 0px;
    width: 100%;
    height: 40px;
    background-color: white;
    z-index: 9999;
    font-size: 14px;
    padding-left: 10px;
    padding-top: 10px;
    border-top: 1px solid grey;
">
    <p><b>Sachsen Lake Monitoring Dashboard | Last updated at {datetime.now()}</b></p>
    <p>Maintained by <a href="https://github.com/manquintana/" target="_blank">jevi</a></p>
</div>
"""
m.get_root().html.add_child(Element(footer))



#m #map
m.save("index.html") #or save html
