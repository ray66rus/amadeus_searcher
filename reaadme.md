# Amadeus ticket searcher

This is a basic CLI application to batch search available tickets in the Amadeus GDS system

## Prerequisites

To use this program, you need an Amadeus API key:

1. Register in the Amadeus developers portal: https://developers.amadeus.com/.
2. Go to "My Self-Service Workspace" page.
3. Select "Create new app".
4. Generate Production Key. To do this, you need to have a valid Visa/Master Card/American Express
card.
5. Use "API Key" as your "Client Id" and "API Secret" as Client Secret". You can pass these values
to the `searcher.py` via `--client-id` and `--client-secret` parameters, or add them to the
environment variables `AMADEUS_SEARCHER_CLIENT_ID` and `AMADEUS_SEARCHER_CLIENT_SECRET`
respectively.

If you want to participate in the development of this software, get the test API key instead - its
usage is free (but limited to the API usage quotas) and does not require specifying your billing
information.

## Usage


### Searching one-way trips

It is possible to search one-way flights from some origin to multiple destinations for multiple
consequent dates, like:

```
./searcher.py
    one_way \
    --origin MAD --destinations BCN,MUC --date 2024-12-10 --timeframe 5 \
    --client_id <your_client_id> --client-secret <your_client_secret>
```

which will search for flights from Madrid to Barcelona and Munich for 2024-12-10, 2024-12-11,
2024-12-12, 2024-12-13 and 2024-12-14.


### "Batch" searching

It is also possible to search flights using a request file in CSV format. Every record in this file
looks  like `<origin>,<destination>,<departure_date>,<return_date>`. Return date can be missed to
search one-way flights. Each entry is on the separate line. Example:

```
MAD,BCN,2024-12-10,
MAD,BCN,2024-12-11,2024-12-21
BCN,MUC,2024-12-20,
MUC,MAD,2024-12-21,
```

If you search using this file, the results will be:
* One-way flights from Madrid to Barcelona departing on 2024-12-10
* Return flights from Madrid to Barcelona departing on 2024-12-10 with the return date 2024-12-21
* One-way flights from Barcelona to Munich departing on 2024-12-20
* One-way flights from Munich to Madrid departing on 2024-12-21


Syntax for such search is the following:
```
./searcher.py batch <file_name>
```

### Displaying the results

For every found flight, the application outputs to the screen the basic information about it.
Example:
```
Departure: 2024-12-14T06:00:00, Durations: PT7H35M, Price: 137.95 EUR, Seats left: 9
```

Also, for every origin-destination pair a separate file in the json format is created in the
`last_search` subdirectory of the current directory (if there were more than one search for the
same origin-destination pair, there will be several files). These files contain the complete
records returned by Amadeus API, which includes a lot of information about every offer found.

## Additional notes

Amadeus API provides a monthly free requests quota. The remaining free calls can be checked on
https://developers.amadeus.com/api-usage page. Also you can find there how much is cost every API
call above the quota.

## Licensing

This application is a free software, licensed under the BSD-3-Clause license:
https://opensource.org/license/bsd-3-clause.
