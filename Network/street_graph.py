import osmnx as ox
import networkx as nx
import time

from random import choice


class StreetGraph():
    graph = None
    ox_nodes_list = None
    ox_tower_node_list = []

    focal_point = None
    graph_size_in_meters = 0

    node_count = 0

    geofence_ox_nodes = []

    def __init__(self, env):
        self.raw_env_variables = env

        self.focal_point = self.raw_env_variables["REGION_CENTRAL_COORD"]

        self.graph_size_in_meters = self.raw_env_variables["REGION_SIZE_METERS"]

        self.generate_graph(self.raw_env_variables["SIMPLIFY_STREET_GRAPH"])

        self.node_count = self.graph.number_of_nodes()
        self.geofence_ox_nodes = []

        while len(self.ox_tower_node_list) < self.raw_env_variables["TOTAL_LOCATION_TOWERS"]:
            ox_node = self.get_random_ox_node()
            nx.set_node_attributes(self.graph, {ox_node: {"is_tower": True}})
            self.ox_tower_node_list.append(ox_node)

        self.tower_distance_strength = self.raw_env_variables["LOCATION_TOWERS_RANGE_METERS"]

    ### THE NETWORK IS SET TO DRIVE BUT WE ALLOW "FOOT" TRAVAL IN RADAR
    def generate_graph(self, simplify):
        """
        Download and generate the node graph with the osmnx library.
        Since this runs locally and is an intense part of the sim; the timing function is here to udnerstand if the size picked is to large.
        :return: None (Graph saved to memory)
        """
        start = time.time()

        self.graph = ox.graph_from_point(self.focal_point, dist=self.graph_size_in_meters, network_type="drive",
                                         simplify=simplify)
        nx.set_node_attributes(self.graph, False, "is_registered_geofence")
        nx.set_node_attributes(self.graph, False, "is_tower")

        self.ox_nodes_list = list(self.graph.nodes)

        graph_gen_time = time.time() - start
        print(f"Graph Generated in {graph_gen_time} seconds.")

    def get_route(self, ox_origin_node, ox_destination_node):
        """
        Create a list of coordinate pairs that indicate a path one would take through the graph from origin to destination.
        :param ox_origin_node: (OSMNX Node)
        :param ox_destination_node: (OSMNX Node)
        :return: (Dict{List[OSMNX],List[(Cords)]}) Dictionary of both the OSMNX Route and Cords Route.Origin and Destination nodes included.
        """
        node_route = self.get_node_route(ox_origin_node, ox_destination_node)

        cord_route = []
        for node in node_route:
            cord = self.convert_ox_node_to_coordinate_pair(node)
            cord_route.append(cord)

        return {
            "OSMNX_ROUTE":  node_route,
            "CORD_ROUTE":   cord_route
        }

    def get_node_route(self, ox_origin_node, ox_destination_node):
        """
        Use NetworkX to find shortest route through node graph.
        :param ox_origin_node: (OSMNX Node)
        :param ox_destination_node: (OSMNX Node)
        :return:
        """
        return nx.shortest_path(self.graph, ox_origin_node, ox_destination_node)

    def add_geofences_by_coords(self, coord, is_trip_destination=False, description="None"):
        """
        Register a geofence from Radar as a node in the OSMNX graph. Set the node attributes to house the geofence point.
        :param description:(String) description for debugging
        :param is_trip_destination: (Bool)  Is this node a node used for trips.
        :param coord: (List) Coordinate pair
        :return: (Bool) Success
        """
        ox_nearest_node = self.get_nearest_ox_node_to_coordinate(coord[0], coord[1])

        if ox_nearest_node is None:
            return False
        else:
            node_info = {
                "geofence_coordinates": coord,
                "is_registered_geofence": True,
                "is_trip_destination": is_trip_destination,
                "description": description
            }

            nx.set_node_attributes(self.graph, {ox_nearest_node : node_info})
            self.geofence_ox_nodes.append(ox_nearest_node)

            return True

    def get_nearest_ox_node_to_coordinate(self, lat, long):
        """
        Get mearest ox node to coordinate pair
        :param lat: (Float) Latitude
        :param long: (Float) Longitude
        :return: (OSMNX Node)
        """
        return ox.nearest_nodes(self.graph, long, lat)

    def visualize(self):
        """
        Visualize the Graph
        :return:
        """
        # node_color = ["b" if self.is_ox_node_geofence(node) elif self.is_ox_node_tower(node)]
        node_color = []
        for node in self.graph.nodes:
            if self.is_ox_node_geofence(node):
                node_color.append("b")
            elif self.is_ox_node_tower(node):
                node_color.append("lime")
            else:
                node_color.append("w")

        ox.plot_graph(self.graph, node_color=node_color)

    def visualize_ox_node_route(self, route):
        """
        Visualize the OX Node Route
        :param route: (OSMNX Node List)
        :return:
        """
        ox.plot_graph_route(self.graph, route, route_linewidth=6, node_size=1, bgcolor="k")

    def get_random_ox_node(self):
        """
        Select a random node from the graph.
        :return: (OSMNX Node)
        """
        return choice(self.ox_nodes_list)

    def get_random_geofence_node(self):
        """
        Select a random geofence node in graph. NOTE: Must have added geofence nodes first
        :return: (OSMNX Node)
        """
        return choice(self.geofence_ox_nodes)

    def get_distance_between(self, point1, point2):
        """
        Get distance between two points
        :param point1: (List[Float,Float]) coordinate pair
        :param point2: (List[Float,Float]) coordinate pair
        :return: Distance in euclidian units? Degrees?
        """
        return ox.distance.euclidean_dist_vec(point1[0], point1[1], point2[0], point2[1])

    def get_meters_between_points(self, point1, point2):
        """
        Rough estimate of distance between two points on graph.
        :param point1: (List[Float,Float]) coordinate pair
        :param point2:  (List[Float,Float]) coordinate pair
        :return: (Float) distance in meters.
        """
        miles_per_degree = 69.2
        meters_per_mile = 1609.34
        conversion = miles_per_degree * meters_per_mile

        return conversion * self.get_distance_between(point1, point2)

    def convert_ox_node_to_coordinate_pair(self, ox_node):
        """
        Convert an OX node to a coordinate pair. This will use the geofence context to replace the actual coordinate pair.
        :param ox_node: (OSMNX Node)
        :return: (Tuple(Float, Float)) Coordinate Pair
        """
        if self.is_ox_node_geofence(ox_node):
            return self.graph.nodes[ox_node]["geofence_coordinates"]
        else:
            return self.graph.nodes[ox_node]["y"], self.graph.nodes[ox_node]["x"]

    def is_ox_node_geofence(self, ox_node):
        """
        Utility function for checking if node is a registered geofence node.
        :param ox_node: (OSMNX Node)
        :return: (bool) Is node a geofence node.
        """
        if self.graph.nodes[ox_node]["is_registered_geofence"]:
            return True
        else:
            return False

    def is_ox_node_tower(self, ox_node):
        """
        Utility function for checking if node is a tower node.
        :param ox_node: (OSMNX Node)
        :return: (bool) Is node a tower node
        """
        if self.graph.nodes[ox_node]["is_tower"]:
            return True
        else:
            return False

    def get_signal_confidence_from_nearest_tower(self, cord):
        """
        Get a multiplier for the accuracy of the location event based on distance and signal strenght. Lower values should result in higher accuracy.
        :param cord: (List[Float,FLoat]) Coordinate Pair
        :return: (Float) Multiplier
        """
        dist = self.get_distance_from_nearest_tower_node_meters(cord)

        # Let's just tier it out
        if dist < (self.tower_distance_strength * 0.15):
            return 0.5  # High Confidence
        elif dist < (self.tower_distance_strength * 0.5):
            return 0.75  # Medium Confidence
        elif dist < self.tower_distance_strength:
            return 1  # Normal Confidence
        elif dist < (self.tower_distance_strength * 1.25):
            return 2  # Lower Confidence
        elif dist < (self.tower_distance_strength * 1.5):
            return 2.75  # Bad Confidence
        else:
            return 10  # No Confidence

    def get_distance_from_nearest_tower_node_meters(self, cord):
        """
        Get the distance from the ox_node to the nearest tower location
        :param cord: (List[Float,FLoat]) Coordinate Pair
        :return: (Float) Meters
        """
        shortest_distance = float("inf")

        for ox_tower_node in self.ox_tower_node_list:
            tower_cord = self.convert_ox_node_to_coordinate_pair(ox_tower_node)
            meters_between = self.get_meters_between_points(cord, tower_cord)
            if meters_between < shortest_distance:
                shortest_distance = meters_between

        return shortest_distance

# G = StreetGraph()
# node = G.graph.nodes[G.get_random_ox_node()]
# G.add_geofences_by_coords([33.19207534963955, -117.37600805474315])
#
# for node in G.graph.nodes:
#     if( G.graph.nodes[node]["is_registered_geofence"]):
#         print(G.graph.nodes[node]["geofence_coordinates"])
