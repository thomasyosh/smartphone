from fastapi import FastAPI
import geopy.distance
import uvicorn
import requests
import json
import urllib3
from urllib3 import ProxyManager
import geopy.distance

app = FastAPI(
    docs_url="/moodle",
)

@app.get("/")
async def root(
    lat: float = 0,
    long: float = 0,
    limit: int = 10
    ):
    
    # http = ProxyManager("")

    page = urllib3.request(
        url="https://resource.data.one.gov.hk/td/carpark/basic_info_all.json",
        method="GET",
    )

    d = page.data
    data = d.decode("utf-8-sig").encode("utf-8")
    jsn = json.loads(data)
    my_lat = lat
    my_lon =  long
    jsn["coor"] = [my_lat,my_lon]

    for entry in jsn["car_park"]:
        lati = entry["latitude"]
        longi = entry["longitude"]
        coor = (lati,longi)
        your_coor = (my_lat,my_lon)
        entry["distance"] = geopy.distance.geodesic(coor,your_coor).km
        
    jsn["car_park"] = sorted(jsn["car_park"], key=lambda k: k.get('distance'), reverse=False)
    
    if limit == 0:
        return jsn
    else:
        jsn["car_park"] = jsn["car_park"][:limit]
        return jsn

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


if __name__ == "__main__":
    uvicorn.run(
        host="0.0.0.0",
        port=8081,
        app="main:app",
        reload=True
          )