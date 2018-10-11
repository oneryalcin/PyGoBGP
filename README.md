# PyGoBGP

PyGoBGP is a simple python package to interact with GOBGP (currently briefly tested on only GoBGP v1.25). GoBGP uses gRPC as the API, however for many network engineers gRPC is a black magic. PyGoBGP handles the gRPC calls for you. However it only supports very basic calls for the moment. 

# Install

Using pip it's a breeze to install it
```
pip install pygobgp
```

## Usage 
PyGoBGP comes with protocol buffers generated `py` files `gobgp_pb2.py` abd `gobgp_pb2_grpc.py` for GoBGP v1.25 only. 

Example Topology:

```
GoBGP address: 10.0.255.2
GoBGP Local AS: 65412

Remote address: 10.0.255.3
Remote Peer AS: 65001
```

Connect to GoBGP instance, default port is `50051` if not specified 

```python
from gobgp import PyGoBGP
gobgp = PyGoBGP(address="10.0.255.2")
```

### Get Neighbor Params
```python
neigbor = gobgp.get_neigbor(address="10.0.255.3")
print(neighbor)

families: 65537
...
conf {
  local_as: 64512
  neighbor_address: "10.0.255.3"
  peer_as: 65001
  ...
  local_address: "10.0.255.2"
}
info {
  ...
  bgp_state: "established"
}
...
```

### Get Global BGP RIB-IN 

Assume remote peer has following route and will advertise to GoBGP:
```python
{
    'prefix': '50.30.16.0/20',
    'as_path': [5607, 1000],
    'next_hop': '60.1.2.3',
    'community': ['1000:2000', '3000:4000'],
    'med': 20
}  

```

```python
routes = gobgp.get_rib()
print(routes)

[{'prefix': '50.30.16.0/20',
  'as_path': [65001, 5607, 1000],
  'next_hop': '60.1.2.3',
  'community': ['1000:2000', '3000:4000'],
  'med': 20}]
```
Note that AS 65001 is prepended as it is an eBGP session.

### Remove Neighbor

```python
gobgp.delete_neighbor(address="10.0.255.3")
neigbor = gobgp.get_neigbor(address="10.0.255.3")
print(neigbor)

None

```


### Add neighbor back

First define neigbor params
```python
neighbor = {
    "local_address": "10.0.255.2",
    "neighbor_address": "10.0.255.3",
    "local_as": 64512,
    "peer_as": 65001,
}
gobgp.add_neighbor(**neighbor)
```

```python
neigbor = gobgp.get_neigbor(address="10.0.255.3")
print(neighbor)

families: 65537
...
conf {
  local_as: 64512
  neighbor_address: "10.0.255.3"
  peer_as: 65001
  ...
  local_address: "10.0.255.2"
}
info {
  ...
  bgp_state: "established"
}
...
```

### Route Injection
Upcoming


# NOTES
This library is not definitely a production grade library yet and not tested properly. Under development and highly likely I will only develop the needed features. Having said that all contributions are welcomed.

# Appendix A (Populating Python GoBGP gRPC files)

 **Download GOBGP proto file**
```
wget https://raw.githubusercontent.com/osrg/gobgp/v1.25/api/gobgp.proto
```
**Install Python GRPC libs**
```
pip install grpcio grpcio-tools googleapis-common-protos
```

**Populate python GRPC API classes to interact with GOBGP**
```
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. gobgp.proto
```

**Now we have the following files available**
```
    gobgp_pb2_grpc.py
    gobgp_pb2.py
```
