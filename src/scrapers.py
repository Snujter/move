import datetime
import requests
import json
import csv
import logging
from lxml import html
import numpy as np
import pandas as pd
from src.apis import GoogleMapsApi
from src.helpers import replace_all_whitespaces, nested_key_exists

logger = logging.getLogger(__name__)


class RightmoveScraper:
    """The `Rightmove` webscraper collects structured data on properties
    returned by a search performed on www.rightmove.co.uk
    An instance of the class provides attributes to access data from the search
    results, the most useful being `get_results`, which returns all results as a
    Pandas DataFrame object.
    The query to Rightmove can be renewed by calling the `refresh_data` method.
    The results can automatically be exported to a .csv file with.
    """
    # base url for the Rightmove website
    BASE_URL = "https://www.rightmove.co.uk"

    # Rightmove artificially limits the max number of available pages for every search
    MAX_ACCESSIBLE_PAGES = 42

    # maximum number of properties shown on a single page
    MAX_RESULT_PER_PAGE = 24

    def __init__(
        self,
        url: str,
        google_maps_api: GoogleMapsApi = None,
        google_maps_directions_config: tuple = ()
    ):
        """Initialize the scraper with a URL from the results of a property
        search performed on www.rightmove.co.uk.
        Args:
            url (str): full HTML link to a page of Rightmove search results.
            google_maps_api (GoogleMapsApi): Object to handle requests for direction data (eg. travel time / distance)
            google_maps_directions_config (tuple): List of params for Google Maps API to use for getting directions.
        """
        self._status_code, self._first_page = self._request(url)
        self._url = url

        self._google_maps_api = google_maps_api
        self._google_maps_directions_config = google_maps_directions_config

        self._validate_url()
        self._results = self._get_results()

    @property
    def url(self):
        return self._url

    @property
    def google_maps_api(self):
        return self._google_maps_api

    @property
    def google_maps_directions_config(self):
        return self._google_maps_directions_config

    @property
    def get_results(self):
        """Pandas DataFrame of all results returned by the search."""
        return self._results

    @property
    def results_count(self):
        """Total number of results returned by `get_results`. Note that the
        rightmove website may state a much higher number of results; this is
        because they artificially restrict the number of results pages that can
        be accessed to self.MAX_ACCESSIBLE_PAGES."""
        return len(self.get_results)

    @staticmethod
    def _request(url: str):
        r = requests.get(url)
        return r.status_code, r.content

    def refresh_data(self, url: str = None):
        """Make a fresh GET request for the Rightmove data.
        Args:
            url (str): optionally pass a new HTML link to a page of Rightmove
                search results (else defaults to the current `url` attribute).
        """
        url = self.url if not url else url
        self._status_code, self._first_page = self._request(url)
        self._url = url
        self._validate_url()
        self._results = self._get_results()

    def _validate_url(self):
        """Basic validation that the URL at least starts in the right format and
        returns status code 200."""
        real_url = "{}://www.rightmove.co.uk/{}/find.html?"
        protocols = ["http", "https"]
        types = ["property-to-rent", "property-for-sale", "new-homes-for-sale"]
        urls = [real_url.format(p, t) for p in protocols for t in types]
        conditions = [self.url.startswith(u) for u in urls]
        conditions.append(self._status_code == 200)
        if not any(conditions):
            logger.error(f"Invalid rightmove search URL: {self.url}")
            raise ValueError(f"Invalid rightmove search URL:\n\n\t{self.url}")

    # @property
    # def rent_or_sale(self):
    #     """String specifying if the search is for properties for rent or sale.
    #     Required because Xpaths are different for the target elements."""
    #     if "/property-for-sale/" in self.url or "/new-homes-for-sale/" in self.url:
    #         return "sale"
    #     elif "/property-to-rent/" in self.url:
    #         return "rent"
    #     elif "/commercial-property-for-sale/" in self.url:
    #         return "sale-commercial"
    #     elif "/commercial-property-to-let/" in self.url:
    #         return "rent-commercial"
    #     else:
    #         raise ValueError(f"Invalid rightmove URL:\n\n\t{self.url}")

    @property
    def results_count_display(self):
        """Returns an integer of the total number of listings as displayed on
        the first page of results. Note that not all listings are available to
        scrape because Rightmove limits the number of accessible pages."""
        tree = html.fromstring(self._first_page)
        xpath = """//span[@class="searchHeader-resultCount"]/text()"""
        return int(tree.xpath(xpath)[0].replace(",", ""))

    @property
    def page_count(self):
        """Returns the number of result pages returned by the search URL. There
        are 24 results per page. Note that the website limits results to a
        maximum of 42 accessible pages."""
        page_count = self.results_count_display // self.MAX_RESULT_PER_PAGE
        if self.results_count_display % self.MAX_RESULT_PER_PAGE > 0:
            page_count += 1

        if page_count > self.MAX_ACCESSIBLE_PAGES:
            page_count = self.MAX_ACCESSIBLE_PAGES
        return page_count

    def _get_page(self, request_content: str):
        """Method to scrape data from a single page of search results. Used
        iteratively by the `get_results` method to scrape data from every page
        returned by the search."""
        # Process the html:
        tree = html.fromstring(request_content)

        # Set xpath for property URL:
        xp_property_links = """//div[@class="propertyCard-details"]//a[@class="propertyCard-link"]/@href"""

        # remove empty property_links
        property_links = list(filter(None, tree.xpath(xp_property_links)))
        # set up unique property_links with base url
        property_links = set(map(lambda x: f"{self.BASE_URL}{x}", property_links))

        # TESTING FOR ONLY 1
        # property_links = list(property_links)[0:1]
        # TESTING FOR ONLY 1

        data = {
            'type': [],
            'price': [],
            'deposit': [],
            'address': [],
            'bedroom_count': [],
            'bathroom_count': [],
            'let_available_date': [],
            'furnish_type': [],
            'let_type': [],
            'minimum_term_in_months': [],
            'latitude': [],
            'longitude': [],
            'google_maps_link': [],
            'images': [],
            'url': [],
            'floorplan_urls': [],
            'agent_url': [],
        }

        for property_link in property_links:
            logger.info(f"Scraping data from property link: {property_link}")
            status_code, content = self._request(property_link)
            if status_code != 200:
                logger.error(f"Response status NOT OK: {property_link}")
                continue
            tree = html.fromstring(content)

            # get global "window.PAGE_MODEL" javascript variable from a script tag, since it has all the info we need
            xp_js_string = """//script[contains(text(), "window.PAGE_MODEL")]/text()"""
            js_string = tree.xpath(xp_js_string)
            try:
                # split string after variable declaration to get the json object
                json_string = js_string[0].split("window.PAGE_MODEL =")[1]
                # make raw string out of it to ignore the potential escape characters
                json_string = r"{}".format(json_string)
                json_data = json.loads(json_string)
            except (ValueError, KeyError) as error:
                # if it can't properly parse the json variable then skip to the next link
                logger.error(f"Invalid JSON data from string: {js_string}")
                logger.error(error)
                continue

            # all property related info should be inside propertyData (duh)
            property_data = json_data.get('propertyData')
            if not property_data:
                logger.error(f"No property data found in JSON data")
                continue

            # add link
            data['url'].append(property_link)

            # get property type (semi-detached, detached etc.)
            if "propertySubType" not in property_data:
                logger.warning("Property type not found in property data")
            data['type'].append(property_data.get('propertySubType', np.nan))

            # get monthly price
            if not nested_key_exists(property_data, ['prices', 'primaryPrice']):
                logger.warning("Price not found in property data")
            data['price'].append(property_data.get('prices', {}).get('primaryPrice', np.nan))

            # get agent urls
            if not nested_key_exists(property_data, ['customer', 'customerProfileUrl']):
                logger.warning("Agent url not found in property data")
            data['agent_url'].append(property_data.get('customer', {}).get('customerProfileUrl', np.nan))

            # get floorplan urls
            if "floorplans" not in property_data:
                logger.warning("Floorplan url not found in property data")
            data['floorplan_urls'].append(
                [fp.get('url', '') for fp in property_data.get('floorplans', [])]
            )

            # get images
            if "images" not in property_data:
                logger.warning("Images not found in property data")
            data['images'].append(
                [fp.get('url', '') for fp in property_data.get('images', [])]
            )

            # get number of bedrooms
            if "bedrooms" not in property_data:
                logger.warning("Number of bedrooms not found in property data")
            data['bedroom_count'].append(property_data.get('bedrooms', np.nan))

            # get number of bathrooms
            if "bathrooms" not in property_data:
                logger.warning("Number of bathrooms not found in property data")
            data['bathroom_count'].append(property_data.get('bathrooms', np.nan))

            # get data related to lettings
            lettings = property_data.get('lettings', {})

            # get let available date
            if "letAvailableDate" not in lettings:
                logger.warning("Let available date not found in property data")
            data['let_available_date'].append(lettings.get('letAvailableDate', 'Now') or 'Now')

            # get deposit
            if "deposit" not in lettings:
                logger.warning("Deposit not found in property data")
            deposit = lettings.get('deposit', np.nan)
            deposit = "£{:,.0f}".format(deposit or 0)
            data['deposit'].append(deposit)

            # get furnish type (furnished / unfurnished)
            if "furnishType" not in lettings:
                logger.warning("Furnish type not found in property data")
            data['furnish_type'].append(lettings.get('furnishType', np.nan))

            # get let type (long term / short term)
            if "letType" not in lettings:
                logger.warning("Let type not found in property data")
            data['let_type'].append(lettings.get('letType', np.nan))

            # get minimum term in months
            if "minimumTermInMonths" not in lettings:
                logger.warning("Minimum term in months not found in property data")
            data['minimum_term_in_months'].append(lettings.get('minimumTermInMonths', 0) or 0)

            # get location
            location_data = property_data.get('location', {})
            if "latitude" not in location_data:
                logger.warning("Latitude not found in property data")
            if "longitude" not in location_data:
                logger.warning("Longitude not found in property data")
            latitude = location_data.get('latitude')
            longitude = location_data.get('longitude')
            # get Google Maps API direction data
            directions_data = self._get_directions_data(latitude, longitude)
            for key, direction_data in directions_data.items():
                duration = direction_data.get('duration') or 'Unknown'
                distance = direction_data.get('distance') or 'Unknown'
                if key not in data or not isinstance(data[key], list):
                    # insert new list for each direction before key "minimum_term_in_months"
                    pos = list(data.keys()).index('minimum_term_in_months')
                    items = list(data.items())
                    items.insert(pos, (key, []))
                    data = dict(items)
                data[key].append(f"{duration} ({distance})")
            data['latitude'].append(latitude)
            data['longitude'].append(longitude)
            # add google maps link
            if latitude is not None and longitude is not None:
                data['google_maps_link'].append(GoogleMapsApi.get_google_maps_url(latitude, longitude))
            else:
                data['google_maps_link'].append(np.nan)

            # get address
            try:
                address_data = property_data.get("address", {})
                if "outcode" not in address_data:
                    logger.warning("Postcode outward code not found in property data")
                if "incode" not in address_data:
                    logger.warning("Postcode inward code not found in property data")
                if "displayAddress" not in address_data:
                    logger.warning("Address not found in property data")
                out_code = address_data.get('outcode')
                in_code = address_data.get('incode')
                display_address = address_data.get('displayAddress', '')
                display_address = display_address.replace(out_code, '').replace(in_code, '')  # remove post code
                display_address = display_address.rstrip(',')  # remove pointless comma from end of string
                display_address = replace_all_whitespaces(display_address)  # remove extra whitespaces

                full_address = []
                if out_code or in_code:
                    full_address.append(f"{out_code}{in_code}")
                if display_address:
                    full_address.append(display_address)
                data['address'].append(', '.join(full_address))
            except KeyError:
                data['address'].append(np.nan)

            logger.info("Scrape successful")

        logger.debug(f"Rightmove scraped data: {data}")
        # return the data in a Pandas DataFrame
        return pd.DataFrame(data)

    def _get_directions_data(self, latitude, longitude):
        directions_data = {}

        # check if directions api should run
        if (
            not isinstance(self.google_maps_api, GoogleMapsApi)
            or not self.google_maps_directions_config
            or latitude is None
            or longitude is None
        ):
            return directions_data

        # run the directions api with the params from the directions config
        for direction_config in self.google_maps_directions_config:
            direction = self.google_maps_api.get_directions(
                origin=f"{latitude},{longitude}",
                place_id=direction_config['place_id'],
                mode=direction_config['mode'],
                arrival_time=direction_config['arrival_time']
            )

            directions_data[direction_config['key']] = {
                'distance': direction.get('distance'),
                'duration': direction.get('duration')
            }

        return directions_data

    def _get_results(self):
        """Build a Pandas DataFrame with all results returned by the search."""
        # get the first page to scrape all the links there
        results = self._get_page(str(self._first_page))

        # iterate through all the rest of the pages
        for p in range(1, self.page_count, 1):

            # create the URL of the specific results page
            next_page = f"{str(self.url)}&index={p * self.MAX_RESULT_PER_PAGE}"

            # make the request
            status_code, content = self._request(next_page)

            # requests to scrape lots of pages eventually dies
            if status_code != 200:
                logger.error(f"Error when trying to scrape url: {next_page}")
                break

            # create a temporary DataFrame of page results:
            temp_df = self._get_page(str(content))

            # concatenate the temporary DataFrame with the full DataFrame:
            results = pd.concat([results, temp_df])

        return self._clean_results(results)

    @staticmethod
    def _clean_results(results: pd.DataFrame):
        # reset the index:
        results.reset_index(inplace=True, drop=True)

        # add column with datetime when the search was run (i.e. now):
        now = datetime.datetime.now()
        results["search_date"] = now

        return results

    def save_results_to_csv(self, path: str, headers: dict):
        # get pandas dataframe
        results = self.get_results

        # format dataframe arrays for csv
        if 'images' in headers:
            results['images'] = ['\n'.join(map(str, img)) for img in results['images']]
        if 'floorplan_urls' in headers:
            results['floorplan_urls'] = ['\n'.join(map(str, floorplan)) for floorplan in results['floorplan_urls']]

        # format columns for csv
        results = results.rename(columns=headers)

        # gets columns to display from the dataframe
        filtered_keys = list(headers.values())

        # save csv to path
        results.to_csv(
            path,
            encoding="utf-8",
            header=True,
            index=False,
            quoting=csv.QUOTE_ALL,
            columns=filtered_keys
        )
