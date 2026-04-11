# Ledger Router Contract

## Overview

The Ledger Router Contract governs the routing mechanism for actor transitions and ledger writer path management within the governance system. This contract implements the core routing logic defined in roadmap item 11.

## Contract Definition

### Router State Machine

```solidity
contract LedgerRouter {
    enum RouterState {
        INITIALIZING,
        ACTIVE,
        SUSPENDED,
        TERMINATED
    }
    
    struct RoutingContext {
        address currentActor;
        string currentRole;
        uint256 sequenceNumber;
        bytes32 taskHash;
        string routingBasis;
    }
    
    struct WriterPath {
        address writerAddress;
        string[] authorizedRoles;
        uint256 priority;
        bool isActive;
    }
}
```

### Core Routing Functions

#### Actor Transition Routing

```solidity
function routeNextActor(
    string memory currentRole,
    string memory taskType,
    string memory routingBasis
) public returns (string memory nextRole, address nextActor) {
    
    require(routerState == RouterState.ACTIVE, "Router not active");
    
    // Apply routing decision matrix
    if (keccak256(abi.encodePacked(routingBasis)) == keccak256("roadmap_sequence_progression")) {
        return applyRoadmapRouting(currentRole, taskType);
    }
    
    if (keccak256(abi.encodePacked(routingBasis)) == keccak256("task_completion_flow")) {
        return applyTaskFlowRouting(currentRole, taskType);
    }
    
    if (keccak256(abi.encodePacked(routingBasis)) == keccak256("governance_escalation")) {
        return applyGovernanceRouting(currentRole, taskType);
    }
    
    revert("Invalid routing basis");
}
```

#### Writer Path Management

```solidity
function assignWriterPath(
    bytes32 taskHash,
    string memory targetPath,
    address writerActor
) public onlyAuthorized {
    
    require(writerPaths[targetPath].isActive, "Writer path not active");
    require(isAuthorizedWriter(writerActor, targetPath), "Unauthorized writer");
    
    writerAssignments[taskHash] = WriterAssignment({
        targetPath: targetPath,
        writerAddress: writerActor,
        assignedAt: block.timestamp,
        status: WriterStatus.ASSIGNED
    });
    
    emit WriterPathAssigned(taskHash, targetPath, writerActor);
}
```

### Routing Decision Matrix

#### Roadmap Sequence Progression

```solidity
function applyRoadmapRouting(
    string memory currentRole,
    string memory taskType
) internal pure returns (string memory, address) {
    
    bytes32 roleHash = keccak256(abi.encodePacked(currentRole));
    
    if (roleHash == keccak256("ANALYST")) {
        return ("AUDITOR", getActorByRole("AUDITOR"));
    }
    
    if (roleHash == keccak256("AUDITOR")) {
        return ("EXECUTOR", getActorByRole("EXECUTOR"));
    }
    
    if (roleHash == keccak256("EXECUTOR")) {
        return ("VALIDATOR", getActorByRole("VALIDATOR"));
    }
    
    if (roleHash == keccak256("VALIDATOR")) {
        return ("ANALYST", getActorByRole("ANALYST"));
    }
    
    revert("Invalid role for roadmap routing");
}
```

#### Task Completion Flow

```solidity
function applyTaskFlowRouting(
    string memory currentRole,
    string memory taskType
) internal pure returns (string memory, address) {
    
    bytes32 taskTypeHash = keccak256(abi.encodePacked(taskType));
    bytes32 roleHash = keccak256(abi.encodePacked(currentRole));
    
    // Implementation task flows
    if (taskTypeHash == keccak256("IMPLEMENTATION")) {
        if (roleHash == keccak256("ANALYST")) return ("EXECUTOR", getActorByRole("EXECUTOR"));
        if (roleHash == keccak256("EXECUTOR")) return ("AUDITOR", getActorByRole("AUDITOR"));
        if (roleHash == keccak256("AUDITOR")) return ("VALIDATOR", getActorByRole("VALIDATOR"));
    }
    
    // Review task flows
    if (taskTypeHash == keccak256("REVIEW")) {
        if (roleHash == keccak256("EXECUTOR")) return ("AUDITOR", getActorByRole("AUDITOR"));
        if (roleHash == keccak256("AUDITOR")) return ("VALIDATOR", getActorByRole("VALIDATOR"));
        if (roleHash == keccak256("VALIDATOR")) return ("ANALYST", getActorByRole("ANALYST"));
    }
    
    revert("Invalid task flow routing");
}
```

### Writer Path Governance

#### Path Authorization Matrix

```solidity
mapping(string => string[]) public pathAuthorizations;

function initializePathAuthorizations() internal {
    // Core governance paths
    pathAuthorizations["governance/"] = ["ANALYST", "AUDITOR"];
    pathAuthorizations["contracts/"] = ["EXECUTOR", "AUDITOR"];
    pathAuthorizations["documentation/"] = ["ANALYST", "VALIDATOR"];
    pathAuthorizations["tests/"] = ["EXECUTOR", "VALIDATOR"];
    
    // System paths
    pathAuthorizations["system/"] = ["AUDITOR"];
    pathAuthorizations["config/"] = ["VALIDATOR"];
    pathAuthorizations["logs/"] = ["ALL_ROLES"];
}
```

