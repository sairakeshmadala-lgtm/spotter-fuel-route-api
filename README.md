# US Fuel Route Optimization API

A Django REST API that calculates a route between two US locations and recommends cost-effective fuel stops using the supplied fuel price dataset.

## Features

- US location input using start and finish addresses
- Route calculation using OSRM
- Location geocoding using OpenStreetMap Nominatim
- Fuel station candidate matching using supplied datasets
- Fuel stop optimization based on fuel prices and vehicle range
- Estimated fuel purchase quantities and costs
- JSON API responses

## Vehicle Assumptions

| Parameter | Value |
|---|---:|
| Maximum driving range | 500 miles |
| Fuel efficiency | 10 miles per gallon |
| Fuel tank capacity | 50 gallons |
| Fuel price currency | USD |

## Technology Stack

- Python
- Django
- Django REST Framework
- Pandas
- Requests
- OSRM
- OpenStreetMap Nominatim

## Project Structure

- config/ - Django project configuration
- fuel_optimizer/ - API endpoints and optimization logic
- data/ - Fuel prices and station coordinate datasets
- manage.py - Django management entry point

## Installation

1. Clone the repository:

   git clone https://github.com/YOUR_USERNAME/spotter-fuel-route-api.git

2. Navigate into the project:

   cd spotter-fuel-route-api

3. Create and activate a virtual environment:

   python -m venv .venv

   Windows PowerShell:

   .\.venv\Scripts\Activate.ps1

4. Install dependencies:

   pip install -r requirements.txt

5. Configure the Django secret key using an environment variable:

    = "your-secret-key"

6. Run Django checks:

   python manage.py check

7. Start the development server:

   python manage.py runserver

## API Endpoints

### 1. Fuel Prices

GET /api/fuel-prices/

Returns fuel price information from the supplied dataset.

### 2. Route Preview

GET /api/route/?start=Dallas, Texas&finish=Austin, Texas

Returns route information between two US locations.

### 3. Fuel Stop Optimization

GET /api/fuel-optimize/?start=New%20York,%20NY&finish=Miami,%20Florida

Returns route details, candidate fuel stops, estimated fuel quantities, and fuel costs.

## Optimization Approach

The optimizer evaluates candidate fuel stations along the route and selects a cost-effective sequence of refueling stops while respecting the vehicle's maximum range.

Fuel availability is modeled using a 500-mile maximum range and 10 miles per gallon efficiency.

## Important Assumptions and Limitations

- Fuel station coordinates are candidate matches and are not guaranteed to represent verified station identities.
- Station detours are approximated using distance from the route.
- Optimization is limited to the supplied candidate station dataset.
- Initial tank fuel cost is excluded from the reported refueling expenditure.
- Public geocoding and routing services are subject to availability and usage policies.
- Results are estimates and should be independently verified before real-world use.

## License

Created as a technical assessment project.
