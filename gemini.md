# Computer Simulation Project - Production Line

## Project Overview
This project simulates a two-stage production line (Processing A and Assembly B) with machine failures (MTBF/MTTR) using discrete event simulation. It aims to analyze bottlenecks and optimize resource allocation.

## Tech Stack
- **Language**: Python 3
- **Simulation**: [SimPy](https://simpy.readthedocs.io/)
- **Data Analysis & Visualization**: Matplotlib, SciPy, Statistics (built-in)

## Configuration & Usage

### Setup

Check for a venv, if not create one:
```bash
p -m venv venv
source venv/bin/activate
```

Install dependencies:
```bash
pp install -r requirements.txt
```

### Running the simulation
To run the Stage 3 simulation and analysis:
```bash
p Projekt/Etap_3/Etap_3.py
```

## Directory Structure
- `Projekt/Etap_1_2/`: Initial models and documentation.
- `Projekt/Etap_3/`: Advanced simulation, hypothesis testing (CRN), and final reports.
- `wyklady/`: Lecture materials.
