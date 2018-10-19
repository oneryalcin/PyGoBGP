import grpc
import socket
import struct
import pygobgp.gobgp_pb2 as gobgp
import pygobgp.gobgp_pb2_grpc as gobgp_grpc
from pygobgp.errors import PeerNotFound


class PyGoBGP:
    """Basic GoBGP v1.25 Python API"""
    
    def __init__(self, address, port=50051):
        """Connect GoBGP via GRPC"""
        self.gobgp_address = "{}:{}".format(address, port)
        self.channel = grpc.insecure_channel(self.gobgp_address)
        self.stub = gobgp_grpc.GobgpApiStub(self.channel)
        
    def get_rib(self):
        """ 
        Get Routes in BGP-RIB.
        Disclaimer: Only Global IPv4 addresses supported at the moment
        Supported BGP attributes: as path, standard community, next hop ip (v4) and MED,
        there is no support for other BGP attributes at the moment.
        
        gRPC for GetRib is defined as below:
        https://github.com/osrg/gobgp/blob/615454451d59e11786fb7756c68c3c693a1fecfe/api/gobgp.proto#L40
        
        service GobgpApi {
          rpc GetRib(GetRibRequest) returns (GetRibResponse) {}
        }
        
        message GetRibRequest {
          Table table = 1;
        }
        
        message Table {
          Resource type = 1;
          string name = 2;
          uint32 family = 3;
          repeated Destination destinations = 4;
          bool post_policy = 5;
        }
        
        """
        
        # Build GetRibRequest object 
        ipv4_family = 65537      # IPv4 Family
        request = gobgp.GetRibRequest()
        table = gobgp.Table(family=ipv4_family)
        request.table.MergeFrom(table)
        
        # Get Rib contents 
        # raw routes is a GetRibResponse object which contains a Table object
        raw_routes = self.stub.GetRib(request)
        
        # GoBGP returns BGP path attributes not so much in a friendly way,
        # we extract them (kind of hackish for the moment)
        routes = self._extract_routes(raw_routes)
        return routes
    
    def get_neighbor(self, address):
        """
            Get a single BGP Neighbor (Peer) details
        
        GRPC service and messages are defined as below:
        
        service GobgpApi {
          rpc GetNeighbor(GetNeighborRequest) returns (GetNeighborResponse) {}
        }
        
        message GetNeighborRequest {
          bool enableAdvertised = 1;
          string address        = 2;
        }
        """
        resp = self.stub.GetNeighbor(gobgp.GetNeighborRequest())

        for peer in resp.peers:
            if peer.conf.neighbor_address == address:
                return peer
            raise PeerNotFound("BGP Neighbor {} is not in the BGP peer list".format(address))

    def get_all_neighbors(self):
        """
            Get All BGP Neighbors

        GRPC service and messages are defined as below:

        service GobgpApi {
          rpc GetNeighbor(GetNeighborRequest) returns (GetNeighborResponse) {}
        }

        message GetNeighborRequest {
          bool enableAdvertised = 1;
          string address        = 2;
        }
        """
        resp = self.stub.GetNeighbor(gobgp.GetNeighborRequest())
        return resp.peers
        
    def delete_neighbor(self, address):
        """
            Remove BGP neighbor 
        
        GRPC service and messages are defined as below:
        
        service GobgpApi {
          rpc DeleteNeighbor(DeleteNeighborRequest) returns (DeleteNeighborResponse) {}
        }
        
        message DeleteNeighborRequest {
          Peer peer = 1;
        }
        
        """
        # Build PeerConf object 
        conf = gobgp.PeerConf(neighbor_address=address)
        
        # Build Peer object
        peer = gobgp.Peer(families=[65537])
        peer.conf.MergeFrom(conf)
        
        # Build DeleteNeighborRequest object
        request = gobgp.DeleteNeighborRequest()
        request.peer.MergeFrom(peer)
        
        # send DeleteNeighborRequest
        resp = self.stub.DeleteNeighbor(request)
        return resp
    
    def add_neighbor(self, neighbor=None, **kwargs):
        """
            Add a new BGP neighbor,

            Two ways to add a neighbor.
                - Either, define neighbor params as dict and pass as kwargs, or
                - Use pygobgp.Neighbor class (preffered) to define Neighbor params.

            If pygobgp.Neighbor class is used, kwargs won't be used.
        
        kwargs must contain at least the following as an example:
        see https://github.com/osrg/gobgp/blob/615454451d59e11786fb7756c68c3c693a1fecfe/api/gobgp.proto#L626 
        for all parameters available
        {
            "local_address": "10.0.255.2",
            "neighbor_address": "10.0.255.3",
            "local_as": 64512,
            "peer_as": 65001,
        }
        
        GRPC service and messages are defined as below:
        
        service GobgpApi {
          rpc DeleteNeighbor(DeleteNeighborRequest) returns (DeleteNeighborResponse) {}
        }
        
        message DeleteNeighborRequest {
          Peer peer = 1;
        }
        
        """
        
        if not neighbor:
            # Build PeerConf object 
            conf = gobgp.PeerConf(**kwargs)
        
            # Build Peer object
            peer = gobgp.Peer(families=[65537])
            peer.conf.MergeFrom(conf)
        else:
            peer = neighbor.peer
        
        # Build AddNeighborRequest object
        request = gobgp.AddNeighborRequest()
        request.peer.MergeFrom(peer)
        
        # send AddNeighborRequest
        resp = self.stub.AddNeighbor(request)
        return resp

    def _extract_routes(self, routes):
        """ 
            Extract prefixes and BGP path attributes from GetRibResponse object
        
        GOBGP returns attributes as bytes, this needs decoding and an example is below
    
        A new route added by using the following command:
        gobgp global rib add 50.30.20.0/20 origin igp nexthop 60.1.2.3 community 64250:65535,61166:56797
            aspath 52428,170 med 48059 -a ipv4
    
        communities: FAFA:FFFFF, EEEE:DDDD
        as path: CCCC:AA
        MED:BBBB

        65535: FFFF
        64250: FAFA
        61166: EEEE
        56797: DDDD
        52428: CCCC 
        48059: BBBB
    
        GoBGP returns the following:
        As Path prefix is 40020A0202. First AS is 0000CCCC and second AS is 000000AA
        Community prefix is C00808. First community FAFA:FFFF second community EEEE:DDDD
        Next Hop prefix is 400304. Next Hop value is 3c010203 (60.1.2.3)
        MED prefix is 800404. MED value is 0000BBBB
        
        """
        container = []
        for destination in routes.table.destinations:
            prefix = destination.prefix
            as_path = self._extract_as_path(destination)
            next_hop = self._extract_next_hop(destination)
            community = self._extract_community(destination)
            med = self._extract_med(destination)
            route = { 
                "prefix": prefix,
                "as_path": as_path,
                "next_hop": next_hop,
                "community": community,
                "med": med,
            }
            container.append(route)
        return container

    def _extract_as_path(self, destination):
        prefix = "4002"
        for attr in destination.paths[0].pattrs:
            attr = attr.hex()
            if attr.startswith(prefix):
                aspath = attr[10:]
                aspath = list(self.chunkstring(string=aspath, length=8))
                return aspath 
        return None
    
    def _extract_community(self, destination):
        prefix = "C00"
        for attr in destination.paths[0].pattrs:
            attr = attr.hex()
            if attr.upper().startswith(prefix):
                communities = attr[6:]
                communities = list(self.chunkstring(string=communities, length=4))
                output = []
                for index, _ in enumerate(communities):
                    if index % 2 == 1:
                        output.append("{}:{}".format(communities[index-1], communities[index]))
                return output
        return None
    
    def _extract_next_hop(self, destination):
        prefix = "4003"
        for attr in destination.paths[0].pattrs:
            attr = attr.hex()
            if attr.startswith(prefix):
                next_hop = int(attr[6:], 16)
                next_hop = socket.inet_ntoa(struct.pack(">L", next_hop))
                return next_hop 
        return None
    
    def _extract_med(self, destination):
        prefix = "800"
        for attr in destination.paths[0].pattrs:
            attr = attr.hex()
            if attr.startswith(prefix):
                med = int(attr[6:], 16)
                return med
        return None
    
    @staticmethod
    def chunkstring(string, length):
        return (int(string[0+i:length+i], 16) for i in range(0, len(string), length))

    
