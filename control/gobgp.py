import grpc
import itertools
import socket
import struct
import gobgp_pb2 as gobgp
import gobgp_pb2_grpc as gobgp_grpc

class PyGoBGP:
    """Rudimentary Read only GOBGP v1.25 Python API"""
    
    def __init__(self, address, port=50051):
        """Connect GOBGP via GRPC"""
        self.gobgp_address = "{}:{}".format(address, port)
        self.channel = grpc.insecure_channel(self.gobgp_address)
        self.stub = gobgp_grpc.GobgpApiStub(self.channel)
        
    def get_rib(self):
        """ 
        Get Routes in BGP-RIB.
        Disclaimer: Only Global supported for the moment
        Supported BGP attributes: as path, standard community, next hop ip (v4) and MED  
        
        GRPC for GetRib is defined as below:
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
        FAMILY = 65537
        request = gobgp.GetRibRequest()
        table = gobgp.Table(family=FAMILY)
        request.table.MergeFrom(table)
        
        # Get Rib contents 
        # raw routes is a GetRibResponse object which contains Table object
        raw_routes = self.stub.GetRib(request)
        
        # GoBGP returns BGP path attributes not in a friendly way, extract them 
        routes = self._extract_routes(raw_routes)
        return routes
    
    def get_neighbor(self, address=None):
        """
            Get BGP Neighbor (Peer) details 
            If address is None then return all peers
        
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
        if not address:
            return resp.peers
        else:
            for peer in resp.peers:
                if peer.conf.neighbor_address == address:
                    return peer
            return None
        
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
        conf = gobgp.PeerConf(neighbor_address = address)
        
        #Build Peer object
        peer = gobgp.Peer(families = [65537])
        peer.conf.MergeFrom(conf)
        
        #Build DeleteNeighborRequest object
        request = gobgp.DeleteNeighborRequest()
        request.peer.MergeFrom(peer)
        
        # send DeleteNeighborRequest
        resp = self.stub.DeleteNeighbor(request)
        return resp
    
    def add_neighbor(self, **kwargs):
        """
            Remove BGP neighbor 
        
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
        # Build PeerConf object 
        conf = gobgp.PeerConf(**kwargs)
        
        #Build Peer object
        peer = gobgp.Peer(families = [65537])
        peer.conf.MergeFrom(conf)
        
        #Build AddNeighborRequest object
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
        gobgp global rib add 50.30.20.0/20 origin igp nexthop 60.1.2.3 community 64250:65535,61166:56797 aspath 52428,170 med 48059 -a ipv4
    
        communities: FAFA:FFFFF, EEEE:DDDD
        as path: CCCC:AA
        MED:BBBB

        65535: FFFF
        64250: FAFA
        61166: EEEE
        56797: DDDD
        52428: CCCC 
        48059: BBBB
    
        GOBGP returns the following:
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
        prefix =  "4002"
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
                communities = list(self.chunkstring(string=communities,
                                                    length=4))
                output = []
                for index, _ in enumerate(communities):
                    if index % 2 == 1:
                        output.append("{}:{}".format(communities[index-1], 
                                                     communities[index]))
                return output
        return None
    
    def _extract_next_hop(self, destination):
        prefix =  "4003"
        for attr in destination.paths[0].pattrs:
            attr = attr.hex()
            if attr.startswith(prefix):
                next_hop = int(attr[6:], 16)
                next_hop = socket.inet_ntoa(struct.pack(">L", next_hop))
                return next_hop 
        return None
    
    def _extract_med(self, destination):
        prefix =  "800"
        for attr in destination.paths[0].pattrs:
            attr = attr.hex()
            if attr.startswith(prefix):
                med = int(attr[6:], 16)
                return med
        return None
    
    def chunkstring(self, string, length):
        return (int(string[0+i:length+i], 16) for i in range(0, 
                                                             len(string),
                                                             length))
    