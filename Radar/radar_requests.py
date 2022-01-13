import requests

class RadarRequests:
    """
    Abstract most relevant Radar API requests.
    """

    base_domain = "https://api.radar.io/v1/"

    def __init__(self, env):
        self.api_key = env["TEST_CLIENT_KEY"]

    def _base_get_request(self, path, params={}):
        """
        Makes a default GET request to the base Radar endpoint
        :param path: The path to make the request to off the base domain. Exclude leading foreslash
        :param params: Query params to make with the get request
        :return: Dictionary of json response
        """

        if params is None:
            params = {}
        url = self.base_domain + path
        headers = {"Authorization": self.api_key}

        response = requests.get(url, headers=headers, params=params)

        return response.json()

    def _base_post_request(self, path, body={}):
        """
        Makes a default POST request to the base Radar endpoint
        :param path: The path to make the request to off the base domain. Exclude leading foreslash
        :param body: JSON body to make with the get request
        :return: Dictionary of json response
        """
        url = self.base_domain + path
        headers = {"Authorization": self.api_key}

        response = requests.post(url, headers=headers, json=body)

        return response.json()

    def get_nearby_geofences(self, cord, radius=5921, limit=20, tags=[]):
        """
        Return a dictionary of the nearby geofences. Refer to Radar API for dictionary schema.
        :param cord: ([Float, Float]) Cordinate for centroid
        :param radius: (Int) Radius from coordinate to perform search. In meters.
        :param limit: (Int) Limit geofences returned
        :param tags: (List) Tags to filter by.
        :return:
        """
        lat = float(cord[0])
        long = float(cord[1])

        path = "search/geofences"
        params = {
            "tags": ",".join(tags),
            "near": f"{lat},{long}",
            "radius": radius,
            "limit": limit
        }

        response = self._base_get_request(path=path, params=params)
        return response

    def get_distance(self, origin, destination, travel_mode, units="metric"):
        """
        Calculate Travel Distance and Duration between origin and destination. Refer to Radar API Doc's
        :param origin: (Tuple) Pair of Lat long Coordinates
        :param destination: (Tuple) Pair of Lat long Coordinates
        :param travel_mode: (String) Value must be either "car" or 'foot"
        :param units: (String) Defaults to "metric" Refer to Radar API Documentation.
        :return: Dictionary of distance and travel times.
        """

        travel_mode = travel_mode.lower() # Normalize
        if travel_mode not in ["car", "foot"]:
            raise ValueError("Travel Mode incorrect value")

        path = "route/distance"
        params = {
            "origin": ",".join(origin),
            "destination": ",".join(destination),
            "modes": travel_mode,
            "units": units
        }

        response = self._base_get_request(path=path, params=params)
        return response

    def reverse_geocode(self, lat, long):
        """
        Convert coordinates to a human readable address. Refer to Radar API documentation.
        :param lat: (Float) Latitude
        :param long: (Float) Longitude
        :return: Dictionary of address information.
        """
        path = "geocode/reverse"
        params = {"coordinates": f"{lat}, {long}"}

        response = self._base_get_request(path=path, params=params)
        return response

    def track(self, device_data, accuracy=10, stopped=False, body={}):
        """
        Submit a location update for a track event in Radar.
        :param device_data: (Dictionary) Must contain ~ 'device_id' (str), 'user_id' (str), 'position' (coordinate pair).
        :param accuracy: (Int) Location update accuracy. Defaults to 10
        :param body: (Dictionary) Additional Track Data
        :return: Dictionary of track response. Refer to Radar API Documentation
        """
        path = "track"

        body["deviceId"] = str(device_data["deviceId"])
        body["userId"] = str(device_data["userId"])
        body["latitude"] = device_data["position"][0]
        body["longitude"] = device_data["position"][1]
        body["accuracy"] = accuracy
        body["stopped"] = stopped

        response = self._base_post_request(path=path, body=body)
        return response

    def trip_update(self, trip_status, device_data, destination_geofence_tag, destination_geofence_id, travel_mode, trip_id=None):
        """
        Start / Complete a trip. Results in 1 track call being made.

        :param trip_status: (str) either "started" or "completed"
        :param device_data: (Dictionary) Must contain ~ 'device_id' (str), 'user_id' (str), 'position' (coordinate pair).
        :param destination_geofence_tag: (str) The tag for the destination geofence in Radar.
        :param destination_geofence_id: (str) The id for the destination geofence in Radar.
        :param travel_mode: (str) either "car" or "foot"
        :param trip_id: (str) Random value to be used for trip ID.
        :return: Dictionary of trip data. Refer to Radar API Documentation.
        """
        if trip_status not in ["started", "completed"]:
            raise ValueError("Trip Status is incorrect Value")

        if travel_mode not in ["car", "foot"]:
            raise ValueError("Travel Mode incorrect value")

        path = "track"

        body = {
            "tripOptions": {
                "externalId": trip_id,
                "destinationGeofenceTag": destination_geofence_tag,
                "destinationGeofenceExternalId": destination_geofence_id,
                "mode": travel_mode,
                "status": trip_status
            }
        }

        response = self.track(device_data, body=body)
        return {"response": response, "trip_id": trip_id}
