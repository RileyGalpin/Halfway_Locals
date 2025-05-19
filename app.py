from flask import Flask, request, render_template
import requests
import googlemaps
import polyline
import json

#TODOS:  draw radii per driver, deal w different cases (driving times, miles vs km, or milage, and be able to return data on miles and driving time)
# also locate places in area, and have option to load more and filter. maybe be able to share routes? or places?? also display
GOOGLE_MAPS_API_KEY = "AIzaSyDA_ZxADAp89anlYWLLYIENka9Zex6BPBw"
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
     
    midpoint_lat = 0
    midpoint_long = 0
    driver1 = 5
    driver2 = 5
    coord1 = {"latitude": 0, "longitude": 0}
    coord2 = {"latitude": 0, "longitude": 0}
    places = []

    if request.method == 'POST':
        
        addr1 = request.form.get('address1', '')
        addr2 = request.form.get('address2', '')
        
        def parse_float(value, default):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        driver1 = parse_float(request.form.get('driver1'), 5)
        driver2 = parse_float(request.form.get('driver2'), 5)

        placetype = request.form.get('place', 'restaurant')

        units = request.form.get('unit', 'imperial')
        
        if units == "imperial":
            driver1 *= 1609.34
            driver2 *= 1609.34
            
        if units == "metric":
            driver1 *= 1000
            driver2 *= 1000
        
        coord1 = get_lat_long(addr1)
        coord2 = get_lat_long(addr2)

        if not coord1 or not coord2:
            return "<h2>Could not geocode one or both addresses.</h2>"

        midpoint_coords, places = calculate_route_midpoint(addr1, addr2, placetype, units, driver1, driver2)
        if not midpoint_coords:
            return "<h2>Route calculation failed.</h2>"
        
        return render_template(
            'halfway.html',
            midpoint_lat = midpoint_coords[0],
            midpoint_long = midpoint_coords[1],
            driver1 = driver1,
            driver2 = driver2,
            places = places,
            coord1 = coord1,
            coord2 = coord2,
            units = units,
            show_map = True
        )

    # For initial GET request, provide empty/default values for all template variables
    return render_template(
        'halfway.html',
        midpoint_lat = midpoint_lat,
        midpoint_long = midpoint_long,
        driver1 = driver1,
        driver2 = driver2,
        places = places,
        coord1 = coord1,
        coord2 = coord2,
        units = "imperial",
        show_map = True
    )
                           
