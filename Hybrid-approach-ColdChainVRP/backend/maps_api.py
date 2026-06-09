import os
import json
import hashlib
import requests
import polyline
import folium
import folium.plugins
import math

DIST_CACHE_FILE = "dist_cache.json"
DIR_CACHE_FILE = "directions_cache.json"

def _load_cache(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_cache(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f)

def haversine(loc1, loc2):
    R = 6371  # Earth radius in km
    lat1, lon1 = loc1['lat'], loc1.get('lon', loc1.get('lng'))
    lat2, lon2 = loc2['lat'], loc2.get('lon', loc2.get('lng'))
    
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _haversine_matrix(locations):
    n = len(locations)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = haversine(locations[i], locations[j])
    return matrix

def get_road_distances(locations, api_key):
    if not api_key:
        print("Warning: Google Maps API key not found. Using haversine fallback.")
        return _haversine_matrix(locations)
    
    coord_strings = [f"{loc['lat']},{loc.get('lon', loc.get('lng'))}" for loc in locations]
    cache_key = "|".join(coord_strings)
    cache_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
    
    cache_data = _load_cache(DIST_CACHE_FILE)
    if cache_hash in cache_data:
        print("Using cached Distance Matrix.")
        return cache_data[cache_hash]

    print("Fetching Distance Matrix from Google Maps API...")
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": cache_key,
        "destinations": cache_key,
        "mode": "driving",
        "key": api_key
    }
    
    try:
        resp = requests.get(url, params=params).json()
        if resp.get("status") != "OK":
            print(f"API Error: {resp.get('error_message', resp.get('status'))}. Using fallback.")
            return _haversine_matrix(locations)
            
        n = len(locations)
        dist_matrix = [[0] * n for _ in range(n)]
        for i, row in enumerate(resp["rows"]):
            for j, element in enumerate(row["elements"]):
                if element["status"] == "OK":
                    dist_matrix[i][j] = element["distance"]["value"] / 1000.0
                else:
                    dist_matrix[i][j] = haversine(locations[i], locations[j])
                    
        cache_data[cache_hash] = dist_matrix
        _save_cache(DIST_CACHE_FILE, cache_data)
        return dist_matrix
        
    except Exception as e:
        print(f"Request failed: {e}. Using fallback.")
        return _haversine_matrix(locations)