class Neighbor:
    """
        PyGoBGP Neighbor class (Only supports basic configuration of IPv4 neighbors currently )

    """
    def __init__(self, local_address, neighbor_address, local_as, peer_as, transport_address=None,
                 ebgp_multihop=True, ebgp_multihop_ttl=255, router_id=None, auth_password=None,
                 description=None, **kwargs):
        """

        
        local_address: Local IPv4 address for BGP peering.
        neighbor_adddress: Remote router IPv4 address for BGP peering.
        local_as : Local autonomous system number
        peer_as: Remote autonomous system number.
        transport_address: IPv4 address for outgoing BGP messages. By default set to local_address
        ebgp_multihop: True if enabled. Default True
        ebgp_multihop_ttl: Unlike Cisco routers, by default it's set to 255, not 1.
        router_id: By default set to local_address
        auth_password: BGP MD5 password by default None
        description: Neighbor description, freetext
        apply_policy: Not yet defined, all accept both for out and in policies currently (TODO: Create Policy Class)
        
        """
        self._families = [65537] # Only support for BGP IPv4 currently
        self._local_address = local_address
        self._neighbor_address = neighbor_address
        self._local_as = local_as
        self._peer_as = peer_as
        self._transport_address = transport_address if transport_address else local_address
        self._ebgp_multihop = ebgp_multihop
        self._ebgp_multihop_ttl = ebgp_multihop_ttl
        self._router_id = router_id if router_id else local_address
        self._auth_password = auth_password
        self._description = description
        self.peer = self._create_peer() 

    def _create_peer(self, **kwargs):
        """ 
        Peer object is required for things like AddNeigborRequest, DeleteNeighborRequest, GetNeighborRequest
        https://github.com/oneryalcin/PyGoBGP-Example/blob/372bf4c15fb0a86b5ca8886c8b7a07ec24127136/docker/control/proto_files/gobgp.proto#L119
        """
        
        # Build PeerConf
        peer_conf = self._create_peer_conf(**kwargs)
        
        # Build BGP Transport 
        transport = self._create_transport(**kwargs)
        
        # Build EBGP Multihop
        ebgp_multihop = self._create_ebgp_multihop(**kwargs)
        
        # Build Peer object
        peer = gobgp.Peer(families=self._families)
        peer.conf.MergeFrom(peer_conf)
        peer.transport.MergeFrom(transport)
        peer.ebgp_multihop.MergeFrom(ebgp_multihop)
        
        return peer

    def _create_peer_conf(self, **kwargs):
        """ 
        Create gRPC object for PeerConf
        https://github.com/oneryalcin/PyGoBGP-Example/blob/372bf4c15fb0a86b5ca8886c8b7a07ec24127136/docker/control/proto_files/gobgp.proto#L626
        """

        # Discard kwargs until I come back to adding this feature later
        _ = kwargs

        params = {
            "local_address": self._local_address,
            "neighbor_address": self._neighbor_address,
            "local_as": self._local_as,
            "peer_as": self._peer_as,
        }
        
        # Add optional Params
        if self._auth_password:
            params['auth_password'] = self._auth_password
            
        if self._description:
            params['description'] = self._description
        
        return gobgp.PeerConf(**params)
        
    def _create_transport(self, **kwargs):
        """ 
        BGP Transport address, where BGP packets are sourced
        https://github.com/oneryalcin/PyGoBGP-Example/blob/372bf4c15fb0a86b5ca8886c8b7a07ec24127136/docker/control/proto_files/gobgp.proto#L607
        """
        # Discard kwargs until I come back to adding this feature later
        _ = kwargs

        params = {
            "local_address": self._local_address,
        }
        
        return gobgp.Transport(**params)
        
    def _create_ebgp_multihop(self, **kwargs):
        """ 
        eBGP Multihop params 
        https://github.com/oneryalcin/PyGoBGP-Example/blob/372bf4c15fb0a86b5ca8886c8b7a07ec24127136/docker/control/proto_files/gobgp.proto#L656
        """

        # Discard kwargs until I come back to adding this feature later
        _ = kwargs

        params = {
            "enabled": self._ebgp_multihop,
            "multihop_ttl": self._ebgp_multihop_ttl,
        }
        
        return gobgp.EbgpMultihop(**params)

