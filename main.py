from fastapi import FastAPI
import geopy.distance
import uvicorn
import requests
import json
import urllib3
from urllib3 import ProxyManager
import geopy.distance
from pyproj import Transformer
import os

app = FastAPI(
    docs_url="/moodle",
)

@app.get("/main_search/")
async def main_search(
    lat: float = 0,
    long: float = 0,
    limit: int = 10
    ):
    
    # http = ProxyManager("")

    carparks = requests.get(
        url="https://resource.data.one.gov.hk/td/carpark/basic_info_all.json",
    )

    carparks_data = carparks.content
    carparks_data_in_utf8 = carparks_data.decode("utf-8-sig")
    carparks_list = json.loads(carparks_data_in_utf8)
    my_lat = lat
    my_lon =  long
    carparks_list["coor"] = [my_lat,my_lon]

    for entry in carparks_list["car_park"]:
        lati = entry["latitude"]
        longi = entry["longitude"]
        coor = (lati,longi)
        your_coor = (my_lat,my_lon)
        entry["distance"] = geopy.distance.geodesic(coor,your_coor).km
        
    carparks_list["car_park"] = sorted(
        carparks_list["car_park"],
        key=lambda k: k.get('distance'),
        reverse=False)
    
    if limit == 0:
        return carparks_list
    else:
        carparks_list["car_park"] = carparks_list["car_park"][:limit]
        return carparks_list

@app.get("/v1")
async def root(
    lat: float = 0,
    long: float = 0,
    limit: int = 10,
    lang: str = ""
    ):
    
    # http = ProxyManager("")

    page = urllib3.request(
        url=f"https://api.data.gov.hk/v1/carpark-info-vacancy?lang={lang}",
        method="GET",
    )

    d = page.data
    data = d.decode("utf-8-sig").encode("utf-8")
    jsn = json.loads(data)
    my_lat = lat
    my_lon =  long
    my_lang = lang
    jsn["coor"] = [my_lat,my_lon]
    jsn["lang"] = my_lang

    for entry in jsn["results"]:
        lati = entry["latitude"]
        longi = entry["longitude"]
        coor = (lati,longi)
        your_coor = (my_lat,my_lon)

        entry["distance"] = geopy.distance.geodesic(coor,your_coor).km

        
    jsn["results"] = sorted(jsn["results"], key=lambda k: k.get('distance'), reverse=False)
    
    if limit == 0:
        return jsn
    else:
        jsn["results"] = jsn["results"][:limit]
        return jsn
    
@app.get(
        "/search",
        description="中英文地址皆可"
        )
async def search(
    address: str = "調景嶺IVE"
    ):
    
    carparks = requests.get(
    url="https://resource.data.one.gov.hk/td/carpark/basic_info_all.json",
    )

    carparks_data = carparks.content
    carparks_data_in_utf8 = carparks_data.decode("utf-8-sig")
    carparks_list = json.loads(carparks_data_in_utf8)
    
    params = {"q":address}
    geoInfoMap = requests.get(
        "https://geodata.gov.hk/gs/api/v1.0.0/locationSearch",
        params=params
        ).json()

    carpark_nearby = []

    for entry in geoInfoMap:
        hk80_coor = [entry["x"],entry["y"]]
        geodetic_params = {
            "inSys":"hkgrid",
            "outSys":"wgsgeog",
            "e":entry["x"],
            "n":entry["y"]
            }
        hk80tolatlong = requests.get(
            "https://www.geodetic.gov.hk/transform/v2/",
            params=geodetic_params
        ).json()

        
        entry["lat_long"] = [hk80tolatlong["wgsLat"],hk80tolatlong["wgsLong"]]
        for carpark in carparks_list["car_park"]:
            carpark["distance_from_input_address"] = geopy.distance.geodesic(
                (entry["lat_long"][0],
                 entry["lat_long"][1]),
                 (carpark['latitude'],
                  carpark['longitude'])
                  ).km
            
            if (carpark["distance_from_input_address"] <= 0.5):
                carpark_nearby.append(carpark)

    carpark_nearby_and_input_address = {}
    carpark_nearby_and_input_address["search_address"] = address
    carpark_nearby_and_input_address["return_result"] = geoInfoMap
    carpark_nearby_and_input_address["carparks_nearby"] =  {(entry["park_id"]): entry for entry in carpark_nearby}

    return carpark_nearby_and_input_address



if __name__ == "__main__":
    uvicorn.run(
        host="0.0.0.0",
        port=80,
        app="main:app",
        reload=True
          )