def build_route_map(routes, depot, clinics, api_key, hide_lines=False):
    if not clinics and routes:
        # If clinics not provided but routes exist, try to guess the scenario and load clinics
        # We can guess based on the node IDs in the routes
        max_id = 0
        for vid, vdata in routes.items():
            route_seq = vdata.get('route', []) if isinstance(vdata, dict) else vdata
            if isinstance(route_seq, list):
                for id in route_seq:
                    orig_id = id // 1000 if id >= 1000 else id
                    if orig_id > max_id: max_id = orig_id
                    
        import sys
        import os
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        if backend_dir not in sys.path: sys.path.insert(0, backend_dir)
        
        try:
            if max_id > 25:
                import scenario_stress as sc
            elif max_id > 15:
                import scenario_hyd as sc
            elif max_id > 10:
                import scenario_blr as sc
            else:
                import scenario as sc
            clinics = sc.CLINICS
            if not depot:
                depot = sc.DEPOT
        except Exception as e:
            print(f"Fallback clinic loading failed: {e}")

    m = folium.Map(
        location=[depot['lat'], depot.get('lon', depot.get('lng'))] if depot else [13.0827, 80.2707], 
        zoom_start=11, 
        tiles="CartoDB dark_matter"
    )
    
    # Inject CSS to make the map background (unused space) pitch black
    m.get_root().html.add_child(folium.Element(
        "<style>.leaflet-container { background: #000 !important; }</style>"
    ))
    
    if depot:
        # Draw depot
        folium.Marker(
            [depot['lat'], depot.get('lon', depot.get('lng'))],
            popup="Depot",
            icon=folium.plugins.BeautifyIcon(
                icon='home',
                icon_shape='marker',
                background_color='black',
                border_color='white',
                text_color='white'
            )
        ).add_to(m)
    
    colors = ['#8fd6c2', '#9fb7e8', '#d8bd7f', '#caa5d8', '#d89b9b']
    clinic_colors = {}
    if routes:
        for idx, (vid, vdata) in enumerate(routes.items()):
            color = colors[idx % len(colors)]
            route_seq = vdata.get('route', []) if isinstance(vdata, dict) else vdata
            if isinstance(route_seq, list):
                for id in route_seq:
                    orig_id = id // 1000 if id >= 1000 else id
                    clinic_colors[orig_id] = color
                    clinic_colors[str(orig_id)] = color

    if clinics:
        for c in clinics:
            cid = c.get('id')
            bg_color = clinic_colors.get(cid, 'black')
            border_color = 'white' if bg_color == 'black' else bg_color
            folium.Marker(
                location=[c['lat'], c.get('lon', c.get('lng'))],
                popup=c.get('name', f"Clinic {cid}"),
                icon=folium.plugins.BeautifyIcon(
                    number=str(cid),
                    icon_shape='marker',
                    background_color=bg_color,
                    border_color=border_color,
                    text_color='white',
                    inner_icon_style='margin-top:0px;font-size:12px;font-weight:bold;'
                )
            ).add_to(m)
        
        node_map = {0: depot}
        for c in clinics:
            node_map[c['id']] = c
    else:
        # Fallback: create node_map from routes if clinics array is empty
        node_map = {0: depot}
        drawn_nodes = set([0])
        if routes:
            for vid, vdata in routes.items():
                route_seq = vdata.get('route', []) if isinstance(vdata, dict) else vdata
                if not isinstance(route_seq, list):
                    continue
                # For predefined scenarios, we don't have lat/lon for the clinics themselves 
                # in the frontend, so we can't draw them accurately unless we fetch them or 
                # pass them from backend. Wait, node_map NEEDS lat/lon to draw lines!
        
    cache_data = _load_cache(DIR_CACHE_FILE)
    colors = ['#8fd6c2', '#9fb7e8', '#d8bd7f', '#caa5d8', '#d89b9b']
    
    metrics = {}

    if routes:
        for idx, (vid, vdata) in enumerate(routes.items()):
            color = colors[idx % len(colors)]
            
            # Support both formats: vdata could be a dict with 'route' or just a list
            route_seq = vdata.get('route', []) if isinstance(vdata, dict) else vdata
            if not isinstance(route_seq, list):
                continue
                    
            coords = []
            for id in route_seq:
                orig_id = id // 1000 if id >= 1000 else id
                if orig_id in node_map:
                    coords.append(node_map[orig_id])
                    
            if len(coords) < 2:
                continue
                
            if not api_key:
                if not hide_lines:
                    pts = [[c['lat'], c.get('lon', c.get('lng'))] for c in coords]
                    folium.PolyLine(pts, color=color, weight=3, opacity=0.8).add_to(m)
                continue
                
            MAX_WPTS = 23 # Google allows 25 total (origin + 23 waypoints + dest)
            chunked_points = []
            
            for i in range(0, len(coords)-1, MAX_WPTS+1):
                chunk = coords[i:i+MAX_WPTS+2]
                if len(chunk) < 2:
                    break
                    
                origin = f"{chunk[0]['lat']},{chunk[0].get('lon', chunk[0].get('lng'))}"
                dest = f"{chunk[-1]['lat']},{chunk[-1].get('lon', chunk[-1].get('lng'))}"
                
                waypoints = ""
                if len(chunk) > 2:
                    w_str = "|".join([f"{c['lat']},{c.get('lon', c.get('lng'))}" for c in chunk[1:-1]])
                    waypoints = f"optimize:false|{w_str}"
                    
                cache_key = f"{origin}_{dest}_{waypoints}"
                cache_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
                
                points = None
                if cache_hash in cache_data:
                    points = cache_data[cache_hash]
                else:
                    url = "https://maps.googleapis.com/maps/api/directions/json"
                    params = {
                        "origin": origin,
                        "destination": dest,
                        "mode": "driving",
                        "key": api_key
                    }
                    if waypoints:
                        params["waypoints"] = waypoints
                        
                    try:
                        resp = requests.get(url, params=params).json()
                        if resp.get("status") == "OK":
                            encoded_poly = resp["routes"][0]["overview_polyline"]["points"]
                            points = polyline.decode(encoded_poly)
                            cache_data[cache_hash] = points
                            _save_cache(DIR_CACHE_FILE, cache_data)
                        else:
                            print(f"Directions API Error: {resp.get('status')}")
                    except Exception as e:
                        print(f"Directions API failed: {e}")
                        
                if points:
                    chunked_points.extend(points)
                else:
                    pts = [[c['lat'], c.get('lon', c.get('lng'))] for c in chunk]
                    chunked_points.extend(pts)
                    
            if chunked_points and not hide_lines:
                folium.PolyLine(chunked_points, color=color, weight=3.5, opacity=0.9).add_to(m)

    return m, metrics
