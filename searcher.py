#!/usr/bin/env python

from dataclasses import dataclass
from typing import List
import requests
import json

BASE_URL = 'https://test.api.amadeus.com'
CLIENT_ID = 'h1fqj83omZ2esY3IDLzie9qKfB23GXv8'
CLIENT_SECRET = 'FhEvNxesUlI2OXs9'


@dataclass
class SearchRequest:
    flight_from: str
    flight_to: str
    flight_date: str
    pax_count: int = 1
    max_result_count: int = 10
    max_price: int = None


@dataclass
class SearchResult:
    seats: int
    departures: List[str]
    arrivals: List[str]
    durations: List[str]
    price: int
    currency: str
    raw_entry: str


def auth() -> str:
    url = f'{BASE_URL}/v1/security/oauth2/token'
    params = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    headers = {
        'Content-type': 'application/x-www-form-urlencoded'
    }

    response = requests.post(url, data=params, headers=headers)

    return response.json()['access_token']


def search_offers(token: str, search_request: SearchRequest) -> List[SearchResult]:
    url = f'{BASE_URL}/v2/shopping/flight-offers'
    params = {
       'originLocationCode': search_request.flight_from,
       'destinationLocationCode': search_request.flight_to,
       'departureDate': search_request.flight_date,
       'adults': search_request.pax_count,
       'max': search_request.max_result_count,
    }
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(url, params=params, headers=headers)
    raw_result = response.json()

    search_results = []
    for entry in raw_result['data']:
        if entry['price']['grandTotal'] > search_request.max_price:
            break
        search_results.append(SearchResult(
            seats=entry['numberOfBookableSeats'],
            departures=[i['segments'][0]['departure']['at'] for i in entry['itineraries']],
            arrivals=[i['segments'][-1]['arrival']['at'] for i in entry['itineraries']],
            durations=[i['duration'] for i in entry['itineraries']],
            price=entry['price']['grandTotal'],
            currency=entry['price']['currency'],
            raw_entry=json.dumps(entry)))

    return search_results


token = auth()

counter = 0
search_request = SearchRequest(flight_from='IST', flight_to='MEX', flight_date='2024-12-20', pax_count=1)
for offer in search_offers(token, search_request):
    print(f"From: {search_request.flight_from}, To: {search_request.flight_to}, Departure: {', '.join(offer.departures)}, Times: {', '.join(offer.durations)}, Price: {offer.price} {offer.currency}, Seats left: {offer.seats}")
    counter += 1

print(f'Offers: {counter}')
