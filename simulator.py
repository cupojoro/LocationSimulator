from typing import List, Any

from traveller import Traveler
from Radar.radar_requests import RadarRequests
from Network.street_graph import StreetGraph

import json
import time
from random import random, choice

ENVIRONMENT_FILE_PATH = "./Environment.json"


class Simulator:
    radar_requests = None
    street_graph = None

    traveller_list: list[Traveler] = []

    roll1 = 0
    roll2 = 0
    roll3 = 0

    fixed_update_poll_delta = 1
    run_clock = 0
    fixed_update_clock = 0

    chance_to_travel_to_geofence = 0
    chance_to_travel_to_multiple_geofences = 0

    run_throttle = 0.2
    max_run_time = 0

    def __init__(self):
        with open(ENVIRONMENT_FILE_PATH) as json_file:
            env_vars = json.load(json_file)

            self.street_graph = StreetGraph(env_vars)
            self.radar_requests = RadarRequests(env_vars)

            self.total_users = env_vars["TOTAL_SIM_USERS"]
            self.max_run_time = env_vars["MAX_RUN_TIME_SECONDS"]

            self.chance_to_travel_to_geofence = env_vars["CHANCE_TO_TRAVEL_TO_GEOFENCE"]
            self.chance_to_travel_to_multiple_nodes = env_vars["CHANCE_TO_TRAVEL_TO_MULTIPLE_NODES"]

            for index in range(0, self.total_users):
                T = Traveler(env_vars, "car", radar_requests=self.radar_requests, street_graph=self.street_graph)
                self.traveller_list.append(T)

            self.load_geofences()

    def load_geofences(self):
        """
        Retrieve geofences in Radar relative to StreetGraph and register them into the StreetGraph
        :return:
        """
        graph_centroid = self.street_graph.focal_point
        graph_size = self.street_graph.graph_size_in_meters
        nearby_geofences = self.radar_requests.get_nearby_geofences(graph_centroid, radius=graph_size)["geofences"]

        geofences_added = []
        for geofence in nearby_geofences:
            geofence_cord = geofence["geometryCenter"]["coordinates"]

            # I THOUGHT IT WAS LAT LONG !! Need to swap I guess
            updated_geofence_cord = [geofence_cord[1], geofence_cord[0]]

            geofences_added.append(geofence["description"])

            simulate_trip = False
            if "metadata" in geofence:
                if "trip_destination" in geofence["metadata"]:
                    simulate_trip = geofence["metadata"]["trip_destination"]

            self.street_graph.add_geofences_by_coords(updated_geofence_cord,
                                                      is_trip_destination=simulate_trip,
                                                      description=geofence["description"])

        print(f"Geofences Added to Graph: \n\t{geofences_added}")

    def run(self):
        """
        Main run function for entire simulation.
        (1) Checks for terminate criteria
        (2) Updates all random variables
        (3) Updates Travellers positions
        :return:
        """
        self.run_clock = time.time()
        self.fixed_update_clock = self.run_clock

        while True:
            time.sleep(self.run_throttle)  # Throttle Update Loop

            # Terminate
            run_time = time.time() - self.run_clock
            if run_time > self.max_run_time:
                return

            # Reroll Update ( Thought I would need this. Going to just save for now )
            # last_fixed_update_delta = time.time() - self.fixed_update_clock
            # if last_fixed_update_delta > self.fixed_update_poll_delta:
            #     self.reroll()
            #     self.fixed_update_clock = time.time()

            # Update Travellers
            for T in self.traveller_list:
                if not T.travelling:
                    ox_origin_node = self.get_random_traveller_node()
                    ox_destination_nodes = self.get_random_destination_node_list()

                    # This might prove to be troublesome with certain setups.
                    while ox_origin_node == ox_destination_nodes[0]:
                        ox_destination_nodes = self.get_random_destination_node_list()

                    T.start(ox_origin_node, ox_destination_nodes)
                else:
                    T.update_position()

    def reroll(self):
        """
        Update random rolls. Thought I would need this since random is expensive.
        :return:
        """
        self.roll1 = random()
        self.roll2 = random()
        self.roll3 = random()

    def get_chance(self):
        """
        Update: Thought I would need this since random is expensive.
        Original:Randomly chose from three random variables to prevent identical Travellers
        :return:
        """
        # return choice([self.roll1, self.roll2, self.roll3])
        return random()

    def get_random_destination_node_list(self):
        """
        Create a list of random destinations for Traveller based on chance context
        :return:
        """
        ox_destination_nodes = [self.get_random_traveller_node()]

        while self.get_chance() < self.chance_to_travel_to_multiple_nodes:
            ox_destination_nodes.append(self.get_random_traveller_node())

        return ox_destination_nodes

    def get_random_traveller_node(self):
        """
        Retrieve a random ox_node for the Traveller based on chance context
        :return:
        """
        if self.get_chance() < self.chance_to_travel_to_geofence:
            return self.street_graph.get_random_geofence_node()
        else:
            return self.street_graph.get_random_ox_node()


S = Simulator()
# S.street_graph.visualize()
S.run()
