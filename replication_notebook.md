# Replication System Design

This document outlines the design decisions and implementation details of our distributed replication system, which provides 2-fault tolerance using the Raft consensus algorithm.

## Overview

Our distributed messaging system implements the Raft consensus algorithm to ensure consistent data replication across multiple nodes. The system is designed to be 2-fault tolerant, meaning it can continue to function correctly even if two nodes fail simultaneously.

The key components of our replication system are:

1. `raft_node.py` - Core implementation of the Raft consensus protocol
2. `start_cluster.py` - Script to start and configure nodes in the cluster

## Design Decisions for `raft_node.py`

### State Management

Each `RaftNode` maintains several state variables:

- `current_term` - The current term number (incremented during elections)
- `voted_for` - The ID of the candidate voted for in the current term
- `state` - The node's current state (follower, candidate, or leader)
- `leader_id` - The ID of the current leader node
- `last_applied` - The index of the last applied log entry
- `db` - A SQLite database instance with a unique file per node (`db_{node_id}.db`)

### Communication Architecture

We implemented a dual-socket architecture:

1. **Peer Communication**: Each node maintains a dedicated socket for Raft protocol messages between peers.
   - Uses threads to handle incoming connections
   - Implements message handlers for various Raft protocol messages (votes, heartbeats, etc.)

2. **Client Communication**: A separate socket for client interactions.
   - Uses selectors for efficient I/O multiplexing
   - Handles client requests and forwards to the leader when necessary

### Leader Election

The leader election process follows the Raft algorithm:

1. If a follower node doesn't receive a heartbeat within its election timeout, it transitions to a candidate.
2. The candidate increments its term, votes for itself, and requests votes from other nodes.
3. If a candidate receives votes from a majority of nodes, it becomes the leader.
4. The leader sends periodic heartbeats to maintain authority.
5. The election timeout is randomized to prevent election conflicts.

### Message Replication

Database operations are replicated using the following approach:

1. When a client sends a write operation to the leader, the leader:
   - Processes the request locally
   - Assigns a commit index to the operation
   - Broadcasts the operation to all followers

2. Each follower:
   - Receives the operation with its commit index
   - Applies the operation to its local database
   - Updates its `last_applied` index
   
3. This approach ensures that all nodes maintain identical database states.

### Fault Tolerance

The system implements several mechanisms to handle node failures:

1. **Leader Failure Detection**: 
   - Follower nodes monitor heartbeats from the leader
   - If no heartbeat is received within the election timeout, a new election is triggered

2. **Peer Monitoring**: 
   - Each node periodically checks the status of its peers
   - Unresponsive peers are temporarily removed from the active peer list

3. **Data Persistence**: 
   - Each node maintains its own database file
   - Operations are committed to disk before being acknowledged

## Design Decisions for `start_cluster.py`

### Configuration Management

The cluster is configured through a JSON file (`config.json`) that specifies:

1. Node IDs, hosts, and ports for both Raft and client communication
2. Protocol versions and other configuration parameters

### Node Initialization

The `start_node` function:

1. Extracts configuration for the specified node ID
2. Initializes a `RaftNode` instance with appropriate parameters
3. Starts both the Raft protocol server and the client server

## 2-Fault Tolerance Implementation

Our system achieves 2-fault tolerance through several mechanisms:

1. **Majority-Based Consensus**: 
   - With 5 nodes, the system can tolerate 2 failures (requires 3 nodes for majority)
   - Leader election requires votes from a majority of nodes

2. **Independent Data Storage**: 
   - Each node maintains its own database
   - No single point of failure for data storage

3. **Operation Replication**: 
   - All database operations are replicated across all nodes
   - `db_update` messages ensure consistency across the cluster

4. **Stateful Recovery**: 
   - When a node rejoins the cluster, it receives the current term and leader information
   - It can catch up on missed operations based on commit indices

## Future Improvements

1. Implement log compaction to prevent unbounded growth of the operation log
2. Add automated recovery mechanisms for failed nodes
3. Implement snapshot-based state transfer for nodes rejoining the cluster
4. Add monitoring and metrics collection for system health

## Conclusion

By implementing the Raft consensus algorithm, our distributed messaging system achieves 2-fault tolerance while maintaining data consistency. The separation of client and peer communication, along with the stateful recovery mechanisms, ensures that the system remains available even when multiple nodes fail.
