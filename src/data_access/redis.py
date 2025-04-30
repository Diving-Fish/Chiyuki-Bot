import redis
import json

redis_global = redis.Redis(host='localhost', port=6379, decode_responses=True)

class RedisData:
    def __init__(self, key, type_loader=str, type_serializer=str, default=''):
        self.key = key
        value = redis_global.get(self.key)
        if value == None:
            self.submit_data = default
        else:
            self.submit_data = type_loader(value)
        self.loader = type_loader
        self.serializer = type_serializer
        self.data = self.submit_data
            
    def set(self, data):
        self.data = data

    def save(self, *args, ex=None, px=None, nx=False, xx=False):
        if len(args) != 0:
            self.set(args[0])
        self.submit_data = self.data
        redis_global.set(self.key, self.serializer(self.submit_data), ex, px, nx, xx)


class NumberRedisData(RedisData):
    def __init__(self, key):
        super().__init__(key, int, str, default=0)


class ListRedisData(RedisData):
    def __init__(self, key):
        super().__init__(key, lambda s : json.loads(s), lambda lst : json.dumps(lst), default=[])
        if type(self.data) != type([]):
            raise Exception(f"{self.__dict__} is not a list")


class DictRedisData(RedisData):
    def __init__(self, key, default={}):
        super().__init__(key, lambda s : json.loads(s), lambda dct : json.dumps(dct), default=default)
        if type(self.data) != type({}):
            raise Exception(f"{self.__dict__} is not a dict")
