import urllib.parse
import yaml
import logging
from datetime import date
from pathlib import Path
from src.apis import GoogleMapsApi
from src.scrapers import RightmoveScraper
from src.caches import FileCache
from src.logging_setup import setup_logging


def is_valid_config():
    # check if file exists
    config_file = Path('config.yaml')
    if not config_file.is_file():
        logger.critical(f"Configuration file {config_file} not found")
        return False

    is_valid = True
    with config_file.open("r") as f:
        config = yaml.safe_load(f)

    # check if rightmove url is set up
    if "RIGHTMOVE_URL" not in config:
        logger.critical("RIGHTMOVE_URL: not found")
        is_valid = False

    # check if csv file path is set up
    if "CSV_FILE_PATH" not in config:
        logger.critical("CSV_FILE_PATH: not found")
        is_valid = False

    # check if cache folder path is set up
    if "BASE_CACHE_FOLDER_PATH" not in config:
        logger.critical("BASE_CACHE_FOLDER_PATH: not found")
        is_valid = False

    # check if directions data is in the config and in the proper format
    if "GOOGLE_MAPS_DIRECTIONS_DATA" in config:
        if type(config["GOOGLE_MAPS_DIRECTIONS_DATA"]) != list:
            logger.critical("GOOGLE_MAPS_DIRECTIONS_DATA: has to be a list")
            is_valid = False
        else:
            # check if all elements have valid keys (arrival_time is optional)
            for (i, direction_config) in enumerate(config["GOOGLE_MAPS_DIRECTIONS_DATA"]):
                number = i + 1
                if "place_id" not in direction_config:
                    logger.critical(f"GOOGLE_MAPS_DIRECTIONS_DATA #{number}: place_id needs to be provided")
                    is_valid = False
                if "mode" not in direction_config:
                    logger.critical(f"GOOGLE_MAPS_DIRECTIONS_DATA #{number}: mode needs to be provided")
                    is_valid = False
                if "key" not in direction_config:
                    logger.critical(f"GOOGLE_MAPS_DIRECTIONS_DATA #{number}: key needs to be provided")
                    is_valid = False
                if "label" not in direction_config:
                    logger.critical(f"GOOGLE_MAPS_DIRECTIONS_DATA #{number}: label needs to be provided")
                    is_valid = False

    return is_valid


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
                          "{color_on} {message:s}{color_off} :: {name}({lineno})",
        libraries_log_level={
            "requests": logging.WARNING,
            "urllib3": logging.WARNING,
        }
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("=== SCRIPT STARTED ===")

        if not is_valid_config():
            logger.critical("INVALID CONFIG - EXITING")
            exit()

        # load config data
        with Path('config.yaml').open("r") as f:
            config = yaml.safe_load(f)
            logger.info("Config loaded")

        url = config["RIGHTMOVE_URL"]
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
        for direction_data in google_maps_directions_config:
            csv_headers[direction_data['key']] = direction_data['label']

        # create parent directories for CSV file if needed
        csv_path = Path(config['CSV_FILE_PATH'])
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Saving CSV file")
        rightmove_scraper.save_results_to_csv(config['CSV_FILE_PATH'], csv_headers)
        logger.info("=== SCRIPT ENDED ===")
    except:
        logger.exception("An exception happened")
