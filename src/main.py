import urllib.parse
import yaml
import logging
from datetime import date
from src.apis import GoogleMapsApi
from src.scrapers import RightmoveScraper
from src.caches import FileCache
from src.logging_setup import setup_logging


if __name__ == '__main__':
    # set up logging
    setup_logging(
        console_log_output="stdout",
        console_log_level="debug",
        console_log_color=True,
        logfile_file=f"logs/main_{str(date.today())}.log",
        logfile_log_level="debug",
        logfile_log_color=False,
        log_line_template="[{asctime},{msecs:0>3.0f}] "
                          "{color_on}{color_reverse}[{levelname:>8s}]{color_off}"
                          "{color_on} {lineno:>4d} {name} :: {message:s}{color_off}",
        libraries_log_level={
            "requests": logging.WARNING,
            "urllib3": logging.WARNING,
        }
    )
    logger = logging.getLogger(__name__)

    logger.info("=== SCRIPT STARTED ===")

    # load config data
    f = open('config.yaml')
    config = yaml.safe_load(f)
    logger.info("Config loaded")

    baseUrl = 'https://www.rightmove.co.uk/property-to-rent/find.html?'
    params = {
        'locationIdentifier': 'STATION^9686',
        'maxBedrooms': 5,
        'minBedrooms': 4,
        'maxPrice': 2500,
        'radius': 5.0,
        'propertyTypes': '',
        'includeLetAgreed': 'false',
        'mustHave': '',
        'dontShow': '',
        'furnishTypes': '',
        'keywords': '',
    }
    url = baseUrl + urllib.parse.urlencode(params)
    logger.info(f"Calling scraper on url: {url}")

    # set up google maps api object and directions config
    google_maps_api = None
    google_maps_directions_config = ()
    if config.get('GOOGLE_MAPS_API_KEY'):
        logger.info(f"Google Maps API key found")
        google_maps_api = GoogleMapsApi(
            api_key=config['GOOGLE_MAPS_API_KEY'],
            file_cache=FileCache(f"{config['BASE_CACHE_FOLDER_PATH']}/api/google_maps")
        )
        google_maps_directions_config = config.get('GOOGLE_MAPS_DIRECTIONS_DATA', ())
    else:
        logger.info(f"Google Maps API key NOT found")

    # set up rightmove scraping object
    rightmove_scraper = RightmoveScraper(
        url=url,
        google_maps_api=google_maps_api,
        google_maps_directions_config=google_maps_directions_config
    )

    # save CSV file to path
    csv_headers = {
        'type': 'Type',
        'price': 'Price (per month)',
        'deposit': 'Deposit',
        'address': 'Address',
        'bedroom_count': 'Bedrooms',
        'bathroom_count': 'Bathrooms',
        'let_available_date': 'Let Available From',
        'furnish_type': 'Furnish Type',
        'let_type': 'Let Type',
        'minimum_term_in_months': 'Minimum Term (in months)',
        'latitude': 'Latitude',
        'longitude': 'Longitude',
        'google_maps_link': 'Google Maps',
        # 'images': 'Images',
        'url': 'Link',
        'floorplan_urls': 'Floorplans',
        'agent_url': 'Agent',
    }
    for direction_data in config['GOOGLE_MAPS_DIRECTIONS_DATA']:
        csv_headers[direction_data['key']] = direction_data['label']

    logger.info("Saving CSV file")
    rightmove_scraper.save_results_to_csv(config['CSV_FILE_PATH'], csv_headers)
    logger.info("=== SCRIPT ENDED ===")
