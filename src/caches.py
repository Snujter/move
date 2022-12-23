import json
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileCache:
    def __init__(self, base_path: str):
        """
        FileCache class handles caching files using a hashmap, can be used to store e.g. json responses from API calls.
        Initialize the class with the path of the cache folder.
        Class will create the folders recursively if they don't exist, and will add a hashmap file.
        Args:
            base_path (str): Path of the base cache folder where files should be saved.
        """
        self._base_path = Path(base_path)
        self._hashmap_file_path = Path(f"{self._base_path}/_hashmap.json")

        self._setup()

    @property
    def hashmap_file_path(self):
        return self._hashmap_file_path

    @property
    def base_path(self):
        return self._base_path

    @property
    def hashmap(self):
        with self.hashmap_file_path.open("r") as f:
            return json.load(f)

    def create_cache_file(self, hash_key: str, content: str, extension: str, uuid_namespace=uuid.NAMESPACE_URL):
        new_file_path = self._add_file_to_hashmap(hash_key, extension, uuid_namespace)
        with new_file_path.open('w') as f:
            f.write(content)
        return True

    def get_cached_file_content(self, hash_key):
        file_path = self._get_file_path_from_hashmap(hash_key)
        if not file_path or not file_path.exists():
            logger.debug(f"No cached content found for {hash_key}")
            return None

        logger.debug(f"Cached content found for {hash_key}")
        with file_path.open('r') as f:
            return f.read()

    # adds a new entry to the hash table and returns a Path for the file
    def _add_file_to_hashmap(self, hash_key, extension, uuid_namespace):
        hashmap_data = self.hashmap
        with self.hashmap_file_path.open("w+") as f:
            uuid_filename_str = str(uuid.uuid5(uuid_namespace, hash_key))
            hashmap_data[hash_key] = self._generate_file_pathname_for_uuid(uuid_filename_str, extension)
            logger.debug(f"Added key to hashmap: {hash_key}")
            f.write(json.dumps(hashmap_data))
        return Path(hashmap_data[hash_key])

    # gets a cached file as a Path from the hashmap
    def _get_file_path_from_hashmap(self, hash_key):
        with self.hashmap_file_path.open("r") as f:
            hashmap = json.load(f)
            filename = hashmap.get(hash_key)
        return Path(filename) if filename else None

    def _generate_file_pathname_for_uuid(self, uuid_str: str, extension: str):
        """Generates the full file path of a cache file from an uuid string.
        :return: Full file path
        """
        return f"{self.base_path}/{uuid_str}.{extension}"

    def _setup(self):
        """Sets up the hashmap file for the directory given during init.
        :return: Boolean of hashmap successfully created
        """
        logger.info("Setting up file cache")
        # check if file already exists
        if self.hashmap_file_path.exists():
            logger.info("Hashmap already exists")
            return True

        # create directory if needed
        logger.info("Creating parent directories for hashmap")
        self.hashmap_file_path.parent.mkdir(parents=True, exist_ok=True)

        # init file with empty json object
        with self.hashmap_file_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({}))

        logger.info("Hashmap successfully created")
        return True
