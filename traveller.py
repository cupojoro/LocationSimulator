from Radar.radar_requests import RadarRequests
from Network.street_graph import StreetGraph

import time
import numpy
import math
from random import randint
import uuid


class Traveler():

    travelling = False
    return_trip = False
    stopped = False
    stopped_clock = 0

    ox_origin = None
    ox_destination = None
    ox_destinations = None

    ox_start_edge_node = None
    ox_end_edge_node = None
    ox_node_route = []

    cord_current_position = None

    track_call_frequency = 0
    last_track_request_clock = 0
    always_track_on_nodes = False
    always_track_on_geofence_nodes = False

    average_accuracy = 0
    current_accuracy = 0

    total_travel_time = 0
    started_travel_on_edge_clock = 0
    travel_mode = None
    travel_speed = 0

    min_dwell_time_seconds = 0
    max_dwell_time_seconds = 0
    dwell_time_at_destination = 0

    def __init__(self, env, travel_mode, radar_requests: RadarRequests, street_graph: StreetGraph):
        self.radar_requests = radar_requests
        self.street_graph = street_graph

        self.min_dwell_time_seconds = env["MIN_DWELL_TIME_SECONDS"]
        self.max_dwell_time_seconds = env["MAX_DWELL_TIME_SECONDS"]

        self.average_accuracy = env["AVERAGE_LOCATION_ACCURACY"]
        self.current_accuracy = self.average_accuracy

        self.travel_mode = travel_mode

        if self.travel_mode.lower() == "car":
            self.travel_speed = env["CAR_TRAVEL_SPEED_METERS_PER_SECOND"]
        elif self.travel_mode.lower() == "foot":
            self.travel_speed = env["FOOT_TRAVEL_SPEED_METERS_PER_SECOND"]

        self.uuid = uuid.uuid4().hex[:8]
        self.userId = env["USER_ID_PREFIX"] + self.uuid
        self.deviceId = env["DEVICE_ID_PREFIX"] + self.uuid

        self.track_call_frequency = env["USER_TRACK_FREQUENCY"]
        self.always_track_on_nodes = env["ALWAYS_TRACK_ON_NODES"]
        self.always_track_on_geofence_nodes = env["ALWAYS_TRACK_ON_GEOFENCE_NODE"]

    def start(self, ox_origin_node, ox_destination_nodes):
        """
        Initiate the traveller with their proper route and coordinates
        :param ox_origin_node:  (OSMNX Node) Origin Node
        :param ox_destination_nodes: (List[OSMNX Node])  List of destinations
        :return: None
        """
        self.travelling = True
        self.return_trip = False

        self.ox_origin = ox_origin_node
        self.ox_destinations = ox_destination_nodes
        self.ox_destination = self.ox_destinations.pop(0)

        self.setup_route(self.ox_origin, self.ox_destination)

    def setup_route(self, ox_start_node, ox_end_node):
        """
        Create a new route with dwell context for the 'update_position' function
        :param ox_start_node: (OSMNX Node)
        :param ox_end_node: (OSMNX Node)
        :return:
        """
        self.ox_node_route = self.street_graph.get_node_route(ox_start_node, ox_end_node)

        self.ox_node_route.pop(0)
        self.ox_start_edge_node = ox_start_node
        self.ox_end_edge_node = self.ox_node_route.pop(0)

        self.cord_current_position = self.street_graph.convert_ox_node_to_coordinate_pair(self.ox_start_edge_node)

        self.total_travel_time = self.calculate_travel_time_between_two_nodes(self.ox_start_edge_node, self.ox_end_edge_node)
        self.dwell_time_at_destination = randint(self.min_dwell_time_seconds, self.max_dwell_time_seconds)

        self.started_travel_on_edge_clock = time.time()

        self.resolve_force_track_options()
        self.stopped = False

    def stop_update(self):
        """
        Handle stop behvaior when at a destination. This will lead to one of three outcomes:
        1) Setting up the next route in a multidestination journey
        2) Setup a return trip if at the end of a journey
        3) Disable travelling if we have reached the end of the return trip
        :return:
        """
        if len(self.ox_destinations) == 0:
            if self.return_trip:
                self.travelling = False
            else:
                self.setup_return_trip()
        else:
            current_dwell_time = time.time() - self.stopped_clock
            if current_dwell_time >= self.dwell_time_at_destination:
                current_ox_node = self.ox_destination #We stopped here
                self.ox_destination = self.ox_destinations.pop(0)

                self.setup_route(current_ox_node, self.ox_destination)

    def setup_return_trip(self):
        """
        Iniate the route from our current position to whereever we started toggling the 'return_trip' flag.
        :return:
        """
        print("\tDestination Reached, Returning to Start.")
        self.setup_route(self.ox_destination, self.ox_origin)
        self.return_trip = True

    def update_position(self):
        """
        LERP the position along the graph (This is bad math but quick)
        :return:
        """
        if not self.travelling:
            return

        if self.stopped:
            self.stop_update()
            return

        start_cord = self.street_graph.convert_ox_node_to_coordinate_pair(self.ox_start_edge_node)
        end_cord = self.street_graph.convert_ox_node_to_coordinate_pair(self.ox_end_edge_node)

        time_passed_on_edge = time.time() - self.started_travel_on_edge_clock
        total_perc_edge_travelled = numpy.clip(time_passed_on_edge / self.total_travel_time, 0, 1.0)  # Percentage

        new_cords = self.lerp_cords(start_cord, end_cord, total_perc_edge_travelled)
        self.cord_current_position = new_cords
        self.update_accuracy()

        delta_time_since_last_track_request = time.time() - self.last_track_request_clock
        if delta_time_since_last_track_request >= self.track_call_frequency:
            self.track()

        if total_perc_edge_travelled >= 1.0:
            self.swap_edges()

    def swap_edges(self):
        """
        Traveller reached end of edge in node graph. Swap to next edge in route.
        :return:
        """
        if len(self.ox_node_route) == 0:
            # Stop then track for event if geofence
            if self.street_graph.is_ox_node_geofence(self.ox_destination):
                self.stopped = True
                self.track()
                self.stopped = False
            self.stopped_clock = time.time()
        else:
            print("\tMoving to new edge.")
            self.ox_start_edge_node = self.ox_end_edge_node
            self.ox_end_edge_node = self.ox_node_route.pop(0)
            self.total_travel_time = self.calculate_travel_time_between_two_nodes(self.ox_start_edge_node,
                                                                                  self.ox_end_edge_node)
            self.started_travel_on_edge_clock = time.time()

            self.resolve_force_track_options()

    def resolve_force_track_options(self):
        """
        Helper function for force tracking depending on environment settings.
        :return:
        """
        if self.always_track_on_nodes:
            self.track()
        elif self.always_track_on_geofence_nodes and self.street_graph.is_ox_node_geofence(self.ox_start_edge_node):
            #Have to stop to ensure event generated in Radar
            self.stopped = True
            self.track()
            self.stopped = False

    def calculate_travel_time_between_two_nodes(self, ox_node_start, ox_node_end):
        """
        Get the amount of time it will take for the travel to move between nodes based on travel mode and speed.
        :param ox_node_start: (OSMNX Node)
        :param ox_node_end: (OSMNX Node)
        :return: (Float) travel time
        """
        start_cord = self.street_graph.convert_ox_node_to_coordinate_pair(ox_node_start)
        end_cord = self.street_graph.convert_ox_node_to_coordinate_pair(ox_node_end)

        meters_between_coords = self.street_graph.get_meters_between_points(start_cord, end_cord)

        return meters_between_coords / self.travel_speed

    def lerp_cords(self, start_cords, end_cords, percentage):
        """
        Utility function to interpolate two coordinates
        :param start_cords: (float,float) Coordinates
        :param end_cords: (float, float) Coordinates
        :param percentage: [0,1]
        :return: (float, float) Interpolated Coordinates
        """
        new_lat = self.lerp(start_cords[0], end_cords[0], percentage)
        new_long = self.lerp(start_cords[1], end_cords[1], percentage)

        return new_lat, new_long

    def lerp(self, s, e, p):
        """
        Lerp over percentage
        :param s: (Float) Start
        :param e: (Float) End
        :param p: (Float)[0:1] Perecntage
        :return: (Float) new value
        """
        return s + (e - s) * p

    # END OF MERP

    def update_accuracy(self):
        """
        Update the accuracy sent in the track call based on distance to a random 'cell tower' defined in the Street Graph
        :return:
        """
        confidence_multiplier = self.street_graph.get_signal_confidence_from_nearest_tower(self.cord_current_position)
        self.current_accuracy = int(math.ceil(self.average_accuracy * confidence_multiplier))

    def track(self):
        """
        Update the accuracy and the current position of the Traveller. Returns if we have reached our destination.
        :return: (Bool) Reached Destination
        """

        track_request = {
            "position": self.cord_current_position,
            "deviceId": self.deviceId,
            "userId": self.userId,
            "accuracy": self.current_accuracy,
            "stopped": self.stopped
        }

        print(f"Track Request: {track_request}")

        self.radar_requests.track(
            {
                "position": self.cord_current_position,
                "deviceId": self.deviceId,
                "userId": self.userId
            },
            accuracy=self.current_accuracy,
            stopped=self.stopped
        )

        self.last_track_request_clock = time.time()

# import json
# ENVIRONMENT_FILE = "./Environment.json"
# with open(ENVIRONMENT_FILE) as json_file:
#         env = json.load(json_file)
#
# G = StreetGraph()
# G.add_geofences_by_coords((33.19207534963955, -117.37600805474315))
# R = RadarRequests()
# T = Traveler(R, G, env, "car")
#
# T.start(G.get_random_ox_node(), [G.get_random_geofence_node(), G.get_random_ox_node(), G.get_random_ox_node()])
#
# while T.travelling:
#     T.update_position()