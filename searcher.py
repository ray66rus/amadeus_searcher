#!/usr/bin/env python

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Union
import argparse
import csv
import datetime
import json
import os
import shutil
import sys

import requests

BASE_URL = 'https://test.api.amadeus.com'
CLIENT_ID = None
CLIENT_SECRET = None


@dataclass(frozen=True)
class SearchRequest:
    flight_from: str
    flight_to: str
    flight_dates: List[Tuple[str, str]]
    pax_count: int = 1
    max_result_count: int = 10
    max_price: int = None

    def __post_init__(self):
        search_one_way_flights = False
        search_return_flights = False
        flight_date_durations: List[Tuple[str, str]] = []
        for departure_date, return_date in self.flight_dates:
            if not return_date:
                search_one_way_flights = True
                flight_date_durations.append((departure_date, ''))
                continue
            else:
                search_return_flights = True

            if not (duration := _calculate_duration(departure_date, return_date)):
                raise ValueError(
                    f"Bad departure/return dates pair: ({departure_date!r}, {return_date!r}")
            flight_date_durations.append((departure_date, str(duration)))

        object.__setattr__(self, 'search_one_way_flights', search_one_way_flights)
        object.__setattr__(self, 'search_return_flights', search_return_flights)
        object.__setattr__(self, 'flight_date_durations', flight_date_durations)

    def __hash__(self):
        repr = (
            f"{self.flight_from}\n{self.flight_to}\n"
            f"{sorted([str(date_pair) for date_pair in self.flight_dates])}\n{self.pax_count}\n"
            f"{self.max_result_count}\n{self.max_price}\n")
        return hash(repr)


def _calculate_duration(departure_date: str, return_date: str) -> int:
    try:
        departure_dt = datetime.date(*[int(p) for p in departure_date.split('-')])
        return_dt = datetime.date(*[int(p) for p in return_date.split('-')])
    except Exception as e:
        print(f"Error while converting date string to datetime object: {e}", file=sys.stderr)
        return 0

    duration = (return_dt - departure_dt).days
    if duration <= 0:
        print(
            "Error while converting date string to datetime object: the return date "
            f"{return_date!r} must be after the departure date {departure_date!r}.",
            file=sys.stderr)
        return 0
    return duration


@dataclass(frozen=True)
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

    for departure_date, return_date in search_request.flight_dates:
        params = {
            'originLocationCode': search_request.flight_from,
            'destinationLocationCode': search_request.flight_to,
            'departureDate': departure_date,
            'adults': search_request.pax_count,
            'max': search_request.max_result_count,
        }
        if return_date:
            params['returnDate'] = return_date
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
    if search_request.search_return_flights and search_request.search_one_way_flights:
        print(
            "Cannot search for both one-way and return flights in one request: {search_request!r}",
            file=sys.stderr)
        return []

    url = f'{BASE_URL}/v1/shopping/flight-dates'
    params = {
        'origin': search_request.flight_from,
        'destination': search_request.flight_to,
        'departureDate': ','.join([d[0] for d in search_request.flight_date_durations]),
    }
    if search_request.search_return_flights:
        params['duration'] =','.join([d[1] for d in search_request.flight_date_durations])
    else:  # search_request.search_one_way_flights:
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
    try:
        base_dt = datetime.date(*[int(p) for p in start_date.split('-')])
    except Exception as e:
        print(f"Error while converting date string to datetime object: {e}", file=sys.stderr)
        return []
    return [(base_dt + i * one_day).strftime("%Y-%m-%d") for i in range(0, day_count)]


def _do_search_one_way(
        token: str,
        start_date: str,
        duration: int,
        origin: str,
        destinations: List[str]) -> Dict[SearchRequest, List[SearchResult]]:
    result = {}
    token = auth()
    date_range = _date_range(start_date, duration)
    for destination in destinations:
        request = SearchRequest(
            flight_from=origin, flight_to=destination, flight_dates={(d, '') for d in date_range})
        result[request] = search_offers(token, request)

    return result


def _do_search_by_data_from_file(
        token: str, csv_file_path: Path) -> Dict[SearchRequest, List[SearchResult]]:
    result = {}
    with open(csv_file_path, newline='') as request_file:
        request_reader = csv.reader(request_file, delimiter=',')
        for raw_request in request_reader:
            request = SearchRequest(
                flight_from=raw_request[0],
                flight_to=raw_request[1],
                flight_dates={(raw_request[2], raw_request[3])})
            result[request] = search_offers(token, request)

    return result


def do_search(search_functor, **search_args):
    token = auth()
    last_search_results_dir = Path.cwd() / 'last_search'
    if last_search_results_dir.is_dir():
        shutil.rmtree(last_search_results_dir)
    os.mkdir(last_search_results_dir)

    counters = {}
    for request, offers in search_functor(token, **search_args).items():
        print(f"From: {request.flight_from}, To: {request.flight_to}")
        for offer in offers:
            print(
                f"Departure: {', '.join(offer.departures)}, "
                f"Durations: {', '.join(offer.durations)}, Price: {offer.price} {offer.currency}, "
                f"Seats left: {offer.seats}")
        print("----------------------------------------------------------------------------------")
        print("")

        counters[request] = counters.get(request, 0) + 1
        results_file_name = (last_search_results_dir /
                             f'{request.flight_from}-{request.flight_to}-{counters[request]}.json')
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

    subparsers = parser.add_subparsers(dest='subcommand', required=True, help="Subcommand")

    parser_batch_search = subparsers.add_parser(
        'batch', help='Search by criteria specified in a file')
    parser_batch_search.add_argument(
        '--file', '-f', required=True, type=Path, help="CSV file containing search requests")

    parser_one_way_search = subparsers.add_parser(
        'one_way', help="Search one-way flights by criteria specified in the command line.")
    parser_one_way_search.add_argument(
        "--origin", "-o",
        type=str,
        required=True,
        help="IATA code for the departure city/airport.")
    parser_one_way_search.add_argument(
        "--destinations", "-d",
        type=str,
        required=True,
        help="Coma-separated IATA codes for the arrival city/airport.")
    parser_one_way_search.add_argument(
        "--date",
        type=str,
        required=True,
        help="First date of the desired range in the form \"YYYY-MM-DD\".")
    parser_one_way_search.add_argument(
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

    if hasattr(args, 'file'):
        do_search(_do_search_by_data_from_file, csv_file_path=args.file)
    else:
        params = {
            'start_date': args.date,
            'duration': args.timeframe,
            'origin': args.origin,
            'destinations': args.destinations.split(','),
        }
        do_search(_do_search_one_way, **params)

if __name__ == '__main__':
    main()
