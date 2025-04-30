from src.data_access.redis import redis_global
from hashlib import sha256
import json


def get_string_hash(s):
    return sha256(bytes(s, encoding='utf-8')).hexdigest()


class PluginManager:
    def __init__(self) -> None:
        self.metadata = {}

    def register_plugin(self, metadata) -> None:
        self.metadata[metadata["name"]] = metadata

    def __get_group_key(self, group_id) -> str:
        return get_string_hash("chiyuki" + str(group_id))

    def get_all(self, group_id):
        status = {}
        for key, meta in self.metadata.items():
            status[key] = meta["enable"]
        redis_data = redis_global.get(self.__get_group_key(group_id))
        try:
            obj = json.loads(redis_data)
            for k, v in obj.items():
                status[k] = v
        except Exception:
            pass
        return status

    def get_enable(self, group_id, plugin_name) -> bool:
        return self.get_all(group_id)[plugin_name]

    def set_enable(self, group_id, plugin_name, enable) -> None:
        status = self.get_all(group_id)
        status[plugin_name] = enable
        redis_global.set(self.__get_group_key(group_id), json.dumps(status))

    def get_groups(self, plugin_name):
        groups = []
        for group_id in redis_global.keys("chiyuki*"):
            status = self.get_all(group_id)
            if status[plugin_name]:
                groups.append(group_id)
        return groups

plugin_manager = PluginManager()