#### Writer Validation

```solidity
function isAuthorizedWriter(
    address writer,
    string memory targetPath
) public view returns (bool) {
    
    string memory writerRole = getActorRole(writer);
    string[] memory authorizedRoles = pathAuthorizations[targetPath];
    
    for (uint i = 0; i < authorizedRoles.length; i++) {
        if (keccak256(abi.encodePacked(authorizedRoles[i])) == keccak256("ALL_ROLES")) {
            return true;
        }
        
        if (keccak256(abi.encodePacked(authorizedRoles[i])) == keccak256(abi.encodePacked(writerRole))) {
            return true;
        }
    }
    
    return false;
}
```

### Emergency Routing Protocols

#### Circuit Breaker Mechanism

```solidity
function emergencyRouteOverride(
    bytes32 taskHash,
    string memory targetRole,
    address targetActor,
    string memory justification
) public onlyEmergencyAuthority {
    
    require(emergencyMode, "Emergency mode not active");
    
    emergencyRoutes[taskHash] = EmergencyRoute({
        targetRole: targetRole,
        targetActor: targetActor,
        justification: justification,
        authorizedBy: msg.sender,
        timestamp: block.timestamp
    });
    
    emit EmergencyRouteActivated(taskHash, targetRole, targetActor);
}
```

#### Fallback Routing

```solidity
function fallbackRouting(
    string memory currentRole
) internal returns (string memory nextRole, address nextActor) {
    
    // Default to AUDITOR for critical path validation
    if (keccak256(abi.encodePacked(currentRole)) != keccak256("AUDITOR")) {
        return ("AUDITOR", getActorByRole("AUDITOR"));
    }
    
    // If already AUDITOR, escalate to VALIDATOR
    return ("VALIDATOR", getActorByRole("VALIDATOR"));
}
```

### Governance Integration

#### State Synchronization

```solidity
function syncRouterState(
    RouterState newState,
    bytes32 stateHash,
    bytes memory proof
) public onlyGovernance {
    
    require(verifyStateTransition(routerState, newState), "Invalid state transition");
    require(verifyProof(stateHash, proof), "Invalid state proof");
    
    RouterState previousState = routerState;
    routerState = newState;
    
    emit RouterStateChanged(previousState, newState, stateHash);
}
```

#### Audit Trail

```solidity
struct RoutingEvent {
    bytes32 taskHash;
    string fromRole;
    string toRole;
    address fromActor;
    address toActor;
    string routingBasis;
    uint256 timestamp;
    bytes32 blockHash;
}

mapping(bytes32 => RoutingEvent[]) public routingHistory;

function recordRouting(
    bytes32 taskHash,
    string memory fromRole,
    string memory toRole,
    address fromActor,
    address toActor,
    string memory routingBasis
) internal {
    
    RoutingEvent memory newEvent = RoutingEvent({
        taskHash: taskHash,
        fromRole: fromRole,
        toRole: toRole,
        fromActor: fromActor,
        toActor: toActor,
        routingBasis: routingBasis,
        timestamp: block.timestamp,
        blockHash: blockhash(block.number - 1)
    });
    
    routingHistory[taskHash].push(newEvent);
    
    emit RoutingRecorded(taskHash, fromRole, toRole, routingBasis);
}
```

## Implementation Requirements

### Deployment Parameters

1. **Router Authority**: Multi-signature governance contract
2. **Emergency Authority**: Designated emergency response actors
3. **State Verification**: Cryptographic proof system for state transitions
4. **Audit Requirements**: Complete routing history retention

### Security Considerations

1. **Role Verification**: All routing decisions must verify actor role authenticity
2. **Path Validation**: Writer path assignments must validate authorization matrices
3. **Emergency Controls**: Circuit breaker mechanisms for routing failures
4. **Audit Compliance**: All routing events must be cryptographically recorded

### Integration Points

1. **Actor Registry**: Integration with actor management system
2. **Task Management**: Coordination with task lifecycle contracts
3. **Governance System**: Alignment with core governance protocols
4. **Audit System**: Integration with audit trail mechanisms

## Contract Events

```solidity
event ActorRouted(bytes32 indexed taskHash, string fromRole, string toRole, address actor);
event WriterPathAssigned(bytes32 indexed taskHash, string path, address writer);
event RoutingRecorded(bytes32 indexed taskHash, string fromRole, string toRole, string basis);
event EmergencyRouteActivated(bytes32 indexed taskHash, string role, address actor);
event RouterStateChanged(RouterState from, RouterState to, bytes32 stateHash);
```

This contract establishes the foundational routing mechanism for next actor governance and ledger writer path management as specified in the governance roadmap.