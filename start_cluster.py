import json
from raft_node import RaftNode
import sys

# python start_cluster.py <node_id>

def start_node(node_id, raft_nodes, client_nodes, accepted_versions, protocol):
    client_host = client_nodes[node_id]['host']
    client_port = client_nodes[node_id]['port']
    current_node = RaftNode(node_id, raft_nodes, client_host, client_port)
    current_node.initialize_client_server()
    current_node.run(accepted_versions, protocol)

if __name__ == '__main__':
    node_id = sys.argv[1]
    with open('config.json', 'r') as f:
        config = json.load(f)
    accepted_versions = config['accepted_versions']
    protocol = config['protocol']
    raft_nodes = config['raft_nodes']
    client_nodes = config['client_nodes']
    node_ids = list(raft_nodes.keys())

    start_node(node_id, raft_nodes, client_nodes, accepted_versions, protocol)