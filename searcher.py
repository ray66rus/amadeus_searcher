#!/usr/bin/env python

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union
import datetime
import json
import os
import shutil

import requests

BASE_URL = 'https://test.api.amadeus.com'
CLIENT_ID = None
CLIENT_SECRET = None


@dataclass
class SearchRequest:
    flight_from: str
    flight_to: str
    flight_dates: List[str]
    pax_count: int = 1
    max_result_count: int = 10
    max_price: int = None
    durations: List[int] = field(default_factory=list)


@dataclass
class SearchResult:
    departures: List[str]
    arrivals: List[str]
    durations: List[str]
    price: float
    currency: str
    raw_entry: str
    seats: Union[int, str] = 'N/A'


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
    search_results = []
    url = f'{BASE_URL}/v2/shopping/flight-offers'

    for flight_date in search_request.flight_dates:
        params = {
            'originLocationCode': search_request.flight_from,
            'destinationLocationCode': search_request.flight_to,
            'departureDate': flight_date,
            'adults': search_request.pax_count,
            'max': search_request.max_result_count,
        }
        headers = {
            'Authorization': f'Bearer {token}',
        }
        response = requests.get(url, params=params, headers=headers)
        raw_result = response.json()

        if 'data' not in raw_result:
            continue

        for entry in raw_result['data']:
            if (search_request.max_price
                    and entry['price']['grandTotal'] > search_request.max_price):
                break
            search_results.append(SearchResult(
                seats=entry['numberOfBookableSeats'],
                departures=[i['segments'][0]['departure']['at'] for i in entry['itineraries']],
                arrivals=[i['segments'][-1]['arrival']['at'] for i in entry['itineraries']],
                durations=[i['duration'] for i in entry['itineraries']],
                price=entry['price']['grandTotal'],
                currency=entry['price']['currency'],
                raw_entry=entry))

    return search_results


def search_cheapest(token: str, search_request: SearchRequest) -> List[SearchResult]:
    url = f'{BASE_URL}/v1/shopping/flight-dates'
    params = {
        'origin': search_request.flight_from,
        'destination': search_request.flight_to,
        'departureDate': ','.join(search_request.flight_dates),
    }
    if search_request.durations:
        params['duration'] = ','.join([str(d) for d in search_request.durations])
    else:
        params['oneWay'] = True

    headers = {
        'Authorization': f'Bearer {token}',
    }
    if search_request.max_price:
        params['maxPrice'] = search_request.max_price

    response = requests.get(url, params=params, headers=headers)
    raw_result = response.json()

    if 'data' not in raw_result:
        return []

    search_results = []
    currency = raw_result['meta']['currency']
    for entry in raw_result['data']:
        search_results.append(SearchResult(
            departures=[entry['departureDate']],
            arrivals=['N/A'],
            durations=['N/A'],
            price=entry['price']['total'],
            currency=currency,
            raw_entry=entry))

    return search_results


def _date_range(start_date: str, day_count: int) -> List[str]:
    one_day = datetime.timedelta(days=1)
    base_dt = datetime.date(*[int(p) for p in start_date.split('-')])
    return [(base_dt + i * one_day).strftime("%Y-%m-%d") for i in range(0, day_count)]


def do_search(start_date: str, timeframe: int, origin: str, destinations: List[str]):
    token = auth()
    last_search_results_dir = Path.cwd() / 'last_search'
    if last_search_results_dir.is_dir():
        shutil.rmtree(last_search_results_dir)
    os.mkdir(last_search_results_dir)

    date_range = _date_range(start_date, timeframe)
    for destination in destinations:
        search_request = SearchRequest(
            flight_from=origin, flight_to=destination, flight_dates=date_range)

        offers = search_offers(token, search_request)
        print(f"From: {origin}, To: {destination}")
        for offer in offers:
            print(
                f"Departure: {', '.join(offer.departures)}, "
                f"Durations: {', '.join(offer.durations)}, Price: {offer.price} {offer.currency}, "
                f"Seats left: {offer.seats}")
        print("----------------------------------------------------------------------------------")
        print("")

        results_file_name = (last_search_results_dir /
                             f'{origin}-{destination}-{date_range[0]}-{date_range[-1]}.json')
        with open(results_file_name, "w") as f:
            f.write(json.dumps([o.raw_entry for o in offers]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--client-id", '--client_id',
        type=str,
        default=os.environ.get('AMADEUS_SEARCHER_CLIENT_ID', ''),
        help="Client id of Amadeus App")
    parser.add_argument(
        "--client-secret", "--client_secret",
        type=str,
        default=os.environ.get('AMADEUS_SEARCHER_CLIENT_SECRET', ''),
        help="Client id of Amadeus App")
    parser.add_argument(
        "--origin", "-o",
        type=str,
        required=True,
        help="IATA code for the departure city/airport.")
    parser.add_argument(
        "--destinations", "-d",
        type=str,
        required=True,
        help="Coma-separated IATA codes for the arrival city/airport.")
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="First date of the desired range in the form \"YYYY-MM-DD\".")
    parser.add_argument(
        "--timeframe",
        type=int,
        default=1,
        help="How many consecutive dates include in the search.")

    return parser.parse_args()


def main():
    args = parse_args()
    if args.client_id:
        global CLIENT_ID
        CLIENT_ID = args.client_id

    if args.client_secret:
        global CLIENT_SECRET
        CLIENT_SECRET = args.client_secret

    do_search(
        start_date=args.date,
        timeframe=args.timeframe,
        origin=args.origin,
        destinations=args.destinations.split(','))

if __name__ == '__main__':
    main()
