# The Domino Effect Challenge 🎯

A sophisticated microservices cascade failure simulation tool that models how failures propagate through distributed systems, helping you understand service dependencies and the domino effect of outages.

## 📋 Overview

This simulator models a network of interconnected services where failures in upstream dependencies can cascade down to dependent services. It provides detailed analytics, root cause analysis, and interactive querying capabilities to help understand complex failure scenarios in distributed architectures.

### Key Features

- **Service Dependency Modeling**: Define complex service topologies with multi-level dependencies
- **Cascade Failure Simulation**: Watch how failures propagate through your service mesh
- **Root Cause Analysis**: Automatically identify the source of outages and prioritize remediation
- **Recovery Simulation**: Model service healing and upstream recovery propagation
- **Interactive Querying**: Ask questions about failures in natural language
- **Blast Radius Analysis**: Understand the impact scope of each service failure
- **Detailed Logging**: Comprehensive simulation logs with timestamps and health metrics

## 🚀 Quick Start

### Prerequisites

- Python 3.7+
- Required packages: `pyyaml` (install with `pip install pyyaml`)

### Basic Usage

1. **Clone and navigate to the project**:
   ```bash
   cd Domino_Effect_Challenge
   ```

2. **Create Virtual Environment**:
   ```bash
   python -m venv venv && .\venv\Scripts\Activate.ps1
   ```
   
3. **Install dependencies**:
   ```bash
   pip install pyyaml
   ```
   
4. **Run with interactive mode**:
   ```bash
   python domino.py --input services.json --config config.yaml --interactive
   ```

## 📁 Project Structure

```
├── domino.py          # Main simulation engine
├── config.yaml        # Simulation parameters
├── services.json      # Service topology definition
├── README.md          # This file
└── runs/              # Generated simulation logs (created automatically)
```

## ⚙️ Configuration

### `config.yaml` Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `ticks` | Number of simulation steps | 50 | 1-1000+ |
| `threshold` | Health threshold below which services fail | 0.70 | 0.0-1.0 |
| `alpha` | Cascade failure propagation strength | 0.8 | 0.0-1.0 |
| `cooldown` | Ticks before failed services can recover | 1 | -1 (disabled) or 1+ |
| `heal_to` | Health level when services recover | 0.88 | 0.0-1.0 |
| `seed` | Random seed for reproducible simulations | 1337 | Any integer |

### Service Definition (`services.json`)

Define your service topology using JSON:

```json
[
  {
    "name": "service-A",
    "depends_on": ["service-B", "service-C"],
    "health": 0.98
  },
  {
    "name": "service-B", 
    "depends_on": [],
    "health": 0.95
  }
]
```

**Fields:**
- `name`: Unique service identifier
- `depends_on`: Array of upstream dependencies (empty array for root services)
- `health`: Initial health score (0.0 = failed, 1.0 = perfect health)

## 🎮 Interactive Queries

The simulator supports natural language queries about your system:

### Available Query Types

1. **Service Failure Analysis**
   ```
   Query> why is service-A failing?
   ```
   - Shows current health status
   - Identifies root cause vs cascade failure
   - Lists failed dependencies
   - Displays blast radius

2. **Historical Analysis**
   ```
   Query> what happened in the last 10 ticks?
   ```
   - Timeline of glitches and failures
   - Root cause events
   - Failure statistics

3. **Impact Analysis**
   ```
   Query> top-impacted
   ```
   - Ranks services by failure frequency
   - Shows health degradation metrics
   - Identifies most vulnerable services

### Query Commands

- `help` - Show available queries
- `exit` or `quit` - Exit interactive mode

## 🔧 Command Line Options

```bash
python domino.py [OPTIONS]

Options:
  --input FILE     Service topology file (default: services.json)
  --config FILE    Configuration file (default: config.yaml)  
  --query TEXT     Run single query after simulation
  --interactive    Enter interactive query mode after simulation
  -h, --help       Show help message
```

## 📊 Understanding the Output

### Simulation Log Format

```
[TICK 1] 14:30:15
[GLITCH] service-D health 0.97 -> 0.52 (random glitch)
[ALERT] service-D fell below threshold (0.52 < 0.70)
[BLAST] due to service-D -> impacted: ['service-B', 'service-A', 'service-J']
[PRIORITY] roots={service-D}, order=['service-D']
[SUGGESTION] Remediate service-D first
```

### Key Log Types

- **`[BOOT]`**: System initialization
- **`[TICK N]`**: Simulation step with timestamp
- **`[GLITCH]`**: Random service degradation
- **`[ALERT]`**: Service failure (below threshold)
- **`[BLAST]`**: Impact analysis
- **`[PRIORITY]`**: Root cause analysis
- **`[SUGGESTION]`**: Remediation recommendations
- **`[HEAL]`**: Service recovery
- **`[RECOVERY]`**: Upstream recovery propagation

