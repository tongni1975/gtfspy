# used for converting extended route types to simple route types
# based on codes found here: https://developers.google.com/transit/gtfs/reference/extended-route-types

ROUTE_TYPE_CONVERSION = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    100: 2,
    101: 2,
    102: 2,
    103: 2,
    105: 2,
    106: 2,
    107: 2,
    108: 2,
    109: 2,
    200: 3,
    201: 3,
    202: 3,
    204: 3,
    208: 3,
    400: 1,
    401: 1,
    402: 1,
    405: 1,
    700: 3,
    701: 3,
    702: 3,
    704: 3,
    715: 3,
    800: 3,
    900: 0,
    1000: 4,
    1300: 6,
    1400: 7,
    1501: 3,
    1700: 3,
    1701: 5,
    1702: 3,
    1104: 99
}
