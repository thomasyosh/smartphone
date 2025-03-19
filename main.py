from fastapi import FastAPI
import geopy.distance
import uvicorn
import requests
import json
import urllib3
from urllib3 import ProxyManager
import geopy.distance
from pyproj import Transformer
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session

app = FastAPI(
    docs_url="/moodle",
)

DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: int

    class Config:
        orm_mode = True

# User model for SQLAlchemy
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    age = Column(Integer, nullable=False)

# Create the database table
Base.metadata.create_all(bind=engine)

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

@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(name=user.name, email=user.email, age=user.age)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users/", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

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
        "/v2",
        description="中英文地址皆可",
        )
async def search(
    address: str = "調景嶺IVE",
    numberOfAddressQueryResult: int = 5,
    kmDistanceOfCarparkFromAddress: float = 1
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
        ).json()[:numberOfAddressQueryResult]

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
            
            if (carpark["distance_from_input_address"] <= kmDistanceOfCarparkFromAddress):
                carpark_nearby.append(carpark)

    carpark_nearby_and_input_address = {}
    carpark_nearby_and_input_address["search_address"] = address
    carpark_nearby_and_input_address["return_result"] = geoInfoMap
    unique = {(item["park_id"]):item for item in
           sorted(carpark_nearby, key=lambda x: x['distance_from_input_address'])}

    carpark_nearby_and_input_address["carparks_nearby"] =  sorted(unique.values(), key=lambda x: (x['park_id']))
    carpark_nearby_and_input_address["carparks_nearby"] =  sorted(carpark_nearby_and_input_address["carparks_nearby"], key=lambda x: (x['distance_from_input_address']))
    return carpark_nearby_and_input_address

@app.get(
        "/v3",
        description="中英文地址皆可",
        )
async def search(
    address: str = "調景嶺IVE",
    numberOfAddressQueryResult: int = 5,
    kmDistanceOfCarparkFromAddress: float = 1,
    lang: str = ""
    ):
    
    carparks = requests.get(
        url=f"https://api.data.gov.hk/v1/carpark-info-vacancy?lang={lang}",
    )

    carparks_data = carparks.content
    carparks_data_in_utf8 = carparks_data.decode("utf-8-sig")
    carparks_list = json.loads(carparks_data_in_utf8)
    
    params = {"q":address}
    geoInfoMap = requests.get(
        "https://geodata.gov.hk/gs/api/v1.0.0/locationSearch",
        params=params
        ).json()[:numberOfAddressQueryResult]

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
        for carpark in carparks_list["results"]:
            carpark["distance_from_input_address"] = geopy.distance.geodesic(
                (entry["lat_long"][0],
                 entry["lat_long"][1]),
                 (carpark['latitude'],
                  carpark['longitude'])
                  ).km
            
            if (carpark["distance_from_input_address"] <= kmDistanceOfCarparkFromAddress):
                carpark_nearby.append(carpark)

    carpark_nearby_and_input_address = {}
    carpark_nearby_and_input_address["search_address"] = address
    carpark_nearby_and_input_address["return_result"] = geoInfoMap
    unique = {(item["park_Id"]):item for item in
           sorted(carpark_nearby, key=lambda x: x['distance_from_input_address'])}

    carpark_nearby_and_input_address["carparks_nearby"] =  sorted(unique.values(), key=lambda x: (x['park_Id']))
    carpark_nearby_and_input_address["carparks_nearby"] =  sorted(carpark_nearby_and_input_address["carparks_nearby"], key=lambda x: (x['distance_from_input_address']))
    return carpark_nearby_and_input_address



if __name__ == "__main__":
    uvicorn.run(
        host="0.0.0.0",
        port=80,
        app="main:app",
        reload=True
          )