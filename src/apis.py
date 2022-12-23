import logging
import requests
import urllib.parse
import json
# from xml.etree import ElementTree
from src.helpers import deg_to_dms
from src.caches import FileCache
from src.helpers import nested_key_exists

logger = logging.getLogger(__name__)


class GoogleMapsApi:
    API_BASE_URL = "https://maps.googleapis.com/maps/api"

    # @TODO - add support for xml
    def __init__(self, api_key: str, file_cache: FileCache = None, response_type="json"):
        """
        This class handles api calls made to the Google Maps API services.
        Args:
            api_key (str): API key to Google Maps API - https://developers.google.com/maps
            file_cache (FileCache|None): FileCache object for caching the responses from the API in a file
            response_type (str): Output format received from the API response
        """
        if not self._is_valid_response_type(response_type):
            raise ValueError(f"Invalid response type:\n\n\t{response_type}")

        self._api_key = api_key
        self._file_cache = file_cache
        self._response_type = response_type

    @property
    def api_key(self):
        return self._api_key

    @property
    def response_type(self):
        return self._response_type

    @staticmethod
    def _is_valid_response_type(response_type):
        return response_type == "json"

    @staticmethod
    def get_google_maps_url(latitude: float, longitude: float):
        lat_dms = deg_to_dms(latitude, 'lat')
        lon_dms = deg_to_dms(longitude, 'lon')
        return f"https://www.google.com/maps/place/{lat_dms}+{lon_dms}"

    def get_directions(self, origin: str, place_id: str, mode=None, arrival_time=None):
        # default return
        direction = {
            'distance': None,
            'duration': None,
        }

        # mandatory params
        params = {
            'origin': origin,
            'destination': f"place_id:{place_id}",
        }
        # optional params
        if mode is not None:
            params['mode'] = mode
        if arrival_time is not None:
            params['arrival_time'] = arrival_time

        # build urls for the request and cache
        url = self._build_api_call_url(params=params, service="directions")

        # try to return the cached direction if there's any
        content = self._get_cache(url)
        if content:
            return content

        # cache not found, make the API call
        logger.info(f"Calling url: {url}")
        response = requests.get(url)

        # validate response
        if response.status_code != 200:
            logger.error(f"Status code is NOT OK: {response.status_code}")
            return direction

        content = response.json()
        if content.get("status") != "OK":
            logger.error(f"API status: {content.get('status', 'Unknown')}")
            logger.error(f"API error: {content.get('error_message', 'Unknown Error')}")
            return direction

        # get the response content
        try:
            # read data from this format >>> direction['routes'][0]['legs'][0]['distance']['text']
            routes = content.get('routes', [])
            legs = routes[0].get('legs', {})
            leg = legs[0]
        except KeyError:
            leg = {}

        if not nested_key_exists(leg, ["duration", "text"]):
            logger.error("Duration of trip not found in response")
            return direction
        if not nested_key_exists(leg, ["distance", "text"]):
            logger.error("Distance of trip not found in response")
            return direction

        duration = leg.get('duration', {}).get('text')
        distance = leg.get('distance', {}).get('text')

        direction = {
            'distance': distance,
            'duration': duration
        }
        cached_content = json.dumps(direction, separators=(',', ':'))

        # try to cache file
        self._save_cache(url, cached_content)

        return direction

    def _build_api_call_url(self, params: dict, service: str):
        all_params = dict(params)
        all_params['key'] = self.api_key

        return f"{self.API_BASE_URL}/{service}/{self.response_type}?{urllib.parse.urlencode(all_params)}"

    def _get_cache(self, url):
        # if file cache is not set up ignore
        if not self._file_cache:
            return None

        # if no file is saved for the url ignore
        content = self._file_cache.get_cached_file_content(url)
        if not content:
            return None

        # return parsed cached data based on return type
        if self.response_type == 'json':
            return json.loads(content)
        # elif self.response_type == 'xml':
        #     return content

    def _save_cache(self, url, response):
        # if file cache is not set up or response is empty ignore
        if not self._file_cache or not response:
            return None

        # cache response in a file
        self._file_cache.create_cache_file(
            hash_key=url,
            content=response,
            extension=self.response_type
        )
