import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_MAPS_API_KEY")

def test_maps():
    print(f"Using API Key: {api_key[:10]}...")
    search_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query=Ferreterias+en+Rosario&key={api_key}"
    res = requests.get(search_url).json()
    
    if res.get("status") != "OK":
        print("Error in TextSearch:", res)
        return
        
    results = res.get("results", [])
    print(f"Found {len(results)} places.")
    
    for place in results[:3]:
        place_id = place.get("place_id")
        details_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_phone_number,formatted_address&key={api_key}"
        det_res = requests.get(details_url).json()
        
        if det_res.get("status") == "OK":
            d = det_res.get("result", {})
            name = d.get("name", "")
            phone = d.get("formatted_phone_number", "")
            address = d.get("formatted_address", "")
            print(f"Name: {name} | Phone: {phone} | Address: {address}")
        else:
            print(f"Error in Details for {place_id}:", det_res)

if __name__ == "__main__":
    test_maps()