#converts address into lat and long coordinates
def get_lat_long(addr):
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": addr,
        "key": GOOGLE_MAPS_API_KEY
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()

        if data["status"] == "OK":
            location = data["results"][0]["geometry"]["location"]
            latitude = location["lat"]
            longitude = location["lng"]
            return {"latitude": latitude, "longitude": longitude}
        else:
            print(f"Geocoding failed with status: {data['status']}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the request: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"An error occurred while parsing the response: {e}")
        return None

#get midpoint of the two addresses (absolute based on coordinates)
def calculate_abolute_midpoint(x1, y1, x2, y2):
    xmidpoint = (x1 + x2) / 2
    ymidpoint = (y1 + y2) / 2
    return {"latitude": xmidpoint, "longitude": ymidpoint}
    
#uses distance matrix api, gets distance in minutes and miles or km from a-b (TEST FOR KM)
def get_distance_duration(place, address, units = "imperial"):
    """
    Calculate distance and duration between a place and an address
    
    Args:
        place: A place dictionary with location information
        address: An address string or coordinates
        units: 'metric' or 'imperial'
    
    Returns:
        Dictionary with distance and duration information or None if failed
    """
    base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    # Format the place's location as a string for the API
    if isinstance(place, dict) and 'location' in place:
        if 'lat' in place['location'] and 'lng' in place['location']:
            origin = f"{place['location']['lat']},{place['location']['lng']}"
        else:
            print(f"Invalid place location format: {place}")
            return None
    else:
        print(f"Invalid place format: {place}")
        return None
    
    # Handle different formats for the address parameter
    if isinstance(address, dict):
        if 'latitude' in address and 'longitude' in address:
            destination = f"{address['latitude']},{address['longitude']}"
        elif 'lat' in address and 'lng' in address:
            destination = f"{address['lat']},{address['lng']}"
        else:
            print(f"Invalid address dictionary format: {address}")
            return None
    elif isinstance(address, str):
        destination = address
    else:
        print(f"Invalid address format: {address}")
        return None
    
    # Set up the API request parameters
    params = {
        "origins": origin,
        "destinations": destination,
        "units": units,
        "key": GOOGLE_MAPS_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Debug the API response if needed
        # print(f"API Response: {json.dumps(data, indent=2)}")
        
        if data["status"] == "OK":
            # Check if we have valid elements
            if (data["rows"] and data["rows"][0]["elements"] and 
                data["rows"][0]["elements"][0]["status"] == "OK"):
                
                element = data["rows"][0]["elements"][0]
                
                # Extract distance and duration values
                if "distance" in element and "duration" in element:
                    distance_info = element["distance"]
                    duration_info = element["duration"]
                    
                    # Return numerical values for comparison, not text
                    return {
                        "Distance": distance_info["value"],  # meters
                        "Duration": duration_info["value"],  # seconds
                        "DistanceText": distance_info["text"],
                        "DurationText": duration_info["text"]
                    }
                else:
                    print(f"Missing distance or duration in response")
                    return None
            else:
                status = data["rows"][0]["elements"][0]["status"] if data["rows"] and data["rows"][0]["elements"] else "UNKNOWN"
                print(f"Invalid route with status: {status}")
                return None
        else:
            print(f"API request failed with status: {data['status']}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing response: {e}")
        return None


#find locations around the midpoint in the radius of driver 1 and 2
#driver radius = 0->midpoint + 5 or given
#use nearby search api
def find_locals(midpoint_coords, radius_meters, place_type="restaurant", max_results=50):
    location = f"{midpoint_coords['latitude']},{midpoint_coords['longitude']}"
    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": location,
        "radius": radius_meters,
        "type": place_type,
        "key": GOOGLE_MAPS_API_KEY
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "OK":
            results = data.get("results", [])[:max_results]
            places = []
            for place in results:
                places.append({
                    "name": place.get("name"),
                    "location": place.get("geometry", {}).get("location"),
                    "business_status": place.get("business_status")
                })  
            return places
        else:
            print(f"Places API error: {data['status']}")
            return []  # Return empty list instead of None

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return []  # Return empty list instead of None

def calculate_route_midpoint(addr1, addr2, placetype, units, driver1, driver2):
    radius = max(driver1, driver2)  # Use the larger radius for the initial search
    if radius == 0:
        radius = 8000
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "routes.polyline.encodedPolyline"
    }

    # Get geocoded coordinates first
    origin = get_lat_long(addr1)
    destination = get_lat_long(addr2)
    if not origin or not destination:
        print("Could not geocode one or both addresses.")
        return None, []  # Return empty list for places

    body = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": origin["latitude"],
                    "longitude": origin["longitude"]
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": destination["latitude"],
                    "longitude": destination["longitude"]
                }
            }
        },
        "travelMode": "DRIVE"
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

        encoded = data["routes"][0]["polyline"]["encodedPolyline"]
        points = polyline.decode(encoded)
        midpoint_index = len(points) // 2
        midpoint_coords = points[midpoint_index]
        print({"lat": midpoint_coords[0], "lng": midpoint_coords[1]})
        midpoint_lat_lng = {"lat": midpoint_coords[0], "lng": midpoint_coords[1]}
        midpoint_lat_long = {"latitude": midpoint_coords[0], "longitude": midpoint_coords[1]}
    
        # Find places within each driver's radius
        places1 = find_locals(midpoint_lat_long, driver1, placetype)
        places2 = find_locals(midpoint_lat_long, driver2, placetype)
        
        # Create sets of place names for each radius
        places1_names = {place['name'] for place in places1}
        places2_names = {place['name'] for place in places2}
        
        # Start with an empty list for final places
        places = []
        added_places = set()
        
        # Add places that are in both radii
        both_radii_names = places1_names.intersection(places2_names)
        for place in places1:
            if place['name'] in both_radii_names:
                place['in_radius'] = 'both'
                places.append(place)
                added_places.add(place['name'])
                print(f"Added place in both radii: {place['name']}")
        
        # Add places that are only in driver1's radius but closer to driver2
        only_in_radius1 = places1_names - places2_names
        for place in places1:
            if place['name'] in only_in_radius1 and place['name'] not in added_places:
                distance1 = get_distance_duration(place, origin, units)
                distance2 = get_distance_duration(place, destination, units)
                
                if distance1 is None or distance2 is None:
                    print(f"Couldn't get distances for {place['name']}")
                    continue
                
                # Check if place is closer to driver2 even though it's only in driver1's radius
                if distance2['Distance'] <= distance1['Distance']:
                    place['in_radius'] = 'driver1_only_closer_to_driver2'
                    place['distance_to_driver1'] = distance1['DistanceText']
                    place['distance_to_driver2'] = distance2['DistanceText']
                    places.append(place)
                    added_places.add(place['name'])
                    print(f"Added place unique to driver1 radius but closer to driver2: {place['name']}")
        
        # Add places that are only in driver2's radius but closer to driver1
        only_in_radius2 = places2_names - places1_names
        for place in places2:
            if place['name'] in only_in_radius2 and place['name'] not in added_places:
                distance1 = get_distance_duration(place, origin, units)
                distance2 = get_distance_duration(place, destination, units)
                
                if distance1 is None or distance2 is None:
                    print(f"Couldn't get distances for {place['name']}")
                    continue
                
                # Check if place is closer to driver1 even though it's only in driver2's radius
                if distance1['Distance'] <= distance2['Distance']:
                    place['in_radius'] = 'driver2_only_closer_to_driver1'
                    place['distance_to_driver1'] = distance1['DistanceText']
                    place['distance_to_driver2'] = distance2['DistanceText']
                    places.append(place)
                    added_places.add(place['name'])
                    print(f"Added place unique to driver2 radius but closer to driver1: {place['name']}")

        print(f"Total places found: {len(places)}")
        for place in places:
            print(f"- {place['name']} ({place.get('in_radius', 'unknown')})")
            
        return midpoint_coords, places

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None, []  # Return empty list for places
    except (KeyError, IndexError) as e:
        print(f"Error parsing response: {e}")
        return None, []  # Return empty list for places

if __name__ == '__main__':
    app.run(debug=True)